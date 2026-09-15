"""验证嵌套模板、快照和部署凭证边界，并对照单租户旧协议。"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.admin.models import ModuleInfo
from bkflow.admin.views import ModuleInfoAdminViewSet
from bkflow.apigw.serializers.template import (
    CreateTemplateSerializer,
    UpdateTemplateSerializer,
)
from bkflow.exceptions import ValidationError as FlowValidationError
from bkflow.space.models import Space
from bkflow.template.debug.service import DebugService
from bkflow.template.models import Template, TemplateReference, TemplateSnapshot
from bkflow.template.tenant import validate_template_references
from bkflow.template.views.template import TemplateInternalViewSet, TemplateViewSet
from bkflow.utils.pipeline import (
    build_default_pipeline_tree,
    replace_subprocess_version,
)


def invoke(view, action, data=None, method="get", internal=False, **kwargs):
    request = getattr(APIRequestFactory(), method)("/boundary-test/", data or {}, format="json")
    request.token = ""
    request.app_internal_token = settings.APP_INTERNAL_TOKEN if internal else ""
    force_authenticate(
        request, user=SimpleNamespace(username="admin", tenant_id="a", is_superuser=True, is_authenticated=True)
    )
    return view.as_view({method: action})(request, **kwargs)


@pytest.fixture
def templates(db):
    """建立真实空间和模板快照，避免模拟查询掩盖越界。"""
    result = []
    for tenant in ("a", "b"):
        space = Space.objects.create(name=tenant, tenant_id=tenant, app_code="global-app")
        tree = build_default_pipeline_tree()
        next(iter(tree["activities"].values()))["name"] = f"PRIVATE_NODE_{tenant}"
        snapshot = TemplateSnapshot.objects.create(data=tree, md5sum=tenant * 32, version="1.0.0")
        template = Template.objects.create(name=tenant, space_id=space.pk, snapshot_id=snapshot.pk)
        snapshot.template_id = template.pk
        snapshot.save(update_fields=["template_id"])
        result.append(template)
    return result


def reference_tree(template_id, converted=False, nested=False):
    node = {"type": "SubProcess", "template_id": template_id, "version": "a" * 32}
    if converted:
        node = {
            "type": "ServiceActivity",
            "component": {"code": "subprocess_plugin", "data": {"subprocess": {"value": node}}},
        }
    tree = {"activities": {"ref": node}}
    if nested:
        tree = {"activities": {"canvas": {"type": "SubCanvas", "pipeline": tree}}}
    return tree


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("converted,nested", [(False, False), (True, False), (False, True), (True, True)])
def test_nested_reference_scope_and_single_compatibility(templates, enabled, converted, nested):
    """多租户拒绝嵌套越界，单租户保留旧引用行为。"""
    own, other = templates
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled):
        validate_template_references(own.space_id, reference_tree(own.pk, converted, nested))
        if enabled:
            with pytest.raises(ValidationError):
                validate_template_references(own.space_id, reference_tree(other.pk, converted, nested))
        else:
            validate_template_references(own.space_id, reference_tree(other.pk, converted, nested))


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
@pytest.mark.parametrize("invalid_id", [None, "${template}", True, -1, ""])
def test_dynamic_reference_rejected(templates, invalid_id):
    """多租户不能使用未固定归属的动态模板 ID。"""
    with pytest.raises(ValidationError):
        validate_template_references(templates[0].space_id, reference_tree(invalid_id))


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_deleted_or_same_tenant_other_space_reference_rejected(templates):
    """租户相同仍不能跨空间引用，已删除模板也不能引用。"""
    own, other = templates
    Space.objects.filter(pk=other.space_id).update(tenant_id="a")
    with pytest.raises(ValidationError):
        validate_template_references(own.space_id, reference_tree(other.pk))
    Template.objects.filter(pk=own.pk).update(is_deleted=True)
    with pytest.raises(ValidationError):
        validate_template_references(own.space_id, reference_tree(own.pk))


@pytest.mark.parametrize("enabled", [False, True])
def test_existing_reference_index_obeys_tenant_boundary(templates, enabled):
    """旧引用索引同样隔离，单租户列表仍展示原有引用信息。"""
    own, other = templates
    TemplateReference.objects.create(
        root_template_id=str(own.pk),
        subprocess_template_id=str(other.pk),
        subprocess_node_id="ref",
        version="b" * 32,
        always_use_latest=False,
    )
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled):
        if enabled:
            with pytest.raises(ValidationError):
                _ = own.subprocess_info
        else:
            assert own.subprocess_info[0]["subprocess_template_name"] == other.name


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
def test_single_tenant_reference_validation_has_no_database_dependency(db, django_assert_num_queries):
    """旧流程不新增查询，也不要求额外字段。"""
    with django_assert_num_queries(0):
        validate_template_references(None, reference_tree("${template}", converted=True, nested=True))


@pytest.mark.parametrize("enabled", [False, True])
def test_copy_keeps_old_snapshot_readable(templates, enabled):
    """复制模板仍创建自己的快照，旧模板的历史版本继续可读。"""
    own = templates[0]
    own_id = own.pk
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled):
        copied = Template.objects.copy_template(own_id, own.space_id, "admin", version="a" * 32)
        assert copied.pk != own_id
        assert copied.snapshot.template_id == copied.pk
        assert copied.get_pipeline_tree_by_version(copied.version) == copied.pipeline_tree
        assert Template.objects.get(pk=own_id).get_pipeline_tree_by_version("a" * 32)


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("serializer_class", [CreateTemplateSerializer, UpdateTemplateSerializer])
def test_apigw_save_checks_converted_subprocess_reference(templates, enabled, serializer_class):
    """网关实际序列化入口检查转换后的子流程，单租户旧保存仍可用。"""
    own, other = templates
    tree = build_default_pipeline_tree()
    next(iter(tree["activities"].values()))["component"] = reference_tree(other.pk, converted=True)["activities"][
        "ref"
    ]["component"]
    serializer = serializer_class(
        data={"name": "nested", "pipeline_tree": tree},
        context={"space_id": own.space_id, "request": SimpleNamespace(user=SimpleNamespace(username="admin"))},
    )
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled):
        assert serializer.is_valid() is (not enabled), serializer.errors
        if enabled:
            assert "空间" in str(serializer.errors)


@pytest.mark.parametrize("enabled", [False, True])
def test_debug_and_persisted_tree_recheck_existing_references(templates, enabled):
    """旧流程和调试临时树都重新检查归属，单租户保留旧引用。"""
    own, other = templates
    tree = reference_tree(other.pk, converted=True, nested=True)
    TemplateSnapshot.objects.filter(pk=own.snapshot_id).update(data=tree)
    service = DebugService(own.pk, space_id=own.space_id, pipeline_tree=tree)
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled):
        for source in (own, service):
            if enabled:
                with pytest.raises(ValidationError):
                    _ = source.pipeline_tree
            else:
                assert source.pipeline_tree == tree


@pytest.mark.parametrize("enabled", [False, True])
def test_snapshot_version_belongs_to_template(templates, enabled):
    """旧 MD5 仍能读取本模板历史版本，但不能读取另一个模板的内容。"""
    own, other = templates
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled):
        assert own.get_pipeline_tree_by_version("a" * 32) == own.pipeline_tree
        with pytest.raises(FlowValidationError):
            own.get_pipeline_tree_by_version("b" * 32)
        # 两个模板内容相同也必须使用各自的版本号。
        TemplateSnapshot.objects.create(template_id=other.pk, md5sum="a" * 32, version="9.0.0", data={})
        tree = replace_subprocess_version(reference_tree(own.pk), True)
        assert tree["activities"]["ref"]["version"] == "1.0.0"


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("semantic_version", [False, True])
def test_current_legacy_snapshot_with_blank_owner_is_still_readable(templates, enabled, semantic_version):
    """兼容旧当前快照的空归属；未知历史快照或明确属于他人的快照仍拒绝。"""
    own, other = templates
    TemplateSnapshot.objects.filter(pk__in=[own.snapshot_id, other.snapshot_id]).update(template_id=None)
    TemplateSnapshot.objects.filter(pk=other.snapshot_id).update(version="9.0.0")
    own_version = "1.0.0" if semantic_version else "a" * 32
    other_version = "9.0.0" if semantic_version else "b" * 32
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled), patch.object(
        own, "validate_space", return_value=semantic_version
    ):
        assert own.get_pipeline_tree_by_version(own_version) == own.pipeline_tree
        with pytest.raises(FlowValidationError):
            own.get_pipeline_tree_by_version(other_version)
        TemplateSnapshot.objects.filter(pk=own.snapshot_id).update(template_id=other.pk)
        with pytest.raises(FlowValidationError):
            own.get_pipeline_tree_by_version(own_version)


@pytest.mark.parametrize("enabled", [False, True])
@override_settings(BLOCK_ADMIN_PERMISSION=False)
def test_public_preview_cannot_read_foreign_snapshot(templates, enabled):
    """通过真实预览入口拒绝串用快照，正常历史预览仍可用。"""
    own, other = templates
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled):
        for template, expected in ((own, True), (other, False)):
            response = invoke(
                TemplateViewSet,
                "preview_task_tree",
                {
                    "appoint_node_ids": list(template.pipeline_tree["activities"]),
                    "is_draft": False,
                    "version": template.snapshot.md5sum,
                },
                "post",
                pk=own.pk,
            )
            assert response.data["result"] is expected, response.data
            assert "PRIVATE_NODE_b" not in str(response.data)


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("scope", ["own", "other", "absent"])
@override_settings(BLOCK_ADMIN_PERMISSION=False)
def test_internal_template_read_space_and_legacy_request(templates, enabled, scope):
    """旧 Engine 无空间参数可继续工作；多租户调用必须绑定父任务空间。"""
    own, other = templates
    params = {} if scope == "absent" else {"space_id": own.space_id if scope == "own" else other.space_id}
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled), patch(
        "bkflow.template.serializers.template.get_webhook_configs", return_value=[]
    ):
        response = invoke(TemplateInternalViewSet, "get_template_data", params, internal=True, pk=own.pk)
    assert response.data["result"] is (not enabled or scope == "own"), response.data


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize(
    "action,method",
    [
        ("list", "get"),
        ("retrieve", "get"),
        ("create", "post"),
        ("partial_update", "patch"),
        ("destroy", "delete"),
        ("get_meta", "get"),
    ],
)
@override_settings(BLOCK_ADMIN_PERMISSION=False)
def test_module_admin_single_mode_retains_crud(templates, enabled, action, method):
    """单租户管理功能保持可用，多租户所有管理动作均不暴露部署凭证。"""
    payload = {
        "space_id": templates[0].space_id,
        "code": "engine",
        "url": "https://example.invalid/",
        "token": "test-engine-credential",
        "type": "TASK",
        "isolation_level": "only_calculation",
    }
    module = ModuleInfo.objects.create(**payload)
    create_data = {**payload, "code": "new-engine", "space_id": templates[1].space_id}
    data = create_data if action == "create" else {"token": "updated-test-token"}
    kwargs = {"pk": module.pk} if action in ("retrieve", "partial_update", "destroy") else {}
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled):
        response = invoke(ModuleInfoAdminViewSet, action, data, method, **kwargs)
    if enabled:
        assert response.status_code == 403 or response.data.get("result") is False, response.data
        assert "test-engine-credential" not in str(response.data)
        module.refresh_from_db()
        assert module.token == payload["token"]
        assert ModuleInfo.objects.count() == 1
    else:
        assert 200 <= response.status_code < 300, response.data
        if action == "retrieve":
            assert "test-engine-credential" in str(response.data)
        if action == "partial_update":
            module.refresh_from_db()
            assert module.token == "updated-test-token"
