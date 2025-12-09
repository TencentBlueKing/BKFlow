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

from bkflow.task.models import TaskInstance
from bkflow.task.operations import OperationResult, TaskNodeOperation
from bkflow.utils.pipeline import build_default_pipeline_tree


@pytest.mark.django_db(transaction=True)
class TestTaskNodeOperation:
    """测试 TaskNodeOperation 节点操作"""

    def test_retry_node(self, mocker):
        """测试重试节点"""
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
            "bamboo_engine.api.get_data", return_value=EngineAPIResult(result=True, data={}, message="success")
        )
        mocker.patch("bamboo_engine.api.retry_node", return_value=EngineAPIResult(result=True, message="success"))

        result = node_operation.retry(operator="test_operator")
        assert isinstance(result, OperationResult)
        assert result.result is True

    def test_skip_node(self, mocker):
        """测试跳过节点"""
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
        mocker.patch("bamboo_engine.api.skip_node", return_value=EngineAPIResult(result=True, message="success"))

        result = node_operation.skip(operator="test_operator")
        assert isinstance(result, OperationResult)
        assert result.result is True

    def test_callback_node(self, mocker):
        """测试节点回调"""
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
        assert isinstance(result, OperationResult)
        assert result.result is True

    def test_skip_exg(self, mocker):
        """测试跳过排他网关"""
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
            "bamboo_engine.api.skip_exclusive_gateway",
            return_value=EngineAPIResult(result=True, message="success"),
        )

        result = node_operation.skip_exg(operator="test_operator", flow_id="flow_123")
        assert isinstance(result, OperationResult)
        assert result.result is True

    def test_skip_cpg(self, mocker):
        """测试跳过条件并行网关"""
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
            "bamboo_engine.api.skip_conditional_parallel_gateway",
            return_value=EngineAPIResult(result=True, message="success"),
        )

        result = node_operation.skip_cpg(
            operator="test_operator", flow_ids=["flow_1", "flow_2"], converge_gateway_id="gateway_123"
        )
        assert isinstance(result, OperationResult)
        assert result.result is True

    def test_forced_fail(self, mocker):
        """测试强制失败"""
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
            "bamboo_engine.api.forced_fail_activity",
            return_value=EngineAPIResult(result=True, message="success"),
        )

        result = node_operation.forced_fail(operator="test_operator", ex_data="test error")
        assert isinstance(result, OperationResult)
        assert result.result is True

    def test_get_node_detail_not_executed(self, mocker):
        """测试获取未执行节点详情"""
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
            return_value=EngineAPIResult(result=True, data={}, message="success"),
        )

        result = node_operation.get_node_detail()
        assert isinstance(result, OperationResult)
        assert result.result is True
        assert result.data["state"] == bamboo_engine_states.READY

    def test_get_outputs(self, mocker):
        """测试获取节点输出"""
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
            return_value=EngineAPIResult(result=True, data={"output1": "value1"}, message="success"),
        )

        result = node_operation.get_outputs()
        assert isinstance(result, OperationResult)
        assert result.result is True
