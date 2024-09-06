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
from pipeline.core.data.base import DataObject

from bkflow.pipeline_plugins.components.collections.base import BKFlowBaseService
from bkflow.task.models import TaskMockData


@pytest.mark.django_db(transaction=True)
class TestBKFlowBaseService:
    MOCK_DATA = {"outputs": {"node1": {"output1": "value1"}}, "nodes": ["node1"]}

    def setup(self):
        self.taskflow_id = 1
        TaskMockData.objects.create(taskflow_id=self.taskflow_id, data=self.MOCK_DATA)
        self.base_service = BKFlowBaseService()
        setattr(self.base_service, "id", "node1")

    def test_get_taskflow_mock_data_success(self):
        mock_data = self.base_service.get_taskflow_mock_data(taskflow_id=self.taskflow_id)
        assert mock_data == self.MOCK_DATA

    def test_is_mock_node(self):
        is_mock_node = self.base_service.is_mock_node(taskflow_id=self.taskflow_id, node_id="node1")
        assert is_mock_node is True
        is_mock_node = self.base_service.is_mock_node(taskflow_id=self.taskflow_id, node_id="node2")
        assert is_mock_node is False

    def test_get_mock_outputs(self):
        outputs = self.base_service.get_mock_outputs(taskflow_id=self.taskflow_id)
        assert outputs == {"node1": {"output1": "value1"}}
        not_exist_taskflow_id = 2
        not_exist_outputs = self.base_service.get_mock_outputs(taskflow_id=not_exist_taskflow_id)
        assert not_exist_outputs == {}

    def test_execute(self):
        data = DataObject(inputs={})
        result = self.base_service.execute(
            data=data,
            parent_data=DataObject(inputs={"is_mock": True, "task_id": self.taskflow_id}),
        )
        assert result is True
        assert data.get_one_of_outputs("output1") == "value1"
        assert self.base_service

    def test_schedule(self):
        data = DataObject(inputs={})
        parent_data = DataObject(inputs={"is_mock": True, "task_id": self.taskflow_id})
        setattr(self.base_service, "__need_schedule__", True)
        execute_result = self.base_service.execute(data=data, parent_data=parent_data)
        assert execute_result is True
        assert self.base_service.interval.next() == 2
        schedule_result = self.base_service.schedule(data=data, parent_data=parent_data)
        assert schedule_result is True
        assert data.get_one_of_outputs("output1") == "value1"
        assert self.base_service
