"""配置输入冻结在调试发起时，与引擎实际执行输入分开保存。"""

import copy

import pytest

from bkflow.template.debug.service import DebugService
from bkflow.template.debug.snapshot import configured_inputs
from bkflow.template.models import DebugContext
from tests.interface.template.debug import test_config_changed
from tests.interface.template.debug.test_snapshot import (
    save,
    snapshot_nodes,
    step,
    view,
)

template = test_config_changed.template


@pytest.mark.django_db
class TestConfiguredInputs:
    def test_unreached_node_keeps_launch_configuration(self, template, mocker):
        """前序失败时未执行节点仍展示原始表达式，后续保存草稿不能覆盖。"""
        save(
            template,
            lambda tree: tree["activities"]["B"]["component"]["data"].update(
                text={"value": "${upstream}"}, options={"value": {"items": [1, False, None]}}, empty={"value": ""}
            ),
        )
        client = test_config_changed.engine_client(mocker)
        DebugService(template.id).global_run({}, "runner")
        save(template, lambda tree: tree["activities"]["B"]["component"]["data"]["text"].update(value="new draft"))
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": "FAILED", "children": {"rtA": {"state": "FAILED"}, "rtB": {"state": "READY"}}},
        }
        node = snapshot_nodes(template)["B"]
        assert node["status"] == "not_run"
        assert node["inputs"] == {}
        assert node["configured_inputs"] == {"text": "${upstream}", "options": {"items": [1, False, None]}, "empty": ""}
        save(template, lambda tree: tree["activities"].pop("B"))
        assert snapshot_nodes(template)["B"] == {**node, "node_deleted": True}

    @pytest.mark.parametrize("run_type", ["global", "step"])
    @pytest.mark.parametrize("status", ["FINISHED", "FAILED"])
    def test_actual_inputs_do_not_replace_configuration(self, template, mocker, run_type, status):
        """轮询成功或失败结果时保留冻结配置，并单独保存引擎返回值。"""
        client = test_config_changed.engine_client(mocker)
        svc = DebugService(template.id)
        if run_type == "global":
            svc.global_run({}, "runner")
        else:
            mocker.patch("bkflow.template.debug.pipeline_builder.build_single_node_pipeline_tree", return_value={})
            svc.step_run("A", "runner", mode="real")
        save(template, lambda tree: tree["activities"]["A"]["component"]["data"]["text"].update(value="new draft"))
        client.get_task_states.return_value = {
            "result": True,
            "data": {"state": status, "children": {"rtA": {"state": status}}},
        }
        client.get_task_node_detail.return_value = {"result": True, "data": {"inputs": {"text": "rendered"}}}
        node = snapshot_nodes(template)["A"]
        assert node["configured_inputs"] == {"text": "before"}
        assert node["inputs"] == {"text": "rendered"}
        assert node["config_changed"] is True

    def test_mock_step_updates_only_target_and_reset_preserves_configuration(self, template):
        """单步更新目标配置，重置只清执行结果，全量重置清整份快照。"""
        step(template, "A")
        step(template, "B")
        before_b = snapshot_nodes(template)["B"]
        save(template, lambda tree: tree["activities"]["A"]["component"]["data"]["text"].update(value="new"))
        step(template, "A", mock_result="fail")
        nodes = snapshot_nodes(template)
        assert nodes["B"] == before_b
        assert nodes["A"]["configured_inputs"] == {"text": "new"}
        assert nodes["A"]["inputs"] == {}
        DebugService(template.id).reset(["A"])
        assert snapshot_nodes(template)["A"]["configured_inputs"] == {"text": "new"}
        assert snapshot_nodes(template)["A"]["status"] == "not_run"
        DebugService(template.id).reset()
        assert view(template)["debug_snapshot"] is None

    def test_legacy_snapshot_returns_null_without_rewriting_history(self, template):
        """旧快照缺字段时只在响应补 null，不能从当前草稿填值或回写数据库。"""
        step(template)
        ctx = DebugContext.objects.get(template_id=template.id)
        ctx.debug_snapshot["nodes"][0].pop("configured_inputs", None)
        ctx.save(update_fields=["debug_snapshot"])
        stored = copy.deepcopy(ctx.debug_snapshot)
        save(template, lambda tree: tree["activities"]["A"]["component"]["data"]["text"].update(value="new"))
        assert snapshot_nodes(template)["A"]["configured_inputs"] is None
        ctx.refresh_from_db()
        assert ctx.debug_snapshot == stored

    def test_configured_credentials_use_existing_display_mask(self, template):
        """配置快照沿用凭证脱敏，且不能修改原始草稿。"""
        credentials = {"api": {"bk_app_code": "test-app", "bk_app_secret": "test-secret"}}
        save(
            template,
            lambda tree: tree["activities"]["A"]["component"]["data"].update(
                request={"value": {"credentials": credentials, "query": "${query}"}}
            ),
        )
        step(template)
        inputs = snapshot_nodes(template)["A"]["configured_inputs"]
        assert inputs["request"] == {
            "credentials": {"api": {"bk_app_code": "test-app", "bk_app_secret": "******"}},
            "query": "${query}",
        }
        assert DebugService(template.id).pipeline_tree["activities"]["A"]["component"]["data"]["request"]["value"] == {
            "credentials": credentials,
            "query": "${query}",
        }


@pytest.mark.parametrize("node_type", ["SubCanvas", "SubProcess"])
def test_subflow_inputs_keep_only_configurable_parameters(node_type):
    """子画布只展示外层可填写的参数，保留表达式和空值，不展开内部变量。"""
    node = {
        "type": node_type,
        "pipeline": {
            "constants": {
                "${visible}": {"show_type": "show", "value": "${parent}"},
                "${empty}": {"show_type": "show", "value": None},
                "${internal}": {"show_type": "hide", "value": "internal"},
            }
        },
    }
    assert configured_inputs(node) == {"${visible}": "${parent}", "${empty}": None}


@pytest.mark.parametrize(
    "node",
    [
        {"type": "ServiceActivity"},
        {"type": "ServiceActivity", "component": {"data": None}},
        {"type": "ServiceActivity", "component": "invalid"},
        {"type": "SubCanvas", "pipeline": "invalid"},
    ],
)
def test_missing_historical_configuration_is_unknown(node):
    """缺失或不完整历史配置返回 null，区别于已确认的空参数。"""
    assert configured_inputs(node) is None
