from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from bkflow.exceptions import APIResponseError, ValidationError
from bkflow.plugin.models import OpenPluginCatalogIndex, SpaceOpenPluginAvailability
from bkflow.plugin.services.open_plugin_catalog import OpenPluginCatalogService
from bkflow.plugin.services.open_plugin_grant import OpenPluginGrantService


@pytest.mark.django_db
class TestOpenPluginCatalogService:
    @override_settings(OPEN_PLUGIN_CATALOG_SYNC_REQUEST_TIMEOUT=120)
    @patch.object(OpenPluginCatalogService, "_get_apigw_credential")
    @patch("bkflow.plugin.services.open_plugin_catalog.UniformAPIClient")
    def test_fetch_api_list_uses_catalog_sync_timeout(self, mock_client_cls, mock_get_credential):
        """测试目录同步使用独立超时，不影响普通 API 插件请求超时"""
        credential = MagicMock()
        credential.content = {"bk_app_code": "app", "bk_app_secret": "secret"}
        mock_get_credential.return_value = credential

        list_resp = MagicMock(result=True, json_resp={"data": {"total": 0, "apis": []}})
        mock_client = mock_client_cls.return_value
        mock_client.request.return_value = list_resp

        assert (
            OpenPluginCatalogService._fetch_api_list(
                space_id=1,
                api_entry=MagicMock(meta_apis="http://example.com/meta_apis"),
                username="admin",
            )
            == []
        )
        mock_client.request.assert_called_once_with(
            url="http://example.com/meta_apis",
            method="GET",
            data={"limit": 200, "offset": 0},
            headers=mock_client.gen_default_apigw_header.return_value,
            username="admin",
            timeout=120,
        )

    @patch.object(OpenPluginCatalogService, "_get_apigw_credential")
    @patch("bkflow.plugin.services.open_plugin_catalog.UniformAPIClient")
    def test_fetch_api_list_preserves_source_error(self, mock_client_cls, mock_get_credential):
        """测试来源请求失败时保留真实错误，不再抛出 NoneType 异常"""
        credential = MagicMock()
        credential.content = {"bk_app_code": "app", "bk_app_secret": "secret"}
        mock_get_credential.return_value = credential

        mock_client_cls.return_value.request.return_value = MagicMock(
            result=False,
            message="gateway timeout",
            json_resp=None,
        )

        with pytest.raises(APIResponseError, match="gateway timeout"):
            OpenPluginCatalogService._fetch_api_list(
                space_id=1,
                api_entry=MagicMock(meta_apis="http://example.com/meta_apis"),
                username="admin",
            )

    @patch.object(OpenPluginCatalogService, "_get_apigw_credential", return_value=None)
    def test_fetch_api_list_rejects_missing_credential(self, _mock_get_credential):
        """测试缺少凭证时同步失败，避免把现有目录误判为空目录"""
        with pytest.raises(ValidationError, match="API Gateway 凭证"):
            OpenPluginCatalogService._fetch_api_list(
                space_id=1,
                api_entry=MagicMock(meta_apis="http://example.com/meta_apis"),
                username="admin",
            )

    @patch.object(OpenPluginCatalogService, "_get_apigw_credential")
    @patch("bkflow.plugin.services.open_plugin_catalog.UniformAPIClient")
    def test_fetch_api_list_rejects_invalid_response_body(self, mock_client_cls, mock_get_credential):
        """测试成功响应体不符合协议时返回明确协议错误"""
        credential = MagicMock()
        credential.content = {"bk_app_code": "app", "bk_app_secret": "secret"}
        mock_get_credential.return_value = credential
        mock_client_cls.return_value.request.return_value = MagicMock(result=True, json_resp=None)

        with pytest.raises(APIResponseError, match="响应体"):
            OpenPluginCatalogService._fetch_api_list(
                space_id=1,
                api_entry=MagicMock(meta_apis="http://example.com/meta_apis"),
                username="admin",
            )

    @patch.object(OpenPluginCatalogService, "_refresh_catalog_index")
    @patch.object(OpenPluginCatalogService, "_fetch_api_list")
    @patch.object(OpenPluginCatalogService, "_get_sources")
    def test_sync_space_plugins_aggregates_api_entries_with_same_source_key(
        self, mock_get_sources, mock_fetch_api_list, mock_refresh_catalog_index
    ):
        """测试两个展示配置映射到同一来源时，只聚合刷新一次目录。"""
        builtin_entry = MagicMock(source_key="sops")
        third_party_entry = MagicMock(source_key="sops")
        builtin_plugin = {"id": "builtin__job_execute_task"}
        third_party_plugin = {"id": "danny-test-plugin"}
        mock_get_sources.return_value = {
            "sops_builtin": builtin_entry,
            "sops_third_party": third_party_entry,
        }
        mock_fetch_api_list.side_effect = [[builtin_plugin], [third_party_plugin]]

        synced_sources = OpenPluginCatalogService.sync_space_plugins(space_id=1)

        assert synced_sources == ["sops"]
        mock_refresh_catalog_index.assert_called_once_with(
            space_id=1,
            source_key="sops",
            api_list=[builtin_plugin, third_party_plugin],
        )

    @patch("bkflow.plugin.services.open_plugin_catalog.SpaceConfig")
    @patch("bkflow.plugin.services.open_plugin_catalog.UniformAPIConfigHandler")
    def test_get_sources_filters_by_effective_source_key(self, mock_handler, mock_sc):
        """测试同步指定来源时可选中映射到该来源的全部展示配置。"""
        mock_sc.get_config.return_value = {"api": {}}
        builtin_entry = MagicMock(source_key="sops")
        third_party_entry = MagicMock(source_key="sops")
        mock_model = MagicMock()
        mock_model.api = {
            "sops_builtin": builtin_entry,
            "sops_third_party": third_party_entry,
        }
        mock_handler.return_value.handle.return_value = mock_model

        sources = OpenPluginCatalogService._get_sources(space_id=1, source_key="sops")

        assert sources == {
            "sops_builtin": builtin_entry,
            "sops_third_party": third_party_entry,
        }

    @patch("bkflow.plugin.services.open_plugin_catalog.SpaceConfig")
    @patch("bkflow.plugin.services.open_plugin_catalog.UniformAPIConfigHandler")
    def test_iter_configured_sources_deduplicates_effective_source_key(self, mock_handler, mock_sc):
        """测试平台准入初始化按执行来源去重，而不是按展示配置授权。"""
        space_config = MagicMock(space_id=1, json_value={"api": {}})
        mock_sc.objects.filter.return_value.only.return_value.iterator.return_value = [space_config]
        mock_model = MagicMock()
        mock_model.api = {
            "sops_builtin": MagicMock(source_key="sops"),
            "sops_third_party": MagicMock(source_key="sops"),
        }
        mock_handler.return_value.handle.return_value = mock_model

        configured_sources = list(OpenPluginCatalogService.iter_configured_sources())

        assert configured_sources == [(1, "sops")]

    @patch("bkflow.plugin.services.open_plugin_catalog.SpaceConfig")
    @patch("bkflow.plugin.services.open_plugin_catalog.UniformAPIConfigHandler")
    def test_iter_configured_sources_skips_invalid_historical_config(self, mock_handler, mock_sc):
        """单个空间的历史脏配置不能阻断后续空间的准入回填。"""
        invalid_config = MagicMock(space_id=1, json_value={"api": "invalid"})
        valid_config = MagicMock(space_id=2, json_value={"api": {}})
        mock_sc.objects.filter.return_value.only.return_value.iterator.return_value = [invalid_config, valid_config]
        valid_model = MagicMock()
        valid_model.api = {"sops_builtin": MagicMock(source_key="sops")}
        mock_handler.return_value.handle.side_effect = [ValueError("invalid historical config"), valid_model]

        configured_sources = list(OpenPluginCatalogService.iter_configured_sources())

        assert configured_sources == [(2, "sops")]

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

    def test_catalog_initialized_is_scoped_by_plugin_source(self):
        OpenPluginCatalogIndex.objects.create(
            space_id=999,
            source_key="sops",
            plugin_id="builtin__job_execute_task",
            plugin_code="job_execute_task",
            plugin_name="JOB 执行作业",
            plugin_source="builtin",
        )

        assert OpenPluginCatalogService.is_catalog_initialized(
            space_id=999,
            source_key="sops",
            plugin_source="builtin",
        )
        assert not OpenPluginCatalogService.is_catalog_initialized(
            space_id=999,
            source_key="sops",
            plugin_source="third_party",
        )
        assert OpenPluginCatalogService.is_catalog_initialized(space_id=999, source_key="sops")

    def test_list_space_plugins_contains_uniform_api_catalog_fields(self):
        OpenPluginGrantService.grant(space_id=999, source_key="sops", operator="admin")
        OpenPluginCatalogIndex.objects.create(
            space_id=999,
            source_key="sops",
            plugin_id="builtin__job_execute_task",
            plugin_code="job_execute_task",
            plugin_name="JOB 执行作业",
            plugin_source="builtin",
            meta_url_template="https://bk-sops.example/plugins/builtin__job_execute_task/?version={version}",
            description="执行 JOB 作业",
        )

        plugin = OpenPluginCatalogService.list_space_plugins(space_id=999, source_key="sops")[0]

        assert plugin["meta_url_template"].endswith("?version={version}")
        assert plugin["description"] == "执行 JOB 作业"

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
                        "category": "JOB",
                        "category_name": "作业平台",
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
        assert index.group_name == "JOB"
        assert index.group_display_name == "作业平台"
        assert index.status == OpenPluginCatalogIndex.Status.AVAILABLE
        assert availability.enabled is False

    @patch("bkflow.plugin.services.open_plugin_catalog.Credential")
    @patch("bkflow.plugin.services.open_plugin_catalog.UniformAPIClient")
    @patch("bkflow.plugin.services.open_plugin_catalog.SpaceConfig")
    @patch("bkflow.plugin.services.open_plugin_catalog.UniformAPIConfigHandler")
    def test_sync_space_plugins_skips_non_v4_items(self, mock_handler, mock_sc, mock_client_cls, mock_cred):
        """目录同步只落 V4 开放插件，避免存量 V2/V3 污染本地索引。"""
        mock_sc.get_config.side_effect = lambda space_id, config_name, scope=None: {
            "uniform_api": {"api": {"sops": {"meta_apis": "http://example.com/meta_apis"}}},
            "api_gateway_credential_name": "test_cred",
        }.get(config_name)
        mock_handler.return_value.handle.return_value = MagicMock(
            api={"sops": MagicMock(meta_apis="http://example.com/meta_apis")}
        )
        mock_cred.objects.filter.return_value.first.return_value = MagicMock(
            content={"bk_app_code": "app", "bk_app_secret": "secret"}
        )
        mock_client = MagicMock()
        mock_client.request.return_value = MagicMock(
            result=True,
            json_resp={
                "data": {
                    "apis": [
                        {
                            "id": "sops_execute",
                            "name": "标准运维执行",
                            "meta_url": "http://example.com/meta/sops",
                        },
                        {
                            "id": "open_plugin_001",
                            "name": "JOB 执行作业",
                            "plugin_source": "builtin",
                            "plugin_code": "job_execute_task",
                            "wrapper_version": "v4.0.0",
                            "default_version": "1.2.0",
                            "latest_version": "1.3.0",
                            "versions": ["1.2.0", "1.3.0"],
                            "meta_url_template": (
                                "https://bk-sops.example/open-plugins/open_plugin_001?version={version}"
                            ),
                        },
                    ]
                }
            },
        )
        mock_client_cls.return_value = mock_client

        OpenPluginCatalogService.sync_space_plugins(space_id=1)

        assert list(OpenPluginCatalogIndex.objects.filter(space_id=1).values_list("plugin_id", flat=True)) == [
            "open_plugin_001"
        ]

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

        with pytest.raises(APIResponseError, match="请求开放插件目录失败.*gateway unavailable"):
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

        with pytest.raises(APIResponseError, match="请求开放插件目录失败.*响应体不是 JSON 对象"):
            OpenPluginCatalogService._fetch_api_list(
                space_id=1,
                api_entry=MagicMock(meta_apis="http://example.com/meta_apis"),
                username="admin",
            )
