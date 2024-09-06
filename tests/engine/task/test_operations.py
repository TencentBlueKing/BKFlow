# -*- coding: utf-8 -*-
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

        task_operation.start(executor)

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
