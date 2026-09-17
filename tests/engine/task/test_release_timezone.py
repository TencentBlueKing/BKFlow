"""周期计划保存显式时区，编辑时兼容没有时区字段的历史调用。"""

import pytest
from django.test import override_settings
from django.utils import timezone

from bkflow.task.models import PeriodicTask
from bkflow.task.serializers import (
    CreatePeriodicTaskSerializer,
    UpdatePeriodicTaskSerializer,
)


@pytest.mark.django_db
@pytest.mark.parametrize("zone", ["Europe/Paris", "Asia/Tokyo"])
def test_schedule_timezone_persists_across_editors(zone):
    cron = {"minute": "0", "hour": "9", "day_of_week": "*", "day_of_month": "*", "month_of_year": "*"}
    task = PeriodicTask.objects.create_task("daily", 1, 1, {**cron, "timezone": zone}, {}, "u")
    assert str(task.celery_task.crontab.timezone) == zone
    with timezone.override("America/New_York"):
        task.modify_cron({**cron, "hour": "10"})
    task.refresh_from_db()
    assert str(task.celery_task.crontab.timezone) == zone
    assert task.celery_task.crontab.hour == "10"


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Shanghai")
def test_legacy_schedule_keeps_deployment_timezone():
    cron = {"minute": "0", "hour": "9", "day_of_week": "*", "day_of_month": "*", "month_of_year": "*"}
    with timezone.override("Europe/Paris"):
        task = PeriodicTask.objects.create_task("legacy", 1, 2, cron, {}, "u")
    assert str(task.celery_task.crontab.timezone) == "Asia/Shanghai"


@pytest.mark.parametrize("serializer_type", [CreatePeriodicTaskSerializer, UpdatePeriodicTaskSerializer])
def test_invalid_schedule_timezone_is_rejected(serializer_type):
    from rest_framework.exceptions import ValidationError

    with pytest.raises(ValidationError):
        serializer_type().validate_cron({"timezone": "bad"})
