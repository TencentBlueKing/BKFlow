import ast
from pathlib import Path
from types import SimpleNamespace

from bkflow.pipeline_plugins.components.collections.uniform_api.v4_0_0 import (
    UniformAPIService,
    build_open_plugin_client_request_id,
    build_open_plugin_execute_payload,
)
from bkflow.task.open_plugin_callback import (
    build_open_plugin_callback_url,
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


def test_build_open_plugin_callback_url_uses_direct_internal_endpoint(settings):
    callback_url = build_open_plugin_callback_url(space_id=10, task_id=123, node_id="node_a")

    assert callback_url.endswith("open_plugin_callback/space/10/task/123/node/node_a/")
    assert "/apigw/" not in callback_url


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


def test_open_plugin_sync_success_finishes_without_polling():
    service = UniformAPIService()
    data = FakeData({})

    result = service._handle_open_plugin_status(
        data=data,
        status_data={"status": "SUCCEEDED", "outputs": {"value": "done"}},
        polling={"url": "https://bk-sops.example/runs/status/"},
        log_prefix="[uniform_api]",
    )

    assert result is True
    assert service.is_schedule_finished() is True
    assert data.outputs.data == {"value": "done"}
    assert data.outputs.get("need_polling", False) is False


def test_open_plugin_waiting_callback_keeps_polling_fallback():
    service = UniformAPIService()
    original_interval = service.interval
    data = FakeData({})

    result = service._handle_open_plugin_status(
        data=data,
        status_data={"status": "WAITING_CALLBACK"},
        polling={"url": "https://bk-sops.example/runs/status/"},
        log_prefix="[uniform_api polling]",
    )

    assert result is True
    assert service.interval is original_interval
    assert service.is_schedule_finished() is False
    assert data.outputs.need_callback is True
    assert data.outputs.need_polling is True


def test_open_plugin_schedule_prefers_callback_data_and_otherwise_polls():
    service = UniformAPIService()
    data = FakeData({"uniform_api_plugin_id": "builtin__job_execute_task"})
    data.outputs.need_callback = True
    data.outputs.need_polling = True
    parent_data = FakeParentData({})
    dispatched = []
    service._dispatch_schedule_callback = lambda *args, **kwargs: dispatched.append("callback") or True
    service._dispatch_schedule_polling = lambda *args, **kwargs: dispatched.append("polling") or True

    assert service.plugin_schedule(data, parent_data, callback_data=None) is True
    assert service.plugin_schedule(data, parent_data, callback_data={"status": "SUCCEEDED"}) is True
    assert dispatched == ["polling", "callback"]


def test_open_plugin_standard_callback_finishes_with_outputs():
    service = UniformAPIService()
    data = FakeData({"uniform_api_plugin_id": "builtin__job_execute_task"})

    result = service._dispatch_schedule_callback(
        data,
        FakeParentData({}),
        callback_data={"status": "SUCCEEDED", "outputs": {"value": "callback-done"}},
    )

    assert result is True
    assert service.is_schedule_finished() is True
    assert data.outputs.data == {"value": "callback-done"}


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


def test_resolve_open_plugin_source_key_uses_saved_hidden_field_only():
    assert (
        UniformAPIService._resolve_open_plugin_source_key(
            space_id=1, plugin_id="open_plugin_001", explicit_source_key="sops"
        )
        == "sops"
    )
    assert UniformAPIService._resolve_open_plugin_source_key(space_id=1, plugin_id="open_plugin_001") == ""
