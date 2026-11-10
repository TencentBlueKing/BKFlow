"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""

import logging

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from bkflow.exceptions import ValidationError
from bkflow.plugin_catalog.models import PluginDirectory, PluginType, SpacePluginCatalogEntry
from bkflow.plugin_catalog.services.ai_classify_service import AiClassifyService
from bkflow.plugin_catalog.services.source_group_service import SourceGroupService
from bkflow.space.configs import PluginCatalogRevisionConfig, SpaceConfigValueType
from bkflow.space.models import SpaceConfig

logger = logging.getLogger(__name__)


class DirectoryService:
    """
    目录批量管理的查询/保存/删除/初始化服务。

    `manage_save` 采用"整页编辑副本 + 乐观锁 revision"模式：GET 拉取时带上当前 revision，
    POST 保存时必须带回 expected_revision，由 `PluginCatalogRevisionConfig`（SpaceConfig）
    记录版本号，保存前在同一事务内 select_for_update 加锁比对，不一致则拒绝本次保存。
    """

    STRATEGY_PROMOTE = "promote"
    STRATEGY_MERGE = "merge"
    STRATEGY_UNCATEGORIZED = "uncategorized"

    REVISION_CONFIG = PluginCatalogRevisionConfig

    # ---------------------------------------------------------------- 查询 ----

    @classmethod
    def get_manage_data(cls, space_id):
        revision = (cls._get_revision_value(space_id) or {}).get("directory_revision", 0)
        directories = PluginDirectory.objects.filter(space_id=space_id).order_by("parent_id", "order", "id")
        directories_doc = {
            str(directory.id): {
                "id": str(directory.id),
                "parent_id": str(directory.parent_id) if directory.parent_id else "",
                "name": directory.name,
                "order": directory.order,
                "bindings": directory.bindings or [],
            }
            for directory in directories
        }
        return {
            "revision": revision,
            "directories": directories_doc,
            "plugins": cls._list_entries(space_id),
        }

    @classmethod
    def _list_entries(cls, space_id):
        entries = SpacePluginCatalogEntry.objects.filter(space_id=space_id, is_deleted=False)
        builtin_names = SourceGroupService.builtin_display_names()
        bk_plugin_names = SourceGroupService.bk_plugin_display_names(space_id)
        api_names = SourceGroupService.api_display_names(space_id)

        result = []
        for entry in entries:
            if entry.plugin_type == PluginType.API:
                plugin_name = api_names.get((entry.source_key, entry.plugin_code), entry.plugin_code)
            elif entry.plugin_type == PluginType.BK_PLUGIN:
                plugin_name = bk_plugin_names.get(entry.plugin_code, entry.plugin_code)
            else:
                plugin_name = builtin_names.get(entry.plugin_code, entry.plugin_code)
            result.append(
                {
                    "id": entry.id,
                    "plugin_type": entry.plugin_type,
                    "source_key": entry.source_key,
                    "plugin_code": entry.plugin_code,
                    "plugin_name": plugin_name,
                    "directory_id": str(entry.directory_id) if entry.directory_id else "",
                    "status": entry.status,
                }
            )
        return result

    @classmethod
    def _get_revision_value(cls, space_id):
        return SpaceConfig.get_config(space_id=space_id, config_name=cls.REVISION_CONFIG.name)

    # ---------------------------------------------------------------- 保存 ----

    @classmethod
    def save_manage_data(cls, space_id, directories, assignments, deleted_plugin_ids, expected_revision, operator):
        with transaction.atomic():
            config = cls._lock_revision_config(space_id)
            current_revision = (config.json_value or {}).get("directory_revision", 0)
            if current_revision != expected_revision:
                raise ValidationError(
                    f"插件目录数据已被修改(当前版本 {current_revision}，提交版本 {expected_revision})，请刷新后重试"
                )

            id_mapping = cls._upsert_directories(space_id, directories or {})
            if assignments:
                cls._apply_assignments(space_id, assignments, id_mapping, operator)
            if deleted_plugin_ids:
                cls._apply_deletions(space_id, deleted_plugin_ids, operator)

            cls._bump_revision(config, current_revision)

        return cls.get_manage_data(space_id)

    @classmethod
    def _lock_revision_config(cls, space_id):
        config = (
            SpaceConfig.objects.select_for_update()
            .filter(space_id=space_id, name=cls.REVISION_CONFIG.name)
            .first()
        )
        if config is None:
            # 首次整理该空间目录，配置行尚不存在；在当前事务内创建即隐式持有该行的锁，
            # 不需要额外再 select_for_update 一次。
            config = SpaceConfig.objects.create(
                space_id=space_id,
                name=cls.REVISION_CONFIG.name,
                value_type=SpaceConfigValueType.JSON.value,
                json_value=dict(cls.REVISION_CONFIG.default_value),
            )
        return config

    @staticmethod
    def _bump_revision(config, current_revision):
        config.json_value = {"directory_revision": current_revision + 1}
        config.save(update_fields=["json_value"])

    @classmethod
    def _upsert_directories(cls, space_id, directories):
        """
        directories: {提交id(str): {"id":..., "parent_id":..., "name":..., "order":..., "bindings":[...]}}
        返回 {提交id: 真实pk} 映射，供 `_apply_assignments` 解析 assignments 里可能引用的新建目录。

        只做 upsert，不把"文档里没出现 = 需要删除"当成推断依据——删除走独立的
        `preview_delete`/`execute_delete` 接口，与整页保存解耦。

        分两轮处理：先一级（parent_id 为空）后二级，使二级目录可以引用"同一批提交里刚新建
        的一级目录"的前端临时 id。
        """
        existing = {directory.id: directory for directory in PluginDirectory.objects.filter(space_id=space_id)}
        submitted = directories or {}

        def resolve_existing_pk(raw_id):
            try:
                pk = int(raw_id)
            except (TypeError, ValueError):
                return None
            return pk if pk in existing else None

        top_items = [item for item in submitted.values() if not item.get("parent_id")]
        child_items = [item for item in submitted.values() if item.get("parent_id")]

        id_mapping = {}

        for item in top_items:
            cls._validate_directory_payload(item, is_child=False)
            pk = resolve_existing_pk(item["id"])
            if pk is not None:
                directory = existing[pk]
                directory.name = item["name"]
                directory.order = item.get("order", directory.order)
                directory.bindings = item.get("bindings") or []
                directory.parent = None
                cls._save_directory(directory, update_fields=["name", "order", "bindings", "parent", "update_time"])
            else:
                directory = PluginDirectory(
                    space_id=space_id,
                    parent=None,
                    name=item["name"],
                    order=item.get("order", 0),
                    bindings=item.get("bindings") or [],
                )
                cls._save_directory(directory)
            existing[directory.id] = directory
            id_mapping[item["id"]] = directory.id

        for item in child_items:
            cls._validate_directory_payload(item, is_child=True)
            parent_raw = item["parent_id"]
            parent_pk = id_mapping.get(parent_raw, resolve_existing_pk(parent_raw))
            parent_directory = existing.get(parent_pk) if parent_pk is not None else None
            if parent_directory is None:
                raise ValidationError(f"目录「{item.get('name')}」的父级目录 {parent_raw} 不存在")
            if parent_directory.parent_id is not None:
                raise ValidationError(f"目录层级最多两级，「{parent_directory.name}」不能再有子目录")

            pk = resolve_existing_pk(item["id"])
            if pk is not None:
                directory = existing[pk]
                directory.name = item["name"]
                directory.order = item.get("order", directory.order)
                directory.parent = parent_directory
                directory.bindings = []  # 二级目录不允许绑定来源，强制清空
                cls._save_directory(directory, update_fields=["name", "order", "bindings", "parent", "update_time"])
            else:
                directory = PluginDirectory(
                    space_id=space_id,
                    parent=parent_directory,
                    name=item["name"],
                    order=item.get("order", 0),
                    bindings=[],
                )
                cls._save_directory(directory)
            existing[directory.id] = directory
            id_mapping[item["id"]] = directory.id

        cls._validate_binding_uniqueness(space_id)
        return id_mapping

    @staticmethod
    def _validate_directory_payload(item, is_child):
        name = (item.get("name") or "").strip()
        if not name:
            raise ValidationError("目录名称不能为空")
        if is_child and item.get("bindings"):
            raise ValidationError(f"二级目录「{name}」不允许绑定来源")

    @staticmethod
    def _save_directory(directory, update_fields=None):
        try:
            if update_fields:
                directory.save(update_fields=update_fields)
            else:
                directory.save()
        except IntegrityError:
            raise ValidationError(f"目录「{directory.name}」与同级目录重名")

    @classmethod
    def _validate_binding_uniqueness(cls, space_id):
        """同一来源（source_key）在同一空间内只能绑定一个一级目录，校验保存后的最终状态。"""
        owner_by_source = {}
        queryset = PluginDirectory.objects.filter(space_id=space_id, parent__isnull=True).exclude(bindings=[])
        for directory in queryset.only("id", "name", "bindings"):
            for source_key in directory.bindings or []:
                owner = owner_by_source.get(source_key)
                if owner and owner.id != directory.id:
                    raise ValidationError(f"来源「{source_key}」同时绑定了「{owner.name}」和「{directory.name}」两个一级目录")
                owner_by_source[source_key] = directory

    @classmethod
    def _apply_assignments(cls, space_id, assignments, id_mapping, operator):
        """assignments: {str(插件条目id): 目录id(真实/本次新建的临时id)或空字符串(未分类)}"""
        try:
            entry_ids = [int(eid) for eid in assignments.keys()]
        except (TypeError, ValueError):
            raise ValidationError("assignments 的 key 必须是插件条目 id")

        entries = {
            entry.id: entry
            for entry in SpacePluginCatalogEntry.objects.filter(space_id=space_id, id__in=entry_ids)
        }
        now = timezone.now()
        to_update = []
        for eid_str, directory_raw in assignments.items():
            entry = entries.get(int(eid_str))
            if entry is None:
                continue
            if not directory_raw:
                new_directory_id = None
            else:
                new_directory_id = id_mapping.get(directory_raw)
                if new_directory_id is None:
                    try:
                        new_directory_id = int(directory_raw)
                    except (TypeError, ValueError):
                        raise ValidationError(f"插件 {entry.plugin_code} 指定的目录 {directory_raw} 不存在")
                    if not PluginDirectory.objects.filter(space_id=space_id, pk=new_directory_id).exists():
                        raise ValidationError(f"插件 {entry.plugin_code} 指定的目录 {directory_raw} 不存在")
            entry.directory_id = new_directory_id
            entry.updated_by = operator
            entry.update_at = now
            to_update.append(entry)
        if to_update:
            SpacePluginCatalogEntry.objects.bulk_update(to_update, ["directory_id", "updated_by", "update_at"])

    @classmethod
    def _apply_deletions(cls, space_id, deleted_plugin_ids, operator):
        """批量清理插件条目记录（软删除，与 04 失效记录的硬删除区分对待，保留误删恢复可能）。"""
        try:
            ids = [int(i) for i in deleted_plugin_ids]
        except (TypeError, ValueError):
            raise ValidationError("deleted_plugin_ids 必须是插件条目 id 列表")
        SpacePluginCatalogEntry.objects.filter(space_id=space_id, id__in=ids).update(
            is_deleted=True, updated_by=operator, update_at=timezone.now()
        )

    # ---------------------------------------------------------------- 删除 ----

    @classmethod
    def preview_delete(cls, space_id, directory_id):
        directory = cls._get_directory_or_404(space_id, directory_id)
        is_top_level = directory.parent_id is None
        children = list(directory.children.all().order_by("order", "id")) if is_top_level else []
        scope_ids = [directory.id] + [child.id for child in children]

        entries = SpacePluginCatalogEntry.objects.filter(
            space_id=space_id, directory_id__in=scope_ids, is_deleted=False
        )
        status_distribution = {}
        for status in entries.values_list("status", flat=True):
            status_distribution[status] = status_distribution.get(status, 0) + 1

        direct_count = SpacePluginCatalogEntry.objects.filter(
            space_id=space_id, directory_id=directory.id, is_deleted=False
        ).count()

        merge_candidates = []
        if is_top_level:
            merge_candidates = list(
                PluginDirectory.objects.filter(space_id=space_id, parent__isnull=True)
                .exclude(id=directory.id)
                .values("id", "name")
            )

        return {
            "level": 1 if is_top_level else 2,
            "name": directory.name,
            "children": [{"id": child.id, "name": child.name} for child in children],
            "total_plugin_count": entries.count(),
            "status_distribution": status_distribution,
            "direct_plugin_count": direct_count,
            "bindings": directory.bindings if is_top_level else [],
            "merge_candidates": merge_candidates,
        }

    @classmethod
    def execute_delete(cls, space_id, directory_id, strategy=None, target_directory_id=None, operator=None):
        with transaction.atomic():
            config = cls._lock_revision_config(space_id)
            current_revision = (config.json_value or {}).get("directory_revision", 0)
            directory = cls._get_directory_or_404(space_id, directory_id, for_update=True)

            if directory.parent_id is not None:
                # 二级目录：固定策略，插件与自身一并移到所属一级目录（二级目录恒无绑定来源）
                SpacePluginCatalogEntry.objects.filter(space_id=space_id, directory_id=directory.id).update(
                    directory_id=directory.parent_id, updated_by=operator, update_at=timezone.now()
                )
                directory.delete()
            elif strategy == cls.STRATEGY_PROMOTE:
                cls._execute_promote(space_id, directory, operator)
            elif strategy == cls.STRATEGY_MERGE:
                cls._execute_merge(space_id, directory, target_directory_id, operator)
            elif strategy == cls.STRATEGY_UNCATEGORIZED:
                cls._execute_uncategorized(space_id, directory, operator)
            else:
                raise ValidationError(f"未知的删除策略: {strategy}")

            cls._bump_revision(config, current_revision)

        return cls.get_manage_data(space_id)

    @classmethod
    def _execute_promote(cls, space_id, directory, operator):
        max_order = (
            PluginDirectory.objects.filter(space_id=space_id, parent__isnull=True)
            .exclude(id=directory.id)
            .aggregate(Max("order"))["order__max"]
            or 0
        )
        children = list(directory.children.all().order_by("order", "id"))
        for offset, child in enumerate(children, start=1):
            child.parent = None
            child.order = max_order + offset
            child.save(update_fields=["parent", "order"])

        SpacePluginCatalogEntry.objects.filter(space_id=space_id, directory_id=directory.id).update(
            directory_id=None, updated_by=operator, update_at=timezone.now()
        )
        directory.delete()

    @classmethod
    def _execute_merge(cls, space_id, directory, target_directory_id, operator):
        if not target_directory_id:
            raise ValidationError("合并策略需要指定目标一级目录 target_directory_id")
        if str(target_directory_id) == str(directory.id):
            raise ValidationError("不能合并到自身")
        target = PluginDirectory.objects.filter(
            space_id=space_id, pk=target_directory_id, parent__isnull=True
        ).first()
        if target is None:
            raise ValidationError(f"目标目录 {target_directory_id} 不存在或不是一级目录")

        existing_names = set(target.children.values_list("name", flat=True))
        for child in directory.children.all().order_by("order", "id"):
            new_name = child.name
            suffix = 2
            while new_name in existing_names:
                new_name = f"{child.name}({suffix})"
                suffix += 1
            existing_names.add(new_name)
            child.parent = target
            child.name = new_name
            child.save(update_fields=["parent", "name"])

        # 来源绑定一并迁移到目标目录，冲突（已被其他一级目录绑定）时直接拒绝本次合并
        owners = {
            source_key: other
            for other in PluginDirectory.objects.filter(space_id=space_id, parent__isnull=True).exclude(
                id__in=[directory.id, target.id]
            )
            for source_key in (other.bindings or [])
        }
        merged_bindings = list(target.bindings or [])
        for source_key in directory.bindings or []:
            owner = owners.get(source_key)
            if owner:
                raise ValidationError(f"来源「{source_key}」已绑定到「{owner.name}」，无法随「{directory.name}」一并合并")
            if source_key not in merged_bindings:
                merged_bindings.append(source_key)
        if merged_bindings != (target.bindings or []):
            target.bindings = merged_bindings
            target.save(update_fields=["bindings"])

        SpacePluginCatalogEntry.objects.filter(space_id=space_id, directory_id=directory.id).update(
            directory_id=target.id, updated_by=operator, update_at=timezone.now()
        )
        directory.delete()

    @classmethod
    def _execute_uncategorized(cls, space_id, directory, operator):
        child_ids = list(directory.children.values_list("id", flat=True))
        scope_ids = [directory.id] + child_ids
        SpacePluginCatalogEntry.objects.filter(space_id=space_id, directory_id__in=scope_ids).update(
            directory_id=None, updated_by=operator, update_at=timezone.now()
        )
        directory.delete()  # parent 外键 on_delete=CASCADE，子目录随之一并删除

    @staticmethod
    def _get_directory_or_404(space_id, directory_id, for_update=False):
        queryset = PluginDirectory.objects.filter(space_id=space_id, pk=directory_id)
        if for_update:
            queryset = queryset.select_for_update()
        directory = queryset.first()
        if directory is None:
            raise ValidationError(f"目录 {directory_id} 不存在")
        return directory

    # ---------------------------------------------------------------- AI 分类 ----

    @classmethod
    def ai_classify(cls, space_id, scope, plugin_ids=None):
        """
        AI 智能分类建议（整理场景），复用 06 新插件策略同一个 `AiClassifyService`。
        不写库，只返回建议，前端把 `patch` 合并进本地编辑副本的 `assignments`，随
        `manage_save` 一起提交；用户撤销由前端自行维护本地快照，后端无需支持。

        scope: "free"（全部未分类插件） | "selected"（指定 plugin_ids）
        """
        if scope == "selected":
            if not plugin_ids:
                return {"result": AiClassifyService.RESULT_EMPTY, "patch": {}, "message": ""}
            queryset = SpacePluginCatalogEntry.objects.filter(
                space_id=space_id, id__in=plugin_ids, is_deleted=False
            )
        else:
            queryset = SpacePluginCatalogEntry.objects.filter(
                space_id=space_id, directory__isnull=True, is_deleted=False
            )

        id_by_key = {}
        plugin_keys = []
        for entry in queryset.only("id", "plugin_type", "source_key", "plugin_code"):
            key = f"{entry.plugin_type}:{entry.source_key}:{entry.plugin_code}"
            plugin_keys.append(key)
            id_by_key[key] = entry.id

        # ai_scope 此处固定传 "free"：08 页面是管理员手动圈定范围（由上面的 scope 决定候选插件），
        # 与 06 自动同步场景里"increment/free"控制 AI 决策范围的语义不同，这里只是复用同一个
        # 请求通道，不代表真的做"自由范围"决策，接入真实 bkaidev 时如需区分再细化。
        result = AiClassifyService.classify(space_id=space_id, plugin_keys=plugin_keys, ai_scope="free")
        if result["result"] != AiClassifyService.RESULT_PATCH:
            return result

        patch_by_entry_id = {
            str(id_by_key[key]): directory_id for key, directory_id in result["patch"].items() if key in id_by_key
        }
        return {"result": result["result"], "patch": patch_by_entry_id, "message": result.get("message", "")}
