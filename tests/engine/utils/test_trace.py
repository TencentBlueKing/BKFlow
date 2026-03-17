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
from django.test import override_settings
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from bkflow.utils.trace import (
    PLUGIN_SCHEDULE_COUNT_KEY,
    PLUGIN_SPAN_ATTRIBUTES_KEY,
    PLUGIN_SPAN_ENDED_KEY,
    PLUGIN_SPAN_ID_KEY,
    PLUGIN_SPAN_NAME_KEY,
    PLUGIN_SPAN_PARENT_SPAN_ID_KEY,
    PLUGIN_SPAN_START_TIME_KEY,
    PLUGIN_SPAN_TRACE_ID_KEY,
    _generate_span_id,
    clean_plugin_span_outputs,
    create_execution_span,
    end_plugin_span,
    get_current_trace_context,
    plugin_method_span,
    start_plugin_span,
)


class MockData:
    def __init__(self):
        self.outputs = {}

    def set_outputs(self, key, value):
        self.outputs[key] = value

    def get_one_of_outputs(self, key, default=None):
        return self.outputs.get(key, default)


@pytest.fixture
def tracer_provider():
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    yield provider
    trace.set_tracer_provider(None)


class TestGetCurrentTraceContext:
    def test_get_current_trace_context_no_span(self):
        result = get_current_trace_context()
        assert result is None

    def test_get_current_trace_context_with_span(self, tracer_provider):
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_span"):
            result = get_current_trace_context()
            assert result is not None
            assert "trace_id" in result
            assert "span_id" in result
            assert len(result["trace_id"]) == 32
            assert len(result["span_id"]) == 16

    def test_get_current_trace_context_invalid_span(self, tracer_provider):
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_span"):
            with mock.patch("opentelemetry.trace.get_current_span") as mock_get_span:
                mock_span = mock.Mock()
                mock_context = mock.Mock()
                mock_context.is_valid = False
                mock_span.get_span_context.return_value = mock_context
                mock_get_span.return_value = mock_span
                result = get_current_trace_context()
                assert result is None


class TestPluginMethodSpan:
    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_plugin_method_span_success(self, tracer_provider):
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
                result = True
            assert result is True
            assert span_result.success is True

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_plugin_method_span_failure(self, tracer_provider):
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
                span_result.set_error("Test error message")
                result = False
            assert result is False
            assert span_result.success is False
            assert span_result.error_message == "Test error message"

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_plugin_method_span_without_parent(self, tracer_provider):
        with plugin_method_span(
            method_name="execute",
            plugin_name="test_plugin",
            task_id="123",
            node_id="node_1",
        ) as span_result:
            assert span_result.success is True

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_plugin_method_span_with_schedule_count(self, tracer_provider):
        with plugin_method_span(
            method_name="schedule",
            plugin_name="test_plugin",
            task_id="123",
            node_id="node_1",
            schedule_count=5,
        ) as span_result:
            assert span_result.success is True

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_plugin_method_span_exception_handling(self, tracer_provider):
        with pytest.raises(ValueError, match="Test exception"):
            with plugin_method_span(
                method_name="execute",
                plugin_name="test_plugin",
                task_id="123",
                node_id="node_1",
            ) as span_result:
                span_result.set_error("Exception occurred")
                raise ValueError("Test exception")

    @override_settings(ENABLE_OTEL_TRACE=False)
    def test_plugin_method_span_trace_disabled(self):
        with plugin_method_span(
            method_name="execute",
            plugin_name="test_plugin",
            task_id="123",
        ) as span_result:
            assert span_result is None

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_plugin_method_span_with_plugin_span_id(self, tracer_provider):
        trace_id = "a" * 32
        parent_span_id = "b" * 16
        plugin_span_id = "c" * 16
        with plugin_method_span(
            method_name="execute",
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            plugin_span_id=plugin_span_id,
            plugin_name="test_plugin",
            task_id="123",
        ) as span_result:
            assert span_result is not None
            assert span_result.success is True


class TestStartPluginSpan:
    def test_start_plugin_span_basic(self):
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
        plugin_span_id = data.get_one_of_outputs(PLUGIN_SPAN_ID_KEY)
        assert plugin_span_id is not None
        assert len(plugin_span_id) == 16
        int(plugin_span_id, 16)

    def test_start_plugin_span_with_trace_context(self):
        data = MockData()
        platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
        span_name = f"{platform_code}.test_plugin"
        trace_id = "a" * 32
        parent_span_id = "b" * 16
        start_plugin_span(
            span_name=span_name,
            data=data,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            task_id="task_1",
        )
        assert data.get_one_of_outputs(PLUGIN_SPAN_TRACE_ID_KEY) == trace_id
        assert data.get_one_of_outputs(PLUGIN_SPAN_PARENT_SPAN_ID_KEY) == parent_span_id
        plugin_span_id = data.get_one_of_outputs(PLUGIN_SPAN_ID_KEY)
        assert plugin_span_id is not None
        assert len(plugin_span_id) == 16
        int(plugin_span_id, 16)

    def test_start_plugin_span_serializes_attributes(self):
        data = MockData()
        platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
        span_name = f"{platform_code}.test_plugin"
        start_plugin_span(
            span_name=span_name,
            data=data,
            task_id=123,
            space_id=None,
        )
        attributes = data.get_one_of_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY)
        assert attributes["task_id"] == "123"
        assert attributes["space_id"] == ""


class TestGenerateSpanId:
    def test_generate_span_id_returns_positive_int(self):
        span_id = _generate_span_id()
        assert isinstance(span_id, int)
        assert span_id >= 0

    def test_generate_span_id_uniqueness(self):
        ids = {_generate_span_id() for _ in range(100)}
        assert len(ids) > 90


class TestCleanPluginSpanOutputs:
    def test_clean_removes_all_span_keys(self):
        data = MockData()
        data.outputs[PLUGIN_SPAN_START_TIME_KEY] = 123
        data.outputs[PLUGIN_SPAN_NAME_KEY] = "test"
        data.outputs[PLUGIN_SPAN_TRACE_ID_KEY] = "aaa"
        data.outputs[PLUGIN_SPAN_PARENT_SPAN_ID_KEY] = "bbb"
        data.outputs[PLUGIN_SPAN_ID_KEY] = "ccc"
        data.outputs[PLUGIN_SPAN_ATTRIBUTES_KEY] = {}
        data.outputs[PLUGIN_SPAN_ENDED_KEY] = True
        data.outputs[PLUGIN_SCHEDULE_COUNT_KEY] = 3
        data.outputs["user_key"] = "should_remain"

        clean_plugin_span_outputs(data)

        assert PLUGIN_SPAN_START_TIME_KEY not in data.outputs
        assert PLUGIN_SPAN_NAME_KEY not in data.outputs
        assert PLUGIN_SPAN_TRACE_ID_KEY not in data.outputs
        assert PLUGIN_SPAN_PARENT_SPAN_ID_KEY not in data.outputs
        assert PLUGIN_SPAN_ID_KEY not in data.outputs
        assert PLUGIN_SPAN_ATTRIBUTES_KEY not in data.outputs
        assert PLUGIN_SPAN_ENDED_KEY not in data.outputs
        assert PLUGIN_SCHEDULE_COUNT_KEY not in data.outputs
        assert data.outputs["user_key"] == "should_remain"

    def test_clean_handles_missing_keys(self):
        data = MockData()
        data.outputs["user_key"] = "value"
        clean_plugin_span_outputs(data)
        assert data.outputs["user_key"] == "value"

    def test_clean_handles_no_outputs(self):
        data = object()
        clean_plugin_span_outputs(data)


class TestCreateExecutionSpan:
    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_create_execution_span_returns_valid_ids(self, tracer_provider):
        trace_id_hex, span_id_hex = create_execution_span(
            task_id=1,
            space_id=100,
            pipeline_instance_id="pipe-123",
            operator="admin",
        )
        assert trace_id_hex is not None
        assert span_id_hex is not None
        assert len(trace_id_hex) == 32
        assert len(span_id_hex) == 16
        int(trace_id_hex, 16)
        int(span_id_hex, 16)

    @override_settings(ENABLE_OTEL_TRACE=False)
    def test_create_execution_span_disabled(self):
        trace_id_hex, span_id_hex = create_execution_span(
            task_id=1,
            space_id=100,
            pipeline_instance_id="pipe-123",
        )
        assert trace_id_hex is None
        assert span_id_hex is None


class TestEndPluginSpan:
    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_end_plugin_span_success(self, tracer_provider):
        data = MockData()
        start_time_ns = time.time_ns()
        platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
        span_name = f"{platform_code}.test_plugin"
        data.set_outputs(PLUGIN_SPAN_START_TIME_KEY, start_time_ns)
        data.set_outputs(PLUGIN_SPAN_NAME_KEY, span_name)
        data.set_outputs(
            PLUGIN_SPAN_ATTRIBUTES_KEY,
            {"task_id": "task_1", "node_id": "node_1", "space_id": "space_1"},
        )
        data.set_outputs(PLUGIN_SPAN_ID_KEY, "c" * 16)
        time.sleep(0.01)
        end_plugin_span(data, success=True)

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_end_plugin_span_failure(self, tracer_provider):
        data = MockData()
        start_time_ns = time.time_ns()
        platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
        span_name = f"{platform_code}.test_plugin"
        data.set_outputs(PLUGIN_SPAN_START_TIME_KEY, start_time_ns)
        data.set_outputs(PLUGIN_SPAN_NAME_KEY, span_name)
        data.set_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY, {"task_id": "task_1"})
        data.set_outputs(PLUGIN_SPAN_ID_KEY, "d" * 16)
        end_plugin_span(data, success=False, error_message="Test error")

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_end_plugin_span_no_start_info(self):
        data = MockData()
        end_plugin_span(data, success=True)

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_end_plugin_span_with_trace_context(self, tracer_provider):
        data = MockData()
        start_time_ns = time.time_ns()
        trace_id = "a" * 32
        parent_span_id = "b" * 16
        data.set_outputs(PLUGIN_SPAN_START_TIME_KEY, start_time_ns)
        data.set_outputs(PLUGIN_SPAN_NAME_KEY, "bk_flow.test_plugin")
        data.set_outputs(PLUGIN_SPAN_TRACE_ID_KEY, trace_id)
        data.set_outputs(PLUGIN_SPAN_PARENT_SPAN_ID_KEY, parent_span_id)
        data.set_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY, {"task_id": "task_1"})
        data.set_outputs(PLUGIN_SPAN_ID_KEY, "e" * 16)
        end_plugin_span(data, success=True)

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_end_plugin_span_with_custom_end_time(self, tracer_provider):
        data = MockData()
        start_time_ns = time.time_ns()
        end_time_ns = start_time_ns + 1_000_000
        platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
        span_name = f"{platform_code}.test_plugin"
        data.set_outputs(PLUGIN_SPAN_START_TIME_KEY, start_time_ns)
        data.set_outputs(PLUGIN_SPAN_NAME_KEY, span_name)
        data.set_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY, {"task_id": "task_1"})
        data.set_outputs(PLUGIN_SPAN_ID_KEY, "f" * 16)
        end_plugin_span(data, success=True, end_time_ns=end_time_ns)

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_end_plugin_span_invalid_trace_context(self, tracer_provider):
        data = MockData()
        start_time_ns = time.time_ns()
        data.set_outputs(PLUGIN_SPAN_START_TIME_KEY, start_time_ns)
        data.set_outputs(PLUGIN_SPAN_NAME_KEY, "bk_flow.test_plugin")
        data.set_outputs(PLUGIN_SPAN_TRACE_ID_KEY, "invalid_trace_id")
        data.set_outputs(PLUGIN_SPAN_PARENT_SPAN_ID_KEY, "invalid_span_id")
        data.set_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY, {"task_id": "task_1"})
        data.set_outputs(PLUGIN_SPAN_ID_KEY, "a1b2c3d4e5f67890")
        end_plugin_span(data, success=True)


class TestPluginSpanIntegration:
    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_start_and_end_plugin_span_integration(self, tracer_provider):
        data = MockData()
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
        assert data.get_one_of_outputs(PLUGIN_SPAN_ID_KEY) is not None
        time.sleep(0.01)
        end_plugin_span(data, success=True)

    @override_settings(ENABLE_OTEL_TRACE=True)
    def test_plugin_method_span_with_plugin_span(self, tracer_provider):
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
                result = True
            assert result is True
            assert span_result.success is True
