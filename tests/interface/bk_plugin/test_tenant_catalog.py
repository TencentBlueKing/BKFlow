"""插件目录、负责人身份和同步删除范围的真实数据库回归。"""

from unittest.mock import call, patch

import pytest
from django.test import override_settings
from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    ValidationError,
)

from bkflow.bk_plugin.models import BKPlugin, BKPluginAuthorization
from bkflow.bk_plugin.tasks import sync_bk_plugins
from bkflow.bk_plugin.views import BKPluginManagerViewSet, BKPluginViewSet
from bkflow.plugin.handlers import BluekingPluginHandler
from bkflow.plugin.services.plugin_detail import PluginDetailService
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService
from bkflow.space.models import Space
from tests.interface.test_tenant_reference_boundaries import invoke


def remote(code, **plugin_fields):
    return {
        "plugin": {
            "code": code,
            "name": f"new-{code}",
            "creator": "admin",
            "logo_url": "",
            "created": "2026-01-01",
            "updated": "2026-09-15",
            **plugin_fields,
        },
        "profile": {"contact": "admin", "tag": 1, "introduction": ""},
    }


@pytest.fixture
def catalog(db):
    """包括系统、两个业务租户和迁移前未知归属的插件。"""
    for code, tenant in (("own", "a"), ("other", "b"), ("shared", "system"), ("legacy", "")):
        BKPlugin.objects.create(code=code, name=code, tag=1, tenant_id=tenant, managers=["admin"])


@pytest.mark.parametrize("enabled", [False, True])
def test_catalog_visibility_and_legacy_response(catalog, enabled):
    """单租户保持完整旧目录和返回字段；多租户只可见自身及系统插件。"""
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled):
        response = invoke(BKPluginViewSet, "list")
    plugins = response.data["data"]["data"]["plugins"]
    assert {p["code"] for p in plugins} == ({"own", "shared"} if enabled else {"own", "other", "shared", "legacy"})
    assert all(("tenant_id" in p) is enabled for p in plugins)


@pytest.mark.parametrize("enabled", [False, True])
@override_settings(BLOCK_ADMIN_PERMISSION=False)
def test_plugin_managers_are_tenant_identities(catalog, enabled):
    """同名管理员在其他租户不继承插件管理身份；旧管理列表保持完整。"""
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled):
        response = invoke(BKPluginManagerViewSet, "list")
    assert {p["code"] for p in response.data["data"]["plugins"]} == (
        {"own"} if enabled else {"own", "other", "shared", "legacy"}
    )


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BLOCK_ADMIN_PERMISSION=False)
@pytest.mark.parametrize("code", ["other", "shared", "legacy"])
def test_foreign_plugin_authorization_cannot_be_written(catalog, code):
    """租户管理员即使与其他租户负责人同名也不能改授权。"""
    response = invoke(BKPluginManagerViewSet, "partial_update", {"status": 1}, "patch", code=code)
    assert response.status_code == 403 or response.data.get("result") is False, response.data
    assert not BKPluginAuthorization.objects.exists()


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BLOCK_ADMIN_PERMISSION=False)
def test_own_plugin_manager_can_update(catalog):
    """本人所在租户的插件管理功能正常。"""
    response = invoke(BKPluginManagerViewSet, "partial_update", {"status": 1}, "patch", code="own")
    assert response.data["result"] is True, response.data
    assert BKPluginAuthorization.objects.get(code="own").status == 1


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_empty_sync_only_removes_current_tenant(catalog):
    """远端完整空目录只能删除本租户，不删除系统、其他租户及未知归属数据。"""
    BKPlugin.objects.sync_bk_plugins({}, tenant_id="a")
    assert set(BKPlugin.objects.values_list("code", flat=True)) == {"other", "shared", "legacy"}


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_sync_accepts_current_paas_payload_and_adopts_legacy(catalog):
    """当前 PaaS 不返回租户字段，用精确查询范围认领旧记录。"""
    BKPlugin.objects.sync_bk_plugins({"own": remote("own"), "legacy": remote("legacy")}, tenant_id="a")
    assert BKPlugin.objects.get(code="legacy").tenant_id == "a"
    assert BKPlugin.objects.get(code="own").name == "new-own"
    assert BKPlugin.objects.get(code="other").tenant_id == "b"
    assert BKPlugin.objects.get(code="shared").tenant_id == "system"


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
@pytest.mark.parametrize("invalid", ["duplicate_code", "declared_owner"])
def test_inconsistent_remote_ownership_preserves_catalog(catalog, invalid):
    """全局编码归属冲突或显式归属矛盾时，拒绝整次更新。"""
    before = list(BKPlugin.objects.order_by("code").values())
    info = remote("other") if invalid == "duplicate_code" else remote("own", tenant_id="b")
    with pytest.raises(ValidationError):
        BKPlugin.objects.sync_bk_plugins({info["plugin"]["code"]: info}, tenant_id="a")
    assert list(BKPlugin.objects.order_by("code").values()) == before


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
def test_single_sync_keeps_old_global_and_empty_result_behavior(catalog):
    """单租户空结果不删除，成功结果仍按旧逻辑同步，且不要求租户字段。"""
    BKPlugin.objects.sync_bk_plugins({})
    assert BKPlugin.objects.count() == 4
    BKPlugin.objects.sync_bk_plugins({"own": remote("own"), "added": remote("added")})
    assert set(BKPlugin.objects.values_list("code", flat=True)) == {"own", "added"}
    assert BKPlugin.objects.get(code="own").tenant_id == "a"
    assert BKPlugin.objects.get(code="added").tenant_id == ""


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
@pytest.mark.parametrize("failure", ["fetch", "apply", "none"])
def test_scheduled_sync_is_atomic_and_always_fetches_system(catalog, failure):
    """任何租户拉取/应用失败都保留原目录；系统插件始终独立同步。"""
    before = list(BKPlugin.objects.order_by("code").values())
    responses = [{"shared": remote("shared")}, {"own": remote("own")}, {"other": remote("other")}]
    if failure == "fetch":
        responses[2] = APIException("offline")
    elif failure == "apply":
        responses[2] = {"own": remote("own")}
    with patch("bkflow.bk_plugin.tasks.BK_PLUGIN_SYNC_TENANTS", ["a", "b"]), patch(
        "bkflow.bk_plugin.tasks.fetch_newest_plugins_dict", side_effect=responses
    ) as fetch:
        sync_bk_plugins()
    assert fetch.call_args_list == [call("system"), call("a"), call("b")]
    if failure != "none":
        assert list(BKPlugin.objects.order_by("code").values()) == before
    else:
        assert BKPlugin.objects.get(code="own").name == "new-own"
        assert BKPlugin.objects.get(code="shared").tenant_id == "system"


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
def test_single_scheduled_sync_keeps_request_protocol(catalog):
    """单租户不额外请求系统目录，不增加租户请求参数。"""
    with patch("bkflow.bk_plugin.tasks.fetch_newest_plugins_dict", return_value={}) as fetch:
        sync_bk_plugins()
    fetch.assert_called_once_with(None)
    assert BKPlugin.objects.count() == 4


@pytest.mark.parametrize("enabled", [False, True])
def test_unified_catalog_obeys_same_scope(catalog, enabled):
    """统一插件列表、按编码查询及批量详情不能绕过租户目录。"""
    space = Space.objects.create(name="catalog-space", tenant_id="a", app_code="app")
    for code in ("own", "other", "shared", "legacy"):
        BKPluginAuthorization.objects.create(code=code, status=1)
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled):
        service = PluginSchemaService(space.pk)
        assert {p["code"] for p in service._list_remote_plugins()} == (
            {"own", "shared"} if enabled else {"own", "other", "shared", "legacy"}
        )
        assert service._get_single_by_type("shared", "remote_plugin")["code"] == "shared"
        handler = BluekingPluginHandler(
            {"space_id": space.pk, "blueking": [{"plugin_code": "other"}], "target_fields": ["name"]}
        )
        if enabled:
            with pytest.raises(ValueError):
                service._get_single_by_type("other", "remote_plugin")
            with pytest.raises(NotFound):
                handler.get_plugin_detail()
        else:
            assert handler.get_plugin_detail()["other"]["name"] == "other"


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("code", ["own", "shared"])
def test_remote_schema_passes_space_tenant_and_retains_single_protocol(catalog, enabled, code):
    """系统共享插件也使用调用空间租户，单租户客户端构造保持旧参数。"""
    space = Space.objects.create(name="schema-space", tenant_id="a", app_code="app")
    BKPluginAuthorization.objects.create(code=code, status=1)
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled), patch(
        "bkflow.plugin.services.plugin_schema_service.cache"
    ) as cache, patch("bkflow.plugin.services.plugin_schema_service.PluginServiceApiClient") as client:
        cache.get.return_value = None
        client.return_value.get_meta.return_value = {"result": True, "data": {"versions": ["1.0.0"]}}
        assert PluginSchemaService(space.pk)._get_remote_plugin_schema(code)["version"] == "1.0.0"
        client.assert_called_once_with(code, **({"tenant_id": "a"} if enabled else {}))
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled), patch(
        "bkflow.plugin.services.plugin_detail.PluginServiceApiClient"
    ) as client:
        client.return_value.get_meta.return_value = {"result": True, "data": {"versions": ["1.0.0"]}}
        client.return_value.get_detail.return_value = {"result": True, "data": {"forms": {}, "inputs": []}}
        PluginDetailService(space.pk, None, "admin")._get_remote_plugin_detail(code, "1.0.0", "bkflow")
        client.assert_called_once_with(code, **({"tenant_id": "a"} if enabled else {}))


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_foreign_schema_and_detail_rejected_before_cache_or_upstream(catalog):
    """缓存命中与全空间授权也不能绕过租户限制。"""
    space = Space.objects.create(name="schema-space", tenant_id="a", app_code="app")
    BKPluginAuthorization.objects.create(code="other", status=1)
    with patch("bkflow.plugin.services.plugin_schema_service.cache") as cache, patch(
        "bkflow.plugin.services.plugin_schema_service.PluginServiceApiClient"
    ) as client:
        with pytest.raises(ValueError):
            PluginSchemaService(space.pk)._get_remote_plugin_schema("other")
        cache.get.assert_not_called()
        client.assert_not_called()
    with patch("bkflow.plugin.services.plugin_detail.PluginServiceApiClient") as client:
        with pytest.raises(PermissionDenied):
            PluginDetailService(space.pk, None, "admin")._get_remote_plugin_detail("other", "1.0.0", "bkflow")
        client.assert_not_called()
