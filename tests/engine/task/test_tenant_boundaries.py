"""Engine 模块凭证和空间边界，不访问 Interface 的数据库。"""

from types import SimpleNamespace

import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.task.models import PeriodicTask, TaskInstance
from bkflow.task.views import PeriodicTaskViewSet, TaskInstanceViewSet
from bkflow.utils.pipeline import build_default_pipeline_tree


def request(space_id, internal=True):
    header = "HTTP_" + settings.APP_INTERNAL_SPACE_ID_HEADER_KEY.upper().replace("-", "_")
    admin_header = "HTTP_" + settings.APP_INTERNAL_FROM_SUPERUSER_HEADER_KEY.upper().replace("-", "_")
    req = APIRequestFactory().get("/task/", **{header: str(space_id), admin_header: "1"})
    req.app_internal_token = settings.APP_INTERNAL_TOKEN if internal else ""
    force_authenticate(
        req, user=SimpleNamespace(username="admin", tenant_id="a", is_superuser=True, is_authenticated=True)
    )
    return req


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_engine_task_id_cannot_escape_internal_space():
    """即便带旧超级管理员标记，也不能从空间 1 读取空间 2 的任务。"""
    task = TaskInstance.objects.create_instance(space_id=2, tenant_id="b", pipeline_tree=build_default_pipeline_tree())
    response = TaskInstanceViewSet.as_view({"get": "retrieve"})(request(1), pk=task.pk)
    assert response.data["result"] is False, response.data


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_periodic_queryset_scoped_by_internal_space():
    """周期任务配置也必须绑定内部调用空间。"""
    for space_id in (1, 2):
        PeriodicTask.objects.create(
            name=str(space_id),
            template_id=space_id,
            trigger_id=space_id,
            config={"space_id": space_id, "tenant_id": str(space_id)},
            extra_info={},
        )
    view = PeriodicTaskViewSet()
    view.action = "list"
    view.request = SimpleNamespace(headers={settings.APP_INTERNAL_SPACE_ID_HEADER_KEY: "1"})
    assert list(view.get_queryset().values_list("trigger_id", flat=True)) == [1]


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_engine_rejects_direct_platform_admin_without_module_credential():
    """平台管理员必须经过 Interface 的租户授权，不能直连 Engine 绕过。"""
    response = TaskInstanceViewSet.as_view({"get": "list"})(request(1, internal=False))
    assert response.data["result"] is False
    assert "模块调用" in response.data["message"]


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_engine_admin_operation_requires_task_in_internal_space():
    from module_settings import check_engine_admin_permission

    task = TaskInstance.objects.create_instance(space_id=2, tenant_id="b", pipeline_tree=build_default_pipeline_tree())
    assert not check_engine_admin_permission(request(1), instance_id=task.instance_id)
    assert check_engine_admin_permission(request(2), instance_id=task.instance_id)
    assert not check_engine_admin_permission(request(2, internal=False), instance_id=task.instance_id)


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_periodic_config_cannot_change_internal_space():
    header = "HTTP_" + settings.APP_INTERNAL_SPACE_ID_HEADER_KEY.upper().replace("-", "_")
    req = APIRequestFactory().post("/periodic/", {"config": {"space_id": 2}}, format="json", **{header: "1"})
    req.app_internal_token = settings.APP_INTERNAL_TOKEN
    force_authenticate(req, user=SimpleNamespace(is_superuser=True, is_authenticated=True))
    response = PeriodicTaskViewSet.as_view({"post": "create"})(req)
    assert response.data["result"] is False
    assert "空间不一致" in response.data["message"]
