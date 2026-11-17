"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (see LICENSE for details).
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from unittest.mock import patch

import pytest

from bkflow.plugin_catalog.models import (
    PluginCatalogStatus,
    PluginType,
    SourceSyncState,
    SpacePluginCatalogEntry,
)
from bkflow.plugin_catalog.services.sync_service import PluginCatalogSyncService


@pytest.mark.django_db
class TestSyncApi:
    """覆盖 API 插件同步的三个行为：V2/V3 不再被过滤、元信息直接取自现场响应、
    来源配置整体删除后能级联失效。"""

    @patch("bkflow.plugin_catalog.services.sync_service.OpenPluginCatalogService")
    def test_sync_api_covers_all_protocol_versions_without_filtering(self, mock_service):
        """V2/V3（无 wrapper_version）与 V4 插件应被一视同仁地写入 SpacePluginCatalogEntry。"""
        mock_service.sync_space_plugins_with_meta.return_value = {"sources": {"sops": {"v2_plugin": ("V2 插件", "V2 描述"), "v4_plugin": ("V4 插件", "V4 描述")}}, "failures": {}, "generations": {}}

        stat = PluginCatalogSyncService.sync_api(space_id=1)

        assert stat == {"created": 2, "invalidated": 0, "skipped": False}
        codes = set(
            SpacePluginCatalogEntry.objects.filter(space_id=1, plugin_type=PluginType.API).values_list(
                "plugin_code", flat=True
            )
        )
        assert codes == {"v2_plugin", "v4_plugin"}

    @patch("bkflow.plugin_catalog.services.sync_service.OpenPluginCatalogService")
    def test_sync_api_writes_metadata_for_v2_and_v3_plugins(self, mock_service):
        """元信息直接来自现场响应，V2/V3 协议插件的名称与描述不应为空。

        现场响应的 schema 里 `name` 是所有协议版本都有的必填字段；此前实现回查只收录
        V4 的展示缓存表，导致 V2/V3 插件的名称与描述永远写不进目录条目表。
        """
        mock_service.sync_space_plugins_with_meta.return_value = {"sources": {"sops": {"v2_plugin": ("V2 插件", "V2 描述"), "v4_plugin": ("V4 插件", "V4 描述")}}, "failures": {}, "generations": {}}

        PluginCatalogSyncService.sync_api(space_id=1)

        entries = {
            entry.plugin_code: (entry.plugin_name, entry.plugin_desc)
            for entry in SpacePluginCatalogEntry.objects.filter(space_id=1, plugin_type=PluginType.API)
        }
        assert entries["v2_plugin"] == ("V2 插件", "V2 描述")
        assert entries["v4_plugin"] == ("V4 插件", "V4 描述")

    @patch("bkflow.plugin_catalog.services.sync_service.OpenPluginCatalogService")
    def test_sync_api_refreshes_metadata_when_source_renames_plugin(self, mock_service):
        """来源侧改了插件名/描述后，下一次同步应把新值刷新到已有条目上。"""
        mock_service.sync_space_plugins_with_meta.return_value = {"sources": {"sops": {"v4_plugin": ("旧名称", "旧描述")}}, "failures": {}, "generations": {}}
        PluginCatalogSyncService.sync_api(space_id=1)

        mock_service.sync_space_plugins_with_meta.return_value = {"sources": {"sops": {"v4_plugin": ("新名称", "新描述")}}, "failures": {}, "generations": {}}
        PluginCatalogSyncService.sync_api(space_id=1)

        entry = SpacePluginCatalogEntry.objects.get(
            space_id=1, plugin_type=PluginType.API, plugin_code="v4_plugin"
        )
        assert (entry.plugin_name, entry.plugin_desc) == ("新名称", "新描述")

    @patch("bkflow.plugin_catalog.services.sync_service.OpenPluginCatalogService")
    def test_sync_api_invalidates_entries_when_source_still_configured_but_plugin_disappears(self, mock_service):
        """同一来源仍配置着，但某个插件从返回清单里消失，应被标记失效。"""
        mock_service.sync_space_plugins_with_meta.return_value = {"sources": {"sops": {"v4_plugin": ("V4 插件", ""), "v2_plugin": ("V2 插件", "")}}, "failures": {}, "generations": {}}
        PluginCatalogSyncService.sync_api(space_id=1)

        mock_service.sync_space_plugins_with_meta.return_value = {"sources": {"sops": {"v4_plugin": ("V4 插件", "")}}, "failures": {}, "generations": {}}
        stat = PluginCatalogSyncService.sync_api(space_id=1)

        assert stat["invalidated"] == 1
        entry = SpacePluginCatalogEntry.objects.get(space_id=1, plugin_type=PluginType.API, plugin_code="v2_plugin")
        assert entry.status == PluginCatalogStatus.EXPIRED

    @patch("bkflow.plugin_catalog.services.sync_service.OpenPluginCatalogService")
    def test_sync_api_cascades_invalid_when_source_config_removed(self, mock_service):
        """
        来源整体配置被删除（不再出现在同步结果里）后，该来源下此前已经生成的目录条目应被
        级联标记失效，不能因为旧的缓存表数据而被忽略。
        """
        mock_service.sync_space_plugins_with_meta.return_value = {"sources": {"sops": {"v4_plugin": ("V4 插件", "")}}, "failures": {}, "generations": {}}
        PluginCatalogSyncService.sync_api(space_id=1)
        entry = SpacePluginCatalogEntry.objects.get(space_id=1, plugin_type=PluginType.API, plugin_code="v4_plugin")
        assert entry.status != PluginCatalogStatus.EXPIRED

        # 模拟来源配置被整体删除：同步结果里不再有这个来源
        mock_service.sync_space_plugins_with_meta.return_value = {"sources": {}, "failures": {}, "generations": {}}
        stat = PluginCatalogSyncService.sync_api(space_id=1)

        assert stat["invalidated"] == 1
        entry.refresh_from_db()
        assert entry.status == PluginCatalogStatus.EXPIRED

    @patch("bkflow.plugin_catalog.services.sync_service.OpenPluginCatalogService")
    def test_sync_api_revives_entry_when_plugin_reappears(self, mock_service):
        """失效后若插件又重新出现在来源清单里，应唤醒回失效前的状态。"""
        mock_service.sync_space_plugins_with_meta.return_value = {"sources": {"sops": {"v4_plugin": ("V4 插件", "")}}, "failures": {}, "generations": {}}
        PluginCatalogSyncService.sync_api(space_id=1)
        entry = SpacePluginCatalogEntry.objects.get(space_id=1, plugin_type=PluginType.API, plugin_code="v4_plugin")
        entry.status = PluginCatalogStatus.ENABLE
        entry.save(update_fields=["status"])

        mock_service.sync_space_plugins_with_meta.return_value = {"sources": {}, "failures": {}, "generations": {}}
        PluginCatalogSyncService.sync_api(space_id=1)
        entry.refresh_from_db()
        assert entry.status == PluginCatalogStatus.EXPIRED

        mock_service.sync_space_plugins_with_meta.return_value = {"sources": {"sops": {"v4_plugin": ("V4 插件", "")}}, "failures": {}, "generations": {}}
        PluginCatalogSyncService.sync_api(space_id=1)
        entry.refresh_from_db()
        assert entry.status == PluginCatalogStatus.ENABLE

    @patch("bkflow.plugin_catalog.services.sync_service.OpenPluginCatalogService")
    def test_sync_api_skips_when_fetch_fails(self, mock_service):
        """现场拉取失败时直接跳过本次目录条目生成/失效判定，不误判删除。"""
        mock_service.sync_space_plugins_with_meta.side_effect = Exception("network error")

        stat = PluginCatalogSyncService.sync_api(space_id=1)

        assert stat == {"created": 0, "invalidated": 0, "skipped": True}
        assert not SpacePluginCatalogEntry.objects.filter(space_id=1).exists()

    @patch("bkflow.plugin_catalog.services.sync_service.OpenPluginCatalogService")
    def test_sync_api_discards_stale_result_by_generation(self, mock_service):
        """采集期间配置变了 -> 旧结果过期，直接丢弃：既不提交也不判定失效。"""
        mock_service.sync_space_plugins_with_meta.return_value = {
            "sources": {"sops": {"v4_plugin": ("V4 插件", "")}},
            "failures": {},
            "generations": {"sops": 1},
        }
        # 让表里的采集代次比本次采集新（模拟期间又发起了新的采集）
        SourceSyncState.objects.create(space_id=1, source_key="sops", collect_generation=2)

        stat = PluginCatalogSyncService.sync_api(space_id=1)

        assert stat["created"] == 0
        assert stat["invalidated"] == 0
        assert not SpacePluginCatalogEntry.objects.filter(space_id=1).exists()

    @patch("bkflow.plugin_catalog.services.sync_service.OpenPluginCatalogService")
    def test_sync_api_invalidates_source_on_auth_failure(self, mock_service):
        """鉴权失败（该来源整体挂了）-> 按覆盖范围失效，把该来源下的插件全部标记失效。"""
        SpacePluginCatalogEntry.objects.create(
            space_id=1,
            plugin_type=PluginType.API,
            source_key="sops",
            plugin_code="v4_plugin",
            plugin_name="V4 插件",
            status=PluginCatalogStatus.ENABLE,
            ever_enabled=True,
            updated_by="tester",
        )
        mock_service.sync_space_plugins_with_meta.return_value = {
            "sources": {},
            "failures": {"sops": ("auth", "status_code: 401")},
            "generations": {},
        }

        stat = PluginCatalogSyncService.sync_api(space_id=1)

        assert stat["invalidated"] == 1
        entry = SpacePluginCatalogEntry.objects.get(space_id=1, plugin_code="v4_plugin")
        assert entry.status == PluginCatalogStatus.EXPIRED

    @patch("bkflow.plugin_catalog.services.sync_service.OpenPluginCatalogService")
    def test_sync_api_keeps_entries_on_timeout_failure(self, mock_service):
        """超时（覆盖范围不明）-> 不判定失效，保留现状。"""
        entry = SpacePluginCatalogEntry.objects.create(
            space_id=1,
            plugin_type=PluginType.API,
            source_key="sops",
            plugin_code="v4_plugin",
            plugin_name="V4 插件",
            status=PluginCatalogStatus.ENABLE,
            ever_enabled=True,
            updated_by="tester",
        )
        mock_service.sync_space_plugins_with_meta.return_value = {
            "sources": {},
            "failures": {"sops": ("timeout", "Read timed out")},
            "generations": {},
        }

        stat = PluginCatalogSyncService.sync_api(space_id=1)

        assert stat["invalidated"] == 0
        entry.refresh_from_db()
        assert entry.status == PluginCatalogStatus.ENABLE
