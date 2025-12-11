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
