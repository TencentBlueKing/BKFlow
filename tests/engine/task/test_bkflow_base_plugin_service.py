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
from django.test import override_settings
from pipeline.core.data.base import DataObject

from bkflow.pipeline_plugins.components.collections.base import (
    PLUGIN_SCHEDULE_COUNT_KEY,
    PLUGIN_SPAN_ENDED_KEY,
    BKFlowBaseService,
)
from bkflow.task.models import TaskMockData
from bkflow.utils.trace import (
    PLUGIN_SPAN_ATTRIBUTES_KEY,
    PLUGIN_SPAN_NAME_KEY,
    PLUGIN_SPAN_START_TIME_KEY,
)


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

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_execute_with_trace_enabled(self):
        """Test execute with trace enabled"""
        data = DataObject(inputs={})
        parent_data = DataObject(
            inputs={
                "task_id": self.taskflow_id,
                "task_space_id": "space_1",
                "_trace_id": "a" * 32,
                "_parent_span_id": "b" * 16,
            }
        )

        # Create a test service with trace enabled
        class TestService(BKFlowBaseService):
            plugin_name = "test_plugin"
            enable_plugin_span = True

            def plugin_execute(self, data, parent_data):
                return True

        service = TestService()
        setattr(service, "id", "node1")

        result = service.execute(data=data, parent_data=parent_data)
        assert result is True

        # Verify span was started
        assert data.get_one_of_outputs(PLUGIN_SPAN_NAME_KEY) == "bk_flow.test_plugin"
        assert data.get_one_of_outputs(PLUGIN_SPAN_START_TIME_KEY) is not None
        assert data.get_one_of_outputs(PLUGIN_SPAN_ENDED_KEY) is True  # Should be ended for sync plugin

    def test_execute_with_trace_disabled(self):
        """Test execute with trace disabled"""
        data = DataObject(inputs={})
        parent_data = DataObject(inputs={"task_id": self.taskflow_id, "task_space_id": "space_1"})

        class TestService(BKFlowBaseService):
            plugin_name = "test_plugin"
            enable_plugin_span = False

            def plugin_execute(self, data, parent_data):
                return True

        service = TestService()
        setattr(service, "id", "node1")

        result = service.execute(data=data, parent_data=parent_data)
        assert result is True

        # Verify span was not started
        assert data.get_one_of_outputs(PLUGIN_SPAN_NAME_KEY) is None

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_execute_with_trace_context(self):
        """Test execute with trace context from parent"""
        data = DataObject(inputs={})
        trace_id = "a" * 32
        parent_span_id = "b" * 16
        parent_data = DataObject(
            inputs={
                "task_id": self.taskflow_id,
                "task_space_id": "space_1",
                "_trace_id": trace_id,
                "_parent_span_id": parent_span_id,
            }
        )

        class TestService(BKFlowBaseService):
            plugin_name = "test_plugin"
            enable_plugin_span = True

            def plugin_execute(self, data, parent_data):
                return True

        service = TestService()
        setattr(service, "id", "node1")

        result = service.execute(data=data, parent_data=parent_data)
        assert result is True

        # Verify trace context was saved
        from bkflow.utils.trace import (
            PLUGIN_SPAN_PARENT_SPAN_ID_KEY,
            PLUGIN_SPAN_TRACE_ID_KEY,
        )

        assert data.get_one_of_outputs(PLUGIN_SPAN_TRACE_ID_KEY) == trace_id
        assert data.get_one_of_outputs(PLUGIN_SPAN_PARENT_SPAN_ID_KEY) == parent_span_id

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_execute_failure_ends_span(self):
        """Test that execute failure ends span"""
        data = DataObject(inputs={})
        parent_data = DataObject(
            inputs={"task_id": self.taskflow_id, "task_space_id": "space_1", "_trace_id": "a" * 32}
        )

        class TestService(BKFlowBaseService):
            plugin_name = "test_plugin"
            enable_plugin_span = True

            def plugin_execute(self, data, parent_data):
                return False

        service = TestService()
        setattr(service, "id", "node1")

        result = service.execute(data=data, parent_data=parent_data)
        assert result is False

        # Verify span was ended
        assert data.get_one_of_outputs(PLUGIN_SPAN_ENDED_KEY) is True

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_schedule_with_trace(self):
        """Test schedule with trace enabled"""
        data = DataObject(inputs={})
        parent_data = DataObject(
            inputs={
                "task_id": self.taskflow_id,
                "task_space_id": "space_1",
                "_trace_id": "a" * 32,
                "_parent_span_id": "b" * 16,
            }
        )

        class TestService(BKFlowBaseService):
            plugin_name = "test_plugin"
            enable_plugin_span = True

            def plugin_execute(self, data, parent_data):
                return True

            def plugin_schedule(self, data, parent_data, callback_data=None):
                self.finish_schedule()
                return True

        service = TestService()
        setattr(service, "id", "node1")
        setattr(service, "__need_schedule__", True)

        # Execute first to start span
        execute_result = service.execute(data=data, parent_data=parent_data)
        assert execute_result is True
        assert data.get_one_of_outputs(PLUGIN_SPAN_ENDED_KEY) is False  # Not ended yet

        # Schedule should end the span
        schedule_result = service.schedule(data=data, parent_data=parent_data)
        assert schedule_result is True
        assert data.get_one_of_outputs(PLUGIN_SPAN_ENDED_KEY) is True

        # Verify schedule count
        assert data.get_one_of_outputs(PLUGIN_SCHEDULE_COUNT_KEY) == 1

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_schedule_multiple_times(self):
        """Test multiple schedule calls increment counter"""
        data = DataObject(inputs={})
        parent_data = DataObject(
            inputs={"task_id": self.taskflow_id, "task_space_id": "space_1", "_trace_id": "a" * 32}
        )

        class TestService(BKFlowBaseService):
            plugin_name = "test_plugin"
            enable_plugin_span = True

            def plugin_execute(self, data, parent_data):
                return True

            def plugin_schedule(self, data, parent_data, callback_data=None):
                # Don't finish schedule yet
                return True

        service = TestService()
        setattr(service, "id", "node1")
        setattr(service, "__need_schedule__", True)

        service.execute(data=data, parent_data=parent_data)

        # First schedule
        service.schedule(data=data, parent_data=parent_data)
        assert data.get_one_of_outputs(PLUGIN_SCHEDULE_COUNT_KEY) == 1

        # Second schedule
        service.schedule(data=data, parent_data=parent_data)
        assert data.get_one_of_outputs(PLUGIN_SCHEDULE_COUNT_KEY) == 2

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_span_attributes(self):
        """Test that span attributes are set correctly"""
        data = DataObject(inputs={})
        parent_data = DataObject(
            inputs={
                "task_id": "task_123",
                "task_space_id": "space_456",
                "_trace_id": "a" * 32,
            }
        )

        class TestService(BKFlowBaseService):
            plugin_name = "test_plugin"
            enable_plugin_span = True

            def plugin_execute(self, data, parent_data):
                return True

        service = TestService()
        setattr(service, "id", "node_789")

        service.execute(data=data, parent_data=parent_data)

        attributes = data.get_one_of_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY)
        assert attributes["task_id"] == "task_123"
        assert attributes["space_id"] == "space_456"
        assert attributes["node_id"] == "node_789"

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_end_plugin_span_idempotent(self):
        """Test that _end_plugin_span is idempotent"""
        data = DataObject(inputs={})
        parent_data = DataObject(inputs={"task_id": self.taskflow_id, "task_space_id": "space_1"})

        class TestService(BKFlowBaseService):
            plugin_name = "test_plugin"
            enable_plugin_span = True

            def plugin_execute(self, data, parent_data):
                return True

        service = TestService()
        setattr(service, "id", "node1")

        service.execute(data=data, parent_data=parent_data)

        # Try to end span multiple times
        service._end_plugin_span(data, success=True)
        service._end_plugin_span(data, success=True)
        service._end_plugin_span(data, success=True)

        # Should only be ended once
        assert data.get_one_of_outputs(PLUGIN_SPAN_ENDED_KEY) is True
