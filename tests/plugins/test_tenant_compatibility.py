"""跨升级兼容测试：使用插件真实方法，外部服务全部替身。"""

import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from pipeline.core.data.base import DataObject
from rest_framework import serializers

from bkflow.pipeline_plugins.components.collections.approve.v1_0 import ApproveService
from bkflow.pipeline_plugins.components.collections.notify.v1_0 import NotifyService
from bkflow.pipeline_plugins.components.collections.sleep_time.legacy import (
    SleepTimerService,
)
from bkflow.utils.message import send_message
from bkflow.utils.tenant import TenantIDField
from bkflow.utils.time_zone import get_user_timezone


@pytest.mark.parametrize("value", [0, 10, "60"])
def test_timer_seconds(value):
    data = DataObject(inputs={"bk_timing": value, "force_check": True})
    before = datetime.datetime.now(datetime.timezone.utc)
    service = SleepTimerService()
    service.logger = MagicMock()
    assert service.plugin_execute(data, DataObject(inputs={})) is True
    delay = (data.outputs.timing_time - before).total_seconds()
    assert int(value) <= delay < int(value) + 2


@pytest.mark.parametrize("offset", ["+0800", "-0500"])
def test_timer_signed_timezone(offset):
    data = DataObject(inputs={"bk_timing": "2099-01-01 00:00:00" + offset, "force_check": True})
    service = SleepTimerService()
    service.logger = MagicMock()
    assert service.plugin_execute(data, DataObject(inputs={})) is True
    assert data.outputs.timing_time.strftime("%z") == offset


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("approved,block,expected", [(True, True, True), (False, True, False), (False, False, True)])
def test_approval_old_and_new_callbacks(nested, approved, block, expected):
    callback = {"approve_result": approved}
    if nested:
        callback = {"ticket": callback}
    data = DataObject(inputs={"rejected_block": block})
    assert ApproveService().plugin_schedule(data, DataObject(inputs={}), callback) is expected
    assert data.outputs.approve_result == ("通过" if approved else "拒绝")


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APIGW_STAGE_NAME="stage")
@pytest.mark.parametrize("response", [{"result": False, "message": "denied"}, None, RuntimeError("unavailable")])
def test_notification_failure_keeps_error(response):
    result = ("v1_send_email", {}, response)
    with patch("bkflow.utils.message.get_client_by_username"), patch(
        "bkflow.utils.message.send_cmsi_message",
        side_effect=response if isinstance(response, Exception) else None,
        return_value=result,
    ):
        failed, message = send_message("user", ["mail"], "receiver", "title", "body", "tenant-a")
        assert failed is True
        assert message


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APIGW_STAGE_NAME="stage")
def test_notification_partial_failure_and_plugin_result():
    inputs = {
        "bk_notify_types": ["mail", "voice"],
        "bk_notify_receivers": "a,b",
        "notify_executor": False,
        "bk_notify_title": "title",
        "bk_notify_content": "body",
    }
    data = DataObject(inputs=inputs)
    with patch("bkflow.utils.message.get_client_by_username"), patch(
        "bkflow.utils.message.send_cmsi_message",
        side_effect=[
            ("v1_send_email", {}, {"result": False, "message": "denied"}),
            ("v1_send_voice", {}, {"result": True}),
        ],
    ) as sender:
        assert NotifyService().plugin_execute(data, DataObject(inputs={"executor": "user", "tenant_id": "t1"})) is False
        assert "denied" in data.outputs.ex_data
        assert sender.call_count == 2
        assert sender.call_args.kwargs["tenant_id"] == "t1"


@pytest.mark.parametrize("enabled", [False, True])
def test_tenant_field_old_request_mode(enabled):
    class InputSerializer(serializers.Serializer):
        tenant_id = TenantIDField(required=True)

    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled):
        serializer = InputSerializer(data={})
        assert serializer.is_valid() is (not enabled)
        if not enabled:
            assert serializer.validated_data["tenant_id"] == "default"
        supplied = InputSerializer(data={"tenant_id": "tenant-a"})
        assert supplied.is_valid()
        assert supplied.validated_data["tenant_id"] == "tenant-a"
        invalid = InputSerializer(data={"tenant_id": ""})
        assert not invalid.is_valid()


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
def test_legacy_timezone_avoids_user_service():
    request = SimpleNamespace(headers={}, user=SimpleNamespace(username="old_user"))
    with patch("bkflow.utils.time_zone.get_client_by_request") as client:
        assert get_user_timezone(request)
        client.assert_not_called()
