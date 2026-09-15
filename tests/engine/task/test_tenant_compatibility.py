"""Engine 只依赖自己的数据库完成回填和旧上下文兼容。"""

import io
import json
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from pipeline.core.data.base import DataObject

from bkflow.task.celery.tasks import bkflow_periodic_task_start
from bkflow.task.models import PeriodicTask, TaskInstance
from bkflow.task.serializers import PeriodicTaskConfigSerializer
from bkflow.utils.pipeline import build_default_pipeline_tree
from bkflow.utils.tenant import get_task_tenant_id


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_engine_backfill_is_idempotent_and_keeps_config(tmp_path):
    task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
    periodic = PeriodicTask.objects.create(
        name="old", template_id=1, trigger_id=1, config={"space_id": 1, "constants": {"x": "keep"}}, extra_info={}
    )
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"1": "tenant-a"}))
    args = {"mapping": str(mapping), "module": "engine", "stdout": io.StringIO()}
    call_command("backfill_tenant_ids", **args)
    task.refresh_from_db()
    periodic.refresh_from_db()
    assert task.tenant_id == "default"
    assert "tenant_id" not in periodic.config
    call_command("backfill_tenant_ids", apply=True, **args)
    call_command("backfill_tenant_ids", apply=True, **args)
    task.refresh_from_db()
    periodic.refresh_from_db()
    assert task.tenant_id == "tenant-a"
    assert periodic.config == {"space_id": 1, "constants": {"x": "keep"}, "tenant_id": "tenant-a"}
    assert get_task_tenant_id(DataObject(inputs={"task_id": task.id})) == "tenant-a"
    # Explicit new contexts keep their own tenant and do not require DB lookups.
    assert get_task_tenant_id(DataObject(inputs={"tenant_id": "tenant-b"})) == "tenant-b"
    mapping.write_text(json.dumps({"1": "tenant-b"}))
    with pytest.raises(CommandError, match="拒绝覆盖"):
        call_command("backfill_tenant_ids", apply=True, **args)


@pytest.mark.parametrize("enabled", [False, True])
def test_periodic_config_requires_tenant_only_in_multi_mode(enabled):
    with override_settings(ENABLE_MULTI_TENANT_MODE=enabled):
        serializer = PeriodicTaskConfigSerializer(data={"space_id": 1})
        assert serializer.is_valid() is (not enabled)


@pytest.mark.django_db
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_old_periodic_resolves_tenant_via_interface():
    tree = build_default_pipeline_tree()
    periodic = PeriodicTask.objects.create(
        name="old", creator="user", template_id=1, trigger_id=1, config={"space_id": 1}, extra_info={}
    )
    with patch("bkflow.task.celery.tasks.InterfaceModuleClient") as interface, patch(
        "bkflow.task.celery.tasks.TaskOperation"
    ) as operation, patch("bkflow.task.celery.tasks.prepare_engine_task_extra_info", return_value={}):
        interface.return_value.get_template_data.return_value = {"result": True, "data": {"pipeline_tree": tree}}
        interface.return_value.get_space_infos.return_value = {"result": True, "data": {"tenant_id": "tenant-a"}}
        operation.return_value.start.return_value = MagicMock(result=True, message="")
        bkflow_periodic_task_start(periodic_task_id=periodic.id)
        assert TaskInstance.objects.get(space_id=1).tenant_id == "tenant-a"
        interface.return_value.get_space_infos.assert_called_once_with(data={"space_id": 1, "include_tenant": "1"})


@pytest.mark.django_db
def test_nested_subtasks_inherit_tenant_and_preserve_snapshots():
    from bkflow.pipeline_plugins.components.collections.base import LoopBaseService

    parent = TaskInstance.objects.create_instance(
        space_id=1, tenant_id="tenant-a", creator="user", pipeline_tree=build_default_pipeline_tree()
    )
    service = LoopBaseService()
    service.id, service.version = "node", "v1.0.0"
    with patch("bkflow.pipeline_plugins.components.collections.base.InterfaceModuleClient") as interface:
        interface.return_value.prepare_task_extra_info.return_value = {
            "result": True,
            "data": {"extra_info": {"open_plugin_snapshot_marker": "preserved"}},
        }
        child = service._create_subprocess_task_instance("child", build_default_pipeline_tree(), parent, "subprocess")
        grandchild = service._create_subprocess_task_instance(
            "grandchild", build_default_pipeline_tree(), child, "subprocess"
        )
        assert child.tenant_id == grandchild.tenant_id == "tenant-a"
        assert child.extra_info["open_plugin_snapshot_marker"] == "preserved"


@override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APIGW_STAGE_NAME="stage")
def test_itsm4_execution_preserves_tenant_and_ticket_id():
    from bkflow.pipeline_plugins.components.collections.approve.v1_0 import (
        ApproveService,
    )

    data = DataObject(inputs={"bk_verifier": "a, b", "bk_approve_title": "title", "bk_approve_content": "content"})
    parent = DataObject(inputs={"executor": "user", "tenant_id": "tenant-a", "task_space_id": 1, "task_id": 2})
    service = ApproveService()
    service.id = "node"
    with patch("bkflow.pipeline_plugins.components.collections.approve.v1_0.get_client_by_username") as client, patch(
        "bkflow.pipeline_plugins.components.collections.approve.v1_0.get_node_callback_url",
        return_value="https://example.com/callback",
    ), patch("bkflow.task.celery.tasks.send_task_message.delay"):
        client.return_value.api.create_ticket.return_value = {"result": True, "data": {"sn": "NEW-1", "id": 17}}
        assert service.plugin_execute(data, parent) is True
        assert data.outputs.sn == "NEW-1"
        assert data.outputs.id == 17
        kwargs = client.return_value.api.create_ticket.call_args
        assert kwargs.kwargs["headers"]["X-Bk-Tenant-Id"] == "tenant-a"
        assert kwargs.args[0]["workflow_key"].startswith("tenant-a_")
