import ast
from pathlib import Path
from types import SimpleNamespace

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
    assert (
        build_open_plugin_client_request_id(task_id=1, node_id="node_a", retry_no=2) == "task-1-node-node_a-attempt-2"
    )


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


def test_build_open_plugin_execute_payload_with_context():
    """execute payload 支持向后兼容地透传业务 context。"""

    payload = build_open_plugin_execute_payload(
        source_key="sops",
        plugin_id="builtin__job_execute_task",
        plugin_version="legacy",
        inputs={"target_ip": "127.0.0.1"},
        client_request_id="task-1-node-node_a-attempt-1",
        callback_url="https://bkflow.example/apigw/space/1/task/1/node/node_a/operate_node/callback/",
        callback_token="callback-token",
        context={"scope_type": "biz", "scope_value": "2", "operator": "zhangsan", "space_id": 10},
    )

    assert payload["context"] == {
        "scope_type": "biz",
        "scope_value": "2",
        "operator": "zhangsan",
        "space_id": 10,
    }
    assert payload["inputs"] == {"target_ip": "127.0.0.1"}


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


class AttrDict(dict):
    """支持属性访问的测试数据容器。"""

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)

    def __setattr__(self, key, value):
        self[key] = value


class FakeData:
    """覆盖 uniform_api open-plugin 分支所需的最小 DataObject 行为。"""

    def __init__(self, inputs):
        self.inputs = AttrDict(inputs)
        self.outputs = AttrDict()

    def get_one_of_inputs(self, key, default=None):
        return self.inputs.get(key, default)

    def get_one_of_outputs(self, key, default=None):
        return self.outputs.get(key, default)

    def set_outputs(self, key, value):
        self.outputs[key] = value


class FakeParentData:
    """覆盖 uniform_api 读取父任务上下文的最小 parent_data 行为。"""

    def __init__(self, inputs):
        self.inputs = inputs

    def get_one_of_inputs(self, key, default=None):
        return self.inputs.get(key, default)


def test_open_plugin_execute_branch_passes_runtime_context(monkeypatch, settings):
    """开放插件 execute 分支把运行时 scope/operator 透传给标准运维。"""

    settings.BKAPP_API_PLUGIN_REQUEST_TIMEOUT = 30
    captured = {}

    class FakeInterfaceClient:
        def get_space_infos(self, params):
            return {"result": True, "data": {"configs": {"uniform_api": {}}}}

    class FakeUniformAPIClient:
        def gen_default_apigw_header(self, app_code, app_secret, username):
            return {"X-Bkapi-Authorization": username}

        def request(self, url, method, data, headers, timeout):
            captured["url"] = url
            captured["method"] = method
            captured["data"] = data
            captured["headers"] = headers
            return SimpleNamespace(
                resp=SimpleNamespace(status_code=200),
                json_resp={"result": True, "data": {"open_plugin_run_id": "run-001", "status": "RUNNING"}},
            )

    monkeypatch.setattr(
        "bkflow.pipeline_plugins.components.collections.uniform_api.v4_0_0.InterfaceModuleClient",
        lambda: FakeInterfaceClient(),
    )
    monkeypatch.setattr(
        "bkflow.pipeline_plugins.components.collections.uniform_api.v4_0_0.UniformAPIClient",
        lambda: FakeUniformAPIClient(),
    )
    monkeypatch.setattr(
        "bkflow.pipeline_plugins.components.collections.uniform_api.v4_0_0.UniformAPIConfigHandler",
        lambda config: SimpleNamespace(
            handle=lambda: SimpleNamespace(
                exclude_none_fields=False,
                enable_api_parameter_conversion=False,
                enable_standard_response=False,
                api={},
            )
        ),
    )
    monkeypatch.setattr(
        "bkflow.pipeline_plugins.components.collections.uniform_api.v4_0_0.issue_open_plugin_callback_token",
        lambda **kwargs: ("callback-token", None),
    )

    service = UniformAPIService()
    service.id = "node_a"
    service._get_credential = lambda *args, **kwargs: ("app-code", "app-secret")
    service._check_response_success = lambda request_result, enable_standard_response: (True, "")
    service._upsert_open_plugin_callback_ref = lambda **kwargs: None

    data = FakeData(
        {
            "uniform_api_plugin_url": "https://bk-sops.example/apigw/plugin-gateway/runs/",
            "uniform_api_plugin_method": "post",
            "uniform_api_plugin_id": "builtin__job_execute_task",
            "uniform_api_plugin_version": "legacy",
            "uniform_api_plugin_source_key": "sops",
            "uniform_api_plugin_polling": {"url": "https://bk-sops.example/apigw/plugin-gateway/runs/status/"},
            "target_ip": "127.0.0.1",
        }
    )
    parent_data = FakeParentData(
        {
            "operator": "zhangsan",
            "task_space_id": 10,
            "task_scope_type": "biz",
            "task_scope_value": "2",
            "task_id": 123,
            "task_name": "全量插件联调",
        }
    )

    assert service._dispatch_schedule_trigger(data, parent_data) is True
    assert captured["data"]["context"] == {
        "scope_type": "biz",
        "scope_value": "2",
        "operator": "zhangsan",
        "space_id": 10,
        "task_id": 123,
        "node_id": "node_a",
        "task_name": "全量插件联调",
    }
    assert captured["data"]["inputs"] == {"target_ip": "127.0.0.1"}


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
