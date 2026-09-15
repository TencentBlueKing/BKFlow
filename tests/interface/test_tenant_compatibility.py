"""Interface 租户升级：入口、旧审批与空间回填。"""

import io
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, override_settings

from bkflow.apigw.serializers.space import CreateSpaceSerializer
from bkflow.interface.itsm.itsm import itsm_approve, itsm_approve_new
from bkflow.space.models import Space


@pytest.mark.django_db
@pytest.mark.parametrize("enabled", [False, True])
def test_space_legacy_request(enabled):
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled):
        serializer = CreateSpaceSerializer(
            data={"name": "new", "platform_url": "https://example.com", "app_code": "app"}
        )
        assert serializer.is_valid() is (not enabled)
        if enabled:
            assert "tenant_id" in serializer.errors


@pytest.mark.django_db
def test_space_backfill_preview_repeat_and_conflict(tmp_path):
    space = Space.objects.create(name="old", app_code="app", platform_url="https://example.com")
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({str(space.id): "tenant-a"}))
    args = {"mapping": str(mapping), "module": "interface", "stdout": io.StringIO()}
    call_command("backfill_tenant_ids", **args)
    space.refresh_from_db()
    assert space.tenant_id == "default"
    call_command("backfill_tenant_ids", apply=True, **args)
    call_command("backfill_tenant_ids", apply=True, **args)
    space.refresh_from_db()
    assert space.tenant_id == "tenant-a"
    mapping.write_text(json.dumps({str(space.id): "tenant-b"}))
    with pytest.raises(CommandError, match="拒绝覆盖"):
        call_command("backfill_tenant_ids", apply=True, **args)
    space.refresh_from_db()
    assert space.tenant_id == "tenant-a"


@pytest.mark.parametrize("view", [itsm_approve, itsm_approve_new])
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_old_ticket_uses_legacy_service_after_upgrade(view):
    request = RequestFactory().post(
        "/itsm_approve_new/",
        data=json.dumps({"space_id": 1, "task_id": 2, "node_id": "node", "is_passed": True, "message": ""}),
        content_type="application/json",
    )
    # Legacy users need not have a tenant attribute when their ticket only contains sn.
    request.user = SimpleNamespace(username="user")
    with patch("bkflow.interface.itsm.itsm.TaskComponentClient") as task_client, patch(
        "bkflow.interface.itsm.itsm.BKItsmClient"
    ) as legacy, patch("bkflow.interface.itsm.itsm.get_client_by_username") as modern:
        task_client.return_value.get_task_node_detail.return_value = {
            "result": True,
            "data": {"outputs": [{"key": "sn", "value": "OLD-1"}]},
        }
        legacy.return_value.get_ticket_info.return_value = {
            "result": True,
            "data": {"current_steps": [{"name": "内置审批节点", "state_id": "step"}], "fields": []},
        }
        legacy.return_value.operate_node.return_value = {"result": True}
        assert json.loads(view(request).content)["result"] is True
        legacy.return_value.get_ticket_info.assert_called_once_with("OLD-1")
        modern.assert_not_called()
        task_client.return_value.get_task_node_detail.assert_called_once()


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APIGW_STAGE_NAME="stag")
def test_new_ticket_uses_itsm4():
    request = RequestFactory().post(
        "/itsm_approve/",
        data=json.dumps({"space_id": 1, "task_id": 2, "node_id": "node", "is_passed": False, "message": "拒绝"}),
        content_type="application/json",
    )
    request.user = SimpleNamespace(username="user", tenant_id="tenant-a")
    with patch("bkflow.interface.itsm.itsm.TaskComponentClient") as tasks, patch(
        "bkflow.interface.itsm.itsm.get_client_by_username"
    ) as client:
        tasks.return_value.get_task_node_detail.return_value = {
            "result": True,
            "data": {"outputs": [{"key": "id", "value": 17}, {"key": "sn", "value": "NEW-1"}]},
        }
        client.return_value.api.ticket_detail.return_value = {
            "result": True,
            "data": {"current_processors": [{"task_id": "step"}]},
        }
        client.return_value.api.handle_approval_node.return_value = {"result": True}
        response = itsm_approve(request)
        client.assert_called_once_with(username="user", stage="stag")
        assert json.loads(response.content)["result"] is True
