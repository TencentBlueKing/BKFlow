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
from pipeline.component_framework.models import ComponentModel

from bkflow.bk_plugin.models import BKPlugin, BKPluginAuthorization
from bkflow.plugin.constants import WRAPPER_CODES
from bkflow.plugin.models import SpaceOpenPluginAvailability
from bkflow.plugin.space_plugin_config_parser import SpacePluginConfigParser
from bkflow.plugin_catalog.models import PluginCatalogStatus, PluginType, SpacePluginCatalogEntry
from bkflow.space.configs import PluginCatalogMigrationConfig, SpacePluginConfig
from bkflow.space.models import SpaceConfig

logger = logging.getLogger(__name__)


class PluginCatalogMigrationService:
    """
    存量空间插件目录初始化迁移：把迁移前的旧配置状态翻译成插件目录条目。

    迁移只做一次性的"种子数据生成"：按迁移前的旧配置状态（内置插件黑白名单/蓝鲸插件授权/
    开放插件启用开关）为每个插件生成一条 `SpacePluginCatalogEntry`（visible/已停用，全部
    挂"未分类"），随后插件的可见性判定权威收敛到该表，不再实时读旧配置；已 `ready=True`
    的空间重跑直接跳过（幂等），不覆盖管理员后续的人工分类/推荐/启停决定。
    """

    @classmethod
    def get_status(cls, space_id):
        return SpaceConfig.get_config(space_id=space_id, config_name=PluginCatalogMigrationConfig.name)

    @classmethod
    def is_ready(cls, space_id):
        status = cls.get_status(space_id) or {}
        return bool(status.get("ready"))

    @classmethod
    def initialize_space(cls, space_id, operator="admin", dry_run=False):
        """幂等：已完成迁移的空间直接返回当前状态，不重复生成/覆盖。"""
        current_status = cls.get_status(space_id) or {}
        if current_status.get("ready"):
            return {"ready": True, "already_migrated": True, **current_status}

        builtin_seed = cls._seed_builtin(space_id)
        bk_plugin_seed = cls._seed_bk_plugin(space_id)
        api_seed = cls._seed_api(space_id)
        seeds = builtin_seed + bk_plugin_seed + api_seed

        preview = {
            "total": len(seeds),
            "visible": sum(1 for item in seeds if item["status"] == PluginCatalogStatus.VISIBLE),
            # preview 的 key 与 status 枚举值保持一致（disabled = 本次生成的「已停用」条目数）
            "disabled": sum(1 for item in seeds if item["status"] == PluginCatalogStatus.DISABLED),
            "by_type": {
                PluginType.BUILTIN: len(builtin_seed),
                PluginType.BK_PLUGIN: len(bk_plugin_seed),
                PluginType.API: len(api_seed),
            },
        }
        if dry_run:
            return {"ready": False, "dry_run": True, "preview": preview}

        legacy_snapshot = cls._build_legacy_snapshot(space_id)
        now = timezone.now()
        with transaction.atomic():
            cls._bulk_create_entries(space_id, seeds)
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
        return {"ready": True, "already_migrated": False, "preview": preview}

    # ------------------------------------------------------------------ 种子数据 ----

    @classmethod
    def _seed_builtin(cls, space_id):
        plugin_config = SpaceConfig.get_config(space_id=space_id, config_name=SpacePluginConfig.name)
        parser = SpacePluginConfigParser(config=plugin_config) if plugin_config else None
        codes = list(
            ComponentModel.objects.filter(status=True).exclude(code__in=WRAPPER_CODES).values_list("code", flat=True)
        )
        if parser:
            visible_codes = parser.get_filtered_plugins("default", codes)
        else:
            visible_codes = set(codes)
        return [
            {
                "plugin_type": PluginType.BUILTIN,
                "source_key": "",
                "plugin_code": code,
                "status": PluginCatalogStatus.VISIBLE if code in visible_codes else PluginCatalogStatus.DISABLED,
            }
            for code in codes
        ]

    @classmethod
    def _seed_bk_plugin(cls, space_id):
        authorized_codes = set(BKPluginAuthorization.objects.get_codes_by_space_id(space_id))
        codes = list(BKPlugin.objects.for_space(space_id).values_list("code", flat=True))
        return [
            {
                "plugin_type": PluginType.BK_PLUGIN,
                "source_key": "",
                "plugin_code": code,
                "status": PluginCatalogStatus.VISIBLE if code in authorized_codes else PluginCatalogStatus.DISABLED,
            }
            for code in codes
        ]

    @classmethod
    def _seed_api(cls, space_id):
        """
        仅覆盖已被 V4 展示缓存（OpenPluginCatalogIndex）收录、且已有 `SpaceOpenPluginAvailability`
        启用记录的插件；未缓存的 V2/V3 协议插件留给迁移后的首轮 `sync_space_plugin_catalog_task`
        正常发现流程处理（按新插件策略判定初始状态），不在迁移这一步强行现场请求远端。
        """
        enabled_map = {
            (item.source_key, item.plugin_id): item.enabled
            for item in SpaceOpenPluginAvailability.objects.filter(space_id=space_id).only(
                "source_key", "plugin_id", "enabled"
            )
        }
        return [
            {
                "plugin_type": PluginType.API,
                "source_key": source_key,
                "plugin_code": plugin_id,
                "status": PluginCatalogStatus.VISIBLE if enabled else PluginCatalogStatus.DISABLED,
            }
            for (source_key, plugin_id), enabled in enabled_map.items()
        ]

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
                status=item["status"],
                directory=None,
                ever_enabled=item["status"] == PluginCatalogStatus.VISIBLE,
                source_valid=True,
                last_synced_at=timezone.now(),
                updated_by="system",
            )
            for item in seeds
            if (item["plugin_type"], item["source_key"], item["plugin_code"]) not in existing_keys
        ]
        if to_create:
            SpacePluginCatalogEntry.objects.bulk_create(to_create)

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
