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

from unittest.mock import patch

import pytest

from bkflow.plugin_catalog.models import (
    PluginCatalogStatus,
    PluginType,
    SpacePluginCatalogEntry,
)
from bkflow.plugin_catalog.services.sync_service import PluginCatalogSyncService


@pytest.mark.django_db
class TestSyncApi:
    """覆盖本次修复的两个行为：V2/V3 不再被过滤、来源配置整体删除后能级联失效。"""

    @patch("bkflow.plugin_catalog.services.sync_service.OpenPluginCatalogService")
    def test_sync_api_covers_all_protocol_versions_without_filtering(self, mock_service):
        """V2/V3（无 wrapper_version）与 V4 插件应被一视同仁地写入 SpacePluginCatalogEntry。"""
        mock_service.sync_space_plugins.return_value = ["sops"]
        mock_service.fetch_all_source_plugins.return_value = {"sops": ["v2_plugin", "v4_plugin"]}

        stat = PluginCatalogSyncService.sync_api(space_id=1)

        assert stat == {"created": 2, "invalidated": 0, "skipped": False}
        codes = set(
            SpacePluginCatalogEntry.objects.filter(space_id=1, plugin_type=PluginType.API).values_list(
                "plugin_code", flat=True
            )
        )
        assert codes == {"v2_plugin", "v4_plugin"}

    @patch("bkflow.plugin_catalog.services.sync_service.OpenPluginCatalogService")
    def test_sync_api_invalidates_entries_when_source_still_configured_but_plugin_disappears(self, mock_service):
        """同一来源仍配置着，但某个插件从返回清单里消失，应被标记失效。"""
        mock_service.sync_space_plugins.return_value = ["sops"]
        mock_service.fetch_all_source_plugins.return_value = {"sops": ["v4_plugin", "v2_plugin"]}
        PluginCatalogSyncService.sync_api(space_id=1)

        mock_service.fetch_all_source_plugins.return_value = {"sops": ["v4_plugin"]}
        stat = PluginCatalogSyncService.sync_api(space_id=1)

        assert stat["invalidated"] == 1
        entry = SpacePluginCatalogEntry.objects.get(space_id=1, plugin_type=PluginType.API, plugin_code="v2_plugin")
        assert entry.status == PluginCatalogStatus.INVALID

    @patch("bkflow.plugin_catalog.services.sync_service.OpenPluginCatalogService")
    def test_sync_api_cascades_invalid_when_source_config_removed(self, mock_service):
        """
        来源整体配置被删除（不再出现在 fetch_all_source_plugins 返回结果里）后，
        该来源下此前已经生成的目录条目应被级联标记失效，不能因为旧的缓存表数据而被忽略。
        """
        mock_service.sync_space_plugins.return_value = ["sops"]
        mock_service.fetch_all_source_plugins.return_value = {"sops": ["v4_plugin"]}
        PluginCatalogSyncService.sync_api(space_id=1)
        entry = SpacePluginCatalogEntry.objects.get(space_id=1, plugin_type=PluginType.API, plugin_code="v4_plugin")
        assert entry.status != PluginCatalogStatus.INVALID

        # 模拟来源配置被整体删除：fetch_all_source_plugins 不再返回这个来源
        mock_service.fetch_all_source_plugins.return_value = {}
        stat = PluginCatalogSyncService.sync_api(space_id=1)

        assert stat["invalidated"] == 1
        entry.refresh_from_db()
        assert entry.status == PluginCatalogStatus.INVALID
        assert entry.invalid_reason == "来源中已不存在该插件"

    @patch("bkflow.plugin_catalog.services.sync_service.OpenPluginCatalogService")
    def test_sync_api_revives_entry_when_plugin_reappears(self, mock_service):
        """失效后若插件又重新出现在来源清单里，应唤醒回失效前的状态。"""
        mock_service.sync_space_plugins.return_value = ["sops"]
        mock_service.fetch_all_source_plugins.return_value = {"sops": ["v4_plugin"]}
        PluginCatalogSyncService.sync_api(space_id=1)
        entry = SpacePluginCatalogEntry.objects.get(space_id=1, plugin_type=PluginType.API, plugin_code="v4_plugin")
        entry.status = PluginCatalogStatus.VISIBLE
        entry.save(update_fields=["status"])

        mock_service.fetch_all_source_plugins.return_value = {}
        PluginCatalogSyncService.sync_api(space_id=1)
        entry.refresh_from_db()
        assert entry.status == PluginCatalogStatus.INVALID

        mock_service.fetch_all_source_plugins.return_value = {"sops": ["v4_plugin"]}
        PluginCatalogSyncService.sync_api(space_id=1)
        entry.refresh_from_db()
        assert entry.status == PluginCatalogStatus.VISIBLE

    @patch("bkflow.plugin_catalog.services.sync_service.OpenPluginCatalogService")
    def test_sync_api_skips_when_fetch_fails(self, mock_service):
        """现场拉取失败时直接跳过本次目录条目生成/失效判定，不误判删除。"""
        mock_service.sync_space_plugins.return_value = []
        mock_service.fetch_all_source_plugins.side_effect = Exception("network error")

        stat = PluginCatalogSyncService.sync_api(space_id=1)

        assert stat == {"created": 0, "invalidated": 0, "skipped": True}
        assert not SpacePluginCatalogEntry.objects.filter(space_id=1).exists()
