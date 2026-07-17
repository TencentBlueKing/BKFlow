from unittest.mock import MagicMock, patch

import pytest

from bkflow.plugin.models import OpenPluginCatalogIndex, SpaceOpenPluginAvailability
from bkflow.plugin.services.open_plugin_catalog import OpenPluginCatalogService
from bkflow.plugin.services.open_plugin_grant import OpenPluginGrantService


@pytest.mark.django_db
class TestOpenPluginCatalogService:
    def test_ungranted_space_sees_no_source(self):
        """测试未准入空间看不到对应来源目录"""
        OpenPluginCatalogIndex.objects.create(
            space_id=999,
            source_key="sops",
            plugin_id="open_plugin_001",
            plugin_code="job_execute_task",
            plugin_name="JOB 执行作业",
            plugin_source="builtin",
            group_name="作业平台",
            default_version="1.2.0",
            latest_version="1.3.0",
            versions=["1.2.0", "1.3.0"],
            meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
            status=OpenPluginCatalogIndex.Status.AVAILABLE,
        )

        assert OpenPluginCatalogService.list_space_plugins(space_id=999, source_key="sops") == []

    def test_enable_all_blocked_without_grant(self):
        """测试未准入空间不能一键启用来源下插件"""
        OpenPluginCatalogIndex.objects.create(
            space_id=999,
            source_key="sops",
            plugin_id="open_plugin_001",
            plugin_code="job_execute_task",
            plugin_name="JOB 执行作业",
            plugin_source="builtin",
            group_name="作业平台",
            default_version="1.2.0",
            latest_version="1.3.0",
            versions=["1.2.0", "1.3.0"],
            meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
            status=OpenPluginCatalogIndex.Status.AVAILABLE,
        )

        with pytest.raises(ValueError, match="来源未准入"):
            OpenPluginCatalogService.enable_all_visible_plugins(space_id=999, source_key="sops")

    def test_granted_space_can_enable_all_visible_plugins(self):
        """测试已准入空间可一键启用来源下可见插件"""
        OpenPluginGrantService.grant(space_id=999, source_key="sops", operator="admin")
        OpenPluginCatalogIndex.objects.create(
            space_id=999,
            source_key="sops",
            plugin_id="open_plugin_001",
            plugin_code="job_execute_task",
            plugin_name="JOB 执行作业",
            plugin_source="builtin",
            group_name="作业平台",
            default_version="1.2.0",
            latest_version="1.3.0",
            versions=["1.2.0", "1.3.0"],
            meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
            status=OpenPluginCatalogIndex.Status.AVAILABLE,
        )

        updated = OpenPluginCatalogService.enable_all_visible_plugins(space_id=999, source_key="sops")

        assert len(updated) == 1
        assert SpaceOpenPluginAvailability.objects.get(
            space_id=999, source_key="sops", plugin_id="open_plugin_001"
        ).enabled

    @patch("bkflow.plugin.services.open_plugin_catalog.Credential")
    @patch("bkflow.plugin.services.open_plugin_catalog.UniformAPIClient")
    @patch("bkflow.plugin.services.open_plugin_catalog.SpaceConfig")
    @patch("bkflow.plugin.services.open_plugin_catalog.UniformAPIConfigHandler")
    def test_sync_space_plugins_creates_index_and_default_disabled_availability(
        self, mock_handler, mock_sc, mock_client_cls, mock_cred
    ):
        """测试同步目录后写入索引，并默认关闭空间开放状态"""
        mock_sc.get_config.side_effect = lambda space_id, config_name, scope=None: {
            "uniform_api": {"api": {"sops": {"meta_apis": "http://example.com/meta_apis"}}},
            "api_gateway_credential_name": "test_cred",
        }.get(config_name)

        mock_model = MagicMock()
        mock_model.api = {"sops": MagicMock(meta_apis="http://example.com/meta_apis")}
        mock_handler.return_value.handle.return_value = mock_model

        mock_cred_obj = MagicMock()
        mock_cred_obj.content = {"bk_app_code": "app", "bk_app_secret": "secret"}
        mock_cred.objects.filter.return_value.first.return_value = mock_cred_obj

        mock_client = MagicMock()
        list_resp = MagicMock()
        list_resp.result = True
        list_resp.json_resp = {
            "data": {
                "apis": [
                    {
                        "id": "open_plugin_001",
                        "name": "JOB 执行作业",
                        "plugin_source": "builtin",
                        "plugin_code": "job_execute_task",
                        "wrapper_version": "v4.0.0",
                        "default_version": "1.2.0",
                        "latest_version": "1.3.0",
                        "versions": ["1.2.0", "1.3.0"],
                        "meta_url_template": "https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
                        "category": "作业平台",
                    }
                ]
            }
        }
        mock_client.request.return_value = list_resp
        mock_client_cls.return_value = mock_client

        OpenPluginCatalogService.sync_space_plugins(space_id=1)

        index = OpenPluginCatalogIndex.objects.get(space_id=1, source_key="sops", plugin_id="open_plugin_001")
        availability = SpaceOpenPluginAvailability.objects.get(
            space_id=1, source_key="sops", plugin_id="open_plugin_001"
        )

        assert index.plugin_code == "job_execute_task"
        assert index.status == OpenPluginCatalogIndex.Status.AVAILABLE
        assert availability.enabled is False

    @patch("bkflow.plugin.services.open_plugin_catalog.Credential")
    @patch("bkflow.plugin.services.open_plugin_catalog.UniformAPIClient")
    @patch("bkflow.plugin.services.open_plugin_catalog.SpaceConfig")
    @patch("bkflow.plugin.services.open_plugin_catalog.UniformAPIConfigHandler")
    def test_sync_space_plugins_marks_missing_plugin_as_unavailable(
        self, mock_handler, mock_sc, mock_client_cls, mock_cred
    ):
        """测试远端插件下线后，本地索引标记 unavailable 且保留历史开放记录"""
        OpenPluginCatalogIndex.objects.create(
            space_id=1,
            source_key="sops",
            plugin_id="open_plugin_001",
            plugin_code="job_execute_task",
            plugin_name="JOB 执行作业",
            plugin_source="builtin",
            group_name="作业平台",
            default_version="1.2.0",
            latest_version="1.3.0",
            versions=["1.2.0", "1.3.0"],
            meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
            status=OpenPluginCatalogIndex.Status.AVAILABLE,
        )
        SpaceOpenPluginAvailability.objects.create(
            space_id=1,
            source_key="sops",
            plugin_id="open_plugin_001",
            enabled=True,
        )

        mock_sc.get_config.side_effect = lambda space_id, config_name, scope=None: {
            "uniform_api": {"api": {"sops": {"meta_apis": "http://example.com/meta_apis"}}},
            "api_gateway_credential_name": "test_cred",
        }.get(config_name)

        mock_model = MagicMock()
        mock_model.api = {"sops": MagicMock(meta_apis="http://example.com/meta_apis")}
        mock_handler.return_value.handle.return_value = mock_model

        mock_cred_obj = MagicMock()
        mock_cred_obj.content = {"bk_app_code": "app", "bk_app_secret": "secret"}
        mock_cred.objects.filter.return_value.first.return_value = mock_cred_obj

        mock_client = MagicMock()
        list_resp = MagicMock()
        list_resp.result = True
        list_resp.json_resp = {"data": {"apis": []}}
        mock_client.request.return_value = list_resp
        mock_client_cls.return_value = mock_client

        OpenPluginCatalogService.sync_space_plugins(space_id=1)

        index = OpenPluginCatalogIndex.objects.get(space_id=1, source_key="sops", plugin_id="open_plugin_001")
        availability = SpaceOpenPluginAvailability.objects.get(
            space_id=1, source_key="sops", plugin_id="open_plugin_001"
        )

        assert index.status == OpenPluginCatalogIndex.Status.UNAVAILABLE
        assert availability.enabled is True

    @patch("bkflow.plugin.services.open_plugin_catalog.Credential")
    @patch("bkflow.plugin.services.open_plugin_catalog.UniformAPIClient")
    @patch("bkflow.plugin.services.open_plugin_catalog.SpaceConfig")
    def test_fetch_api_list_raises_clear_error_when_remote_request_fails(self, mock_sc, mock_client_cls, mock_cred):
        """测试目录来源请求失败时抛出可定位的错误，而不是继续解析空响应。"""
        mock_sc.get_config.return_value = "test_cred"
        mock_cred_obj = MagicMock()
        mock_cred_obj.content = {"bk_app_code": "app", "bk_app_secret": "secret"}
        mock_cred.objects.filter.return_value.first.return_value = mock_cred_obj

        list_resp = MagicMock(result=False, message="gateway unavailable", json_resp=None)
        mock_client_cls.return_value.request.return_value = list_resp

        with pytest.raises(ValueError, match="开放插件目录请求失败.*gateway unavailable"):
            OpenPluginCatalogService._fetch_api_list(
                space_id=1,
                api_entry=MagicMock(meta_apis="http://example.com/meta_apis"),
                username="admin",
            )

    @patch("bkflow.plugin.services.open_plugin_catalog.Credential")
    @patch("bkflow.plugin.services.open_plugin_catalog.UniformAPIClient")
    @patch("bkflow.plugin.services.open_plugin_catalog.SpaceConfig")
    def test_fetch_api_list_raises_clear_error_for_malformed_response(self, mock_sc, mock_client_cls, mock_cred):
        """测试目录来源成功但响应体为空时抛出明确错误。"""
        mock_sc.get_config.return_value = "test_cred"
        mock_cred_obj = MagicMock()
        mock_cred_obj.content = {"bk_app_code": "app", "bk_app_secret": "secret"}
        mock_cred.objects.filter.return_value.first.return_value = mock_cred_obj

        list_resp = MagicMock(result=True, message="", json_resp=None)
        mock_client_cls.return_value.request.return_value = list_resp

        with pytest.raises(ValueError, match="开放插件目录响应不是合法 JSON"):
            OpenPluginCatalogService._fetch_api_list(
                space_id=1,
                api_entry=MagicMock(meta_apis="http://example.com/meta_apis"),
                username="admin",
            )
