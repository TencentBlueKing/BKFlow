"""Regression coverage for ordinary-dict validated data in DRF 3.15."""

import copy

import pytest

from bkflow.task.models import PeriodicTask
from bkflow.task.serializers import UpdatePeriodicTaskSerializer


@pytest.mark.django_db
def test_update_preserves_config_and_validated_data_when_disabling():
    """Updating the enabled flag must neither mutate iteration input nor replace unrelated config."""
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
    original = copy.deepcopy(serializer.validated_data)
    serializer.update(task, serializer.validated_data)
    task.refresh_from_db()
    task.celery_task.refresh_from_db()
    assert task.config == {"tenant_id": "default", "space_id": 123, "constants": {"value": "new"}}
    assert task.celery_task.enabled is False
    assert serializer.validated_data == original
