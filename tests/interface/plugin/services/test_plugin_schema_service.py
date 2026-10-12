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

from unittest.mock import MagicMock, patch

import pytest

from bkflow.pipeline_plugins.query.uniform_api.utils import (
    UniformAPIClient as RealUniformAPIClient,
)
from bkflow.plugin.models import OpenPluginCatalogIndex, SpaceOpenPluginAvailability
from bkflow.plugin.services.plugin_schema_service import (
    PluginSchemaAccessDenied,
    PluginSchemaInfrastructureError,
    PluginSchemaService,
)
from bkflow.utils.api_client import HttpRequestResult


def uniform_meta_result(data, result=True, response_result=True, message=""):
    """构造通过统一 API meta schema 校验的 HttpRequestResult。"""
    meta = {
        "url": "https://bk-sops.example/run/",
        "methods": ["POST"],
    }
    meta.update(data)
    return HttpRequestResult(
        result=result,
        message=message,
        json_resp={"result": response_result, "message": message, "data": meta},
    )


class TestListComponentPlugins:
    """测试内置插件列表查询"""

    @patch.object(PluginSchemaService, "_list_remote_uniform_api_plugins")
    @pytest.mark.django_db
    def test_strict_catalog_propagates_legacy_provider_outage(self, remote_catalog):
        """A hard authorization replay cannot turn a provider outage into an empty legacy catalog."""
        remote_catalog.side_effect = PluginSchemaInfrastructureError("sentinel-outage")

        with pytest.raises(PluginSchemaInfrastructureError, match="sentinel-outage"):
            PluginSchemaService(space_id=1).list_plugins(plugin_type="uniform_api", strict=True)

    @patch("bkflow.plugin.services.plugin_schema_service.SpacePluginConfigModel")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_list_component_plugins_basic(self, mock_cm, mock_sc, mock_spcm):
        """测试基本的内置插件列表查询"""
        mock_spcm.objects.get_space_allow_list.return_value = []
        mock_sc.get_config.return_value = None

        mock_obj1 = MagicMock()
        mock_obj1.code = "job_fast_execute_script"
        mock_obj1.name = "作业平台(JOB)-快速执行脚本"
        mock_obj1.version = "v1.0.0"

        mock_obj2 = MagicMock()
        mock_obj2.code = "bk_notify"
        mock_obj2.name = "蓝鲸服务(BK)-发送通知"
        mock_obj2.version = "v1.0.0"

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_obj1, mock_obj2]))
        mock_qs.count.return_value = 2
        mock_cm.objects.filter.return_value.exclude.return_value = mock_qs

        service = PluginSchemaService(space_id=1)
        plugins, count = service.list_plugins(plugin_type="component")

        assert count == 2
        assert plugins[0]["code"] == "job_fast_execute_script"
        assert plugins[0]["plugin_type"] == "component"
        assert plugins[0]["name"] == "快速执行脚本"
        assert plugins[0]["group_name"] == "作业平台(JOB)"
        assert "inputs" not in plugins[0]

    @patch("bkflow.plugin.services.plugin_schema_service.SpacePluginConfigModel")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_list_component_plugins_keyword_filter(self, mock_cm, mock_sc, mock_spcm):
        """测试 keyword 搜索过滤"""
        mock_spcm.objects.get_space_allow_list.return_value = []
        mock_sc.get_config.return_value = None

        mock_obj1 = MagicMock()
        mock_obj1.code = "job_fast_execute_script"
        mock_obj1.name = "作业平台(JOB)-快速执行脚本"
        mock_obj1.version = "v1.0.0"

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_obj1]))
        mock_qs.count.return_value = 1
        mock_cm.objects.filter.return_value.exclude.return_value = mock_qs

        service = PluginSchemaService(space_id=1)
        plugins, count = service.list_plugins(plugin_type="component", keyword="脚本")

        assert count == 1
        assert plugins[0]["code"] == "job_fast_execute_script"


class TestComponentSchema:
    """测试内置插件 schema 提取"""

    @patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_component_schema(self, mock_cm, mock_lib):
        """测试从 ComponentLibrary 提取 inputs/outputs"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0"]

        mock_component = MagicMock()
        mock_component.desc = "执行脚本"
        mock_component.inputs_format.return_value = [
            {"key": "script_content", "name": "脚本内容", "type": "string", "required": True, "schema": {}},
        ]
        mock_component.outputs_format.return_value = [
            {"key": "_result", "name": "执行结果", "type": "bool", "schema": {}},
        ]
        mock_lib.get_component_class.return_value = mock_component

        service = PluginSchemaService(space_id=1)
        schema = service._get_component_schema("job_fast_execute_script")

        assert schema["inputs"][0]["key"] == "script_content"
        assert schema["outputs"][0]["key"] == "_result"
        assert schema["description"] == "执行脚本"

    @patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_component_schema_with_version(self, mock_cm, mock_lib):
        """测试指定版本查询"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0", "v2.0.0"]

        mock_component = MagicMock()
        mock_component.desc = "v2 版本"
        mock_component.inputs_format.return_value = []
        mock_component.outputs_format.return_value = []
        mock_lib.get_component_class.return_value = mock_component

        service = PluginSchemaService(space_id=1)
        schema = service._get_component_schema("test_code", version="v2.0.0")

        assert schema["description"] == "v2 版本"
        mock_lib.get_component_class.assert_called_with("test_code", "v2.0.0")

    @patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_component_schema_rejects_explicit_unavailable_version(self, mock_cm, mock_lib):
        """Falling back to latest for an explicit version would resolve a pinned binding incorrectly."""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0", "v2.0.0"]

        with pytest.raises(ValueError, match="版本"):
            PluginSchemaService(space_id=1)._get_component_schema("test_code", version="v9.0.0")

        mock_lib.get_component_class.assert_not_called()


class TestRemotePlugins:
    """测试蓝鲸标准插件查询"""

    @patch("bkflow.plugin.services.plugin_schema_service.BKPluginAuthorization")
    @patch("bkflow.plugin.services.plugin_schema_service.BKPlugin")
    def test_list_remote_plugins(self, mock_bp, mock_auth):
        """测试蓝鲸插件列表"""
        mock_plugin = MagicMock()
        mock_plugin.code = "my_plugin"
        mock_plugin.name = "我的插件"
        mock_plugin.introduction = "自定义插件"

        mock_bp.objects.for_space.return_value = [mock_plugin]

        mock_auth_obj = MagicMock()
        mock_auth_obj.code = "my_plugin"
        mock_auth_obj.white_list = ["*"]
        mock_auth.objects.filter.return_value = [mock_auth_obj]

        service = PluginSchemaService(space_id=1)
        results = service._list_remote_plugins()

        assert len(results) == 1
        assert results[0]["code"] == "my_plugin"
        assert results[0]["plugin_type"] == "remote_plugin"
        assert results[0]["description"] == "自定义插件"

    @patch("bkflow.plugin.services.plugin_schema_service.BKPluginAuthorization")
    @patch("bkflow.plugin.services.plugin_schema_service.BKPlugin")
    def test_list_remote_plugins_auth_filter(self, mock_bp, mock_auth):
        """测试蓝鲸插件授权过滤 — 非授权空间的插件不展示"""
        mock_plugin = MagicMock()
        mock_plugin.code = "restricted_plugin"
        mock_plugin.name = "受限插件"
        mock_plugin.introduction = ""

        mock_bp.objects.for_space.return_value = [mock_plugin]

        mock_auth_obj = MagicMock()
        mock_auth_obj.code = "restricted_plugin"
        mock_auth_obj.white_list = ["999"]
        mock_auth.objects.filter.return_value = [mock_auth_obj]

        service = PluginSchemaService(space_id=1)
        results = service._list_remote_plugins()

        assert len(results) == 0

    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.PluginServiceApiClient")
    def test_get_remote_plugin_schema(self, mock_client_cls, mock_cache):
        """测试蓝鲸插件 schema 获取"""
        mock_cache.get.return_value = None

        mock_client = MagicMock()
        mock_client.get_meta.return_value = {
            "result": True,
            "data": {
                "versions": ["1.0.0", "1.2.0"],
                "inputs": [
                    {"key": "param1", "name": "参数1", "type": "string", "required": True},
                ],
                "outputs": [
                    {"key": "result_data", "name": "结果", "type": "string"},
                ],
            },
        }
        mock_client_cls.return_value = mock_client

        service = PluginSchemaService(space_id=1)
        schema = service._get_remote_plugin_schema("my_plugin")

        assert schema["inputs"][0]["key"] == "param1"
        assert schema["outputs"][0]["key"] == "result_data"
        assert schema["version"] == "1.2.0"
        mock_cache.set.assert_called_once()


class TestUniformApiSourceSelection:
    """测试多来源开放插件的详情目录选择。"""

    @patch.object(PluginSchemaService, "_list_uniform_api_plugins")
    def test_get_single_uniform_api_selects_exact_source_and_version(self, list_plugins):
        """同一空间同一插件 ID 存在多个来源时，详情选择必须锁定来源和版本。"""
        list_plugins.return_value = [
            {
                "code": "shared_open_plugin",
                "source_key": "first-source",
                "plugin_code": "first-code",
                "versions": ["first-v1", "first-v2"],
                "default_version": "first-v1",
                "latest_version": "first-v2",
                "_meta_url_template": "https://first.example/{version}",
            },
            {
                "code": "shared_open_plugin",
                "source_key": "second-source",
                "plugin_code": "second-code",
                "versions": ["second-v1", "second-v2"],
                "default_version": "second-v1",
                "latest_version": "second-v2",
                "_meta_url_template": "https://second.example/{version}",
            },
        ]

        selected = PluginSchemaService(space_id=1)._get_single_by_type(
            "shared_open_plugin",
            "uniform_api",
            version="second-v2",
            source_key="second-source",
        )

        assert selected["source_key"] == "second-source"
        assert selected["plugin_code"] == "second-code"
        assert selected["version"] == "second-v2"
        assert selected["_meta_url"] == "https://second.example/second-v2"

    @patch.object(PluginSchemaService, "_list_uniform_api_plugins")
    def test_get_single_uniform_api_exact_source_mode_keeps_legacy_none_distinct(self, list_plugins):
        """Harness exact lookup must not treat a None legacy source as the public wildcard."""
        list_plugins.return_value = [
            {"code": "shared", "source_key": "legacy_uniform_api", "_meta_url": "https://v4.example"},
            {"code": "shared", "source_key": None, "_meta_url": "https://legacy.example"},
        ]

        selected = PluginSchemaService(space_id=1)._get_single_by_type(
            "shared", "uniform_api", source_key=None, exact_source=True
        )

        assert selected["_meta_url"] == "https://legacy.example"


@pytest.mark.django_db
class TestUniformApiPlugins:
    """测试 API 插件查询"""

    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.Credential")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIClient")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIConfigHandler")
    def test_list_uniform_api_plugins(self, mock_handler, mock_sc, mock_client_cls, mock_cred, mock_cache):
        """测试 API 插件列表查询"""
        mock_cache.get.return_value = None

        mock_sc.get_config.side_effect = lambda space_id, config_name, scope=None: {
            "uniform_api": {"api": {"default": {"meta_apis": "http://example.com/meta_apis"}}},
            "api_gateway_credential_name": "test_cred",
        }.get(config_name)

        mock_model = MagicMock()
        mock_model.api = {"default": MagicMock(meta_apis="http://example.com/meta_apis")}
        mock_handler.return_value.handle.return_value = mock_model

        mock_cred_obj = MagicMock()
        mock_cred_obj.content = {"bk_app_code": "app", "bk_app_secret": "secret"}
        mock_cred.objects.filter.return_value.first.return_value = mock_cred_obj

        mock_client = MagicMock()
        list_resp = MagicMock()
        list_resp.json_resp = {
            "data": {
                "total": 1,
                "apis": [{"id": "sops_execute", "name": "标准运维执行", "meta_url": "http://example.com/meta/sops"}],
            }
        }
        mock_client.request.return_value = list_resp
        mock_client_cls.return_value = mock_client

        service = PluginSchemaService(space_id=1)
        results = service._list_uniform_api_plugins()

        assert len(results) == 1
        assert results[0]["code"] == "sops_execute"
        assert results[0]["plugin_type"] == "uniform_api"

    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.Credential")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIClient")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIConfigHandler")
    def test_remote_uniform_catalog_exhausts_provider_pages_and_refresh_revokes_cached_item(
        self, mock_handler, mock_sc, mock_client_cls, mock_cred, mock_cache
    ):
        """Legacy provider snapshots must include index 100/200 and replace, never extend, the cache on refresh."""
        mock_cache.get.return_value = None
        mock_sc.get_config.side_effect = lambda space_id, config_name, scope=None: {
            "uniform_api": {"api": {"default": {"meta_apis": "http://example.com/meta_apis"}}},
            "api_gateway_credential_name": "test_cred",
        }.get(config_name)
        mock_handler.return_value.handle.return_value.api = {
            "default": MagicMock(meta_apis="http://example.com/meta_apis")
        }
        mock_cred.objects.filter.return_value.first.return_value.content = {
            "bk_app_code": "app",
            "bk_app_secret": "secret",
        }
        items = [
            {"id": "legacy-{}".format(index), "name": "Legacy {}".format(index), "meta_url": "https://meta"}
            for index in range(201)
        ]

        def paged_response(url, method, data, headers, username):
            response = MagicMock()
            offset = data["offset"]
            response.json_resp = {"data": {"total": len(items), "apis": items[offset : offset + data["limit"]]}}
            return response

        mock_client_cls.return_value.request.side_effect = paged_response
        mock_client_cls.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA = (
            RealUniformAPIClient.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA
        )
        mock_client_cls.return_value.validate_response_data.side_effect = RealUniformAPIClient.validate_response_data
        service = PluginSchemaService(space_id=1)

        populated = service._list_remote_uniform_api_plugins()
        items.pop()
        refreshed = service._list_remote_uniform_api_plugins(refresh=True)

        assert populated[100]["code"] == "legacy-100"
        assert populated[200]["code"] == "legacy-200"
        offsets = [call.kwargs["data"]["offset"] for call in mock_client_cls.return_value.request.call_args_list]
        assert offsets == [0, 200, 0]
        assert len(refreshed) == 200
        assert mock_cache.set.call_count == 2
        expected_cached = items + [{"id": "legacy-200", "name": "Legacy 200", "meta_url": "https://meta"}]
        assert mock_cache.set.call_args_list[0].args[1] == expected_cached

    @pytest.mark.parametrize(
        "totals,pages",
        (
            ([201, 202], None),
            ([201], {0: []}),
            ([201, 201], {200: [{"id": "legacy-0", "name": "Duplicate", "meta_url": "https://meta"}]}),
            ([True], None),
            ([-1], None),
            ([1], {0: "not-a-list"}),
            ([0], {0: [{"id": "safe", "name": "Safe", "meta_url": "https://meta"}]}),
            ([1], {0: [{"id": "safe", "name": "Safe", "meta_url": "https://meta"}] * 201}),
            ([1], {0: [{"id": "safe", "name": "Safe", "meta_url": "https://meta"}] * 2}),
            ([1], {0: [{"id": "bad\ud800", "name": "Safe", "meta_url": "https://meta"}]}),
            ([1], {0: [{"id": "safe", "name": "x" * 100000, "meta_url": "https://meta"}]}),
        ),
    )
    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.Credential")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIClient")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIConfigHandler")
    def test_remote_uniform_catalog_rejects_inconsistent_or_nonprogressing_snapshot(
        self, mock_handler, mock_sc, mock_client_cls, mock_cred, mock_cache, totals, pages
    ):
        """A partial legacy provider result must not become an authorization cache entry."""
        mock_cache.get.return_value = None
        mock_sc.get_config.side_effect = lambda space_id, config_name, scope=None: {
            "uniform_api": {"api": {"default": {"meta_apis": "http://example.com/meta_apis"}}},
            "api_gateway_credential_name": "test_cred",
        }.get(config_name)
        mock_handler.return_value.handle.return_value.api = {
            "default": MagicMock(meta_apis="http://example.com/meta_apis")
        }
        mock_cred.objects.filter.return_value.first.return_value.content = {
            "bk_app_code": "app",
            "bk_app_secret": "secret",
        }
        all_items = [
            {"id": "legacy-{}".format(index), "name": "Legacy {}".format(index), "meta_url": "https://meta"}
            for index in range(201)
        ]
        calls = []

        def response(url, method, data, headers, username):
            result = MagicMock()
            calls.append(data["offset"])
            result.json_resp = {
                "data": {
                    "total": totals[len(calls) - 1] if len(totals) > 1 else totals[0],
                    "apis": (
                        pages[data["offset"]]
                        if pages and data["offset"] in pages
                        else all_items[data["offset"] : data["offset"] + 200]
                    ),
                }
            }
            return result

        mock_client_cls.return_value.request.side_effect = response
        mock_client_cls.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA = (
            RealUniformAPIClient.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA
        )
        mock_client_cls.return_value.validate_response_data.side_effect = RealUniformAPIClient.validate_response_data

        with pytest.raises(ValueError, match="uniform API catalog"):
            PluginSchemaService(space_id=1)._list_remote_uniform_api_plugins()

        assert mock_cache.set.call_count == 0

    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.Credential")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIClient")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIConfigHandler")
    def test_get_uniform_api_schema(self, mock_handler, mock_sc, mock_client_cls, mock_cred, mock_cache):
        """测试 API 插件 schema 获取"""
        mock_cache.get.return_value = None

        mock_sc.get_config.side_effect = lambda space_id, config_name, scope=None: {
            "uniform_api": {"api": {"default": {"meta_apis": "http://example.com/meta_apis"}}},
            "api_gateway_credential_name": "test_cred",
        }.get(config_name)

        mock_model = MagicMock()
        mock_model.api = {"default": MagicMock(meta_apis="http://example.com/meta_apis")}
        mock_handler.return_value.handle.return_value = mock_model

        mock_cred_obj = MagicMock()
        mock_cred_obj.content = {"bk_app_code": "app", "bk_app_secret": "secret"}
        mock_cred.objects.filter.return_value.first.return_value = mock_cred_obj

        mock_client = MagicMock()
        list_resp = MagicMock()
        list_resp.json_resp = {
            "data": {
                "total": 1,
                "apis": [{"id": "sops_execute", "name": "标准运维执行", "meta_url": "http://example.com/meta/sops"}],
            }
        }
        meta_resp = uniform_meta_result(
            {
                "id": "sops_execute",
                "name": "标准运维执行",
                "desc": "执行标准运维流程",
                "inputs": [
                    {"key": "biz_id", "name": "业务ID", "type": "int", "required": True},
                ],
            }
        )
        mock_client.request.side_effect = [list_resp, meta_resp]
        mock_client_cls.return_value = mock_client

        service = PluginSchemaService(space_id=1)
        schema = service._get_uniform_api_schema("sops_execute")

        assert schema["inputs"][0]["key"] == "biz_id"
        assert schema["description"] == "执行标准运维流程"
        mock_cache.set.assert_called()

    @pytest.mark.django_db
    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    def test_list_uniform_api_plugins_prefers_local_catalog_index(self, mock_sc, mock_cache):
        """测试开放插件优先从本地目录索引读取"""
        mock_cache.get.return_value = None
        mock_sc.get_config.return_value = None

        OpenPluginCatalogIndex.objects.create(
            space_id=1,
            source_key="sops",
            plugin_id="open_plugin_001",
            plugin_code="job_execute_task",
            plugin_name="JOB 执行作业",
            plugin_source="builtin",
            group_name="作业平台",
            wrapper_version="v4.0.0",
            default_version="1.2.0",
            latest_version="1.3.0",
            versions=["1.2.0", "1.3.0"],
            meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
            status="available",
        )
        SpaceOpenPluginAvailability.objects.create(
            space_id=1,
            source_key="sops",
            plugin_id="open_plugin_001",
            enabled=True,
        )

        service = PluginSchemaService(space_id=1)
        results = service._list_uniform_api_plugins()

        assert len(results) == 1
        assert results[0]["code"] == "open_plugin_001"
        assert results[0]["plugin_type"] == "uniform_api"
        assert results[0]["version"] == "1.3.0"
        assert results[0]["plugin_source"] == "builtin"
        assert results[0]["plugin_code"] == "job_execute_task"
        assert results[0]["wrapper_version"] == "v4.0.0"
        assert results[0]["source_key"] == "sops"

    @pytest.mark.django_db
    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    def test_list_uniform_api_plugins_filters_disabled_catalog_entry(self, mock_sc, mock_cache):
        """测试开放插件未开启时不出现在查询结果中"""
        mock_cache.get.return_value = None
        mock_sc.get_config.return_value = None

        OpenPluginCatalogIndex.objects.create(
            space_id=1,
            source_key="sops",
            plugin_id="open_plugin_001",
            plugin_code="job_execute_task",
            plugin_name="JOB 执行作业",
            plugin_source="builtin",
            group_name="作业平台",
            wrapper_version="v4.0.0",
            default_version="1.2.0",
            latest_version="1.3.0",
            versions=["1.2.0", "1.3.0"],
            meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
            status="available",
        )
        SpaceOpenPluginAvailability.objects.create(
            space_id=1,
            source_key="sops",
            plugin_id="open_plugin_001",
            enabled=False,
        )

        service = PluginSchemaService(space_id=1)

        assert service._list_uniform_api_plugins() == []

    @pytest.mark.django_db
    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.Credential")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIClient")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIConfigHandler")
    def test_list_uniform_api_plugins_merges_v4_catalog_with_remote_v2(
        self, mock_handler, mock_sc, mock_client_cls, mock_cred, mock_cache
    ):
        """目录同步后仍要回落远端，合并 V4 已开启项与存量 V2/V3。"""
        mock_cache.get.return_value = None
        mock_sc.get_config.side_effect = lambda space_id, config_name, scope=None: {
            "uniform_api": {"api": {"default": {"meta_apis": "http://example.com/meta_apis"}}},
            "api_gateway_credential_name": "test_cred",
        }.get(config_name)
        mock_handler.return_value.handle.return_value = MagicMock(
            api={"default": MagicMock(meta_apis="http://example.com/meta_apis")}
        )
        mock_cred.objects.filter.return_value.first.return_value = MagicMock(
            content={"bk_app_code": "app", "bk_app_secret": "secret"}
        )
        mock_client = MagicMock()
        mock_client.request.return_value = MagicMock(
            json_resp={
                "data": {
                    "total": 1,
                    "apis": [
                        {
                            "id": "sops_execute",
                            "name": "标准运维执行",
                            "meta_url": "http://example.com/meta/sops",
                        }
                    ],
                }
            }
        )
        mock_client_cls.return_value = mock_client

        OpenPluginCatalogIndex.objects.create(
            space_id=1,
            source_key="sops",
            plugin_id="sops_execute",
            plugin_name="标准运维执行",
            wrapper_version="",
            meta_url_template="http://example.com/meta/sops",
            status="available",
        )
        SpaceOpenPluginAvailability.objects.create(
            space_id=1,
            source_key="sops",
            plugin_id="sops_execute",
            enabled=False,
        )
        OpenPluginCatalogIndex.objects.create(
            space_id=1,
            source_key="sops",
            plugin_id="open_plugin_001",
            plugin_code="job_execute_task",
            plugin_name="JOB 执行作业",
            plugin_source="builtin",
            wrapper_version="v4.0.0",
            default_version="1.2.0",
            latest_version="1.3.0",
            versions=["1.2.0", "1.3.0"],
            meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
            status="available",
        )
        SpaceOpenPluginAvailability.objects.create(
            space_id=1,
            source_key="sops",
            plugin_id="open_plugin_001",
            enabled=True,
        )

        service = PluginSchemaService(space_id=1)
        results = service._list_uniform_api_plugins()
        codes = {item["code"] for item in results}

        assert codes == {"sops_execute", "open_plugin_001"}
        v2_item = next(item for item in results if item["code"] == "sops_execute")
        assert v2_item["_meta_url"] == "http://example.com/meta/sops"
        assert v2_item.get("wrapper_version") != "v4.0.0"

    @pytest.mark.django_db
    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.Credential")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIClient")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIConfigHandler")
    def test_get_uniform_api_schema_uses_remote_meta_url_after_v2_catalog_sync(
        self, mock_handler, mock_sc, mock_client_cls, mock_cred, mock_cache
    ):
        """存量 V2 被写入目录且未开启时，schema 仍走原 meta_url。"""
        mock_cache.get.return_value = None
        mock_sc.get_config.side_effect = lambda space_id, config_name, scope=None: {
            "uniform_api": {"api": {"default": {"meta_apis": "http://example.com/meta_apis"}}},
            "api_gateway_credential_name": "test_cred",
        }.get(config_name)
        mock_handler.return_value.handle.return_value = MagicMock(
            api={"default": MagicMock(meta_apis="http://example.com/meta_apis")}
        )
        mock_cred.objects.filter.return_value.first.return_value = MagicMock(
            content={"bk_app_code": "app", "bk_app_secret": "secret"}
        )
        mock_client = MagicMock()
        list_resp = MagicMock()
        list_resp.json_resp = {
            "data": {
                "total": 1,
                "apis": [{"id": "sops_execute", "name": "标准运维执行", "meta_url": "http://example.com/meta/sops"}],
            }
        }
        meta_resp = uniform_meta_result(
            {
                "id": "sops_execute",
                "name": "标准运维执行",
                "desc": "执行标准运维流程",
                "inputs": [{"key": "biz_id", "name": "业务ID", "type": "int", "required": True}],
            }
        )
        mock_client.request.side_effect = [list_resp, meta_resp]
        mock_client_cls.return_value = mock_client

        OpenPluginCatalogIndex.objects.create(
            space_id=1,
            source_key="sops",
            plugin_id="sops_execute",
            plugin_name="标准运维执行",
            wrapper_version="",
            meta_url_template="http://example.com/meta/sops",
            status="available",
        )
        SpaceOpenPluginAvailability.objects.create(
            space_id=1,
            source_key="sops",
            plugin_id="sops_execute",
            enabled=False,
        )

        service = PluginSchemaService(space_id=1)
        schema = service._get_uniform_api_schema("sops_execute")

        assert schema["inputs"][0]["key"] == "biz_id"
        assert mock_client.request.call_args_list[-1].kwargs["url"] == "http://example.com/meta/sops"

    @pytest.mark.django_db
    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    def test_list_uniform_api_plugins_filters_plugin_source(self, mock_sc, mock_cache):
        """plugin_source 只返回匹配的 V4 开放插件。"""
        mock_cache.get.return_value = None
        mock_sc.get_config.return_value = None
        for plugin_id, plugin_source in (("open_builtin", "builtin"), ("open_third", "third_party")):
            OpenPluginCatalogIndex.objects.create(
                space_id=1,
                source_key="sops",
                plugin_id=plugin_id,
                plugin_code=plugin_id,
                plugin_name=plugin_id,
                plugin_source=plugin_source,
                wrapper_version="v4.0.0",
                default_version="1.0.0",
                latest_version="1.0.0",
                versions=["1.0.0"],
                meta_url_template="https://example.com/{}/{{version}}".format(plugin_id),
                status="available",
            )
            SpaceOpenPluginAvailability.objects.create(
                space_id=1,
                source_key="sops",
                plugin_id=plugin_id,
                enabled=True,
            )

        service = PluginSchemaService(space_id=1)
        results = service._list_uniform_api_plugins(plugin_source="builtin")

        assert [item["code"] for item in results] == ["open_builtin"]

    @pytest.mark.django_db
    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.Credential")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIClient")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    def test_get_uniform_api_schema_with_explicit_plugin_version(self, mock_sc, mock_client_cls, mock_cred, mock_cache):
        """测试开放插件支持显式版本查询并返回来源字段"""
        mock_cache.get.return_value = None
        mock_sc.get_config.return_value = "test_cred"

        mock_cred_obj = MagicMock()
        mock_cred_obj.content = {"bk_app_code": "app", "bk_app_secret": "secret"}
        mock_cred.objects.filter.return_value.first.return_value = mock_cred_obj

        OpenPluginCatalogIndex.objects.create(
            space_id=1,
            source_key="sops",
            plugin_id="open_plugin_001",
            plugin_code="job_execute_task",
            plugin_name="JOB 执行作业",
            plugin_source="builtin",
            group_name="作业平台",
            wrapper_version="v4.0.0",
            default_version="1.2.0",
            latest_version="1.3.0",
            versions=["1.2.0", "1.3.0"],
            meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
            status="available",
        )
        SpaceOpenPluginAvailability.objects.create(
            space_id=1,
            source_key="sops",
            plugin_id="open_plugin_001",
            enabled=True,
        )

        mock_client = MagicMock()
        mock_client.request.return_value = uniform_meta_result(
            {
                "id": "open_plugin_001",
                "name": "JOB 执行作业",
                "plugin_version": "1.2.0",
                "desc": "执行标准运维作业",
                "inputs": [
                    {"key": "biz_id", "name": "业务ID", "type": "int", "required": True},
                ],
                "outputs": [],
            }
        )
        mock_client_cls.return_value = mock_client

        service = PluginSchemaService(space_id=1, username="admin")
        schema = service.get_plugin_schema(code="open_plugin_001", version="1.2.0", plugin_type="uniform_api")

        assert schema["plugin_source"] == "builtin"
        assert schema["plugin_code"] == "job_execute_task"
        assert schema["version"] == "1.2.0"
        assert schema["wrapper_version"] == "v4.0.0"
        mock_client.request.assert_called_once()
        assert mock_client.request.call_args.kwargs["url"].endswith("version=1.2.0")

    @pytest.mark.django_db
    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.Credential")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIClient")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    def test_get_uniform_api_schema_rejects_plugin_version_not_in_catalog_versions(
        self, mock_sc, mock_client_cls, mock_cred, mock_cache
    ):
        """测试 schema 显式版本查询会拒绝已从目录版本列表移除的业务版本"""
        mock_cache.get.return_value = None
        mock_sc.get_config.return_value = "test_cred"
        mock_cred.objects.filter.return_value.first.return_value = MagicMock(
            content={"bk_app_code": "app", "bk_app_secret": "secret"}
        )

        OpenPluginCatalogIndex.objects.create(
            space_id=1,
            source_key="sops",
            plugin_id="open_plugin_001",
            plugin_code="job_execute_task",
            plugin_name="JOB 执行作业",
            plugin_source="builtin",
            group_name="作业平台",
            wrapper_version="v4.0.0",
            default_version="1.2.0",
            latest_version="1.3.0",
            versions=["1.2.0", "1.3.0"],
            meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
            status="available",
        )
        SpaceOpenPluginAvailability.objects.create(
            space_id=1,
            source_key="sops",
            plugin_id="open_plugin_001",
            enabled=True,
        )

        service = PluginSchemaService(space_id=1, username="admin")
        with pytest.raises(ValueError, match="版本"):
            service.get_plugin_schema(code="open_plugin_001", version="9.9.9", plugin_type="uniform_api")

        mock_client_cls.assert_not_called()


class TestGetPluginSchema:
    """测试统一 get_plugin_schema 方法"""

    @patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_plugin_schema_component(self, mock_cm, mock_lib):
        """测试指定 plugin_type=component 查询"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0"]
        mock_cm.objects.filter.return_value.first.return_value = MagicMock(
            code="test_code", name="分组-插件", version="v1.0.0"
        )

        mock_component = MagicMock()
        mock_component.desc = "测试描述"
        mock_component.inputs_format.return_value = []
        mock_component.outputs_format.return_value = []
        mock_lib.get_component_class.return_value = mock_component

        service = PluginSchemaService(space_id=1)
        result = service.get_plugin_schema(code="test_code", plugin_type="component")

        assert result["code"] == "test_code"
        assert result["plugin_type"] == "component"
        assert "inputs" in result
        assert "outputs" in result

    @patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_plugin_schema_adds_resolved_version_without_changing_version(self, mock_cm, mock_lib):
        """Harness callers need the exact version while legacy callers retain ``version``."""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0"]
        mock_cm.objects.filter.return_value.first.return_value = MagicMock(
            code="test_code", name="分组-插件", version="v1.0.0"
        )
        mock_component = MagicMock()
        mock_component.desc = "测试描述"
        mock_component.inputs_format.return_value = []
        mock_component.outputs_format.return_value = []
        mock_lib.get_component_class.return_value = mock_component

        result = PluginSchemaService(space_id=1).get_plugin_schema(code="test_code", plugin_type="component")

        assert result["version"] == "v1.0.0"
        assert result["resolved_version"] == "v1.0.0"

    @patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_harness_only_conversion_metadata_is_exact_and_not_exposed_by_default(self, mock_cm, mock_lib):
        """The public schema API remains IO-only while the resolver gets trusted wrapper facts."""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0", "v2.0.0"]
        mock_cm.objects.filter.return_value.first.return_value = MagicMock(
            code="test_code", name="分组-插件", version="v2.0.0"
        )
        mock_component = MagicMock()
        mock_component.desc = "测试描述"
        mock_component.inputs_format.return_value = []
        mock_component.outputs_format.return_value = []
        mock_lib.get_component_class.return_value = mock_component
        service = PluginSchemaService(space_id=1)

        public = service.get_plugin_schema(code="test_code", version="v2.0.0", plugin_type="component")
        harness = service.get_plugin_schema(
            code="test_code", version="v2.0.0", plugin_type="component", include_conversion_metadata=True
        )

        assert "conversion_metadata" not in public
        assert harness["conversion_metadata"] == {
            "kind": "component",
            "wrapper_code": "test_code",
            "wrapper_version": "v2.0.0",
        }

    @patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_plugin_schema_component_reports_actual_requested_loaded_version(self, mock_cm, mock_lib):
        """Reporting the row selected first instead of the loaded version breaks exact component references."""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0", "v2.0.0"]
        mock_cm.objects.filter.return_value.first.return_value = MagicMock(
            code="test_code", name="分组-插件", version="v1.0.0"
        )
        mock_component = MagicMock()
        mock_component.desc = "测试描述"
        mock_component.inputs_format.return_value = []
        mock_component.outputs_format.return_value = []
        mock_lib.get_component_class.return_value = mock_component

        result = PluginSchemaService(space_id=1).get_plugin_schema(
            code="test_code", version="v2.0.0", plugin_type="component"
        )

        assert result["version"] == "v1.0.0"
        assert result["resolved_version"] == "v2.0.0"
        mock_lib.get_component_class.assert_called_with("test_code", "v2.0.0")

    @patch("bkflow.plugin.services.plugin_schema_service.BKPlugin")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_plugin_schema_auto_resolve_not_found(self, mock_cm, mock_bp):
        """测试自动解析失败 — 所有注册表未命中"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        mock_cm.objects.filter.return_value.exists.return_value = False
        mock_bp.objects.for_space.return_value.filter.return_value.exists.return_value = False

        service = PluginSchemaService(space_id=1)
        with pytest.raises(ValueError, match="未找到插件"):
            service.get_plugin_schema(code="nonexistent")

    @patch("bkflow.plugin.services.plugin_schema_service.BKPlugin")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_plugin_schema_auto_resolve_ambiguous(self, mock_cm, mock_bp):
        """测试自动解析歧义"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0"]
        mock_cm.objects.filter.return_value.exists.return_value = True
        mock_bp.objects.for_space.return_value.filter.return_value.exists.return_value = True

        service = PluginSchemaService(space_id=1)
        with pytest.raises(ValueError, match="请指定 plugin_type"):
            service.get_plugin_schema(code="ambiguous_code")


class TestManifestIdentityRegistry:
    """Exercise the explicit global-only manifest identity check separately from space ACL."""

    @pytest.mark.django_db
    def test_v4_uniform_manifest_identity_can_be_global_but_not_current_space_visible(self):
        """Treating another space's catalog entry as current authorization would leak it into this space."""
        OpenPluginCatalogIndex.objects.create(
            space_id=2,
            source_key="global-source",
            plugin_id="global-plugin",
            plugin_code="global-plugin-code",
            plugin_name="Global Plugin",
            plugin_source="bkaidev",
            wrapper_version="v4.0.0",
            status=OpenPluginCatalogIndex.Status.AVAILABLE,
        )

        service = PluginSchemaService(space_id=1)

        assert service.manifest_identity_exists("uniform_api", "global-source", "global-plugin") is True
        visible, total = service.list_plugins(plugin_type="uniform_api")
        assert visible == []
        assert total == 0

    def test_legacy_uniform_manifest_identity_is_explicitly_unavailable(self):
        """Guessing a legacy remote uniform identity without a global registry would make overrides unsafe."""
        assert PluginSchemaService(space_id=1).manifest_identity_exists("uniform_api", None, "legacy-plugin") is False

    @pytest.mark.django_db
    def test_exact_v4_disabled_catalog_is_typed_as_access_loss(self):
        """A V4 entry disappearing from availability between list and exact get is semantic revocation."""
        OpenPluginCatalogIndex.objects.create(
            space_id=1,
            source_key="source-a",
            plugin_id="disabled-plugin",
            plugin_code="disabled-plugin",
            plugin_name="disabled",
            plugin_source="builtin",
            wrapper_version="v4.0.0",
            versions=["1.0.0"],
            status=OpenPluginCatalogIndex.Status.AVAILABLE,
        )
        SpaceOpenPluginAvailability.objects.create(
            space_id=1, source_key="source-a", plugin_id="disabled-plugin", enabled=False
        )

        with pytest.raises(PluginSchemaAccessDenied):
            PluginSchemaService(space_id=1).get_plugin_schema(
                code="disabled-plugin",
                version="1.0.0",
                plugin_type="uniform_api",
                source_key="source-a",
                exact_source=True,
            )


class TestCaching:
    """测试缓存行为"""

    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.PluginServiceApiClient")
    def test_cache_hit_skips_remote_call(self, mock_client_cls, mock_cache):
        """缓存命中时不触发远程调用"""
        mock_cache.get.return_value = {
            "version": "1.0.0",
            "inputs": [{"key": "p1", "name": "P1", "type": "string", "required": True, "description": ""}],
            "outputs": [],
        }

        service = PluginSchemaService(space_id=1)
        schema = service._get_remote_plugin_schema("cached_plugin")

        assert schema["version"] == "1.0.0"
        mock_client_cls.assert_not_called()

    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.PluginServiceApiClient")
    def test_remote_schema_refresh_bypasses_legacy_cache(self, mock_client_cls, mock_cache):
        """A hard resolver must observe same-version provider schema drift immediately, not after cache TTL."""
        mock_cache.get.return_value = {"version": "1.0.0", "inputs": [], "outputs": []}
        mock_client_cls.return_value.get_meta.return_value = {
            "result": True,
            "data": {"versions": ["1.0.0"], "inputs": [{"key": "new"}], "outputs": []},
        }

        schema = PluginSchemaService(space_id=1)._get_remote_plugin_schema("cached_plugin", refresh=True)

        assert schema["inputs"][0]["key"] == "new"
        mock_cache.get.assert_not_called()
        mock_client_cls.return_value.get_meta.assert_called_once_with()

    @pytest.mark.django_db
    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.Credential")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIClient")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    def test_uniform_api_schema_cache_is_scoped_by_source_key(self, mock_sc, mock_client_cls, mock_cred, mock_cache):
        """同 ID 不同来源的 schema 不能共用缓存。"""
        store = {}
        mock_cache.get.side_effect = lambda key: store.get(key)
        mock_cache.set.side_effect = lambda key, value, ttl=None: store.__setitem__(key, value)
        mock_sc.get_config.return_value = "test_cred"
        mock_cred.objects.filter.return_value.first.return_value = MagicMock(
            content={"bk_app_code": "app", "bk_app_secret": "secret"}
        )

        for source_key, plugin_code in (("source-a", "code_from_a"), ("source-b", "code_from_b")):
            OpenPluginCatalogIndex.objects.create(
                space_id=1,
                source_key=source_key,
                plugin_id="open_plugin_001",
                plugin_code=plugin_code,
                plugin_name=plugin_code,
                plugin_source="builtin",
                wrapper_version="v4.0.0",
                default_version="1.2.0",
                latest_version="1.2.0",
                versions=["1.2.0"],
                meta_url_template="https://{}.example/open-plugins/open_plugin_001?version={{version}}".format(
                    source_key
                ),
                status="available",
            )
            SpaceOpenPluginAvailability.objects.create(
                space_id=1,
                source_key=source_key,
                plugin_id="open_plugin_001",
                enabled=True,
            )

        mock_client = MagicMock()
        mock_client.request.side_effect = [
            uniform_meta_result(
                {
                    "id": "open_plugin_001",
                    "name": "from-a",
                    "plugin_version": "1.2.0",
                    "desc": "schema-a",
                    "inputs": [{"key": "a", "name": "A", "type": "string", "required": True}],
                    "outputs": [],
                }
            ),
            uniform_meta_result(
                {
                    "id": "open_plugin_001",
                    "name": "from-b",
                    "plugin_version": "1.2.0",
                    "desc": "schema-b",
                    "inputs": [{"key": "b", "name": "B", "type": "string", "required": True}],
                    "outputs": [],
                }
            ),
        ]
        mock_client_cls.return_value = mock_client
        service = PluginSchemaService(space_id=1, username="admin")

        schema_a = service.get_plugin_schema(
            code="open_plugin_001",
            version="1.2.0",
            plugin_type="uniform_api",
            source_key="source-a",
        )
        schema_b = service.get_plugin_schema(
            code="open_plugin_001",
            version="1.2.0",
            plugin_type="uniform_api",
            source_key="source-b",
        )

        assert schema_a["plugin_code"] == "code_from_a"
        assert schema_a["description"] == "schema-a"
        assert schema_a["inputs"][0]["key"] == "a"
        assert schema_b["plugin_code"] == "code_from_b"
        assert schema_b["description"] == "schema-b"
        assert schema_b["inputs"][0]["key"] == "b"
        assert mock_client.request.call_count == 2
        assert mock_client.request.call_args_list[0].kwargs["url"].startswith("https://source-a.example/")
        assert mock_client.request.call_args_list[1].kwargs["url"].startswith("https://source-b.example/")


@pytest.mark.parametrize(
    "meta_result, match",
    (
        (
            uniform_meta_result({"id": "open_plugin_001", "name": "JOB"}, result=False, message="network failed"),
            "network failed",
        ),
        (
            uniform_meta_result(
                {"id": "open_plugin_001", "name": "JOB"},
                response_result=False,
                message="provider rejected",
            ),
            "provider rejected",
        ),
        (uniform_meta_result({"id": "open_plugin_001", "name": "JOB", "inputs": []}), "plugin_version"),
        (
            uniform_meta_result(
                {
                    "id": "open_plugin_001",
                    "name": "JOB 执行作业",
                    "plugin_version": "9.9.9",
                    "inputs": [{"key": "biz_id", "name": "业务ID"}],
                    "outputs": [],
                }
            ),
            "1.2.0.*9.9.9",
        ),
    ),
    ids=("http-false", "business-false", "missing-plugin-version", "version-mismatch"),
)
@pytest.mark.django_db
@patch("bkflow.plugin.services.plugin_schema_service.cache")
@patch("bkflow.plugin.services.plugin_schema_service.Credential")
@patch("bkflow.plugin.services.plugin_schema_service.UniformAPIClient")
@patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
def test_get_uniform_api_schema_does_not_cache_invalid_provider_meta(
    mock_sc, mock_client_cls, mock_cred, mock_cache, meta_result, match
):
    """provider 失败或版本不可核验时不得写入 schema 缓存。"""
    mock_cache.get.return_value = None
    mock_sc.get_config.return_value = "test_cred"
    mock_cred.objects.filter.return_value.first.return_value = MagicMock(
        content={"bk_app_code": "app", "bk_app_secret": "secret"}
    )
    OpenPluginCatalogIndex.objects.create(
        space_id=1,
        source_key="sops",
        plugin_id="open_plugin_001",
        plugin_code="job_execute_task",
        plugin_name="JOB 执行作业",
        plugin_source="builtin",
        group_name="作业平台",
        wrapper_version="v4.0.0",
        default_version="1.2.0",
        latest_version="1.3.0",
        versions=["1.2.0", "1.3.0"],
        meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
        status="available",
    )
    SpaceOpenPluginAvailability.objects.create(
        space_id=1,
        source_key="sops",
        plugin_id="open_plugin_001",
        enabled=True,
    )
    mock_client_cls.return_value.request.return_value = meta_result

    service = PluginSchemaService(space_id=1, username="admin")
    with pytest.raises(ValueError, match=match):
        service.get_plugin_schema(code="open_plugin_001", version="1.2.0", plugin_type="uniform_api")

    mock_cache.set.assert_not_called()
