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

from django.apps import apps
from django.conf import settings
from pipeline.core.flow import AbstractIntervalGenerator, StaticIntervalGenerator
from pipeline.core.flow.activity import Service

from bkflow.utils.trace import end_plugin_span, plugin_method_span, start_plugin_span

# 标记 Span 是否已结束的 key
PLUGIN_SPAN_ENDED_KEY = "_plugin_span_ended"
# 记录 schedule 调用次数的 key
PLUGIN_SCHEDULE_COUNT_KEY = "_plugin_schedule_count"


class BKFlowBaseService(Service):
    # 插件名称，子类应覆盖此属性来声明插件名称
    plugin_name = "base"
    # 是否启用插件执行 Span 追踪，子类可以覆盖此属性来禁用
    enable_plugin_span = True

    @staticmethod
    def get_taskflow_mock_data(taskflow_id):
        TaskMockData = apps.get_model("task.TaskMockData")
        mock_data = TaskMockData.objects.filter(taskflow_id=taskflow_id).first()
        return getattr(mock_data, "data", {})

    def is_mock_node(self, taskflow_id, node_id):
        mock_data = self.get_taskflow_mock_data(taskflow_id)
        return node_id in mock_data.get("nodes", [])

    def get_mock_outputs(self, taskflow_id):
        mock_data = self.get_taskflow_mock_data(taskflow_id)
        return mock_data.get("outputs", {})

    def mock_schedule(self, data, parent_data, callback_data=None):
        taskflow_id = parent_data.get_one_of_inputs("task_id")
        taskflow_outputs = self.get_mock_outputs(taskflow_id)
        mock_outputs = taskflow_outputs.get(self.id, {})
        for k, value in mock_outputs.items():
            data.set_outputs(k, value)
        self.finish_schedule()
        return True

    def mock_execute(self, data, parent_data):
        if self.need_schedule():
            # 如果需要 schedule，一律改成 2s 轮询
            self.interval = StaticIntervalGenerator(2)
            return True
        taskflow_id = parent_data.get_one_of_inputs("task_id")
        taskflow_outputs = self.get_mock_outputs(taskflow_id)
        mock_outputs = taskflow_outputs.get(self.id, {})
        for k, value in mock_outputs.items():
            data.set_outputs(k, value)
        return True

    def plugin_execute(self, data, parent_data):
        pass

    def plugin_schedule(self, data, parent_data, callback_data=None):
        pass

    def _get_span_name(self):
        """获取 Span 名称，使用 PLATFORM_CODE 前缀加上插件名称"""
        platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
        return f"{platform_code}.{self.plugin_name}"

    def _get_span_attributes(self, data, parent_data):
        """获取 Span 属性，子类可以覆盖此方法来添加自定义属性"""
        return {
            "space_id": parent_data.get_one_of_inputs("task_space_id"),
            "task_id": parent_data.get_one_of_inputs("task_id"),
            "node_id": self.id,
        }

    def _get_trace_context(self, parent_data):
        """从 parent_data 中获取 trace context"""
        return {
            "trace_id": parent_data.get_one_of_inputs("_trace_id"),
            "parent_span_id": parent_data.get_one_of_inputs("_parent_span_id"),
        }

    def _get_method_span_attributes(self, data, parent_data):
        """获取方法级别 Span 的属性"""
        attrs = self._get_span_attributes(data, parent_data)
        attrs["plugin_name"] = self.plugin_name
        return attrs

    def _start_plugin_span(self, data, parent_data):
        """启动插件执行 Span"""
        # 只有在启用 trace 且插件启用 span 追踪时才启动
        if not self.enable_plugin_span or not settings.ENABLE_OTEL_TRACE:
            return

        span_name = self._get_span_name()
        attributes = self._get_span_attributes(data, parent_data)

        # 从 parent_data 中获取 trace context（由 start_task 时注入）
        trace_id = parent_data.get_one_of_inputs("_trace_id")
        parent_span_id = parent_data.get_one_of_inputs("_parent_span_id")

        start_plugin_span(
            span_name=span_name,
            data=data,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            **attributes,
        )
        data.set_outputs(PLUGIN_SPAN_ENDED_KEY, False)

    def _end_plugin_span(self, data, success, error_message=None):
        """结束插件执行 Span（确保只调用一次）"""
        # 只有在启用 trace 且插件启用 span 追踪时才结束
        if not self.enable_plugin_span or not settings.ENABLE_OTEL_TRACE:
            return

        if data.get_one_of_outputs(PLUGIN_SPAN_ENDED_KEY, False):
            return

        end_plugin_span(data, success=success, error_message=error_message)
        data.set_outputs(PLUGIN_SPAN_ENDED_KEY, True)

    def _get_error_message(self, data):
        """从 data 中获取错误信息"""
        return data.get_one_of_outputs("ex_data") or "Plugin execution failed"

    def execute(self, data, parent_data):
        # Mock 模式不追踪 Span
        if parent_data.get_one_of_inputs("is_mock") and self.is_mock_node(
            parent_data.get_one_of_inputs("task_id"), self.id
        ):
            return self.mock_execute(data, parent_data)

        self._start_plugin_span(data, parent_data)

        trace_context = self._get_trace_context(parent_data)
        method_attrs = self._get_method_span_attributes(data, parent_data)
        if self.enable_plugin_span and settings.ENABLE_OTEL_TRACE:
            data.set_outputs(PLUGIN_SCHEDULE_COUNT_KEY, 0)
            with plugin_method_span(
                method_name="execute",
                trace_id=trace_context.get("trace_id"),
                parent_span_id=trace_context.get("parent_span_id"),
                **method_attrs,
            ) as span_result:
                result = self.plugin_execute(data, parent_data)
                if not result:
                    span_result.set_error(self._get_error_message(data))
        else:
            result = self.plugin_execute(data, parent_data)

        if not result:
            self._end_plugin_span(data, success=False, error_message=self._get_error_message(data))
        elif not self.need_schedule():
            self._end_plugin_span(data, success=True)

        return result

    def schedule(self, data, parent_data, callback_data=None):
        # Mock 模式不追踪 Span
        if parent_data.get_one_of_inputs("is_mock") and self.is_mock_node(
            parent_data.get_one_of_inputs("task_id"), self.id
        ):
            return self.mock_schedule(data, parent_data)

        trace_context = self._get_trace_context(parent_data)
        method_attrs = self._get_method_span_attributes(data, parent_data)
        if self.enable_plugin_span and settings.ENABLE_OTEL_TRACE:
            schedule_count = data.get_one_of_outputs(PLUGIN_SCHEDULE_COUNT_KEY, 0) + 1
            data.set_outputs(PLUGIN_SCHEDULE_COUNT_KEY, schedule_count)
            method_attrs["schedule_count"] = schedule_count
            with plugin_method_span(
                method_name="schedule",
                trace_id=trace_context.get("trace_id"),
                parent_span_id=trace_context.get("parent_span_id"),
                **method_attrs,
            ) as span_result:
                result = self.plugin_schedule(data, parent_data, callback_data)
                if not result:
                    span_result.set_error(self._get_error_message(data))
        else:
            result = self.plugin_schedule(data, parent_data, callback_data)

        # 判断是否需要结束主 Span
        # _end_plugin_span 内部已有幂等保护，不会重复结束
        if not result:
            self._end_plugin_span(data, success=False, error_message=self._get_error_message(data))
        elif self.is_schedule_finished():
            self._end_plugin_span(data, success=True)

        return result


class StepIntervalGenerator(AbstractIntervalGenerator):
    def __init__(self, max_count=200, init_interval=10, max_interval=600, fix_interval=None):
        """
        :param max_count: 最大计数次数，用于 reach_limit 判断
        :param init_interval: 初始的间隔时间
        :param max_interval: 最大的间隔时间，到达后不会继续增加
        :param fix_interval: 固定的间隔时间，优先级最高
        """
        super().__init__()
        self.fix_interval = fix_interval
        self.init_interval = init_interval
        self.max_interval = max_interval
        self.max_count = max_count

    def next(self):
        super().next()
        # 最小 10s，最大 600s 一次
        return self.fix_interval or (
            self.init_interval if self.count < 30 else min((self.count - 25) ** 2, self.max_interval)
        )

    def reach_limit(self):
        return self.count >= self.max_count
