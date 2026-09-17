"""验证新查询路径与旧列表使用相同的来源 headers。"""

from unittest.mock import MagicMock, patch

import pytest

from bkflow.pipeline_plugins.query.uniform_api import uniform_api as query
from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
from bkflow.plugin.services.open_plugin_catalog import OpenPluginCatalogService
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService
from bkflow.plugin.services.uniform_api_headers import get_source_headers
from bkflow.utils.api_client import HttpRequestResult

HEADERS = {"X-Bk-Tenant-Id": "tenant-a", "X-Provider": "provider-a"}
ENTRY = {
    "meta_apis": "https://example.com/plugins/",
    "api_categories": "",
    "display_name": "provider",
    "source_key": "source-a",
    "headers": HEADERS,
}
CONFIG = {"api": {"provider": ENTRY}}


@patch("bkflow.plugin.services.uniform_api_headers.SpaceConfig.get_config", return_value=CONFIG)
def test_headers_are_selected_by_source_not_first_entry(_config):
    assert get_source_headers(1, "source-a") == HEADERS
    assert get_source_headers(1, "missing-source") == {}


@patch(
    "bkflow.pipeline_plugins.query.uniform_api.uniform_api._get_api_credential",
    return_value={"bk_app_code": "app", "bk_app_secret": "secret"},
)
@patch("bkflow.space.models.SpaceConfig.get_config", return_value=CONFIG)
@patch.object(
    UniformAPIClient,
    "request",
    return_value=HttpRequestResult(result=True, json_resp={"data": {"total": 0, "apis": []}}),
)
def test_remote_list_preserves_configured_headers(request, _config, _credential):
    query._get_space_uniform_api_list_info(1, {"api_name": "provider"}, "meta_apis", "user")
    assert all(request.call_args.kwargs["headers"][key] == value for key, value in HEADERS.items())


@patch.object(
    OpenPluginCatalogService,
    "_get_apigw_credential",
    return_value=MagicMock(content={"bk_app_code": "app", "bk_app_secret": "secret"}),
)
@patch.object(
    UniformAPIClient,
    "request",
    return_value=HttpRequestResult(result=True, json_resp={"data": {"total": 0, "apis": []}}),
)
def test_background_catalog_preserves_configured_headers(request, _credential):
    assert OpenPluginCatalogService._fetch_api_list(1, ENTRY, "user") == []
    assert all(request.call_args.kwargs["headers"][key] == value for key, value in HEADERS.items())


@patch("bkflow.plugin.services.plugin_schema_service.cache")
@patch("bkflow.plugin.services.uniform_api_headers.SpaceConfig.get_config", return_value=CONFIG)
@patch.object(
    PluginSchemaService,
    "_get_apigw_credential",
    return_value=MagicMock(content={"bk_app_code": "app", "bk_app_secret": "secret"}),
)
@patch.object(UniformAPIClient, "request", return_value=HttpRequestResult(result=False, message="stop after headers"))
def test_schema_preserves_source_headers(request, _credential, _config, cache):
    cache.get.return_value = None
    with pytest.raises(ValueError, match="stop after headers"):
        PluginSchemaService(space_id=1, username="user")._get_uniform_api_schema(
            "plugin", api_item={"source_key": "source-a", "_meta_url": "https://example.com/meta"}
        )
    assert all(request.call_args.kwargs["headers"][key] == value for key, value in HEADERS.items())
