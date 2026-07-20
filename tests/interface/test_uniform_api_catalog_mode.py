from unittest.mock import MagicMock, patch

import pytest

from bkflow.exceptions import ValidationError
from bkflow.pipeline_plugins.query.uniform_api import uniform_api as uniform_api_query
from bkflow.space.configs import UniformApiConfig

LIST_KEY = UniformApiConfig.Keys.META_APIS.value
CATEGORY_KEY = UniformApiConfig.Keys.API_CATEGORIES.value
LIST_URL = "https://bk-sops.example/plugins/?plugin_source=builtin"
CATEGORY_URL = "https://bk-sops.example/categories/?plugin_source=builtin"


def build_uniform_api_config(catalog_mode="remote"):
    return {
        "api": {
            "sops_builtin": {
                "meta_apis": LIST_URL,
                "api_categories": CATEGORY_URL,
                "display_name": "标准运维内置插件",
                "source_key": "sops",
                "catalog_mode": catalog_mode,
            }
        }
    }


def build_cached_plugin(
    plugin_id="builtin__job_execute_task",
    name="执行作业",
    plugin_source="builtin",
    category="JOB",
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
        "wrapper_version": "v4.0.0",
        "default_version": "legacy",
        "latest_version": "legacy",
        "versions": ["legacy"],
        "meta_url_template": "https://bk-sops.example/plugins/{}/?version={{version}}".format(plugin_id),
        "description": "plugin description",
        "status": status,
        "enabled": enabled,
    }


def configure_query(catalog_mode, client, catalog_service, grant_service):
    return (
        patch(
            "bkflow.space.models.SpaceConfig.get_config",
            return_value=build_uniform_api_config(catalog_mode),
        ),
        patch.object(uniform_api_query, "UniformAPIClient", return_value=client),
        patch.object(uniform_api_query, "OpenPluginCatalogService", catalog_service, create=True),
        patch.object(uniform_api_query, "OpenPluginGrantService", grant_service, create=True),
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


def test_build_cached_categories_uses_visible_plugin_groups():
    plugins = [
        build_cached_plugin(category="JOB"),
        build_cached_plugin(plugin_id="builtin__cc_update_host", name="更新主机", category="CC"),
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
        {"id": "CC", "name": "CC"},
        {"id": "JOB", "name": "JOB"},
    ]


def test_remote_mode_preserves_remote_query():
    client = MagicMock()
    remote_data = {"total": 0, "apis": []}
    client.request.return_value = MagicMock(result=True, json_resp={"data": remote_data})
    catalog_service = MagicMock()
    grant_service = MagicMock()
    patches = configure_query("remote", client, catalog_service, grant_service)

    with patches[0], patches[1], patches[2], patches[3], patch.object(
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

    assert result == remote_data
    client.request.assert_called_once()
    catalog_service.is_catalog_initialized.assert_not_called()


def test_cache_first_uses_initialized_cache_without_remote_request():
    client = MagicMock()
    catalog_service = MagicMock()
    catalog_service.is_catalog_initialized.return_value = True
    catalog_service.list_space_plugins.return_value = [build_cached_plugin()]
    grant_service = MagicMock()
    grant_service.is_granted.return_value = True
    patches = configure_query("cache_first", client, catalog_service, grant_service)

    with patches[0], patches[1], patches[2], patches[3], patch.object(
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
    grant_service = MagicMock()
    grant_service.is_granted.return_value = True
    patches = configure_query("cache_first", client, catalog_service, grant_service)

    with patches[0], patches[1], patches[2], patches[3], patch.object(
        uniform_api_query, "_get_request_scope", create=True
    ):
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
    grant_service = MagicMock()
    grant_service.is_granted.return_value = True
    patches = configure_query("cache_first", client, catalog_service, grant_service)

    with patches[0], patches[1], patches[2], patches[3], patch.object(
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
    grant_service = MagicMock()
    grant_service.is_granted.return_value = True
    patches = configure_query("cache_only", client, catalog_service, grant_service)

    with patches[0], patches[1], patches[2], patches[3], patch.object(
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


def test_cache_first_ungranted_source_does_not_fallback_to_remote():
    client = MagicMock()
    catalog_service = MagicMock()
    grant_service = MagicMock()
    grant_service.is_granted.return_value = False
    patches = configure_query("cache_first", client, catalog_service, grant_service)

    with patches[0], patches[1], patches[2], patches[3], patch.object(
        uniform_api_query, "_get_request_scope", create=True
    ):
        result = uniform_api_query._get_space_uniform_api_list_info(
            space_id=1,
            request_data={"api_name": "sops_builtin", "limit": 50, "offset": 0},
            config_key=LIST_KEY,
            username="dannydeng",
            template_id=1,
        )

    assert result == {"total": 0, "apis": []}
    catalog_service.is_catalog_initialized.assert_not_called()
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
