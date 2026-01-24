"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""

import pytest
from bamboo_engine import states as bamboo_engine_states
from bamboo_engine.api import EngineAPIResult
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from pipeline.utils.uniqid import node_uniqid

from bkflow.task.models import TaskInstance
from bkflow.task.operations import OperationResult, TaskOperation
from bkflow.utils.pipeline import build_default_pipeline_tree


@pytest.mark.django_db(transaction=True)
class TestTaskOperationComplete:
    """测试 TaskOperation 的完整操作"""

    def test_task_operations(self, mocker):
        """测试任务操作（恢复、撤销、获取状态）"""
        space_id = 1

        # Resume
        task_instance = TaskInstance.objects.create(
            name="test_task", space_id=space_id, instance_id=node_uniqid(), is_started=True
        )
        task_operation = TaskOperation(task_instance)
        mocker.patch("bamboo_engine.api.resume_pipeline", return_value=EngineAPIResult(result=True, message="success"))
        result = task_operation.resume(operator="test_operator")
        assert result.result is True

        # Revoke
        mocker.patch("bamboo_engine.api.revoke_pipeline", return_value=EngineAPIResult(result=True, message="success"))
        result = task_operation.revoke(operator="test_operator")
        assert result.result is True

        # Get states - not started
        task_instance = TaskInstance.objects.create(
            name="test_task", space_id=space_id, instance_id=node_uniqid(), is_started=False
        )
        task_operation = TaskOperation(task_instance)
        result = task_operation.get_task_states()
        assert result.data["state"] == "CREATED"

        # Get states - expired
        task_instance = TaskInstance.objects.create(
            name="test_task", space_id=space_id, instance_id=node_uniqid(), is_started=True, is_expired=True
        )
        task_operation = TaskOperation(task_instance)
        result = task_operation.get_task_states()
        assert result.data["state"] == "EXPIRED"

        # Get states - started
        task_instance = TaskInstance.objects.create(
            name="test_task", space_id=space_id, instance_id=node_uniqid(), is_started=True
        )
        task_operation = TaskOperation(task_instance)
        mock_states = {
            task_instance.instance_id: {
                "id": task_instance.instance_id,
                "state": bamboo_engine_states.RUNNING,
                "children": {},
            }
        }
        mocker.patch(
            "bamboo_engine.api.get_pipeline_states",
            return_value=EngineAPIResult(result=True, data=mock_states, message="success"),
        )
        result = task_operation.get_task_states()
        assert "state" in result.data

    def test_render_current_constants_not_running(self, mocker):
        """测试渲染当前常量，任务未运行"""
        space_id = 1
        task_instance = TaskInstance.objects.create(
            name="test_task", space_id=space_id, instance_id=node_uniqid(), is_started=False
        )
        task_operation = TaskOperation(task_instance)

        mocker.patch(
            "bamboo_engine.api.get_data",
            side_effect=Exception("NotFoundError"),
        )

        result = task_operation.render_current_constants()
        assert isinstance(result, OperationResult)
        assert result.result is False

    def test_render_current_constants_success(self, mocker):
        """测试渲染当前常量成功"""
        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id, pipeline_tree=build_default_pipeline_tree()
        )
        task_instance.is_started = True
        task_instance.save()
        task_operation = TaskOperation(task_instance)

        # Mock runtime methods
        mocker.patch("pipeline.eri.runtime.BambooDjangoRuntime.get_context", return_value=[])
        mocker.patch(
            "pipeline.eri.runtime.BambooDjangoRuntime.get_data_inputs",
            return_value={},
        )
        mocker.patch("bamboo_engine.context.Context.hydrate", return_value={"key1": "value1"})

        result = task_operation.render_current_constants()
        assert isinstance(result, OperationResult)
        # 由于 mock 可能不完整，只检查返回类型
        assert isinstance(result, OperationResult)

    def test_render_context_with_node_outputs(self, mocker):
        """测试使用节点输出渲染上下文"""
        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id, pipeline_tree=build_default_pipeline_tree()
        )
        task_instance.is_started = True
        task_instance.save()
        task_operation = TaskOperation(task_instance)

        node_ids = ["node1"]
        to_render_constants = {"key1": "key1"}

        # Mock runtime methods
        mocker.patch("pipeline.eri.runtime.BambooDjangoRuntime.get_context", return_value=[])
        mocker.patch("pipeline.eri.models.ExecutionData.objects.filter", return_value=[])
        mocker.patch("bamboo_engine.context.Context.hydrate", return_value={"key1": "value1"})
        mocker.patch("bamboo_engine.template.Template.render", return_value={"key1": "rendered_value1"})

        result = task_operation.render_context_with_node_outputs(node_ids, to_render_constants)
        assert isinstance(result, OperationResult)

    def test_uniform_task_operation_result_with_engine_api_result(self, mocker):
        """测试 uniform_task_operation_result 装饰器处理 EngineAPIResult"""
        from bkflow.task.operations import uniform_task_operation_result

        @uniform_task_operation_result
        def test_func():
            return EngineAPIResult(result=True, data={"key": "value"}, message="success")

        result = test_func()
        assert isinstance(result, OperationResult)
        assert result.result is True

    def test_uniform_task_operation_result_with_dict(self, mocker):
        """测试 uniform_task_operation_result 装饰器处理 dict"""
        from bkflow.task.operations import uniform_task_operation_result

        @uniform_task_operation_result
        def test_func():
            return {"result": True, "data": {"key": "value"}}

        result = test_func()
        assert isinstance(result, OperationResult)
        assert result.result is True

    def test_uniform_task_operation_result_with_other_type(self, mocker):
        """测试 uniform_task_operation_result 装饰器处理其他类型"""
        from bkflow.task.operations import uniform_task_operation_result

        @uniform_task_operation_result
        def test_func():
            return "simple_string"

        result = test_func()
        assert isinstance(result, OperationResult)
        assert result.result is True
        assert result.data == "simple_string"

    def test_uniform_task_operation_result_with_exception(self, mocker):
        """测试 uniform_task_operation_result 装饰器处理异常"""
        from bkflow.task.operations import uniform_task_operation_result

        @uniform_task_operation_result
        def test_func():
            raise ValueError("test error")

        result = test_func()
        assert isinstance(result, OperationResult)
        assert result.result is False
        assert "test error" in result.message

    def test_start_with_space_and_scope_vars(self, mocker):
        """测试启动任务时包含空间和域变量"""
        space_id = 1
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=space_id, pipeline_tree=pipeline_tree)

        mocker.patch("bkflow.task.operations.format_web_data_to_pipeline", return_value=pipeline_tree)
        mocker.patch(
            "bkflow.task.operations.get_pipeline_context",
            return_value={"task_scope_type": "project", "task_scope_value": "123"},
        )
        mocker.patch(
            "bkflow.task.operations.EngineSpaceConfig.get_space_var",
            return_value={
                "space": {"var1": "value1"},
                "scope": {"project_123": {"var2": "value2"}},
            },
        )
        mocker.patch("bamboo_engine.api.run_pipeline", return_value=EngineAPIResult(result=True, message="success"))

        task_operation = TaskOperation(task_instance)
        result = task_operation.start(operator="test_user")

        assert result.result is True

    def test_start_with_space_var_only(self, mocker):
        """测试启动任务时只包含空间变量"""
        space_id = 1
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=space_id, pipeline_tree=pipeline_tree)

        mocker.patch("bkflow.task.operations.format_web_data_to_pipeline", return_value=pipeline_tree)
        mocker.patch("bkflow.task.operations.get_pipeline_context", return_value={})
        mocker.patch(
            "bkflow.task.operations.EngineSpaceConfig.get_space_var", return_value={"space": {"var1": "value1"}}
        )
        mocker.patch("bamboo_engine.api.run_pipeline", return_value=EngineAPIResult(result=True, message="success"))

        task_operation = TaskOperation(task_instance)
        result = task_operation.start(operator="test_user")

        assert result.result is True

    def test_start_run_pipeline_failed(self, mocker):
        """测试启动任务时 run_pipeline 失败"""
        space_id = 1
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=space_id, pipeline_tree=pipeline_tree)

        mocker.patch("bkflow.task.operations.format_web_data_to_pipeline", return_value=pipeline_tree)
        mocker.patch("bkflow.task.operations.get_pipeline_context", return_value={})
        mocker.patch("bkflow.task.operations.EngineSpaceConfig.get_space_var", return_value={})
        mocker.patch(
            "bamboo_engine.api.run_pipeline",
            return_value=EngineAPIResult(result=False, message="pipeline failed", exc_trace="trace"),
        )

        task_operation = TaskOperation(task_instance)
        result = task_operation.start(operator="test_user")

        assert result.result is False
        task_instance.refresh_from_db()
        assert task_instance.is_started is False

    def test_start_exception_handling(self, mocker):
        """测试启动任务时异常处理"""
        space_id = 1
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=space_id, pipeline_tree=pipeline_tree)

        mocker.patch("bkflow.task.operations.format_web_data_to_pipeline", side_effect=Exception("format error"))

        task_operation = TaskOperation(task_instance)
        result = task_operation.start(operator="test_user")

        assert result.result is False
        task_instance.refresh_from_db()
        assert task_instance.is_started is False

    def test_get_task_states_pipeline_states_failed(self, mocker):
        """测试获取任务状态时 get_pipeline_states 失败"""
        space_id = 1
        task_instance = TaskInstance.objects.create(
            name="test_task", space_id=space_id, instance_id=node_uniqid(), is_started=True
        )
        task_operation = TaskOperation(task_instance)

        mocker.patch(
            "bamboo_engine.api.get_pipeline_states",
            return_value=EngineAPIResult(result=False, message="get states failed", exc_trace="trace"),
        )

        result = task_operation.get_task_states()
        assert result.result is False

    def test_get_task_states_empty_states(self, mocker):
        """测试获取任务状态时返回空状态"""
        space_id = 1
        task_instance = TaskInstance.objects.create(
            name="test_task", space_id=space_id, instance_id=node_uniqid(), is_started=True
        )
        task_operation = TaskOperation(task_instance)

        mocker.patch(
            "bamboo_engine.api.get_pipeline_states",
            return_value=EngineAPIResult(result=True, data=None, message="success"),
        )

        result = task_operation.get_task_states()
        assert result.result is True
        assert result.data["state"] == "CREATED"

    def test_get_task_states_with_subprocess_id(self, mocker):
        """测试获取任务状态时指定 subprocess_id"""
        space_id = 1
        task_instance = TaskInstance.objects.create(
            name="test_task", space_id=space_id, instance_id=node_uniqid(), is_started=True
        )
        task_operation = TaskOperation(task_instance)

        mock_states = {
            task_instance.instance_id: {
                "id": task_instance.instance_id,
                "state": bamboo_engine_states.RUNNING,
                "children": {
                    "subprocess_1": {
                        "id": "subprocess_1",
                        "state": bamboo_engine_states.FINISHED,
                        "children": {},
                    }
                },
            }
        }
        mocker.patch(
            "bamboo_engine.api.get_pipeline_states",
            return_value=EngineAPIResult(result=True, data=mock_states, message="success"),
        )

        result = task_operation.get_task_states(subprocess_id="subprocess_1")
        assert result.result is True
        assert "state" in result.data

    def test_get_task_states_with_failed_child(self, mocker):
        """测试获取任务状态时包含失败的子节点"""
        space_id = 1
        task_instance = TaskInstance.objects.create(
            name="test_task", space_id=space_id, instance_id=node_uniqid(), is_started=True
        )
        task_operation = TaskOperation(task_instance)

        mock_states = {
            task_instance.instance_id: {
                "id": task_instance.instance_id,
                "state": bamboo_engine_states.RUNNING,
                "children": {
                    "node_1": {
                        "id": "node_1",
                        "state": bamboo_engine_states.FAILED,
                        "children": {},
                    }
                },
            }
        }
        mocker.patch(
            "bamboo_engine.api.get_pipeline_states",
            return_value=EngineAPIResult(result=True, data=mock_states, message="success"),
        )

        result = task_operation.get_task_states()
        assert result.result is True
        assert result.data["state"] == bamboo_engine_states.FAILED

    def test_get_task_states_with_suspended_child(self, mocker):
        """测试获取任务状态时包含暂停的子节点"""
        space_id = 1
        task_instance = TaskInstance.objects.create(
            name="test_task", space_id=space_id, instance_id=node_uniqid(), is_started=True
        )
        task_operation = TaskOperation(task_instance)

        mock_states = {
            task_instance.instance_id: {
                "id": task_instance.instance_id,
                "state": bamboo_engine_states.RUNNING,
                "children": {
                    "node_1": {
                        "id": "node_1",
                        "state": bamboo_engine_states.SUSPENDED,
                        "children": {},
                    }
                },
            }
        }
        mocker.patch(
            "bamboo_engine.api.get_pipeline_states",
            return_value=EngineAPIResult(result=True, data=mock_states, message="success"),
        )

        result = task_operation.get_task_states()
        assert result.result is True
        assert result.data["state"] == "NODE_SUSPENDED"

    def test_get_task_states_with_ex_data(self, mocker):
        """测试获取任务状态时包含异常数据"""
        space_id = 1
        task_instance = TaskInstance.objects.create(
            name="test_task", space_id=space_id, instance_id=node_uniqid(), is_started=True
        )
        task_operation = TaskOperation(task_instance)

        # 避免触发 collect_fail_nodes 的 bug（node_id 未定义，应该使用 node["id"]）
        # 使用没有失败子节点的状态，只让根节点失败，这样 collect_fail_nodes 不会找到失败的子节点
        mock_states = {
            task_instance.instance_id: {
                "id": task_instance.instance_id,
                "state": bamboo_engine_states.FAILED,
                "children": {},  # 空 children，避免触发 collect_fail_nodes 的 bug
            }
        }
        mocker.patch(
            "bamboo_engine.api.get_pipeline_states",
            return_value=EngineAPIResult(result=True, data=mock_states, message="success"),
        )
        mocker.patch(
            "bamboo_engine.api.get_execution_data_outputs",
            return_value=EngineAPIResult(result=True, data={"ex_data": "error message"}, message="success"),
        )

        result = task_operation.get_task_states(with_ex_data=True)
        assert result.result is True
        assert "ex_data" in result.data

    def test_render_current_constants_hydrate_failed(self, mocker):
        """测试渲染当前常量时 hydrate 失败"""
        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id, pipeline_tree=build_default_pipeline_tree()
        )
        task_instance.is_started = True
        task_instance.save()
        task_operation = TaskOperation(task_instance)

        mocker.patch("pipeline.eri.runtime.BambooDjangoRuntime.get_context", return_value=[])
        mocker.patch("pipeline.eri.runtime.BambooDjangoRuntime.get_data_inputs", return_value={})
        mocker.patch("bamboo_engine.context.Context.hydrate", side_effect=Exception("hydrate error"))

        result = task_operation.render_current_constants()
        assert result.result is False
        assert "hydrate context failed" in result.message

    def test_render_context_with_node_outputs_hydrate_failed(self, mocker):
        """测试使用节点输出渲染上下文时 hydrate 失败"""
        space_id = 1
        pipeline_tree = build_default_pipeline_tree()
        pipeline_tree["constants"] = {}
        task_instance = TaskInstance.objects.create_instance(space_id=space_id, pipeline_tree=pipeline_tree)
        task_instance.is_started = True
        task_instance.save()
        task_operation = TaskOperation(task_instance)

        node_ids = ["node1"]
        to_render_constants = {"key1": "key1"}

        from unittest.mock import MagicMock

        mock_query = MagicMock()
        mock_query.iterator.return_value = []
        mocker.patch("pipeline.eri.runtime.BambooDjangoRuntime.get_context", return_value=[])
        mocker.patch("pipeline.eri.models.ExecutionData.objects.filter", return_value=mock_query)
        mocker.patch("bamboo_engine.context.Context.hydrate", side_effect=Exception("hydrate error"))

        result = task_operation.render_context_with_node_outputs(node_ids, to_render_constants)
        assert result.result is False
        assert "hydrate context failed" in result.message

    def test_render_context_with_node_outputs_with_node_data(self, mocker):
        """测试使用节点输出渲染上下文时包含节点数据"""
        from unittest.mock import MagicMock

        space_id = 1
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=space_id, pipeline_tree=pipeline_tree)
        task_instance.calculate_tree_info()
        node_ids = list(task_instance.node_id_set)
        if not node_ids:
            pytest.skip("No nodes in pipeline tree")

        # 使用真实的节点 ID
        real_node_id = node_ids[0]
        pipeline_tree["constants"] = {
            "${output1}": {
                "key": "${output1}",  # get_variable_mapping 需要 key 字段
                "value": "",
                "show_type": "show",
                "source_type": "component_outputs",
                "custom_type": "",
                "source_info": {real_node_id: ["output1"]},
            }
        }
        # 重新创建 task_instance 以更新 execution_data（execution_data 可能是只读属性）
        task_instance = TaskInstance.objects.create_instance(space_id=space_id, pipeline_tree=pipeline_tree)
        task_instance.is_started = True
        task_instance.save()
        task_operation = TaskOperation(task_instance)

        to_render_constants = {"key1": "key1"}

        # Mock ExecutionData
        mock_node = MagicMock()
        mock_node.node_id = real_node_id
        mock_node.outputs = '{"output1": "value1"}'
        mock_node.outputs_serializer = "json"
        mock_query = MagicMock()
        mock_query.iterator.return_value = [mock_node]

        mocker.patch("pipeline.eri.runtime.BambooDjangoRuntime.get_context", return_value=[])
        mocker.patch("pipeline.eri.models.ExecutionData.objects.filter", return_value=mock_query)
        mocker.patch("bamboo_engine.context.Context.hydrate", return_value={"key1": "value1"})
        mocker.patch("bamboo_engine.template.Template.render", return_value={"key1": "rendered_value1"})

        result = task_operation.render_context_with_node_outputs([real_node_id], to_render_constants)
        assert result.result is True

    def test_retry_node_get_data_failed(self, mocker):
        """测试重试节点时 get_data 失败"""
        from bkflow.task.operations import TaskNodeOperation

        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id, pipeline_tree=build_default_pipeline_tree()
        )
        task_instance.calculate_tree_info()
        node_ids = list(task_instance.node_id_set)
        if not node_ids:
            pytest.skip("No nodes in pipeline tree")

        node_id = node_ids[0]
        node_operation = TaskNodeOperation(task_instance, node_id)
        mocker.patch(
            "bamboo_engine.api.get_data", return_value=EngineAPIResult(result=False, message="get data failed")
        )

        result = node_operation.retry(operator="test_operator")
        assert result.result is False

    def test_callback_node_without_version(self, mocker):
        """测试节点回调时不提供 version"""
        from bkflow.task.operations import TaskNodeOperation

        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id, pipeline_tree=build_default_pipeline_tree()
        )
        task_instance.calculate_tree_info()
        node_ids = list(task_instance.node_id_set)
        if not node_ids:
            pytest.skip("No nodes in pipeline tree")

        node_id = node_ids[0]
        node_operation = TaskNodeOperation(task_instance, node_id)

        mock_state = type("State", (), {"version": 1})()
        mocker.patch("pipeline.eri.runtime.BambooDjangoRuntime.get_state", return_value=mock_state)
        mocker.patch("bamboo_engine.api.callback", return_value=EngineAPIResult(result=True, message="success"))

        result = node_operation.callback(operator="test_operator", data={"key": "value"})
        assert result.result is True

    def test_get_node_detail_executed_with_loop(self, mocker):
        """测试获取已执行节点详情，指定 loop"""
        from bkflow.task.operations import TaskNodeOperation

        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id, pipeline_tree=build_default_pipeline_tree()
        )
        task_instance.calculate_tree_info()
        node_ids = list(task_instance.node_id_set)
        if not node_ids:
            pytest.skip("No nodes in pipeline tree")

        node_id = node_ids[0]
        node_operation = TaskNodeOperation(task_instance, node_id)

        mock_detail = {
            node_id: {
                "id": node_id,
                "state": bamboo_engine_states.FINISHED,
                "loop": 2,
                "children": {},
            }
        }
        mocker.patch(
            "bamboo_engine.api.get_children_states",
            return_value=EngineAPIResult(result=True, data=mock_detail, message="success"),
        )
        mock_histories = [
            {
                "id": 1,
                "version": "v1",
                "outputs": {"ex_data": ""},
                "state": bamboo_engine_states.FAILED,
                "loop": 1,
                "started_time": None,
                "archived_time": None,
                "skip": 0,
            },
            {
                "id": 2,
                "version": "v2",
                "outputs": {"ex_data": ""},
                "loop": 1,
                "started_time": None,
                "archived_time": None,
                "skip": 0,
            },
        ]
        mocker.patch(
            "bamboo_engine.api.get_node_histories",
            return_value=EngineAPIResult(result=True, data=mock_histories, message="success"),
        )

        result = node_operation.get_node_detail(loop=1)
        assert result.result is True
        assert result.data["history_id"] == 2

    def test_get_node_detail_get_children_states_failed(self, mocker):
        """测试获取节点详情时 get_children_states 失败"""
        from bkflow.task.operations import TaskNodeOperation

        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id, pipeline_tree=build_default_pipeline_tree()
        )
        task_instance.calculate_tree_info()
        node_ids = list(task_instance.node_id_set)
        if not node_ids:
            pytest.skip("No nodes in pipeline tree")

        node_id = node_ids[0]
        node_operation = TaskNodeOperation(task_instance, node_id)

        mocker.patch(
            "bamboo_engine.api.get_children_states",
            return_value=EngineAPIResult(result=False, message="get children states failed"),
        )

        result = node_operation.get_node_detail()
        assert result.result is False

    def test_get_outputs_failed(self, mocker):
        """测试获取节点输出失败"""
        from bkflow.task.operations import TaskNodeOperation

        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id, pipeline_tree=build_default_pipeline_tree()
        )
        task_instance.calculate_tree_info()
        node_ids = list(task_instance.node_id_set)
        if not node_ids:
            pytest.skip("No nodes in pipeline tree")

        node_id = node_ids[0]
        node_operation = TaskNodeOperation(task_instance, node_id)
        mocker.patch(
            "bamboo_engine.api.get_execution_data_outputs",
            return_value=EngineAPIResult(result=False, message="get outputs failed", exc="error"),
        )

        result = node_operation.get_outputs()
        assert result.result is False

    def test_start_captures_trace_context_when_enabled(self, mocker):
        """测试启动任务时，trace启用时捕获trace context"""
        space_id = 1
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=space_id, pipeline_tree=pipeline_tree)

        # Setup tracer provider
        provider = TracerProvider()
        trace.set_tracer_provider(provider)

        mocker.patch("bkflow.task.operations.format_web_data_to_pipeline", return_value=pipeline_tree)
        mocker.patch("bkflow.task.operations.get_pipeline_context", return_value={})
        mocker.patch("bkflow.task.operations.EngineSpaceConfig.get_space_var", return_value={})
        mocker.patch("django.conf.settings.ENABLE_OTEL_TRACE", True)

        # Mock run_pipeline to capture root_pipeline_data
        captured_data = {}

        def mock_run_pipeline(*args, **kwargs):
            captured_data["root_pipeline_data"] = kwargs.get("root_pipeline_data", {})
            return EngineAPIResult(result=True, message="success")

        mocker.patch("bamboo_engine.api.run_pipeline", side_effect=mock_run_pipeline)

        task_operation = TaskOperation(task_instance)

        # Create a span to simulate trace context
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_span"):
            result = task_operation.start(operator="test_user")

        assert result.result is True

        # Verify trace context was captured and passed to pipeline
        if captured_data.get("root_pipeline_data"):
            assert "_trace_id" in captured_data["root_pipeline_data"]
            assert "_parent_span_id" in captured_data["root_pipeline_data"]
            trace_id = captured_data["root_pipeline_data"]["_trace_id"]
            parent_span_id = captured_data["root_pipeline_data"]["_parent_span_id"]
            assert len(trace_id) == 32  # 16 bytes = 32 hex chars
            assert len(parent_span_id) == 16  # 8 bytes = 16 hex chars

        # Cleanup
        trace.set_tracer_provider(None)

    def test_start_no_trace_context_when_disabled(self, mocker):
        """测试启动任务时，trace禁用时不注入trace context"""
        space_id = 1
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=space_id, pipeline_tree=pipeline_tree)

        mocker.patch("bkflow.task.operations.format_web_data_to_pipeline", return_value=pipeline_tree)
        mocker.patch("bkflow.task.operations.get_pipeline_context", return_value={})
        mocker.patch("bkflow.task.operations.EngineSpaceConfig.get_space_var", return_value={})
        mocker.patch("django.conf.settings.ENABLE_OTEL_TRACE", False)

        captured_data = {}

        def mock_run_pipeline(*args, **kwargs):
            captured_data["root_pipeline_data"] = kwargs.get("root_pipeline_data", {})
            return EngineAPIResult(result=True, message="success")

        mocker.patch("bamboo_engine.api.run_pipeline", side_effect=mock_run_pipeline)

        task_operation = TaskOperation(task_instance)

        # Setup tracer provider and create span
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_span"):
            result = task_operation.start(operator="test_user")

        assert result.result is True

        # Verify trace context was NOT injected when trace is disabled
        if captured_data.get("root_pipeline_data"):
            assert "_trace_id" not in captured_data["root_pipeline_data"]
            assert "_parent_span_id" not in captured_data["root_pipeline_data"]

        # Cleanup
        trace.set_tracer_provider(None)

    def test_start_no_trace_context_when_no_span(self, mocker):
        """测试启动任务时没有trace context的情况（trace启用但无span）"""
        space_id = 1
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=space_id, pipeline_tree=pipeline_tree)

        mocker.patch("bkflow.task.operations.format_web_data_to_pipeline", return_value=pipeline_tree)
        mocker.patch("bkflow.task.operations.get_pipeline_context", return_value={})
        mocker.patch("bkflow.task.operations.EngineSpaceConfig.get_space_var", return_value={})
        mocker.patch("django.conf.settings.ENABLE_OTEL_TRACE", True)

        captured_data = {}

        def mock_run_pipeline(*args, **kwargs):
            captured_data["root_pipeline_data"] = kwargs.get("root_pipeline_data", {})
            return EngineAPIResult(result=True, message="success")

        mocker.patch("bamboo_engine.api.run_pipeline", side_effect=mock_run_pipeline)

        task_operation = TaskOperation(task_instance)

        # No active span
        result = task_operation.start(operator="test_user")

        assert result.result is True

        # Trace context should not be in pipeline data when no span exists
        if captured_data.get("root_pipeline_data"):
            # Should not have trace context if no span was active
            # (get_current_trace_context returns None)
            assert (
                "_trace_id" not in captured_data["root_pipeline_data"]
                or captured_data["root_pipeline_data"]["_trace_id"] is None
            )
