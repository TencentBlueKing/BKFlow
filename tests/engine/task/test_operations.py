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
from bamboo_engine.api import EngineAPIResult

from bkflow.task.models import TaskInstance
from bkflow.task.operations import OperationResult, TaskOperation
from bkflow.utils.pipeline import build_default_pipeline_tree


class TestTaskOperationTrace:
    def test_start_method_passes_custom_span_attributes_to_execution_span(self, mocker, settings):
        """启动任务时会把 extra_info 中的自定义 Span 属性传给执行级 Span"""
        settings.ENABLE_OTEL_TRACE = True
        custom_span_attributes = {"request_id": "req-001", "source": "apigw"}
        task_instance = mocker.MagicMock()
        task_instance.id = 1
        task_instance.space_id = 100
        task_instance.instance_id = "pipeline-1"
        task_instance.execution_data = {"pipeline": "data"}
        task_instance.extra_info = {"custom_context": {"custom_span_attributes": custom_span_attributes}}

        update_queryset = mocker.MagicMock()
        update_queryset.update.return_value = 1
        mocker.patch("bkflow.task.operations.TaskInstance.objects.filter", return_value=update_queryset)
        mocker.patch("bkflow.task.operations.format_web_data_to_pipeline", return_value={"pipeline": "formatted"})
        mocker.patch("bkflow.task.operations.get_pipeline_context", return_value={})
        mock_client = mocker.patch("bkflow.task.operations.InterfaceModuleClient")
        mock_client.return_value.get_variable.return_value = {"result": True, "data": {}}
        mocker.patch(
            "bkflow.task.operations.bamboo_engine_api.run_pipeline",
            return_value=EngineAPIResult(result=True, message="success"),
        )
        mocker.patch("bkflow.task.operations.taskflow_started.send")
        mock_create_execution_span = mocker.patch(
            "bkflow.task.operations.create_execution_span", return_value=("a" * 32, "b" * 16)
        )

        TaskOperation(task_instance, queue="test_queue").start(operator="test_executor")

        mock_create_execution_span.assert_called_once_with(
            task_id=task_instance.id,
            space_id=task_instance.space_id,
            pipeline_instance_id=task_instance.instance_id,
            operator="test_executor",
            custom_span_attributes=custom_span_attributes,
        )


@pytest.mark.django_db(transaction=True)
class TestTaskOperation:
    def test_start_method_updates_task_instance_start_time_and_executor_before_running_pipeline(self, mocker):
        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id, pipeline_tree=build_default_pipeline_tree()
        )
        queue = "test_queue"
        executor = "test_executor"
        task_operation = TaskOperation(task_instance, queue)
        mocker.patch("bamboo_engine.api.run_pipeline", return_value=EngineAPIResult(result=True, message="success"))
        mock_client = mocker.patch("bkflow.task.operations.InterfaceModuleClient")
        mock_client.return_value.get_variable.return_value = {"result": True, "data": {}}

        task_operation.start(operator=executor)

        task_instance.refresh_from_db()
        assert task_instance.is_started is True
        assert task_instance.start_time is not None
        assert task_instance.executor == executor

    def test_pause_method_updates_task_instance_pause_time_and_operator_before_pausing_pipeline(self, mocker):
        space_id = 1
        task_instance = TaskInstance.objects.create(name="test_task", space_id=space_id, is_started=True)
        operator = "test_operator"
        task_operation = TaskOperation(task_instance)
        mocker.patch("bamboo_engine.api.pause_pipeline", return_value=EngineAPIResult(result=True, message="success"))

        result = task_operation.pause(operator)
        assert isinstance(result, OperationResult)
        assert result.result is True

        task_instance.refresh_from_db()
        assert task_instance.is_started is True
        assert task_instance.is_finished is False

    def test_start_method_raises_validation_error_if_task_already_started(self, mocker):
        space_id = 1
        task_instance = TaskInstance.objects.create(name="test_task", space_id=space_id, is_started=True)
        queue = "test_queue"
        executor = "test_executor"
        task_operation = TaskOperation(task_instance, queue)

        result = task_operation.start(executor)
        assert isinstance(result, OperationResult)
        assert result.result is False
        assert result.exc == "task already started"

    def test_start_method_raises_exception_if_pipeline_execution_fails(self, mocker):
        space_id = 1
        task_instance = TaskInstance.objects.create(name="test_task", space_id=space_id)
        queue = "test_queue"
        executor = "test_executor"
        task_operation = TaskOperation(task_instance, queue)
        mocker.patch("bamboo_engine.api.run_pipeline", return_value=EngineAPIResult(result=False, message="failure"))

        result = task_operation.start(executor)
        assert isinstance(result, OperationResult)
        assert result.result is False

    def test_start_method_calls_calculate_tree_info(self, mocker):
        space_id = 1
        task_instance = TaskInstance.objects.create(name="test_task", space_id=space_id)
        queue = "test_queue"
        executor = "test_executor"
        task_operation = TaskOperation(task_instance, queue)
        mocker.patch("bamboo_engine.api.run_pipeline", return_value=EngineAPIResult(result=True, message="success"))
        mocker.patch.object(task_instance, "calculate_tree_info")

        task_operation.start(executor)

        task_instance.calculate_tree_info.assert_called_once()

    def test_start_skips_open_plugin_validate_for_plain_task(self, mocker):
        """不含开放插件的存量任务启动时不应请求 Interface 做预检。"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        mocker.patch("bamboo_engine.api.run_pipeline", return_value=EngineAPIResult(result=True, message="success"))
        mock_client = mocker.patch("bkflow.task.operations.InterfaceModuleClient")
        mock_client.return_value.get_variable.return_value = {"result": True, "data": {}}

        result = TaskOperation(task_instance).start(operator="test_executor")

        assert result.result is True
        mock_client.return_value.validate_open_plugins_for_start.assert_not_called()

    def test_start_validates_open_plugins_when_snapshot_exists(self, mocker):
        """含开放插件快照的任务启动时，Engine 用已有 extra_info 请求 Interface 预检。"""
        extra_info = {
            "plugin_reference_snapshot": [
                {
                    "node_id": "node1",
                    "plugin_id": "open_plugin_001",
                    "plugin_version": "1.2.0",
                    "source_key": "sops",
                }
            ]
        }
        task_instance = TaskInstance.objects.create_instance(
            space_id=1, pipeline_tree=build_default_pipeline_tree(), extra_info=extra_info
        )
        mocker.patch("bamboo_engine.api.run_pipeline", return_value=EngineAPIResult(result=True, message="success"))
        mock_client = mocker.patch("bkflow.task.operations.InterfaceModuleClient")
        mock_client.return_value.get_variable.return_value = {"result": True, "data": {}}
        mock_client.return_value.validate_open_plugins_for_start.return_value = {"result": True, "data": {}}

        result = TaskOperation(task_instance).start(operator="test_executor")

        assert result.result is True
        mock_client.return_value.validate_open_plugins_for_start.assert_called_once()
        payload = mock_client.return_value.validate_open_plugins_for_start.call_args.kwargs.get("data")
        if payload is None:
            payload = mock_client.return_value.validate_open_plugins_for_start.call_args.args[0]
        assert payload["space_id"] == 1
        assert payload["snapshot"][0]["plugin_id"] == "open_plugin_001"
        assert "pipeline_tree" not in payload

    def test_start_rejects_when_open_plugin_validate_fails(self, mocker):
        """Interface 预检失败时不应把任务标成已启动。"""
        extra_info = {
            "plugin_reference_snapshot": [
                {
                    "node_id": "node1",
                    "plugin_id": "open_plugin_001",
                    "plugin_version": "1.2.0",
                    "source_key": "sops",
                }
            ]
        }
        task_instance = TaskInstance.objects.create_instance(
            space_id=1, pipeline_tree=build_default_pipeline_tree(), extra_info=extra_info
        )
        mock_run = mocker.patch(
            "bamboo_engine.api.run_pipeline", return_value=EngineAPIResult(result=True, message="success")
        )
        mock_client = mocker.patch("bkflow.task.operations.InterfaceModuleClient")
        mock_client.return_value.validate_open_plugins_for_start.return_value = {
            "result": False,
            "message": "开放插件 [open_plugin_001] 在当前空间未开放",
        }

        result = TaskOperation(task_instance).start(operator="test_executor")

        assert result.result is False
        assert "在当前空间未开放" in result.message
        mock_run.assert_not_called()
        task_instance.refresh_from_db()
        assert task_instance.is_started is False
