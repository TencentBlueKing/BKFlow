"""租户边界通过真实 DRF 入口验证，不依赖线上网关、数据库或通知服务。"""

import io
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.interface.task.view import TaskInterfaceAdminViewSet
from bkflow.interface.utils import APIGWUserModelBackend
from bkflow.space.models import Space, SpaceConfig
from bkflow.space.serializers import SpaceSerializer
from bkflow.space.views import SpaceInternalViewSet, SpaceViewSet
from bkflow.statistics.models import TemplateStatistics
from bkflow.statistics.views import SystemStatisticsViewSet
from bkflow.template.models import Template, TemplateSnapshot
from bkflow.template.views.debug import DebugViewSet
from bkflow.template.views.template import AdminTemplateViewSet, TemplateVersionViewSet
from bkflow.utils.pipeline import build_default_pipeline_tree
from bkflow.utils.tenant import get_request_tenant_id


@pytest.fixture
def tenant_spaces(db):
    """两个租户使用同一个应用，且故意给同名账号配置空间管理员权限。"""
    spaces = [Space.objects.create(name=f"space-{t}", app_code="global-app", tenant_id=t) for t in ("a", "b")]
    for space in spaces:
        SpaceConfig.objects.create(space_id=space.id, name="superusers", value_type="JSON", json_value=["member"])
    return spaces


def user(tenant="a", admin=False):
    return SimpleNamespace(username="member", tenant_id=tenant, is_superuser=admin, is_authenticated=True)


def invoke(view, action, data=None, method="get", actor=None, **kwargs):
    request = getattr(APIRequestFactory(), method)("/tenant-test/", data or {}, format="json")
    request.token = ""
    request.app_internal_token = ""
    force_authenticate(request, user=actor or user())
    return view.as_view({method: action}, basename="space" if view is SpaceViewSet else "tenant-test")(
        request, **kwargs
    )


def assert_denied(response):
    assert response.status_code == 403 or response.data.get("result") is False, response.data
    assert "租户" in str(response.data), response.data


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True, BLOCK_ADMIN_PERMISSION=False)
@pytest.mark.parametrize("admin", [False, True])
@pytest.mark.parametrize("method,action", [("get", "retrieve"), ("patch", "partial_update"), ("delete", "destroy")])
def test_other_tenant_space_denied_even_for_admin(tenant_spaces, admin, method, action):
    """拥有空间管理员或平台管理员身份也不能越过租户边界。"""
    response = invoke(SpaceViewSet, action, {"desc": "changed"}, method, user(admin=admin), pk=tenant_spaces[1].pk)
    assert_denied(response)
    tenant_spaces[1].refresh_from_db()
    assert tenant_spaces[1].is_deleted is False
    assert tenant_spaces[1].desc != "changed"


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True, BLOCK_ADMIN_PERMISSION=False)
@pytest.mark.parametrize("admin", [False, True])
def test_own_space_allowed_and_list_scoped(tenant_spaces, admin):
    """同租户操作正常，列表不暴露其他租户。"""
    actor = user(admin=admin)
    response = invoke(SpaceViewSet, "retrieve", actor=actor, pk=tenant_spaces[0].pk)
    assert response.data["result"] is True
    assert response.data["data"]["id"] == tenant_spaces[0].pk
    listing = invoke(SpaceViewSet, "list", actor=actor)
    assert str(tenant_spaces[1].name) not in str(listing.data)
    assert tenant_spaces[0].name in str(listing.data)


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True, BLOCK_ADMIN_PERMISSION=False)
def test_space_cannot_change_tenant_or_enable_global(tenant_spaces):
    """空间创建/修改不能选择其他租户，当前只接受独立租户空间。"""
    for data in ({"tenant_id": "b"}, {"tenant_mode": "global"}):
        response = invoke(SpaceViewSet, "partial_update", data, "patch", user(admin=True), pk=tenant_spaces[0].pk)
        assert response.data["result"] is False
    with patch("bkflow.space.views.ApiGwClient") as client:
        response = invoke(
            SpaceViewSet,
            "create",
            {"name": "new", "app_code": "global-app", "platform_url": "https://example.com", "tenant_id": "b"},
            "post",
            user(admin=True),
        )
        assert response.data["result"] is False
        client.assert_not_called()


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=False)
@pytest.mark.parametrize("tenant", ["", "   "])
def test_legacy_blank_space_tenant_create_and_edit(tenant_spaces, tenant):
    """旧登录产生的空字符串不会阻断单租户创建和编辑空间。"""
    response = invoke(
        SpaceViewSet,
        "create",
        {"name": "legacy-new", "app_code": "legacy-app", "platform_url": "https://example.com", "tenant_id": tenant},
        "post",
        user(tenant="", admin=True),
    )
    assert response.data["result"] is True, response.data
    space = Space.objects.get(name="legacy-new")
    assert space.tenant_id == "default"
    serializer = SpaceSerializer(space, data={"tenant_id": tenant, "desc": "updated"}, partial=True)
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    assert space.desc == "updated"


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True, BLOCK_ADMIN_PERMISSION=False)
def test_template_only_debug_and_snapshot_ids_are_scoped(tenant_spaces):
    """没有 space_id 的调试入口与快照详情也按真实归属校验。"""
    initial = TemplateSnapshot.objects.create(data=build_default_pipeline_tree(), md5sum="initial")
    template = Template.objects.create(name="other-template", space_id=tenant_spaces[1].pk, snapshot_id=initial.pk)
    snapshot = TemplateSnapshot.objects.create(template_id=template.pk, data={}, md5sum="test")
    with patch("bkflow.template.views.debug.DebugService") as service:
        assert_denied(invoke(DebugViewSet, "context", {"template_id": template.pk}, actor=user(admin=True)))
        service.assert_not_called()
    assert_denied(invoke(TemplateVersionViewSet, "retrieve", actor=user(admin=True), pk=snapshot.pk))


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True, BLOCK_ADMIN_PERMISSION=False)
def test_batch_template_ids_cannot_reference_another_tenant(tenant_spaces):
    """批量入口不能使用本租户 space_id 搭配他租户模板 ID。"""
    initial = TemplateSnapshot.objects.create(data=build_default_pipeline_tree(), md5sum="initial")
    template = Template.objects.create(name="other-template", space_id=tenant_spaces[1].pk, snapshot_id=initial.pk)
    response = invoke(
        AdminTemplateViewSet,
        "batch_delete",
        {"space_id": tenant_spaces[0].pk, "template_ids": [template.pk], "is_full": False},
        "post",
        user(admin=True),
    )
    assert_denied(response)


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True, BLOCK_ADMIN_PERMISSION=False)
def test_task_proxy_denies_before_engine_call(tenant_spaces):
    """平台管理员在调用 Engine 前就被租户边界拒绝。"""
    with patch("bkflow.interface.task.view.TaskComponentClient") as client:
        assert_denied(
            invoke(TaskInterfaceAdminViewSet, "get_task_list", actor=user(admin=True), space_id=tenant_spaces[1].pk)
        )
        client.assert_not_called()


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True, BLOCK_ADMIN_PERMISSION=False)
def test_statistics_only_aggregate_current_tenant(tenant_spaces):
    """平台管理员的系统统计只聚合本租户空间。"""
    for i, space in enumerate(tenant_spaces, 1):
        TemplateStatistics.objects.create(template_id=i, space_id=space.pk, template_name=f"t{i}")
    response = invoke(SystemStatisticsViewSet, "overview", {"date_range": "30d"}, actor=user(admin=True))
    assert response.data.get("total_templates") == 1, response.data


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BLOCK_ADMIN_PERMISSION=False)
@pytest.mark.parametrize("tenant", [None, "", "  "])
def test_missing_user_tenant_is_rejected(tenant):
    """缺失租户不能回退为 system 或单租户。"""
    with pytest.raises(PermissionDenied):
        get_request_tenant_id(SimpleNamespace(user=user(tenant)))


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True, BLOCK_ADMIN_PERMISSION=False)
def test_gateway_backend_keeps_verified_tenant_without_reusing_admin():
    """JWT 租户必须匹配持久化用户身份，不能借用其他租户管理员。"""
    backend = APIGWUserModelBackend()
    backend.user_model.objects.create(username="gateway-user", tenant_id="b", is_superuser=True)
    rejected = backend.authenticate(None, "test", "gateway-user", True, tenant_id="a")
    assert not rejected.is_authenticated
    accepted = backend.authenticate(None, "test", "gateway-user", True, tenant_id="b")
    assert accepted.tenant_id == "b" and accepted.is_superuser
    created = backend.authenticate(None, "test", "new-gateway-user", True, tenant_id="a")
    assert created.tenant_id == "a" and not created.is_superuser


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BLOCK_ADMIN_PERMISSION=False)
@pytest.mark.parametrize("failure_step", ["system_create", "system_migrate"])
@pytest.mark.parametrize("failure", [None, {"result": False, "message": "denied"}, RuntimeError("offline")])
def test_init_tenant_failure_is_not_success(failure_step, failure):
    """两个外部步骤的业务失败和异常均以 CommandError 终止。"""
    path = "bkflow.contrib.itsm_workflow.management.commands.migrate_itsm_workflow.get_client_by_username"
    with patch(path) as client:
        api = client.return_value.api
        api.system_create.return_value = {"result": True}
        api.system_migrate.return_value = {"result": True}
        target = getattr(api, failure_step)
        if isinstance(failure, Exception):
            target.side_effect = failure
        else:
            target.return_value = failure
        with pytest.raises(CommandError):
            call_command("init_tenant", tenant_id="a", stdout=io.StringIO())
        if failure_step == "system_create":
            api.system_migrate.assert_not_called()


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_gateway_identity_cannot_mix_with_other_tenant_session():
    """已登录 session 不能掩盖 JWT 的另一个租户身份。"""
    request = SimpleNamespace(
        user=user("a"), jwt=SimpleNamespace(payload={"user": {"verified": True, "tenant_id": "b"}})
    )
    with pytest.raises(PermissionDenied):
        get_request_tenant_id(request)


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_internal_client_never_forwards_superuser_bypass():
    """Interface 即便由平台管理员触发，也不能让 Engine 忽略空间。"""
    from django.conf import settings

    from bkflow.contrib.api.collections.task import TaskComponentClient

    with patch.object(TaskComponentClient, "get_module_info", return_value=SimpleNamespace(token="internal")):
        client = TaskComponentClient(space_id=7, from_superuser=True)
        headers = client._pre_process_headers({})
        assert headers[settings.APP_INTERNAL_FROM_SUPERUSER_HEADER_KEY] == "0"
        assert headers[settings.APP_INTERNAL_SPACE_ID_HEADER_KEY] == "7"


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_uniform_api_query_checks_tenant_before_admin_bypass(tenant_spaces):
    """Web 插件查询受空间边界约束，不改变第三方 API 插件协议。"""
    from bkflow.pipeline_plugins.query.uniform_api.utils import check_resource_token

    callback = Mock(return_value={"result": True})
    request = SimpleNamespace(user=user(admin=True))
    with pytest.raises(PermissionDenied):
        check_resource_token(callback)(request, space_id=tenant_spaces[1].pk)
    callback.assert_not_called()
    assert check_resource_token(callback)(request, space_id=tenant_spaces[0].pk) == {"result": True}


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_native_admin_has_no_unscoped_tenant_entry():
    from bkflow.utils.middlewares import TenantAdminBoundaryMiddleware

    request = SimpleNamespace(resolver_match=SimpleNamespace(app_names=["admin"]))
    response = TenantAdminBoundaryMiddleware(lambda request: None).process_view(request, None, (), {})
    assert response.status_code == 403


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True, BLOCK_ADMIN_PERMISSION=False)
def test_internal_credential_is_only_accepted_by_internal_view(tenant_spaces):
    from django.conf import settings

    for view, allowed in ((SpaceInternalViewSet, True), (SpaceViewSet, False)):
        request = APIRequestFactory().get("/space/")
        request.app_internal_token = settings.APP_INTERNAL_TOKEN
        force_authenticate(request, user=user(tenant="", admin=True))
        response = view.as_view({"get": "retrieve"})(request, pk=tenant_spaces[0].pk)
        assert response.data["result"] is allowed


def app_request(mode="global", tenant="a", app_tenant="", user_tenant=None, **kwargs):
    jwt_user = {"verified": user_tenant is not None, "tenant_id": user_tenant}
    return SimpleNamespace(
        app=SimpleNamespace(verified=True, tenant_mode=mode, tenant_id=app_tenant, bk_app_code="global-app"),
        headers={"X-Bk-Tenant-Id": tenant} if tenant is not None else {},
        jwt=SimpleNamespace(payload={"user": jwt_user}),
        resolver_match=SimpleNamespace(kwargs=kwargs),
    )


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
@pytest.mark.parametrize(
    "mode,tenant,app_tenant,user_tenant",
    [
        ("global", None, "", None),
        ("global", "", "", None),
        ("single", "b", "a", None),
        ("single", None, "", None),
        ("global", "b", "", "a"),
        ("", "a", "a", None),
    ],
)
def test_app_request_rejects_missing_or_mismatched_identity(mode, tenant, app_tenant, user_tenant):
    from bkflow.utils.tenant import get_apigw_request_tenant_id

    with pytest.raises(PermissionDenied):
        get_apigw_request_tenant_id(app_request(mode, tenant, app_tenant, user_tenant))


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APIGW_REQUIRE_EXEMPT=False)
def test_global_app_uses_separate_spaces_without_user_identity(tenant_spaces):
    from bkflow.apigw.decorators import check_jwt_and_space

    callback = Mock(return_value={"result": True})
    for space in tenant_spaces:
        request = app_request(tenant=space.tenant_id, space_id=space.pk)
        assert check_jwt_and_space(callback)(request) == {"result": True}
        request.headers["X-Bk-Tenant-Id"] = "other"
        with pytest.raises(PermissionDenied):
            check_jwt_and_space(callback)(request)
    assert callback.call_count == 2


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APIGW_REQUIRE_EXEMPT=True)
def test_gateway_exemption_does_not_bypass_tenant(tenant_spaces):
    from bkflow.apigw.decorators import check_jwt_and_space

    callback = Mock()
    with pytest.raises(PermissionDenied):
        check_jwt_and_space(callback)(app_request(tenant="a", space_id=tenant_spaces[1].pk))
    callback.assert_not_called()


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APIGW_REQUIRE_EXEMPT=False)
def test_app_bound_template_and_task_still_require_same_tenant(tenant_spaces):
    from bkflow.apigw.decorators import (
        check_task_bk_app_code,
        check_template_bk_app_code,
    )

    initial = TemplateSnapshot.objects.create(data=build_default_pipeline_tree(), md5sum="initial")
    template = Template.objects.create(
        name="other-template", space_id=tenant_spaces[1].pk, snapshot_id=initial.pk, bk_app_code="global-app"
    )
    callback = Mock()
    with pytest.raises(PermissionDenied):
        check_template_bk_app_code(callback)(app_request(tenant="a", template_id=template.pk))
    with patch("bkflow.apigw.decorators.TaskComponentClient") as client:
        client.return_value.get_task_detail.return_value = {
            "result": True,
            "data": {"template_id": template.pk, "space_id": tenant_spaces[1].pk},
        }
        with pytest.raises(PermissionDenied):
            check_task_bk_app_code(callback)(app_request(tenant="a", task_id=12))
    callback.assert_not_called()


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APIGW_REQUIRE_EXEMPT=True)
def test_app_cannot_create_space_for_another_request_tenant():
    import inspect
    import json

    from bkflow.apigw.decorators import return_json_response
    from bkflow.apigw.views.create_space import create_space

    request = app_request(tenant="a")
    request.body = json.dumps({"name": "bad", "platform_url": "https://example.com", "tenant_id": "b"})
    response = return_json_response(inspect.unwrap(create_space))(request)
    assert response.status_code == 403
    assert not Space.objects.filter(name="bad").exists()
