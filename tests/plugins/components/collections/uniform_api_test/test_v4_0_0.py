import ast
from pathlib import Path

import pytest

from bkflow.pipeline_plugins.components.collections.uniform_api.v4_0_0 import (
    UniformAPIService,
    build_open_plugin_client_request_id,
    build_open_plugin_execute_payload,
)
from bkflow.plugin.models import OpenPluginCatalogIndex, OpenPluginRunCallbackRef
from bkflow.plugin.services.open_plugin_callback import (
    callback_token_digest,
    issue_open_plugin_callback_token,
    parse_open_plugin_callback_token,
)


def test_v4_uniform_api_component_metadata():
    module_path = (
        Path(__file__).resolve().parents[5]
        / "bkflow"
        / "pipeline_plugins"
        / "components"
        / "collections"
        / "uniform_api"
        / "v4_0_0.py"
    )
    assert module_path.exists()

    module = ast.parse(module_path.read_text(encoding="utf-8"))
    component_class = next(
        node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "UniformAPIComponent"
    )

    assignments = {
        target.id: node.value.value
        for node in component_class.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant)
    }

    assert assignments["code"] == "uniform_api"
    assert assignments["version"] == "v4.0.0"


def test_build_open_plugin_client_request_id():
    assert build_open_plugin_client_request_id(task_id=1, node_id="node_a", retry_no=2) == "task-1-node-node_a-attempt-2"


def test_build_open_plugin_execute_payload():
    payload = build_open_plugin_execute_payload(
        source_key="sops",
        plugin_id="open_plugin_001",
        plugin_version="1.2.0",
        inputs={"target_ip": "127.0.0.1"},
        client_request_id="task-1-node-node_a-attempt-1",
        callback_url="https://bkflow.example/apigw/space/1/task/1/node/node_a/operate_node/callback/",
        callback_token="callback-token",
    )

    assert payload == {
        "source_key": "sops",
        "plugin_id": "open_plugin_001",
        "plugin_version": "1.2.0",
        "client_request_id": "task-1-node-node_a-attempt-1",
        "callback_url": "https://bkflow.example/apigw/space/1/task/1/node/node_a/operate_node/callback/",
        "callback_token": "callback-token",
        "inputs": {"target_ip": "127.0.0.1"},
    }


def test_issue_open_plugin_callback_token_round_trip():
    token, expire_at = issue_open_plugin_callback_token(
        task_id=1,
        node_id="node_a",
        client_request_id="task-1-node-node_a-attempt-1",
        node_version="v4.0.0",
    )

    payload = parse_open_plugin_callback_token(token)

    assert payload["task_id"] == 1
    assert payload["node_id"] == "node_a"
    assert payload["node_version"] == "v4.0.0"
    assert payload["client_request_id"] == "task-1-node-node_a-attempt-1"
    assert payload["expire_at"] == expire_at.isoformat()


@pytest.mark.django_db
def test_resolve_open_plugin_source_key_from_catalog():
    OpenPluginCatalogIndex.objects.create(
        space_id=1,
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

    assert UniformAPIService._resolve_open_plugin_source_key(space_id=1, plugin_id="open_plugin_001") == "sops"


@pytest.mark.django_db
def test_upsert_open_plugin_callback_ref():
    token, expire_at = issue_open_plugin_callback_token(
        task_id=1,
        node_id="node_a",
        client_request_id="task-1-node-node_a-attempt-1",
        node_version="v4.0.0",
    )

    UniformAPIService._upsert_open_plugin_callback_ref(
        task_id=1,
        node_id="node_a",
        node_version="v4.0.0",
        client_request_id="task-1-node-node_a-attempt-1",
        open_plugin_run_id="run-001",
        callback_token=token,
        callback_expire_at=expire_at,
        plugin_source="builtin",
        source_key="sops",
        plugin_id="open_plugin_001",
        plugin_version="1.2.0",
        cancel_url="https://bk-sops.example/open-plugin-runs/run-001/cancel",
        credential_key="default",
    )

    callback_ref = OpenPluginRunCallbackRef.objects.get(client_request_id="task-1-node-node_a-attempt-1")
    assert callback_ref.open_plugin_run_id == "run-001"
    assert callback_ref.callback_token_digest == callback_token_digest(token)
    assert callback_ref.plugin_id == "open_plugin_001"
    assert callback_ref.source_key == "sops"
    assert callback_ref.cancel_url == "https://bk-sops.example/open-plugin-runs/run-001/cancel"
    assert callback_ref.credential_key == "default"
