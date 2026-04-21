import io
from copy import deepcopy
from unittest.mock import patch

import pytest
from django.core.management import call_command

from bkflow.plugin.models import OpenPluginCatalogIndex, SpaceOpenPluginAvailability
from bkflow.plugin.services.open_plugin_snapshot import OpenPluginSnapshotService
from bkflow.space.models import Space
from bkflow.template.models import Template, TemplateSnapshot


def build_open_plugin_pipeline_tree(plugin_id="open_plugin_001", plugin_version="1.2.0", source_key="sops"):
    return {
        "id": "pipeline_001",
        "start_event": {
            "id": "start_event",
            "type": "EmptyStartEvent",
            "incoming": "",
            "outgoing": "flow1",
            "name": "",
        },
        "end_event": {
            "id": "end_event",
            "type": "EmptyEndEvent",
            "incoming": ["flow2"],
            "outgoing": "",
            "name": "",
        },
        "activities": {
            "node1": {
                "id": "node1",
                "type": "ServiceActivity",
                "name": "开放插件节点",
                "incoming": ["flow1"],
                "outgoing": "flow2",
                "component": {
                    "code": "uniform_api",
                    "version": "",
                    "api_meta": {"source_key": source_key},
                    "data": {
                        "uniform_api_plugin_id": {"value": plugin_id},
                        "uniform_api_plugin_version": {"value": plugin_version},
                    },
                    "inputs": {},
                },
                "optional": False,
                "skippable": True,
                "retryable": True,
                "error_ignorable": False,
                "timeout": None,
            }
        },
        "flows": {
            "flow1": {"id": "flow1", "source": "start_event", "target": "node1", "is_default": False},
            "flow2": {"id": "flow2", "source": "node1", "target": "end_event", "is_default": False},
        },
        "gateways": {},
        "constants": {},
        "outputs": [],
    }


@pytest.mark.django_db
def test_get_snapshot_node_statuses_marks_missing_catalog_as_unavailable():
    extra_info = {
        OpenPluginSnapshotService.REFERENCE_SNAPSHOT_KEY: [
            {
                "node_id": "node1",
                "plugin_id": "missing_plugin",
                "plugin_code": "job_execute_task",
                "plugin_name": "JOB 执行作业",
                "plugin_source": "builtin",
                "source_key": "sops",
                "plugin_version": "1.2.0",
                "wrapper_version": "v4.0.0",
            }
        ]
    }

    statuses = OpenPluginSnapshotService.get_snapshot_node_statuses(space_id=1, extra_info=extra_info)

    assert statuses == {"node1": OpenPluginCatalogIndex.Status.UNAVAILABLE}


@pytest.mark.django_db
@patch("bkflow.plugin.services.open_plugin_snapshot.OpenPluginSnapshotService.build_schema_snapshot")
def test_backfill_open_plugin_snapshots_fills_missing_fields_without_overwriting_existing(mock_build_schema_snapshot):
    space = Space.objects.create(name="test", app_code="test")
    pipeline_tree = build_open_plugin_pipeline_tree()

    OpenPluginCatalogIndex.objects.create(
        space_id=space.id,
        source_key="sops",
        plugin_id="open_plugin_001",
        plugin_code="job_execute_task",
        plugin_name="JOB 执行作业",
        plugin_source="builtin",
        group_name="作业平台",
        wrapper_version="v4.0.0",
        default_version="1.2.0",
        latest_version="1.2.0",
        versions=["1.2.0"],
        meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
        status="available",
    )
    SpaceOpenPluginAvailability.objects.create(space_id=space.id, source_key="sops", plugin_id="open_plugin_001", enabled=True)

    mock_build_schema_snapshot.return_value = {
        "node1": {
            "schema_protocol_version": OpenPluginSnapshotService.SCHEMA_PROTOCOL_VERSION,
            "plugin_id": "open_plugin_001",
            "plugin_code": "job_execute_task",
            "plugin_source": "builtin",
            "plugin_version": "1.2.0",
            "wrapper_version": "v4.0.0",
            "inputs": [],
            "outputs": [],
            "description": "schema from remote",
        }
    }

    existing_snapshot = {
        OpenPluginSnapshotService.REFERENCE_SNAPSHOT_KEY: [
            {
                "node_id": "node1",
                "plugin_id": "open_plugin_001",
                "plugin_code": "job_execute_task",
                "plugin_name": "JOB 执行作业",
                "plugin_source": "builtin",
                "source_key": "sops",
                "plugin_version": "1.2.0",
                "wrapper_version": "v4.0.0",
            }
        ],
        OpenPluginSnapshotService.SCHEMA_SNAPSHOT_KEY: {
            "node1": {
                "schema_protocol_version": OpenPluginSnapshotService.SCHEMA_PROTOCOL_VERSION,
                "plugin_id": "open_plugin_001",
                "plugin_code": "job_execute_task",
                "plugin_source": "builtin",
                "plugin_version": "1.2.0",
                "wrapper_version": "v4.0.0",
                "inputs": [],
                "outputs": [],
                "description": "keep-me",
            }
        },
    }
    template_snapshot = TemplateSnapshot.create_snapshot(pipeline_tree, "admin", "1.0.0")
    template = Template.objects.create(
        name="template-with-snapshot",
        space_id=space.id,
        snapshot_id=template_snapshot.id,
        creator="admin",
        updated_by="admin",
        extra_info=deepcopy(existing_snapshot),
    )
    template_snapshot.template_id = template.id
    template_snapshot.save(update_fields=["template_id"])

    missing_wrapper_snapshot = {
        OpenPluginSnapshotService.REFERENCE_SNAPSHOT_KEY: [
            {
                "node_id": "node1",
                "plugin_id": "open_plugin_001",
                "plugin_code": "job_execute_task",
                "plugin_name": "JOB 执行作业",
                "plugin_source": "builtin",
                "source_key": "sops",
                "plugin_version": "1.2.0",
                "wrapper_version": "",
            }
        ],
        OpenPluginSnapshotService.SCHEMA_SNAPSHOT_KEY: {
            "node1": {
                "schema_protocol_version": OpenPluginSnapshotService.SCHEMA_PROTOCOL_VERSION,
                "plugin_id": "open_plugin_001",
                "plugin_code": "job_execute_task",
                "plugin_source": "builtin",
                "plugin_version": "1.2.0",
                "wrapper_version": "",
                "inputs": [],
                "outputs": [],
                "description": "keep-schema",
            }
        },
    }
    missing_wrapper_template_snapshot = TemplateSnapshot.create_snapshot(pipeline_tree, "admin", "1.0.0")
    missing_wrapper_template = Template.objects.create(
        name="template-missing-wrapper",
        space_id=space.id,
        snapshot_id=missing_wrapper_template_snapshot.id,
        creator="admin",
        updated_by="admin",
        extra_info=deepcopy(missing_wrapper_snapshot),
    )
    missing_wrapper_template_snapshot.template_id = missing_wrapper_template.id
    missing_wrapper_template_snapshot.save(update_fields=["template_id"])

    dry_run_stdout = io.StringIO()
    call_command("backfill_open_plugin_snapshots", "--space-id", str(space.id), "--dry-run", stdout=dry_run_stdout)

    template.refresh_from_db()
    missing_wrapper_template.refresh_from_db()
    assert template.extra_info == existing_snapshot
    assert missing_wrapper_template.extra_info == missing_wrapper_snapshot
    assert "dry-run" in dry_run_stdout.getvalue().lower()

    execute_stdout = io.StringIO()
    call_command("backfill_open_plugin_snapshots", "--space-id", str(space.id), stdout=execute_stdout)

    template.refresh_from_db()
    missing_wrapper_template.refresh_from_db()

    assert template.extra_info == existing_snapshot
    assert (
        missing_wrapper_template.extra_info[OpenPluginSnapshotService.REFERENCE_SNAPSHOT_KEY][0]["wrapper_version"]
        == "v4.0.0"
    )
    assert (
        missing_wrapper_template.extra_info[OpenPluginSnapshotService.SCHEMA_SNAPSHOT_KEY]["node1"]["wrapper_version"]
        == "v4.0.0"
    )
    assert (
        missing_wrapper_template.extra_info[OpenPluginSnapshotService.SCHEMA_SNAPSHOT_KEY]["node1"]["description"]
        == "keep-schema"
    )
    assert "updated_templates=1" in execute_stdout.getvalue()
    assert "updated_tasks=0" in execute_stdout.getvalue()
