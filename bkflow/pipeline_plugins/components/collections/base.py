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
import copy
import datetime

from bamboo_engine.context import Context
from bamboo_engine.eri import ContextValue, ContextValueType
from bamboo_engine.template import Template
from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from pipeline.core.flow import AbstractIntervalGenerator, StaticIntervalGenerator
from pipeline.core.flow.activity import Service
from pipeline.core.flow.io import ArrayItemSchema, IntItemSchema, ObjectItemSchema
from pipeline.eri.runtime import BambooDjangoRuntime

from bkflow.constants import TaskOperationSource, TaskOperationType
from bkflow.contrib.api.collections.interface import InterfaceModuleClient
from bkflow.exceptions import ValidationError
from bkflow.utils.handlers import mask_sensitive_data_for_display
from bkflow.utils.trace import (
    PLUGIN_SCHEDULE_COUNT_KEY,
    PLUGIN_SPAN_ENDED_KEY,
    PLUGIN_SPAN_ID_KEY,
    clean_plugin_span_outputs,
    end_plugin_span,
    plugin_method_span,
    start_plugin_span,
)


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

    def _get_mock_fail_info(self, taskflow_id):
        mock_data = self.get_taskflow_mock_data(taskflow_id)
        return mock_data.get("fail_nodes", []), mock_data.get("errors", {})

    def mock_schedule(self, data, parent_data, callback_data=None):
        taskflow_id = parent_data.get_one_of_inputs("task_id")
        fail_nodes, errors = self._get_mock_fail_info(taskflow_id)
        if self.id in fail_nodes:
            data.set_outputs("ex_data", errors.get(self.id, "mock failed"))
            return False
        taskflow_outputs = self.get_mock_outputs(taskflow_id)
        mock_outputs = taskflow_outputs.get(self.id, {})
        for k, value in mock_outputs.items():
            data.set_outputs(k, value)
        self.finish_schedule()
        return True

    def mock_execute(self, data, parent_data):
        taskflow_id = parent_data.get_one_of_inputs("task_id")
        fail_nodes, errors = self._get_mock_fail_info(taskflow_id)
        if self.id in fail_nodes:
            data.set_outputs("ex_data", errors.get(self.id, "mock failed"))
            return False
        if self.need_schedule():
            # 如果需要 schedule，一律改成 2s 轮询
            self.interval = StaticIntervalGenerator(2)
            return True
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
        return f"{platform_code}.plugin.{self.plugin_name}"

    def _get_span_attributes(self, data, parent_data):
        """获取 Span 属性，子类可以覆盖此方法来添加自定义属性"""
        attributes = {
            "space_id": parent_data.get_one_of_inputs("task_space_id"),
            "task_id": parent_data.get_one_of_inputs("task_id"),
            "node_id": self.id,
        }

        # 从 parent_data 中获取 custom_span_attributes，并合并到 Span 属性中
        # custom_span_attributes 通过 TaskContext 从 extra_info.custom_context 传递过来
        custom_span_attributes = parent_data.get_one_of_inputs("custom_span_attributes")
        if custom_span_attributes and isinstance(custom_span_attributes, dict):
            # 将自定义属性合并到基础属性中，自定义属性优先级更高
            attributes.update(custom_span_attributes)

        return attributes

    def _get_trace_context(self, data, parent_data):
        """从 parent_data 中获取 trace context"""
        return {
            "trace_id": parent_data.get_one_of_inputs("_trace_id"),
            "parent_span_id": parent_data.get_one_of_inputs("_parent_span_id"),
            "plugin_span_id": data.get_one_of_outputs(PLUGIN_SPAN_ID_KEY),
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
        clean_plugin_span_outputs(data)

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

        trace_context = self._get_trace_context(data, parent_data)
        method_attrs = self._get_method_span_attributes(data, parent_data)
        if self.enable_plugin_span and settings.ENABLE_OTEL_TRACE:
            data.set_outputs(PLUGIN_SCHEDULE_COUNT_KEY, 0)
            with plugin_method_span(
                method_name="execute",
                trace_id=trace_context.get("trace_id"),
                parent_span_id=trace_context.get("parent_span_id"),
                plugin_span_id=trace_context.get("plugin_span_id"),
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

        trace_context = self._get_trace_context(data, parent_data)
        method_attrs = self._get_method_span_attributes(data, parent_data)
        if self.enable_plugin_span and settings.ENABLE_OTEL_TRACE:
            schedule_count = data.get_one_of_outputs(PLUGIN_SCHEDULE_COUNT_KEY, 0) + 1
            data.set_outputs(PLUGIN_SCHEDULE_COUNT_KEY, schedule_count)
            method_attrs["schedule_count"] = schedule_count
            with plugin_method_span(
                method_name="schedule",
                trace_id=trace_context.get("trace_id"),
                parent_span_id=trace_context.get("parent_span_id"),
                plugin_span_id=trace_context.get("plugin_span_id"),
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


class LoopBaseService(BKFlowBaseService):
    """循环基类服务，提供循环执行相关的基础方法"""

    runtime = BambooDjangoRuntime()

    def outputs_format(self):
        return [
            self.OutputItem(name="任务ID", key="task_id", type="int", schema=IntItemSchema(description="Task ID")),
            self.OutputItem(
                name="循环输出",
                key=settings.PLUGIN_LOOP_OUTPUTS_KEY,
                type="array",
                schema=ArrayItemSchema(
                    description="循环输出", item_schema=ObjectItemSchema(description="循环输出", property_schemas={})
                ),
            ),
        ]

    def _render_parent_parameters(self, pipeline_tree, parent_task):
        """渲染父任务参数到子流程常量"""

        # 渲染父任务中的参数
        constants = pipeline_tree.get("constants", {})
        subprocess_inputs = {
            key: constant["value"]
            for key, constant in constants.items()
            if constant.get("show_type") == "show" and constant.get("need_render", True)
        }
        raw_subprocess_inputs = copy.deepcopy(subprocess_inputs)
        inputs_refs = Template(subprocess_inputs).get_reference()
        self.logger.info(f"subprocess original refs: {inputs_refs}")
        additional_refs = self.runtime.get_context_key_references(pipeline_id=self.top_pipeline_id, keys=inputs_refs)
        inputs_refs = inputs_refs.union(additional_refs)
        self.logger.info(f"subprocess final refs: {inputs_refs}")
        context_values = self.runtime.get_context_values(pipeline_id=self.top_pipeline_id, keys=inputs_refs)
        node = self.runtime.get_node(self.id)
        if node.loop_enabled:
            loop_params = (
                parent_task.pipeline_tree["activities"][self.id].get("loop_config", {}).get("loop_params") or {}
            )
            min_loop_times = None
            for param_key, param_value in loop_params.items():
                param_refs = Template(param_value).get_reference()
                if param_refs:
                    param_context_values = self.runtime.get_context_values(
                        pipeline_id=self.top_pipeline_id, keys=param_refs
                    )

                    hydrated_context = Context(self.runtime, param_context_values, {}).hydrate(deformat=True)
                    inputs = Template(param_value).render(hydrated_context)

                    # 判断渲染后的值是否为可迭代对象（列表/元组/字典），若不是则抛出异常
                    if not isinstance(inputs, (list, tuple, dict)):
                        raise ValidationError(
                            f"循环参数 {param_key} 的值必须是可迭代对象，" f"当前值类型为 {type(inputs).__name__}，值为：{inputs}"
                        )

                    if len(inputs) > settings.MAX_LOOP_TIMES:
                        raise ValidationError(f"循环参数 {param_key} 的值超过最大循环次数 {settings.MAX_LOOP_TIMES}")

                    current_len = len(inputs)
                    loop_item_value = list(inputs)[self.inner_loop - 1]
                else:
                    items = [item.strip() for item in param_value.split(",") if item.strip()]
                    current_len = len(items)
                    loop_item_value = items[self.inner_loop - 1]

                min_loop_times = current_len if min_loop_times is None else min(min_loop_times, current_len)

                context_value = ContextValue(
                    key=param_key, type=ContextValueType.PLAIN, value=loop_item_value, code=None
                )
                context_values.append(context_value)

            if not node.loop_times:
                self.runtime.update_node_loop_times(node_id=self.id, loop_times=min_loop_times)

        context_mappings = {c.key: c for c in context_values}
        root_pipeline_inputs = {
            key: inputs.value for key, inputs in self.runtime.get_data_inputs(self.top_pipeline_id).items()
        }
        context = Context(self.runtime, context_values, root_pipeline_inputs)
        hydrated_context = context.hydrate(deformat=True)
        # 对上下文进行脱敏后再打印日志，避免泄露 credentials 等敏感信息
        self.logger.info(f"subprocess parent hydrated context: {mask_sensitive_data_for_display(hydrated_context)}")

        parsed_subprocess_inputs = Template(subprocess_inputs).render(hydrated_context)
        parent_constants = parent_task.pipeline_tree["constants"]
        for key, constant in pipeline_tree.get("constants", {}).items():
            # 如果父流程直接勾选，则直接使用父流程对应变量的值
            raw_constant_value = raw_subprocess_inputs.get(key)
            if (
                raw_constant_value
                and isinstance(raw_constant_value, str)
                and parent_constants.get(raw_constant_value)
                and self.id in parent_constants[raw_constant_value]["source_info"]
                and key in parent_constants[raw_constant_value]["source_info"][self.id]
            ):
                constant["value"] = context_mappings[raw_subprocess_inputs[key]].value
            elif constant.get("need_render", True) and key in parsed_subprocess_inputs:
                constant["value"] = parsed_subprocess_inputs[key]
        # 对 constants 进行脱敏后再打印日志，避免泄露 credentials 等敏感信息
        self.logger.info(
            f'subprocess parsed constants: {mask_sensitive_data_for_display(pipeline_tree.get("constants", {}))}'
        )
        return context_values

    def _create_subprocess_task_instance(
        self, template_name, pipeline_tree, parent_task, trigger_method, template_id=None, notify_config=None
    ):
        """创建子任务实例和关系记录"""
        from bkflow.task.models import (
            TaskFlowRelation,
            TaskInstance,
            TaskOperationRecord,
        )
        from bkflow.task.utils import extract_extra_info

        with transaction.atomic():
            time_zone = timezone.pytz.timezone(settings.TIME_ZONE) or "Asia/Shanghai"
            time_stamp = datetime.datetime.now(tz=time_zone).strftime("%Y%m%d%H%M%S")
            create_task_data = {
                "name": f"{template_name}_子流程_{time_stamp}",
                "template_id": template_id,
                "creator": parent_task.creator,
                "scope_type": parent_task.scope_type,
                "scope_value": parent_task.scope_value,
                "space_id": parent_task.space_id,
                "pipeline_tree": pipeline_tree,
                "trigger_method": trigger_method,
                "mock_data": {},
            }
            DEFAULT_NOTIFY_CONFIG = {
                "notify_type": {"fail": [], "success": []},
                "notify_receivers": {"more_receiver": "", "receiver_group": []},
            }
            create_task_data.setdefault("extra_info", {}).update(
                {"notify_config": notify_config or DEFAULT_NOTIFY_CONFIG}
            )

            interface_client = InterfaceModuleClient()
            prepare_result = interface_client.prepare_task_extra_info(
                data={
                    "space_id": parent_task.space_id,
                    "pipeline_tree": pipeline_tree,
                    "extra_info": create_task_data.get("extra_info"),
                    "username": parent_task.creator,
                    "scope_type": parent_task.scope_type,
                    "scope_id": parent_task.scope_value,
                }
            )
            if not prepare_result.get("result"):
                raise ValidationError(f"生成开放插件快照失败: {prepare_result.get('message')}")
            create_task_data["extra_info"] = prepare_result["data"]["extra_info"]

            task_instance = TaskInstance.objects.create_instance(**create_task_data)

            # 记录操作流水
            pipeline_constants = task_instance.pipeline_tree.get("constants")
            extra_info = extract_extra_info(pipeline_constants)
            TaskOperationRecord.objects.create(
                instance_id=task_instance.id,
                operate_type=TaskOperationType.create.name,
                operate_source=TaskOperationSource.api.name,
                operator=parent_task.creator,
                extra_info=extra_info,
            )

            try:
                root_task_id = TaskFlowRelation.objects.get(task_id=parent_task.id).root_task_id
            except TaskFlowRelation.DoesNotExist:
                root_task_id = parent_task.id

            relate_info = {"node_id": self.id, "node_version": self.version, "trigger_method": trigger_method}
            TaskFlowRelation.objects.create(
                task_id=task_instance.id,
                parent_task_id=parent_task.id,
                root_task_id=root_task_id,
                extra_info=relate_info,
            )

            return task_instance

    def plugin_execute(self, data, parent_data):
        pass

    def plugin_schedule(self, data, parent_data, callback_data=None):
        from bkflow.task.models import TaskInstance

        task_success = callback_data.get("task_success", False)
        task_id = data.get_one_of_outputs("task_id")

        try:
            subprocess_task = TaskInstance.objects.get(id=task_id)
        except TaskInstance.DoesNotExist:
            message = f"子任务[{task_id}]不存在"
            self.logger.error(message)
            data.set_outputs("ex_data", message)
            return False

        subprocess_pipeline_id = subprocess_task.instance_id
        self.logger.info(f"subprocess pipeline id: {subprocess_pipeline_id}")
        subprocess_execution_data_outputs = self.runtime.get_execution_data_outputs(node_id=subprocess_pipeline_id)
        self.logger.info(f"subprocess execution data outputs: {subprocess_execution_data_outputs}")
        node_outputs = self.runtime.get_data_outputs(self.id)
        self.logger.info(f"node outputs: {node_outputs}")

        node = self.runtime.get_node(self.id)
        loop_outputs_key = node.loop_outputs_key
        self.finish_schedule()
        if not node.loop_enabled:
            if not task_success:
                data.set_outputs("ex_data", "子任务执行失败，请检查失败节点")
                return False

            for key in filter(lambda x: x in subprocess_execution_data_outputs, node_outputs.keys()):
                data.set_outputs(key, subprocess_execution_data_outputs[key])
        else:
            # 先剔除上下文循环输出列表中与当前循环次数（inner_loop）相同的旧记录，
            # 避免同一次循环被重复回调时（如节点先失败跳过、后重试成功的场景）
            # 导致上下文输出列表中出现重复记录。之后再由 extract_outputs 统一追加本次的 outputs。
            parent_task_id = parent_data.get_one_of_inputs("task_id")
            parent_pipeline_id = TaskInstance.objects.get(id=parent_task_id).instance_id

            loop_context_values = self.runtime.get_context_values(parent_pipeline_id, {loop_outputs_key})
            if loop_context_values:
                current_value = loop_context_values[0].value
                if isinstance(current_value, list):
                    filtered_value = [
                        item
                        for item in current_value
                        if not (isinstance(item, dict) and item.get("inner_loop") == self.inner_loop)
                    ]
                    if len(filtered_value) != len(current_value):
                        updated_context_values = [
                            ContextValue(
                                key=loop_outputs_key,
                                type=ContextValueType.PLAIN,
                                value=filtered_value,
                            )
                        ]
                        self.runtime.update_context_values(parent_pipeline_id, updated_context_values)

            outputs = {"task_id": task_id, "inner_loop": self.inner_loop}
            if not task_success:
                outputs["ex_data"] = "子任务执行失败，请检查失败节点"
                data.set_outputs("ex_data", "子任务执行失败，请检查失败节点")
            else:
                # 遍历子流程的输出，判断该输出是否在节点的输出变量中，在则加入
                for key, value in subprocess_execution_data_outputs.items():
                    data.set_outputs(key, subprocess_execution_data_outputs[key])
                    key = key.removeprefix("${").removesuffix("}")
                    outputs[key] = value
            # 无论成功失败，都将 outputs 字典设置到输出中，由 extract_outputs 统一追加到列表
            data.set_outputs(settings.LOOP_OUTPUTS_INNER_KEY, outputs)
            if not task_success:
                return False
        return True
