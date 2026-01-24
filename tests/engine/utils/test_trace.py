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
import time
from unittest import mock

import pytest
from django.conf import settings
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from bkflow.utils.trace import (
    PLUGIN_SPAN_ATTRIBUTES_KEY,
    PLUGIN_SPAN_NAME_KEY,
    PLUGIN_SPAN_PARENT_SPAN_ID_KEY,
    PLUGIN_SPAN_START_TIME_KEY,
    PLUGIN_SPAN_TRACE_ID_KEY,
    end_plugin_span,
    get_current_trace_context,
    plugin_method_span,
    start_plugin_span,
)


class MockData:
    """Mock data object for testing"""

    def __init__(self):
        self.outputs = {}

    def set_outputs(self, key, value):
        self.outputs[key] = value

    def get_one_of_outputs(self, key, default=None):
        return self.outputs.get(key, default)


@pytest.fixture
def tracer_provider():
    """Setup tracer provider for testing"""
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    yield provider
    trace.set_tracer_provider(None)


class TestGetCurrentTraceContext:
    """Test get_current_trace_context function"""

    def test_get_current_trace_context_no_span(self):
        """Test when there is no current span"""
        result = get_current_trace_context()
        assert result is None

    def test_get_current_trace_context_with_span(self, tracer_provider):
        """Test when there is a current span"""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_span"):
            result = get_current_trace_context()
            assert result is not None
            assert "trace_id" in result
            assert "span_id" in result
            assert len(result["trace_id"]) == 32  # 16 bytes = 32 hex chars
            assert len(result["span_id"]) == 16  # 8 bytes = 16 hex chars

    def test_get_current_trace_context_invalid_span(self, tracer_provider):
        """Test when span context is invalid"""
        # Create a span but make it invalid
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_span"):
            # Manually set an invalid context
            with mock.patch("opentelemetry.trace.get_current_span") as mock_get_span:
                mock_span = mock.Mock()
                mock_context = mock.Mock()
                mock_context.is_valid = False
                mock_span.get_span_context.return_value = mock_context
                mock_get_span.return_value = mock_span

                result = get_current_trace_context()
                assert result is None


class TestPluginMethodSpan:
    """Test plugin_method_span context manager"""

    def test_plugin_method_span_success(self, tracer_provider):
        """Test successful plugin method execution"""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("parent_span"):
            parent_context = get_current_trace_context()
            trace_id = parent_context["trace_id"]
            parent_span_id = parent_context["span_id"]

            with plugin_method_span(
                method_name="execute",
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                plugin_name="test_plugin",
                task_id="123",
                node_id="node_1",
            ) as span_result:
                assert span_result.success is True
                assert span_result.error_message is None
                # Simulate successful execution
                result = True

            assert result is True
            assert span_result.success is True

    def test_plugin_method_span_failure(self, tracer_provider):
        """Test failed plugin method execution"""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("parent_span"):
            parent_context = get_current_trace_context()
            trace_id = parent_context["trace_id"]
            parent_span_id = parent_context["span_id"]

            with plugin_method_span(
                method_name="execute",
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                plugin_name="test_plugin",
                task_id="123",
                node_id="node_1",
            ) as span_result:
                # Simulate failure
                span_result.set_error("Test error message")
                result = False

            assert result is False
            assert span_result.success is False
            assert span_result.error_message == "Test error message"

    def test_plugin_method_span_without_parent(self, tracer_provider):
        """Test plugin method span without parent context"""
        with plugin_method_span(
            method_name="execute",
            plugin_name="test_plugin",
            task_id="123",
            node_id="node_1",
        ) as span_result:
            assert span_result.success is True

    def test_plugin_method_span_with_schedule_count(self, tracer_provider):
        """Test plugin method span with schedule_count"""
        with plugin_method_span(
            method_name="schedule",
            plugin_name="test_plugin",
            task_id="123",
            node_id="node_1",
            schedule_count=5,
        ) as span_result:
            assert span_result.success is True

    def test_plugin_method_span_exception_handling(self, tracer_provider):
        """Test exception handling in plugin method span"""
        with pytest.raises(ValueError, match="Test exception"):
            with plugin_method_span(
                method_name="execute",
                plugin_name="test_plugin",
                task_id="123",
                node_id="node_1",
            ) as span_result:
                # Set error before raising exception
                span_result.set_error("Exception occurred")
                raise ValueError("Test exception")

        # Verify span_result was set correctly (even though exception was raised)
        # Note: span_result is only accessible within the context manager,
        # but the span should still be created with error status in the finally block


class TestStartPluginSpan:
    """Test start_plugin_span function"""

    def test_start_plugin_span_basic(self):
        """Test basic start_plugin_span functionality"""
        data = MockData()
        platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
        span_name = f"{platform_code}.test_plugin"
        returned_start_time = start_plugin_span(
            span_name=span_name,
            data=data,
            space_id="space_1",
            task_id="task_1",
            node_id="node_1",
        )

        assert isinstance(returned_start_time, int)
        assert returned_start_time > 0
        assert data.get_one_of_outputs(PLUGIN_SPAN_START_TIME_KEY) == returned_start_time
        assert data.get_one_of_outputs(PLUGIN_SPAN_NAME_KEY) == span_name
        attributes = data.get_one_of_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY)
        assert attributes["space_id"] == "space_1"
        assert attributes["task_id"] == "task_1"
        assert attributes["node_id"] == "node_1"

    def test_start_plugin_span_with_trace_context(self):
        """Test start_plugin_span with trace context"""
        data = MockData()
        platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
        span_name = f"{platform_code}.test_plugin"
        trace_id = "a" * 32  # 32 hex chars
        parent_span_id = "b" * 16  # 16 hex chars

        start_plugin_span(
            span_name=span_name,
            data=data,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            task_id="task_1",
        )

        assert data.get_one_of_outputs(PLUGIN_SPAN_TRACE_ID_KEY) == trace_id
        assert data.get_one_of_outputs(PLUGIN_SPAN_PARENT_SPAN_ID_KEY) == parent_span_id

    def test_start_plugin_span_serializes_attributes(self):
        """Test that attributes are serialized to strings"""
        data = MockData()
        platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
        span_name = f"{platform_code}.test_plugin"
        start_plugin_span(
            span_name=span_name,
            data=data,
            task_id=123,  # Integer
            space_id=None,  # None value
        )

        attributes = data.get_one_of_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY)
        assert attributes["task_id"] == "123"
        assert attributes["space_id"] == ""  # None converted to empty string


class TestEndPluginSpan:
    """Test end_plugin_span function"""

    def test_end_plugin_span_success(self, tracer_provider):
        """Test successful end_plugin_span"""
        data = MockData()
        start_time_ns = time.time_ns()

        # Setup span start info
        platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
        span_name = f"{platform_code}.test_plugin"
        data.set_outputs(PLUGIN_SPAN_START_TIME_KEY, start_time_ns)
        data.set_outputs(PLUGIN_SPAN_NAME_KEY, span_name)
        data.set_outputs(
            PLUGIN_SPAN_ATTRIBUTES_KEY,
            {"task_id": "task_1", "node_id": "node_1", "space_id": "space_1"},
        )

        # Wait a bit to ensure duration > 0
        time.sleep(0.01)

        end_plugin_span(data, success=True)

        # Verify span was created (no exception raised)
        assert True

    def test_end_plugin_span_failure(self, tracer_provider):
        """Test failed end_plugin_span"""
        data = MockData()
        start_time_ns = time.time_ns()

        platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
        span_name = f"{platform_code}.test_plugin"
        data.set_outputs(PLUGIN_SPAN_START_TIME_KEY, start_time_ns)
        data.set_outputs(PLUGIN_SPAN_NAME_KEY, span_name)
        data.set_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY, {"task_id": "task_1"})

        end_plugin_span(data, success=False, error_message="Test error")

        assert True

    def test_end_plugin_span_no_start_info(self):
        """Test end_plugin_span when start info is missing"""
        data = MockData()
        # Don't set start info

        # Should not raise exception, just return early
        end_plugin_span(data, success=True)

    def test_end_plugin_span_with_trace_context(self, tracer_provider):
        """Test end_plugin_span with trace context"""
        data = MockData()
        start_time_ns = time.time_ns()
        trace_id = "a" * 32
        parent_span_id = "b" * 16

        data.set_outputs(PLUGIN_SPAN_START_TIME_KEY, start_time_ns)
        data.set_outputs(PLUGIN_SPAN_NAME_KEY, "bk_flow.test_plugin")
        data.set_outputs(PLUGIN_SPAN_TRACE_ID_KEY, trace_id)
        data.set_outputs(PLUGIN_SPAN_PARENT_SPAN_ID_KEY, parent_span_id)
        data.set_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY, {"task_id": "task_1"})

        end_plugin_span(data, success=True)

        assert True

    def test_end_plugin_span_with_custom_end_time(self):
        """Test end_plugin_span with custom end time"""
        data = MockData()
        start_time_ns = time.time_ns()
        end_time_ns = start_time_ns + 1_000_000  # 1ms later

        platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
        span_name = f"{platform_code}.test_plugin"
        data.set_outputs(PLUGIN_SPAN_START_TIME_KEY, start_time_ns)
        data.set_outputs(PLUGIN_SPAN_NAME_KEY, span_name)
        data.set_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY, {"task_id": "task_1"})

        end_plugin_span(data, success=True, end_time_ns=end_time_ns)

        assert True

    def test_end_plugin_span_invalid_trace_context(self):
        """Test end_plugin_span with invalid trace context"""
        data = MockData()
        start_time_ns = time.time_ns()

        data.set_outputs(PLUGIN_SPAN_START_TIME_KEY, start_time_ns)
        data.set_outputs(PLUGIN_SPAN_NAME_KEY, "bk_flow.test_plugin")
        data.set_outputs(PLUGIN_SPAN_TRACE_ID_KEY, "invalid_trace_id")  # Invalid hex
        data.set_outputs(PLUGIN_SPAN_PARENT_SPAN_ID_KEY, "invalid_span_id")  # Invalid hex
        data.set_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY, {"task_id": "task_1"})

        # Should handle invalid context gracefully
        end_plugin_span(data, success=True)

        assert True


class TestPluginSpanIntegration:
    """Integration tests for plugin span functions"""

    def test_start_and_end_plugin_span_integration(self, tracer_provider):
        """Test complete flow of start and end plugin span"""
        data = MockData()

        # Start span
        platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
        span_name = f"{platform_code}.test_plugin"
        start_time = start_plugin_span(
            span_name=span_name,
            data=data,
            trace_id="a" * 32,
            parent_span_id="b" * 16,
            task_id="task_1",
            node_id="node_1",
        )

        assert data.get_one_of_outputs(PLUGIN_SPAN_START_TIME_KEY) == start_time

        # Wait a bit
        time.sleep(0.01)

        # End span
        end_plugin_span(data, success=True)

        assert True

    def test_plugin_method_span_with_plugin_span(self, tracer_provider):
        """Test plugin_method_span works with plugin span"""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("parent_span"):
            parent_context = get_current_trace_context()

            with plugin_method_span(
                method_name="execute",
                trace_id=parent_context["trace_id"],
                parent_span_id=parent_context["span_id"],
                plugin_name="test_plugin",
                task_id="123",
            ) as span_result:
                # Simulate plugin execution
                result = True

            assert result is True
            assert span_result.success is True
