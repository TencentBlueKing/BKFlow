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
from bkflow.plugin_catalog.models import (
    CatalogChangeSource,
    CatalogChangeType,
    PluginDirectory,
    SpacePluginCatalogEntry,
)
from bkflow.plugin_catalog.services.ai_classify_service import AiClassifyService
from bkflow.plugin_catalog.services.change_record_service import CatalogChangeRecordService
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

        result = []
        for entry in entries:
            result.append(
                {
                    "id": entry.id,
                    "plugin_type": entry.plugin_type,
                    "source_key": SourceGroupService.display_source_id(entry.plugin_type, entry.source_key),
                    "plugin_code": entry.plugin_code,
                    # 插件名 / 描述取自目录条目表（来源同步写入的副本），不再实时查外部只读表
                    "plugin_name": entry.plugin_name or entry.plugin_code,
                    "plugin_desc": entry.plugin_desc or "",
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
    def save_manage_data(
        cls,
        space_id,
        directories,
        assignments,
        expected_revision,
        operator,
        operate_source=CatalogChangeSource.WEB,
        request_id="",
    ):
        """整页保存目录管理页的改动：目录树 + 插件归属。
        """
        with transaction.atomic():
            config = cls._lock_revision_config(space_id)
            current_revision = (config.json_value or {}).get("directory_revision", 0)
            if current_revision != expected_revision:
                raise ValidationError(
                    f"插件目录数据已被修改(当前版本 {current_revision}，提交版本 {expected_revision})，请刷新后重试"
                )

            before_snapshot = cls._manage_snapshot(space_id)

            id_mapping = cls._upsert_directories(space_id, directories or {})
            if assignments:
                cls._apply_assignments(space_id, assignments, id_mapping, operator)

            cls._bump_revision(config, current_revision)

            CatalogChangeRecordService.record(
                space_id=space_id,
                # 整页保存是空间级动作，没有单一目录对象，用 0 表示空间级
                instance_id=0,
                operate_type=CatalogChangeType.DIRECTORY_SAVE,
                operator=operator,
                before_value=before_snapshot,
                after_value=cls._manage_snapshot(space_id),
                method="directories/manage_save",
                operate_source=operate_source,
                request_id=request_id,
            )

        return cls.get_manage_data(space_id)

    @staticmethod
    def _manage_snapshot(space_id):
        """目录树 + 插件归属快照，作为目录保存变更记录的前后值。"""
        directories = {
            str(directory.id): {
                "id": directory.id,
                "parent_id": directory.parent_id,
                "name": directory.name,
                "order": directory.order,
            }
            for directory in PluginDirectory.objects.filter(space_id=space_id).order_by("id")
        }
        assignments = {
            str(entry.id): entry.directory_id
            for entry in SpacePluginCatalogEntry.objects.filter(space_id=space_id, is_deleted=False).order_by("id")
        }
        return {"directories": directories, "assignments": assignments}

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
        directories: {提交id(str): {"id":..., "parent_id":..., "name":..., "order":...}}
        返回 {提交id: 真实pk} 映射，供 `_apply_assignments` 解析 assignments 里可能引用的新建目录。

        **整页替换语义**：`directories` 是该空间目录树的最终完整状态——
        - 提交里有、库里也有 → 更新；
        - 提交里有、库里没有 → 新建；
        - 库里有、提交里没有 → 删除（视为用户删掉了该目录）。

        分两轮处理：先一级（parent_id 为空）后二级，使二级目录可以引用"同一批提交里刚新建
        的一级目录"的前端临时 id。
        """
        existing = {directory.id: directory for directory in PluginDirectory.objects.filter(space_id=space_id)}
        original_ids = set(existing.keys())
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
                directory.parent = None
                cls._save_directory(directory, update_fields=["name", "order", "parent", "update_time"])
            else:
                directory = PluginDirectory(
                    space_id=space_id,
                    parent=None,
                    name=item["name"],
                    order=item.get("order", 0),
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
                cls._save_directory(directory, update_fields=["name", "order", "parent", "update_time"])
            else:
                directory = PluginDirectory(
                    space_id=space_id,
                    parent=parent_directory,
                    name=item["name"],
                    order=item.get("order", 0),
                )
                cls._save_directory(directory)
            existing[directory.id] = directory
            id_mapping[item["id"]] = directory.id

        # 整页替换：库里原本存在、但本次没提交的目录，视为用户删掉。
        # （新建目录用的是前端临时 id，不会落进 submitted_real_ids，不会被误删）
        submitted_real_ids = set()
        for raw_id in submitted:
            pk = resolve_existing_pk(raw_id)
            if pk is not None:
                submitted_real_ids.add(pk)

        for pk in original_ids - submitted_real_ids:
            directory = existing[pk]
            # 子目录仍在提交里：先提升为一级，避免 parent 的 CASCADE 把它一起删掉
            for child in directory.children.all():
                if child.id in submitted_real_ids:
                    child.parent = None
                    child.save(update_fields=["parent", "update_time"])
            # 删除目录后，挂在其下的插件由外键 on_delete=SET_NULL 回到「未分类」
            directory.delete()

        return id_mapping

    @staticmethod
    def _validate_directory_payload(item, is_child):
        name = (item.get("name") or "").strip()
        if not name:
            raise ValidationError("目录名称不能为空")

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

    # ---------------------------------------------------------------- 删除 ----

    @classmethod
    def preview_delete(cls, space_id, directory_ids):
        """删除目录前的影响预览（只读，不写正式数据），支持批量。

        返回结构对齐设计稿 `8.png` 的确认弹窗表格——两行「子对象 / 删除后的改动」，
        后端把结论算好，前端直接展示，不用自己推断：

            4 个子目录   变成一级目录
            8 个插件     移入「未分类插件」

        二级目录没有子目录、目录里也没有插件时，对应行写 0 + 「无影响」。

        `items` 逐个目录给出一份结论（前端可逐行展示），顶层再给合计。

        `conflicts` 是提升为一级目录时会撞名的目录名（开发文档 02 L63 要求的
        「冲突预览」）：一级目录名在库里对 NULL 父级不唯一（`unique_together`
        遇到 NULL 不生效），所以重名不会被数据库拦下，必须由业务层提前发现。
        批量时冲突要**跨目录**一起算：A 的子目录和 B 的子目录可能互相撞名，
        所以一次性把整批待提升的子目录都算进来，结果与请求顺序无关。
        """
        directories = cls._get_directories_for_delete(space_id, directory_ids)
        plan = cls._build_delete_plan(space_id, directories)

        items = []
        for directory in directories:
            children = plan["children_by_directory"].get(directory.id, [])
            plugin_count = plan["plugin_count_by_directory"].get(directory.id, 0)
            items.append(
                {
                    "id": directory.id,
                    "name": directory.name,
                    "level": 1 if directory.parent_id is None else 2,
                    "children_count": len(children),
                    "children_effect": "变成一级目录" if children else "无影响",
                    "plugin_count": plugin_count,
                    "plugin_effect": "移入「未分类插件」" if plugin_count else "无影响",
                    "conflicts": [name for name in plan["conflicts"] if name in {c.name for c in children}],
                }
            )

        return {
            "items": items,
            "total": len(items),
            "total_children_count": len(plan["promoted_children"]),
            "total_plugin_count": plan["total_plugin_count"],
            "conflicts": plan["conflicts"],
        }

    @classmethod
    def _get_directories_for_delete(cls, space_id, directory_ids):
        """取待删除的目录列表，任何一个不存在就直接报错（整体拒绝，不做部分删除）。"""
        directory_ids = list(directory_ids or [])
        if not directory_ids:
            raise ValidationError("至少要指定一个待删除目录")
        found = {
            directory.id: directory
            for directory in PluginDirectory.objects.filter(space_id=space_id, id__in=directory_ids)
        }
        missing = [str(directory_id) for directory_id in directory_ids if directory_id not in found]
        if missing:
            raise ValidationError(f"目录 {', '.join(missing)} 不存在")
        # 保持请求顺序
        return [found[directory_id] for directory_id in directory_ids]

    @classmethod
    def _build_delete_plan(cls, space_id, directories):
        """算清这一批删除的最终结果（与请求顺序无关）。

        - `children_by_directory`：每个待删目录删除后，有哪些子目录会提升为一级目录。
          只提升**直接子目录**，且排除掉"本身也在这一批待删集合里"的子目录
          （那种情况它会被直接删掉，不需要提升）。
        - `plugin_count_by_directory`：每个待删目录里直接挂着的插件数（会移未分类）。
        - `promoted_children`：整批待提升为一级目录的子目录。
        - `conflicts`：待提升的子目录名里，与空间现有一级目录、或彼此之间重名的。
        """
        delete_ids = {directory.id for directory in directories}
        children_by_directory = {}
        for directory in directories:
            children_by_directory[directory.id] = [
                child
                for child in directory.children.all().order_by("order", "id")
                if child.id not in delete_ids
            ]

        plugin_count_by_directory = {
            directory.id: SpacePluginCatalogEntry.objects.filter(
                space_id=space_id, directory_id=directory.id, is_deleted=False
            ).count()
            for directory in directories
        }

        promoted_children = []
        for children in children_by_directory.values():
            promoted_children.extend(children)

        conflicts = cls._detect_promote_conflicts(space_id, directories, promoted_children)

        return {
            "children_by_directory": children_by_directory,
            "plugin_count_by_directory": plugin_count_by_directory,
            "promoted_children": promoted_children,
            "total_plugin_count": sum(plugin_count_by_directory.values()),
            "conflicts": conflicts,
        }

    @classmethod
    def _detect_promote_conflicts(cls, space_id, directories, promoted_children):
        """子目录提升为一级目录时，会重名的名称列表。

        一级目录的 `unique_together = (space_id, parent, name)` 在 `parent` 为 NULL 时
        不生效（SQL 里 NULL 不参与唯一性比较），所以重名不会被数据库拦下，
        必须在业务层检测出来：重名时直接拒绝删除，让管理员先改名。

        批量删除时有两类冲突：
        1. 待提升的子目录 与 空间里已有的一级目录重名；
        2. 待提升的子目录**彼此之间**重名（删 A 和删 B，A、B 的子目录同名）。
        """
        if not promoted_children:
            return []

        # 这批待删目录本身也在删除中，不算"已有的一级目录"
        deleting_ids = {directory.id for directory in directories}
        existing_names = set(
            PluginDirectory.objects.filter(space_id=space_id, parent__isnull=True)
            .exclude(id__in=deleting_ids)
            .values_list("name", flat=True)
        )

        conflicts = []
        seen = set()
        for child in promoted_children:
            # 彼此之间重名：同名出现第二次就是冲突
            if child.name in seen:
                if child.name not in conflicts:
                    conflicts.append(child.name)
                continue
            seen.add(child.name)
            if child.name in existing_names and child.name not in conflicts:
                conflicts.append(child.name)
        return conflicts

    @classmethod
    def execute_delete(
        cls,
        space_id,
        directory_ids,
        operator=None,
        operate_source=CatalogChangeSource.WEB,
        request_id="",
    ):
        """批量删除目录：唯一一套行为，不让调用方选策略。

        开发文档 04 L18：「删除后子目录提升、直接插件含未启用移未分类」，
        设计稿 `8.png` 的确认弹窗也是这两行：

            4 个子目录 → 变成一级目录
            8 个插件   → 移入「未分类插件」

        - 一级目录：子目录提升为一级目录（排在一级目录末尾）；**直接挂在本目录的插件**
          （含未启用的）移到未分类；本目录删除。
        - 二级目录：没有子目录，它自己的插件同样移到未分类；本目录删除。

        批量时：
        - 冲突检测**一次性跨目录**做完（待提升的子目录之间也可能重名），
          与请求顺序无关；有冲突则整批拒绝，不做部分删除。
        - 同时删了父目录和它的子目录时，子目录直接被删、不需要提升。
        - 整批只 bump 一次 revision（一次操作 = 一次版本变更）。
        - 每个目录留一条变更记录，便于逐个回溯。
        """
        with transaction.atomic():
            config = cls._lock_revision_config(space_id)
            current_revision = (config.json_value or {}).get("directory_revision", 0)

            directories = cls._get_directories_for_delete(space_id, directory_ids)
            # 加锁重查，保证并发删除时不会互相踩
            directories = [
                PluginDirectory.objects.select_for_update().get(pk=directory.id) for directory in directories
            ]

            plan = cls._build_delete_plan(space_id, directories)
            if plan["conflicts"]:
                raise ValidationError(
                    f"子目录「{'」「'.join(plan['conflicts'])}」提升为一级目录后与已有的一级目录重名，"
                    "请先重命名后再删除"
                )

            delete_ids = {directory.id for directory in directories}
            promoted_total = 0
            uncategorized_total = 0

            for directory in directories:
                # directory.delete() 之后 Django 会把实例的 pk 置空，这里先留一份 id 用于写变更记录
                deleted_directory_id = directory.id
                before_snapshot = cls._delete_snapshot(space_id, directory)
                is_top_level = directory.parent_id is None
                children = plan["children_by_directory"].get(directory.id, [])

                if is_top_level and children:
                    # 子目录提升为一级目录，排在一级目录末尾
                    max_order = (
                        PluginDirectory.objects.filter(space_id=space_id, parent__isnull=True)
                        .exclude(id__in=delete_ids)
                        .aggregate(Max("order"))["order__max"]
                        or 0
                    )
                    for offset, child in enumerate(children, start=1):
                        child.parent = None
                        child.order = max_order + offset
                        child.save(update_fields=["parent", "order"])
                    promoted_total += len(children)

                # 直接挂在本目录的插件（含未启用的）移到未分类；
                # 子目录里的插件跟着子目录走，不受影响。
                uncategorized_total += SpacePluginCatalogEntry.objects.filter(
                    space_id=space_id, directory_id=directory.id
                ).update(directory_id=None, updated_by=operator, update_at=timezone.now())
                directory.delete()

                CatalogChangeRecordService.record(
                    space_id=space_id,
                    instance_id=deleted_directory_id,
                    operate_type=CatalogChangeType.DIRECTORY_DELETE,
                    operator=operator,
                    before_value=before_snapshot,
                    after_value={"level": 1 if is_top_level else 2},
                    method="directories/execute_delete",
                    operate_source=operate_source,
                    request_id=request_id,
                )

            cls._bump_revision(config, current_revision)

        result = cls.get_manage_data(space_id)
        result["deleted"] = len(directories)
        result["promoted"] = promoted_total
        result["uncategorized"] = uncategorized_total
        return result

    @staticmethod
    def _delete_snapshot(space_id, directory):
        """被删目录及其子目录、归属插件的快照，作为目录删除变更记录的变更前值。"""
        child_ids = list(directory.children.values_list("id", flat=True))
        scope_ids = [directory.id] + child_ids
        return {
            "directory": {
                "id": directory.id,
                "parent_id": directory.parent_id,
                "name": directory.name,
                "order": directory.order,
            },
            "children": child_ids,
            "entries": {
                str(entry_id): directory_id
                for entry_id, directory_id in SpacePluginCatalogEntry.objects.filter(
                    space_id=space_id, directory_id__in=scope_ids
                ).values_list("id", "directory_id")
            },
        }

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
    def ai_classify(cls, space_id, content=None, thread_id=None):
        """
        AI 智能分类建议（整理场景），复用 06 新插件策略同一个 `AiClassifyService`。

        默认整理**该空间全部未分类插件**（目录为空的那些），不需要前端圈定范围。

        :param content: 用户额外提的需求，追加到固定 prompt 末尾
        :param thread_id: 智能体会话 id；传了就延续该会话（智能体读取历史记录）

        **返回与 `GET directories/manage_data` 完全同构的目录文档**，前端可直接转成
        `manage_save` 的入参（整页替换）。外加三个字段：

        - `result` / `message`：AI 调用状态
        - `thread_id`：本次会话 id，用户接着追问时传回本接口

        AI 新建目录用临时 key、删除空目录直接从 `directories` 里去掉；接口本身不写库。
        """
        queryset = SpacePluginCatalogEntry.objects.filter(
            space_id=space_id, directory__isnull=True, is_deleted=False
        )
        plugin_keys = [
            f"{entry.plugin_type}:{entry.source_key}:{entry.plugin_code}"
            for entry in queryset.only("id", "plugin_type", "source_key", "plugin_code")
        ]
        empty = {"result": AiClassifyService.RESULT_EMPTY, "thread_id": thread_id or ""}
        if not plugin_keys:
            return cls._ai_manage_document(space_id, empty)

        plan = AiClassifyService.classify_for_directory_manage(
            space_id=space_id, plugin_keys=plugin_keys, content=content, thread_id=thread_id
        )
        return cls._ai_manage_document(space_id, plan)

    @classmethod
    def _ai_manage_document(cls, space_id, plan):
        """把 AI 的整理方案组装成 `manage_data` 同构的文档。"""
        base = cls.get_manage_data(space_id)

        # --- 目录树 = 现有目录 + AI 新建的 - AI 判定删掉的（空目录）---
        directories = dict(base["directories"])
        for omit_id in plan.get("omit_directory_ids") or []:
            directories.pop(str(omit_id), None)
        for item in plan.get("new_directories") or []:
            key = item["key"]
            directories[key] = {
                "id": key,
                "parent_id": item.get("parent_key") or "",
                "name": item["name"],
                "order": item.get("order", 0),
            }

        # --- 插件归属：AI 分配的覆盖原值（没提到的插件保持原样）---
        assignments = plan.get("assignments") or {}
        entry_by_id = {
            entry.id: entry
            for entry in SpacePluginCatalogEntry.objects.filter(space_id=space_id, is_deleted=False).only(
                "id", "plugin_type", "source_key", "plugin_code"
            )
        }
        plugins = []
        for plugin in base["plugins"]:
            entry = entry_by_id.get(plugin["id"])
            if entry is not None:
                key = f"{entry.plugin_type}:{entry.source_key}:{entry.plugin_code}"
                if key in assignments:
                    plugin = dict(plugin)
                    # directory_key 为 None 表示建议放「未分类」
                    plugin["directory_id"] = assignments[key] or ""
            plugins.append(plugin)

        return {
            "result": plan.get("result", AiClassifyService.RESULT_EMPTY),
            "message": plan.get("message", ""),
            # 智能体会话 id：用户接着追问时传回本接口的 thread_id
            "thread_id": plan.get("thread_id", ""),
            "revision": base["revision"],
            "directories": directories,
            "plugins": plugins,
        }
