from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.urls import resolve
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory
from pipeline.component_framework.models import ComponentModel

from bkflow.exceptions import APIResponseError

from bkflow.plugin.permissions import (
    PluginSpaceSuperuserPermission,
    PluginTokenPermissions,
)
from bkflow.plugin.services.plugin_detail import build_detail
from bkflow.plugin.views import plugin as plugin_views

EXPECTED_DETAIL_KEYS = {
    "plugin_type",
    "plugin_code",
    "plugin_version",
    "source_key",
    "plugin_source",
    "protocol",
    "wrapper_version",
    "name",
    "description",
    "inputs",
    "outputs",
    "credentials",
    "forms",
    "form_schema",
    "form_context",
    "execution_kind",
    "url",
    "methods",
    "response_data_path",
    "polling",
    "callback",
    "credential_key",
}


def uniform_request(**overrides):
    """构造统一插件详情请求。"""
    data = {
        "space_id": "245",
        "template_id": "2329",
        "plugin_type": "uniform_api",
        "plugin_code": "builtin__job_fast_execute_script",
        "plugin_version": "v2.0",
        "source_key": "sops",
        "scope_type": "biz",
        "scope_value": "100605",
    }
    data.update(overrides)
    return data


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture(autouse=True)
def disable_unrelated_login_middleware(settings):
    """API view 单测不经过蓝鲸登录跳转中间件。"""
    settings.MIDDLEWARE = ("bkflow.permission.middleware.TokenMiddleware",)


@pytest.fixture
def user():
    return SimpleNamespace(username="dannydeng", is_superuser=True, is_authenticated=True)


def drf_request(request):
    """把 factory 的 Django request 包装为可解析 body 的 DRF request。"""
    return Request(request, parsers=[JSONParser()])


def test_detail_route_resolves_before_dynamic_component_route():
    """静态 detail 路由不能被动态组件 code 路由吞掉。"""
    match = resolve("/api/plugin/detail/")

    assert getattr(plugin_views, "PluginDetailView", None) is not None
    assert match.func.view_class is plugin_views.PluginDetailView


@patch.object(plugin_views, "PluginDetailService", create=True)
def test_detail_route_uses_authenticated_operator(service_cls, api_client, user):
    """service operator 必须来自认证用户而非请求 body。"""
    service_cls.return_value.get_detail.return_value = build_detail(plugin_type="uniform_api")
    api_client.force_authenticate(user)

    response = api_client.post("/api/plugin/detail/", uniform_request(), format="json")

    assert response.status_code == 200
    assert response.data["result"] is True
    assert set(response.data["data"]) == EXPECTED_DETAIL_KEYS
    assert service_cls.call_args.kwargs["operator"] == user.username


@patch.object(plugin_views, "PluginDetailService", create=True)
def test_detail_route_rejects_forged_operator(service_cls, api_client, user):
    """body 中伪造 operator 必须在调用 service 前被拒绝。"""
    api_client.force_authenticate(user)

    response = api_client.post(
        "/api/plugin/detail/",
        uniform_request(operator="attacker"),
        format="json",
    )

    assert response.status_code == 400
    assert "operator" in response.data
    service_cls.assert_not_called()


def test_space_superuser_permission_reads_space_id_from_post_body():
    """空间管理员权限必须从 POST body 读取 space_id。"""
    request = drf_request(APIRequestFactory().post("/api/plugin/detail/", uniform_request(), format="json"))
    request.user = SimpleNamespace(username="space_admin")

    with patch("bkflow.plugin.permissions.SpaceConfig.get_config", return_value=["space_admin"]) as get_config:
        allowed = PluginSpaceSuperuserPermission().has_permission(request, MagicMock())

    assert allowed is True
    get_config.assert_called_once_with("245", "superusers")


def test_token_permission_reads_space_id_from_post_body():
    """token 权限必须从 POST body 读取 space_id。"""
    request = drf_request(APIRequestFactory().post("/api/plugin/detail/", uniform_request(), format="json"))
    request.token = "valid-token"
    token = SimpleNamespace(space_id=245, has_expired=lambda: False)

    with patch("bkflow.plugin.permissions.Token.objects.filter") as token_filter:
        token_filter.return_value.first.return_value = token
        allowed = PluginTokenPermissions().has_permission(request, MagicMock())

    assert allowed is True


def test_space_superuser_permission_rejects_conflicting_query_and_post_space_id():
    """空间管理员不能用 query 空间权限操作 body 中的其他空间。"""
    request = drf_request(
        APIRequestFactory().post(
            "/api/plugin/detail/?space_id=245",
            uniform_request(space_id="246"),
            format="json",
        )
    )
    request.user = SimpleNamespace(username="space_admin")

    with patch("bkflow.plugin.permissions.SpaceConfig.get_config", return_value=["space_admin"]) as get_config:
        with pytest.raises(PermissionDenied, match="space_id.*不一致"):
            PluginSpaceSuperuserPermission().has_permission(request, MagicMock())

    get_config.assert_not_called()


def test_token_permission_rejects_conflicting_query_and_post_space_id():
    """token 不能用 query 空间权限操作 body 中的其他空间。"""
    request = drf_request(
        APIRequestFactory().post(
            "/api/plugin/detail/?space_id=245",
            uniform_request(space_id="246"),
            format="json",
        )
    )
    request.token = "valid-token"
    token = SimpleNamespace(space_id=245, has_expired=lambda: False)

    with patch("bkflow.plugin.permissions.Token.objects.filter") as token_filter:
        token_filter.return_value.first.return_value = token
        with pytest.raises(PermissionDenied, match="space_id.*不一致"):
            PluginTokenPermissions().has_permission(request, MagicMock())


@patch.object(plugin_views, "PluginDetailService", create=True)
def test_detail_route_rejects_conflicting_space_id_before_admin_short_circuit(service_cls, api_client, user):
    """query/body 空间冲突不能被系统管理员权限短路放行。"""
    service_cls.return_value.get_detail.return_value = build_detail(plugin_type="uniform_api")
    api_client.force_authenticate(user)

    response = api_client.post(
        "/api/plugin/detail/?space_id=245",
        uniform_request(space_id="246"),
        format="json",
    )

    assert response.status_code == 403
    service_cls.assert_not_called()


def test_plugin_permissions_keep_get_query_behavior():
    """原 GET query 的空间权限读取行为保持不变。"""
    request = drf_request(APIRequestFactory().get("/api/plugin/?space_id=245"))
    request.user = SimpleNamespace(username="space_admin")

    with patch("bkflow.plugin.permissions.SpaceConfig.get_config", return_value=["space_admin"]):
        allowed = PluginSpaceSuperuserPermission().has_permission(request, MagicMock())

    assert allowed is True


def test_detail_route_rejects_request_without_permission(api_client):
    """非管理员、非空间管理员且无 token 时返回 403。"""
    api_client.force_authenticate(SimpleNamespace(username="normal_user", is_superuser=False, is_authenticated=True))

    with patch("bkflow.plugin.permissions.SpaceConfig.get_config", return_value=[]), patch(
        "bkflow.plugin.permissions.Token.objects.filter"
    ) as token_filter:
        token_filter.return_value.first.return_value = None
        response = api_client.post("/api/plugin/detail/", uniform_request(), format="json")

    assert response.status_code == 403


@patch.object(plugin_views, "PluginDetailService", create=True)
def test_detail_route_returns_serializer_error(service_cls, api_client, user):
    """请求契约错误时返回 400 且不调用 service。"""
    api_client.force_authenticate(user)

    response = api_client.post(
        "/api/plugin/detail/",
        uniform_request(source_key=""),
        format="json",
    )

    assert response.status_code == 400
    assert "source_key" in response.data
    service_cls.assert_not_called()


@pytest.mark.parametrize(
    ("error", "status_code"),
    (
        (NotFound("插件版本不存在或已下架"), 404),
        (PermissionDenied("插件来源与请求不一致"), 403),
    ),
)
@patch.object(plugin_views, "PluginDetailService", create=True)
def test_detail_route_preserves_drf_adapter_errors(service_cls, error, status_code, api_client, user):
    """adapter 的 NotFound 与 PermissionDenied 保留明确状态和消息。"""
    service_cls.return_value.get_detail.side_effect = error
    api_client.force_authenticate(user)

    response = api_client.post("/api/plugin/detail/", uniform_request(), format="json")

    assert response.status_code == status_code
    assert response.data["detail"] == str(error)


@patch.object(plugin_views, "PluginDetailService", create=True)
def test_detail_route_preserves_api_response_error(service_cls, api_client, user):
    """统一 API 上游失败原样交给全局异常层处理。"""
    service_cls.return_value.get_detail.side_effect = APIResponseError("provider rejected")
    api_client.force_authenticate(user)

    with pytest.raises(APIResponseError, match="provider rejected"):
        api_client.post("/api/plugin/detail/", uniform_request(), format="json")


@pytest.mark.django_db
class TestComponentModelSetViewSet:
    @pytest.fixture(autouse=True)
    def setup(self, api_client, user):
        self.client = api_client
        self.user = user
        self.client.force_authenticate(self.user)

    @patch("bkflow.plugin.views.plugin.SpacePluginConfigModel.objects.get_space_allow_list")
    @patch("bkflow.plugin.views.plugin.SpaceConfig.get_config")
    def test_list_applies_system_plugin_filter(self, mock_get_config, mock_allow_list):
        """get_queryset 应根据系统插件白名单排除未授权的插件"""
        mock_allow_list.return_value = ["allowed_plugin"]
        mock_get_config.return_value = None
        with patch.object(plugin_views.settings, "SPACE_PLUGIN_LIST", ["allowed_plugin", "excluded_plugin"]):
            response = self.client.get("/api/plugin/?space_id=1")

        assert response.status_code == 200
        assert response.data["result"] is True

    @patch("bkflow.plugin.views.plugin.SpacePluginConfigModel.objects.get_space_allow_list")
    @patch("bkflow.plugin.views.plugin.SpaceConfig.get_config")
    def test_list_skip_space_config(self, mock_get_config, mock_allow_list):
        """skip_space_config=true 时不再读取空间插件配置"""
        mock_allow_list.return_value = []
        response = self.client.get("/api/plugin/?space_id=1&skip_space_config=true")

        assert response.status_code == 200
        mock_get_config.assert_not_called()

    @patch("bkflow.plugin.views.plugin.SpacePluginConfigModel.objects.get_space_allow_list")
    @patch("bkflow.plugin.views.plugin.SpaceConfig.get_config")
    @patch("bkflow.plugin.views.plugin.SpacePluginConfigParser")
    def test_list_with_space_config(self, mock_parser_cls, mock_get_config, mock_allow_list):
        """空间配置存在且非 allow_all 时应调用解析器过滤 queryset"""
        mock_allow_list.return_value = []
        mock_get_config.return_value = {"default": {"mode": "allow_list", "plugin_codes": ["plugin1"]}}
        mock_parser = mock_parser_cls.return_value
        mock_parser.get_filtered_plugin_qs.return_value = ComponentModel.objects.none()

        response = self.client.get("/api/plugin/?space_id=1")

        assert response.status_code == 200
        mock_parser.get_filtered_plugin_qs.assert_called_once()
