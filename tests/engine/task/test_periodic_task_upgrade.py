"""Regression coverage for ordinary-dict validated data in DRF 3.15."""

import pytest
from rest_framework.test import APIRequestFactory

from bkflow.task.models import PeriodicTask
from bkflow.task.serializers import UpdatePeriodicTaskSerializer
from bkflow.task.views import PeriodicTaskViewSet


@pytest.mark.django_db
def test_update_preserves_config_and_input_keys_when_disabling():
    """更新开关不删除遍历中的键，部分配置合并后仍保留其余字段。"""
    task = PeriodicTask.objects.create_task(
        name="upgrade periodic task",
        template_id=1,
        trigger_id=987654,
        cron={"minute": "0", "hour": "*"},
        config={"tenant_id": "default", "space_id": 123, "constants": {"value": "old"}},
        creator="test",
    )
    serializer = UpdatePeriodicTaskSerializer(
        data={
            "trigger_id": 987654,
            "config": {"tenant_id": "default", "constants": {"value": "new"}},
            "is_enabled": False,
        }
    )
    assert serializer.is_valid(), serializer.errors
    original_keys = set(serializer.validated_data)
    serializer.update(task, serializer.validated_data)
    task.refresh_from_db()
    task.celery_task.refresh_from_db()
    assert task.config == {"tenant_id": "default", "space_id": 123, "constants": {"value": "new"}}
    assert task.celery_task.enabled is False
    assert set(serializer.validated_data) == original_keys
    assert serializer.validated_data["is_enabled"] is False
    assert serializer.data["config"]["space_id"] == 123
    assert serializer.data["config"]["constants"] == {"value": "new"}


@pytest.mark.django_db
@pytest.mark.parametrize("is_enabled", [False, True])
def test_partial_update_response_preserves_saved_config(is_enabled):
    """通过实际更新接口核对响应与存储中的合并配置一致。"""
    config = {
        "tenant_id": "default",
        "space_id": 123,
        "constants": {"value": "old"},
        "scope_type": "project",
        "scope_value": "fixture",
        "pipeline_tree": {"id": "fixture"},
    }
    task = PeriodicTask.objects.create_task(
        name="upgrade response regression",
        template_id=1,
        trigger_id=987655,
        cron={"minute": "0", "hour": "*"},
        config=config,
        creator="test",
    )
    request = APIRequestFactory().post(
        "/periodic_task/update/",
        {
            "trigger_id": task.trigger_id,
            "config": {"tenant_id": "default", "constants": {"value": "new"}},
            "is_enabled": is_enabled,
        },
        format="json",
        HTTP_BKFLOW_INTERNAL_SPACE_ID="123",
    )
    response = PeriodicTaskViewSet.as_view({"post": "update_task"})(request)
    assert response.status_code == 200, response.data
    expected = {**config, "constants": {"value": "new"}}
    assert response.data["data"]["config"] == expected
    assert response.data["data"]["is_enabled"] is is_enabled
    task.refresh_from_db()
    assert task.config == expected
    assert task.enabled is is_enabled
