import json
from unittest.mock import MagicMock, patch

import pytest
from requests import Response

from bkflow.exceptions import ValidationError
from bkflow.pipeline_plugins.query.uniform_api import uniform_api as uniform_api_query
from bkflow.space.configs import UniformApiConfig, ApiGatewayCredentialConfig
from bkflow.utils.api_client import HttpRequestResult

LIST_KEY = UniformApiConfig.Keys.META_APIS.value
CATEGORY_KEY = UniformApiConfig.Keys.API_CATEGORIES.value
_UNSET = object()
LIST_URL = "https://bk-sops.example/plugins/?plugin_source=builtin"
CATEGORY_URL = "https://bk-sops.example/categories/?plugin_source=builtin"


def build_uniform_api_config(catalog_mode="remote"):
    api_entry = {
        "meta_apis": LIST_URL,
        "api_categories": CATEGORY_URL,
        "display_name": "标准运维内置插件",
        "source_key": "sops",
    }
    if catalog_mode is not None:
        api_entry["catalog_mode"] = catalog_mode
    return {"api": {"sops_builtin": api_entry}}


def build_cached_plugin(
    plugin_id="builtin__job_execute_task",
    name="执行作业",
    plugin_source="builtin",
    category="JOB",
    category_name=None,
    status="available",
    enabled=True,
):
    return {
        "source_key": "sops",
        "plugin_id": plugin_id,
        "plugin_code": plugin_id.replace("builtin__", ""),
        "plugin_name": name,
        "plugin_source": plugin_source,
        "group_name": category,
        "group_display_name": category_name or category,
        "wrapper_version": "v4.0.0",
        "default_version": "legacy",
        "latest_version": "legacy",
        "versions": ["legacy"],
        "meta_url_template": "https://bk-sops.example/plugins/{}/?version={{version}}".format(plugin_id),
        "description": "plugin description",
        "status": status,
        "enabled": enabled,
    }


def configure_query(catalog_mode, client, catalog_service):
    return (
        patch(
            "bkflow.space.models.SpaceConfig.get_config",
            return_value=build_uniform_api_config(catalog_mode),
        ),
        patch.object(uniform_api_query, "UniformAPIClient", return_value=client),
        patch.object(uniform_api_query, "OpenPluginCatalogService", catalog_service, create=True),
    )


def test_extract_plugin_source_from_configured_url():
    assert uniform_api_query._extract_plugin_source(LIST_URL) == "builtin"
    assert uniform_api_query._extract_plugin_source("https://bk-sops.example/plugins/") is None


def test_build_cached_list_filters_visibility_source_keyword_and_paginates():
    plugins = [
        build_cached_plugin(name="执行作业"),
        build_cached_plugin(plugin_id="builtin__job_execute_task_2", name="执行作业 2"),
        build_cached_plugin(plugin_id="builtin__cc_update_host", name="更新主机", category="CC"),
        build_cached_plugin(plugin_id="third-party", name="执行第三方", plugin_source="third_party"),
        build_cached_plugin(plugin_id="builtin__disabled", name="执行已停用", enabled=False),
        build_cached_plugin(plugin_id="builtin__unavailable", name="执行已下架", status="unavailable"),
    ]

    result = uniform_api_query._build_cached_catalog_data(
        plugins=plugins,
        request_data={"category": "JOB", "key": "执行", "limit": 1, "offset": 1},
        config_key=LIST_KEY,
        plugin_source="builtin",
    )

    assert result["total"] == 2
    assert [plugin["id"] for plugin in result["apis"]] == ["builtin__job_execute_task_2"]
    assert result["apis"][0]["meta_url_template"].endswith("?version={version}")
    assert result["apis"][0]["category"] == "JOB"
    assert result["apis"][0]["source_key"] == "sops"


def test_build_cached_categories_uses_visible_plugin_groups():
    plugins = [
        build_cached_plugin(category="JOB", category_name="作业平台"),
        build_cached_plugin(
            plugin_id="builtin__cc_update_host",
            name="更新主机",
            category="CC",
            category_name="配置平台",
        ),
        build_cached_plugin(plugin_id="builtin__disabled", name="停用", category="MONITOR", enabled=False),
    ]

    result = uniform_api_query._build_cached_catalog_data(
        plugins=plugins,
        request_data={},
        config_key=CATEGORY_KEY,
        plugin_source="builtin",
    )

    assert result == [
        {"id": "all", "name": "全部"},
        {"id": "CC", "name": "配置平台"},
        {"id": "JOB", "name": "作业平台"},
    ]


def test_remote_mode_preserves_remote_query():
    client = MagicMock()
    remote_data = {"total": 1, "apis": [{"id": "builtin__job_execute_task"}]}
    client.request.return_value = MagicMock(result=True, json_resp={"data": remote_data})
    catalog_service = MagicMock()
    patches = configure_query("remote", client, catalog_service)

    with patches[0], patches[1], patches[2], patch.object(
        uniform_api_query,
        "_get_api_credential",
        return_value={"bk_app_code": "app", "bk_app_secret": "secret"},
    ):
        result = uniform_api_query._get_space_uniform_api_list_info(
            space_id=1,
            request_data={"api_name": "sops_builtin", "limit": 50, "offset": 0},
            config_key=LIST_KEY,
            username="dannydeng",
            template_id=1,
        )

    assert result == {
        "total": 1,
        "apis": [{"id": "builtin__job_execute_task", "source_key": "sops"}],
    }
    client.request.assert_called_once()
    catalog_service.is_catalog_initialized.assert_not_called()


def test_default_mode_queries_remote_without_extra_admission():
    """未显式配置 catalog_mode 的存量空间必须照常直连远端取列表。"""
    client = MagicMock()
    remote_data = {"total": 1, "apis": [{"id": "builtin__job_execute_task"}]}
    client.request.return_value = MagicMock(result=True, json_resp={"data": remote_data})
    catalog_service = MagicMock()
    patches = configure_query(None, client, catalog_service)

    with patches[0], patches[1], patches[2], patch.object(
        uniform_api_query,
        "_get_api_credential",
        return_value={"bk_app_code": "app", "bk_app_secret": "secret"},
    ):
        result = uniform_api_query._get_space_uniform_api_list_info(
            space_id=1,
            request_data={"api_name": "sops_builtin", "limit": 50, "offset": 0},
            config_key=LIST_KEY,
            username="dannydeng",
            template_id=1,
        )

    assert result == {
        "total": 1,
        "apis": [{"id": "builtin__job_execute_task", "source_key": "sops"}],
    }
    client.request.assert_called_once()
    catalog_service.is_catalog_initialized.assert_not_called()


def test_open_plugin_meta_requires_source_key():
    """使用业务版本详情模板时，调用方必须携带开放插件来源。"""
    serializer = uniform_api_query.UniformAPIMetaSerializer(
        data={
            "template_id": 1,
            "meta_url_template": "https://bk-sops.example/plugins/{version}/",
            "version": "1.2.0",
        }
    )

    assert serializer.is_valid() is False
    assert "source_key" in str(serializer.errors)


def _failed_meta_result(status_code, message="provider failed", json_resp=None, response_json=_UNSET):
    response = Response()
    response.status_code = status_code
    if response_json is not _UNSET:
        response._content = json.dumps(response_json).encode()
    return HttpRequestResult(
        result=False,
        message=message,
        resp=response,
        json_resp=json_resp if json_resp is not None else {},
    )


@pytest.mark.parametrize("response_json", ([], None))
def test_uniform_api_client_handles_non_object_http_error_body(response_json):
    """非对象 HTTP 错误体也应返回失败结果，供调用方按状态分类。"""
    response = Response()
    response.status_code = 403
    response._content = json.dumps(response_json).encode()
    with patch("bkflow.utils.api_client.requests.get", return_value=response):
        result = uniform_api_query.UniformAPIClient.http_request("https://example.com/meta", "GET")

    assert result.result is False
    assert result.resp is response
    assert "status_code: 403" in result.message


def test_meta_serializer_accepts_structured_error():
    """任务执行页可以显式请求结构化错误。"""
    serializer = uniform_api_query.UniformAPIMetaSerializer(
        data={
            "task_id": "10001",
            "meta_url": "https://example.com/meta",
            "structured_error": True,
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["structured_error"] is True


def test_structured_meta_error_ignores_uncontracted_provider_code():
    """统一 API 协议未约定错误码，不得据此判定插件已下架。"""
    error = uniform_api_query._build_structured_meta_error(
        request_result=_failed_meta_result(
            200,
            message="[request api error] message: plugin not found.",
            json_resp={"error_code": "PLUGIN_NOT_FOUND", "message": "plugin not found"},
        ),
    )

    assert error is None


def test_structured_meta_error_keeps_uncontracted_provider_message_generic():
    """没有稳定业务码时不得根据自由文本断言插件已下架。"""
    error = uniform_api_query._build_structured_meta_error(
        request_result=_failed_meta_result(
            400,
            message="[request api error] message: 插件已下架.",
            json_resp={"message": "插件已下架"},
        ),
    )

    assert error is None


def test_structured_meta_error_does_not_call_ambiguous_403_unavailable():
    """无业务语义的 403 只能提示详情不可用，不能直接判定下架。"""
    error = uniform_api_query._build_structured_meta_error(
        request_result=_failed_meta_result(403),
    )

    assert error.error_code == "PLUGIN_DETAIL_UNAVAILABLE"


def test_structured_meta_error_does_not_call_ambiguous_404_unavailable():
    """无业务语义的 404 也只能提示详情不可用。"""
    error = uniform_api_query._build_structured_meta_error(
        request_result=_failed_meta_result(404),
    )

    assert error.error_code == "PLUGIN_DETAIL_UNAVAILABLE"


@pytest.mark.parametrize(
    "response_json",
    ([], None),
)
def test_structured_meta_error_handles_non_object_response_body(response_json):
    """非对象错误体不得击穿 403 的谨慎提示。"""
    error = uniform_api_query._build_structured_meta_error(
        request_result=_failed_meta_result(403, response_json=response_json),
    )

    assert error.error_code == "PLUGIN_DETAIL_UNAVAILABLE"


def test_structured_meta_error_keeps_network_failure_generic():
    """无 HTTP 状态的网络失败应沿用原有通用错误。"""
    error = uniform_api_query._build_structured_meta_error(
        request_result=HttpRequestResult(result=False, message="network failed"),
    )

    assert error is None


def test_cache_first_uses_initialized_cache_without_remote_request():
    client = MagicMock()
    catalog_service = MagicMock()
    catalog_service.is_catalog_initialized.return_value = True
    catalog_service.list_space_plugins.return_value = [build_cached_plugin()]
    patches = configure_query("cache_first", client, catalog_service)

    with patches[0], patches[1], patches[2], patch.object(
        uniform_api_query, "_get_request_scope", create=True
    ) as mock_get_scope, patch.object(uniform_api_query, "_get_api_credential") as mock_get_credential:
        result = uniform_api_query._get_space_uniform_api_list_info(
            space_id=1,
            request_data={"api_name": "sops_builtin", "category": "JOB", "limit": 50, "offset": 0},
            config_key=LIST_KEY,
            username="dannydeng",
            template_id=1,
        )

    assert result["total"] == 1
    assert result["apis"][0]["id"] == "builtin__job_execute_task"
    mock_get_scope.assert_called_once_with(space_id=1, template_id=1, task_id=None)
    mock_get_credential.assert_not_called()
    catalog_service.is_catalog_initialized.assert_called_once_with(
        space_id=1,
        source_key="sops",
        plugin_source="builtin",
    )
    catalog_service.list_space_plugins.assert_called_once_with(space_id=1, source_key="sops")
    client.request.assert_not_called()


def test_cache_first_does_not_fallback_for_filtered_empty_result():
    client = MagicMock()
    catalog_service = MagicMock()
    catalog_service.is_catalog_initialized.return_value = True
    catalog_service.list_space_plugins.return_value = [build_cached_plugin(category="JOB")]
    patches = configure_query("cache_first", client, catalog_service)

    with patches[0], patches[1], patches[2], patch.object(uniform_api_query, "_get_request_scope", create=True):
        result = uniform_api_query._get_space_uniform_api_list_info(
            space_id=1,
            request_data={"api_name": "sops_builtin", "category": "CC", "limit": 50, "offset": 0},
            config_key=LIST_KEY,
            username="dannydeng",
            template_id=1,
        )

    assert result == {"total": 0, "apis": []}
    client.request.assert_not_called()


def test_cache_first_falls_back_to_remote_and_requests_sync_when_uninitialized():
    client = MagicMock()
    remote_data = {"total": 0, "apis": []}
    client.request.return_value = MagicMock(result=True, json_resp={"data": remote_data})
    catalog_service = MagicMock()
    catalog_service.is_catalog_initialized.return_value = False
    patches = configure_query("cache_first", client, catalog_service)

    with patches[0], patches[1], patches[2], patch.object(
        uniform_api_query,
        "_get_api_credential",
        return_value={"bk_app_code": "app", "bk_app_secret": "secret"},
    ), patch.object(uniform_api_query, "_get_request_scope", return_value=("biz", "2")), patch.object(
        uniform_api_query, "_dispatch_catalog_sync", create=True
    ) as mock_dispatch_sync:
        result = uniform_api_query._get_space_uniform_api_list_info(
            space_id=1,
            request_data={"api_name": "sops_builtin", "limit": 50, "offset": 0},
            config_key=LIST_KEY,
            username="dannydeng",
            template_id=1,
        )

    assert result == remote_data
    client.request.assert_called_once()
    mock_dispatch_sync.assert_called_once_with(space_id=1, source_key="sops")


def test_cache_only_rejects_uninitialized_catalog_without_remote_request():
    client = MagicMock()
    catalog_service = MagicMock()
    catalog_service.is_catalog_initialized.return_value = False
    patches = configure_query("cache_only", client, catalog_service)

    with patches[0], patches[1], patches[2], patch.object(
        uniform_api_query, "_get_request_scope", create=True
    ), pytest.raises(ValidationError, match="目录缓存未初始化"):
        uniform_api_query._get_space_uniform_api_list_info(
            space_id=1,
            request_data={"api_name": "sops_builtin", "limit": 50, "offset": 0},
            config_key=LIST_KEY,
            username="dannydeng",
            template_id=1,
        )

    client.request.assert_not_called()


def test_dispatch_catalog_sync_deduplicates_requests():
    with patch.object(uniform_api_query.cache, "add", side_effect=[True, False]), patch(
        "bkflow.plugin.tasks.sync_open_plugin_catalog_source.delay"
    ) as mock_delay:
        uniform_api_query._dispatch_catalog_sync(space_id=1, source_key="sops")
        uniform_api_query._dispatch_catalog_sync(space_id=1, source_key="sops")

    mock_delay.assert_called_once_with(space_id=1, source_key="sops")


def test_dispatch_catalog_sync_ignores_cache_backend_error():
    with patch.object(uniform_api_query.cache, "add", side_effect=RuntimeError("cache unavailable")), patch.object(
        uniform_api_query.logger, "exception"
    ) as mock_logger:
        uniform_api_query._dispatch_catalog_sync(space_id=1, source_key="sops")

    mock_logger.assert_called_once()


def test_get_api_credential_uses_default_scope_when_scope_empty():
    """scope_type/scope_value 为空时应回退到 default 凭证"""
    with patch("bkflow.space.models.SpaceConfig") as mock_space_config, patch(
        "bkflow.space.models.Credential"
    ) as mock_credential:
        mock_space_config.get_config.return_value = "default_cred"
        mock_filter_qs = MagicMock()
        mock_filter_qs.exists.return_value = True
        mock_filter_qs.first.return_value = MagicMock(content={"bk_app_code": "app", "bk_app_secret": "secret"})
        mock_credential.objects.filter.return_value = mock_filter_qs

        result = uniform_api_query._get_api_credential(space_id=1, request_scope=(None, None))

        mock_space_config.get_config.assert_called_once_with(
            space_id=1, config_name=ApiGatewayCredentialConfig.name, scope="default"
        )
        assert result == {"bk_app_code": "app", "bk_app_secret": "secret"}
