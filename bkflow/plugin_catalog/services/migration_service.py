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

from django.db import transaction
from django.utils import timezone
from bkflow.bk_plugin.models import BKPluginAuthorization
from bkflow.plugin.models import OpenPluginCatalogIndex, SpaceOpenPluginAvailability
from bkflow.plugin.space_plugin_config_parser import SpacePluginConfigParser
from bkflow.plugin_catalog.models import (
    CatalogChangeSource,
    CatalogChangeType,
    PluginCatalogStatus,
    PluginType,
    SpacePluginCatalogEntry,
    TemplatePluginReferenceRole,
)
from bkflow.plugin_catalog.services.change_record_service import CatalogChangeRecordService
from bkflow.plugin_catalog.services.source_group_service import SourceGroupService
from bkflow.space.configs import PluginCatalogMigrationConfig, SpacePluginConfig
from bkflow.space.models import SpaceConfig
from bkflow.template.models import Template, TemplateSnapshot

logger = logging.getLogger(__name__)


class PluginCatalogMigrationService:
    """
    存量空间插件目录初始化迁移：把迁移前的旧配置状态翻译成插件目录条目。

    迁移只做一次性的"种子数据生成"：按迁移前的旧配置状态（内置插件黑白名单/蓝鲸插件授权/
    开放插件启用开关）为每个插件生成一条 `SpacePluginCatalogEntry`（visible/已停用，全部
    挂"未分类"），同时回填存量流程的插件引用记录 `TemplatePluginReference`（线上版与
    草稿版两套），随后插件的可见性判定权威收敛到该表，不再实时读旧配置；已 `ready=True`
    的空间重跑直接跳过（幂等），不覆盖管理员后续的人工分类/推荐/启停决定。

    引用回填与目录种子、ready 状态在同一个事务内按空间原子提交（设计文档
    `03 后台任务与迁移清单`「执行存量初始化」要求写入「目录与统一引用」）。
    """

    @classmethod
    def get_status(cls, space_id):
        return SpaceConfig.get_config(space_id=space_id, config_name=PluginCatalogMigrationConfig.name)

    @classmethod
    def is_ready(cls, space_id):
        status = cls.get_status(space_id) or {}
        return bool(status.get("ready"))

    # ------------------------------------------------------ 迁移状态展示视图 ----

    # 旧配置「过滤方式」的展示文案：与设计稿表格第一行的说明一致
    FILTER_MODE_TEXTS = {
        "allow_list": "仅显示名单中的插件",
        "deny_list": "仅显示名单外的插件",
        "allow_all": "显示所有插件",
    }

    # 快照行的固定说明（前半段「名称 + 时间」由后端拼好，见 build_legacy_snapshot_view）
    SNAPSHOT_NOTE = "初始化插件目录时保存；如有改动，再次初始化插件分类目录时可以恢复此配置"

    @classmethod
    def get_status_view(cls, space_id):
        """迁移状态 + **前端可直接展示**的旧配置快照。

        设计稿「空间插件 - 引导」页的「迁移前的配置（只读）」表格：

            过滤方式        仅显示名单中的插件
            插件            HTTP 请求  Python 代码  审批  暂停
            按 scope 覆盖   无
            快照            admin 于 2026-09-10 00:00 初始化插件目录时保存；如有改动，……

        加工放在**读取侧**而不是迁移写入侧：迁移是幂等的，已迁移空间的
        `legacy_snapshot` 是存量数据（重跑不会重写），若只在写入侧加工，
        存量空间永远拿不到新结构。
        """
        status = cls.get_status(space_id) or {"ready": False}
        view = dict(status)
        view["legacy_snapshot"] = cls.build_legacy_snapshot_view(
            space_id,
            status.get("legacy_snapshot") or {},
            migrated_by=status.get("migrated_by") or "",
            migrated_at=status.get("migrated_at") or "",
        )
        return view

    @classmethod
    def build_legacy_snapshot_view(cls, space_id, legacy_snapshot,migrated_by="admin",migrated_at=None):
        """把迁移时存的旧配置快照原始结构，转成前端能直接渲染成表格的结构。

        原始快照是内部结构（`space_plugin_config` 的原始 JSON），前端拿它
        没法直接展示，这里补齐三部分：

        - `filter_mode` / `filter_mode_text`：旧配置的过滤方式及其说明
        - `operations`：旧配置里放行的插件（code + 中文展示名），对应「操作」行
        - `scope_overrides`：旧配置里除 `default` 外的按 scope 覆盖项，对应「按 scope 覆盖」行
        - `migrated_by`：迁移人
        - `migrated_at`：迁移时间
        """
        plugin_config = legacy_snapshot.get("space_plugin_config") or {}
        default_config = plugin_config.get("default") or {}
        mode = default_config.get("mode") or ""

        name_maps = {
            "builtin": SourceGroupService.builtin_display_names(),
            "bk_plugin": SourceGroupService.bk_plugin_display_names(space_id),
        }

        plugins = []
        for code in default_config.get("plugin_codes") or []:
            full_name = name_maps["builtin"].get(code) or name_maps["bk_plugin"].get(code) or code
            plugins.append(
                {
                    "code": code,
                    "name": full_name
                }
            )

        scope_overrides = []
        for scope_key, scope_config in plugin_config.items():
            if scope_key == "default" or not isinstance(scope_config, dict):
                continue
            scope_overrides.append(
                {
                    "scope": scope_key,
                    "mode": scope_config.get("mode") or "",
                    "plugin_codes": scope_config.get("plugin_codes") or [],
                }
            )

        return {
            "filter_mode": mode,
            "filter_mode_text": cls.FILTER_MODE_TEXTS.get(mode, ""),
            "plugins": plugins,
            "scope_overrides": scope_overrides,
            "snapshot_note":f"{migrated_by} 于 {migrated_at} {cls.SNAPSHOT_NOTE}" ,
            "open_plugin_enabled_count": legacy_snapshot.get("open_plugin_enabled_count", 0),
        }

    @classmethod
    def initialize_space(
        cls,
        space_id,
        operator="admin",
        dry_run=False,
        operate_source=CatalogChangeSource.COMMAND,
    ):
        """幂等：已完成迁移的空间直接返回当前状态，不重复生成/覆盖。"""
        current_status = cls.get_status(space_id) or {}
        if current_status.get("ready"):
            return {"ready": True, "already_migrated": True, **current_status}

        builtin_seed = cls._seed_builtin(space_id)
        bk_plugin_seed = cls._seed_bk_plugin(space_id)
        api_seed = cls._seed_api(space_id)
        seeds = builtin_seed + bk_plugin_seed + api_seed

        # 存量流程的插件引用同样属于初始化范围：目录条目 + 统一引用一起提交，
        # 否则引用计数会停留在"虚假零引用"（设计文档要求未就绪不得返回零引用）。
        reference_preview = cls._preview_template_references(space_id)

        preview = {
            "total": len(seeds),
            "enable": sum(1 for item in seeds if item["status"] == PluginCatalogStatus.ENABLE),
            # preview 的 key 与 status 枚举值保持一致（disabled = 本次生成的「已停用」条目数）
            "disabled": sum(1 for item in seeds if item["status"] == PluginCatalogStatus.DISABLED),
            "by_type": {
                PluginType.BUILTIN: len(builtin_seed),
                PluginType.BK_PLUGIN: len(bk_plugin_seed),
                PluginType.API: len(api_seed),
            },
            "references": reference_preview,
        }
        if dry_run:
            return {"ready": False, "dry_run": True, "preview": preview}

        legacy_snapshot = cls._build_legacy_snapshot(space_id)
        now = timezone.now()
        with transaction.atomic():
            cls._bulk_create_entries(space_id, seeds)
            reference_result = cls._backfill_template_references(space_id)
            SpaceConfig.objects.batch_update(
                space_id=space_id,
                configs={
                    PluginCatalogMigrationConfig.name: {
                        "ready": True,
                        "migrated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "migrated_by": operator,
                        "legacy_snapshot": legacy_snapshot,
                    }
                },
            )
            # 初始化同时留痕：变更前值 = 迁移前的旧管理配置快照，变更后值 = 本次执行结果，
            # 供上线回退时做差异核对（设计文档「变更记录中的旧管理配置快照」）。
            CatalogChangeRecordService.record(
                space_id=space_id,
                instance_id=space_id,
                operate_type=CatalogChangeType.INITIALIZE,
                operator=operator,
                before_value=legacy_snapshot,
                after_value={"preview": preview, "references": reference_result},
                method="initialize_plugin_catalog",
                operate_source=operate_source,
            )
        return {
            "ready": True,
            "already_migrated": False,
            "preview": preview,
            "references": reference_result,
        }

    # ------------------------------------------------------------------ 种子数据 ----

    @classmethod
    def _seed_builtin(cls, space_id):
        plugin_config = SpaceConfig.get_config(space_id=space_id, config_name=SpacePluginConfig.name)
        parser = SpacePluginConfigParser(config=plugin_config) if plugin_config else None
        # 元信息与插件清单一次取回（code / name / version 同一次查询）
        metadata = SourceGroupService.collect_builtin_metadata()
        codes = list(metadata.keys())
        if parser:
            visible_codes = parser.get_filtered_plugins("default", codes)
        else:
            visible_codes = set(codes)
        return [
            {
                "plugin_type": PluginType.BUILTIN,
                "source_key": "",
                "plugin_code": code,
                "plugin_name": metadata[code][0],
                "plugin_desc": metadata[code][1],
                "status": PluginCatalogStatus.ENABLE if code in visible_codes else PluginCatalogStatus.DISABLED,
            }
            for code in codes
        ]

    @classmethod
    def _seed_bk_plugin(cls, space_id):
        authorized_codes = set(BKPluginAuthorization.objects.get_codes_by_space_id(space_id))
        # 元信息与插件清单一次取回（code / name / introduction 同一次查询）
        metadata = SourceGroupService.collect_bk_plugin_metadata(space_id)
        return [
            {
                "plugin_type": PluginType.BK_PLUGIN,
                "source_key": "",
                "plugin_code": code,
                "plugin_name": metadata[code][0],
                "plugin_desc": metadata[code][1],
                "status": PluginCatalogStatus.ENABLE if code in authorized_codes else PluginCatalogStatus.DISABLED,
            }
            for code in metadata
        ]

    @classmethod
    def _seed_api(cls, space_id):
        """
        API 插件的种子数据，两张表各司其职：

        - `SpaceOpenPluginAvailability`（**范围**）：这个空间主动启用/关闭了哪些 API 插件，
          它承载的就是**迁移前的旧配置状态**——迁移要翻译的正是这个开关状态。
        - `OpenPluginCatalogIndex`（**元信息**）：这些插件叫什么、描述是什么。迁移这一步
          不现场请求远端，元信息只能从这张来源目录缓存里读。

        V2/V3 协议插件不会出现在这里：`SpaceOpenPluginAvailability` 的记录来自开放插件目录
        缓存刷新与前端开关操作，而缓存只收录 V4 协议插件，前端开关列表也读的是这张缓存表，
        所以迁移前 V2/V3 就没有开关记录、无从翻译，交给迁移后的首轮
        `sync_space_plugin_catalog_task` 按新插件策略正常发现（不在迁移这一步强行请求远端）。

        `OpenPluginCatalogIndex.status` 为 unavailable（来源侧已下架但开关还开着）的插件
        仍然会被 seed：这样它在目录里保留"存量身份"，首轮同步只把它标记为失效、记住原状态，
        来源重新出现时唤醒回启用态，而不会因为漏了种子被当成新插件重新审核
        （开发文档 04 L23「存量不重审」）。
        """
        enabled_map = {
            (item.source_key, item.plugin_id): item.enabled
            for item in SpaceOpenPluginAvailability.objects.filter(space_id=space_id).only(
                "source_key", "plugin_id", "enabled"
            )
        }
        metadata = {
            (item.source_key, item.plugin_id): (item.plugin_name, item.description or "")
            for item in OpenPluginCatalogIndex.objects.filter(space_id=space_id).only(
                "source_key", "plugin_id", "plugin_name", "description"
            )
        }
        seeds = []
        for source_key, plugin_id in enabled_map:
            # 元信息取不到时用 plugin_id 兜底，与对外「plugin_name 为空回退展示 plugin_code」一致，
            # 避免目录里出现一个没有名字的条目
            plugin_name, plugin_desc = metadata.get((source_key, plugin_id), (plugin_id, ""))
            seeds.append(
                {
                    "plugin_type": PluginType.API,
                    "source_key": source_key,
                    "plugin_code": plugin_id,
                    "plugin_name": plugin_name,
                    "plugin_desc": plugin_desc,
                    "status": (
                        PluginCatalogStatus.ENABLE
                        if enabled_map[(source_key, plugin_id)]
                        else PluginCatalogStatus.DISABLED
                    ),
                }
            )
        return seeds

    @classmethod
    def _bulk_create_entries(cls, space_id, seeds):
        existing_keys = set(
            SpacePluginCatalogEntry.objects.filter(space_id=space_id).values_list(
                "plugin_type", "source_key", "plugin_code"
            )
        )
        to_create = [
            SpacePluginCatalogEntry(
                space_id=space_id,
                plugin_type=item["plugin_type"],
                source_key=item["source_key"],
                plugin_code=item["plugin_code"],
                plugin_name=item.get("plugin_name", ""),
                plugin_desc=item.get("plugin_desc", ""),
                status=item["status"],
                directory=None,
                ever_enabled=item["status"] == PluginCatalogStatus.ENABLE,
                last_synced_at=timezone.now(),
                updated_by="system",
            )
            for item in seeds
            if (item["plugin_type"], item["source_key"], item["plugin_code"]) not in existing_keys
        ]
        if to_create:
            SpacePluginCatalogEntry.objects.bulk_create(to_create)

    # ------------------------------------------------------------------ 存量流程引用回填 ----

    @classmethod
    def backfill_references(cls, space_id, operator="admin", dry_run=False):
        """给已完成迁移的空间补写存量流程的插件引用记录。

        初始化命令对 `ready=True` 的空间是幂等跳过的，而引用回填必须能单独补跑，
        否则会出现「目录已迁移、引用仍为空」的半成品状态（插件引用计数恒为 0）。
        本方法不改目录条目、不改 ready 状态、不覆盖管理员的人工决定，
        只按流程当前快照重算引用（先删后插，天然幂等）。

        未完成初始化的空间不做回填：未就绪空间按设计应返回"未就绪"而不是零引用。
        """
        current_status = cls.get_status(space_id) or {}
        if not current_status.get("ready"):
            return {"ready": False, "skipped": True, "reason": "空间尚未完成插件目录初始化"}

        if dry_run:
            return {"ready": True, "dry_run": True, "references": cls._preview_template_references(space_id)}

        with transaction.atomic():
            result = cls._backfill_template_references(space_id)
        return {"ready": True, "dry_run": False, "references": result, "operator": operator}

    @classmethod
    def _backfill_template_references(cls, space_id):
        """按空间回填存量流程的插件引用记录，返回统计信息。

        引用与流程快照同源：线上版取该模板最新的 published 快照，草稿版取最新的
        draft 快照，两套 role 各自独立重算（设计文档「无草稿≠未引用」——只有线上版的
        流程同样是有引用的，不能只回填 draft 一套）。

        解析不出插件身份的节点按 `resolved=False` 落库（无法识别的 API 节点），
        不计入插件引用计数，只体现在"未识别节点数"统计里。
        """
        # 延迟 import：reference_service -> query_service -> migration_service 存在循环依赖，
        # 这里保持"用时才导入"，避免应用加载阶段就触发循环导入错误。
        from bkflow.plugin_catalog.services.reference_service import PluginReferenceService

        templates = 0
        nodes = 0
        for template_id, role, pipeline_tree in cls._iter_space_template_trees(space_id):
            templates += 1
            nodes += PluginReferenceService.rebuild_template_references(
                space_id=space_id,
                template_id=template_id,
                role=role,
                pipeline_tree=pipeline_tree,
            )
        return {"templates": templates, "nodes": nodes}

    @classmethod
    def _preview_template_references(cls, space_id):
        """统计将回填的存量流程引用条数（不写库），用于 `--dry-run` 核对。"""
        # 延迟 import：guard_service 模块级导入 migration_service，存在循环依赖。
        from bkflow.plugin_catalog.services.guard_service import PluginCatalogGuardService

        templates = 0
        nodes = 0
        for template_id, role, pipeline_tree in cls._iter_space_template_trees(space_id):
            templates += 1
            nodes += len(PluginCatalogGuardService.extract_node_plugin_identities(pipeline_tree))
        return {"templates": templates, "nodes": nodes}

    @classmethod
    def _iter_space_template_trees(cls, space_id):
        """产出 (template_id, role, pipeline_tree)：每个流程的线上版与草稿版各一份。

        只反映流程的"当前线上版/草稿版"引用了哪些插件，不含历史版本。
        """
        templates = Template.objects.filter(space_id=space_id, is_deleted=False).only("id", "snapshot_id")
        for template in templates:
            published_snapshot = cls._pick_published_snapshot(template)
            if published_snapshot is not None:
                yield template.id, TemplatePluginReferenceRole.PUBLISHED, published_snapshot.data
            draft_snapshot = cls._pick_draft_snapshot(template)
            if draft_snapshot is not None:
                yield template.id, TemplatePluginReferenceRole.DRAFT, draft_snapshot.data

    @staticmethod
    def _pick_published_snapshot(template):
        """取流程的线上版快照。

        以 `Template.snapshot_id` 为准（保存/发布时它指向的就是当前线上版快照）；
        该快照缺失或指向草稿时，回退到该流程最新的 published 快照。
        """
        if template.snapshot_id:
            snapshot = TemplateSnapshot.objects.filter(id=template.snapshot_id).first()
            if snapshot is not None and not snapshot.draft:
                return snapshot
        return (
            TemplateSnapshot.objects.filter(template_id=template.id, draft=False, is_deleted=False)
            .order_by("-id")
            .first()
        )

    @staticmethod
    def _pick_draft_snapshot(template):
        """取流程的草稿版快照（开启流程版本管理的空间才有）。"""
        return (
            TemplateSnapshot.objects.filter(template_id=template.id, draft=True, is_deleted=False)
            .order_by("-id")
            .first()
        )

    # ------------------------------------------------------------------ 旧配置快照 ----

    @classmethod
    def _build_legacy_snapshot(cls, space_id):
        plugin_config = SpaceConfig.get_config(space_id=space_id, config_name=SpacePluginConfig.name) or {}
        open_plugin_enabled_count = SpaceOpenPluginAvailability.objects.filter(
            space_id=space_id, enabled=True
        ).count()
        return {
            "space_plugin_config": plugin_config,
            "open_plugin_enabled_count": open_plugin_enabled_count,
        }
