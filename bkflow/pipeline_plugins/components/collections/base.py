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

import copy
import json
import logging

from django.apps import apps
from django.conf import settings
from pipeline.core.flow import AbstractIntervalGenerator, StaticIntervalGenerator
from pipeline.core.flow.activity import Service
from pipeline.eri.runtime import BambooDjangoRuntime

from bamboo_engine.template import Template
from bkflow.utils import crypto
from bkflow.utils.trace import (
    PLUGIN_SCHEDULE_COUNT_KEY,
    PLUGIN_SPAN_ENDED_KEY,
    PLUGIN_SPAN_ID_KEY,
    clean_plugin_span_outputs,
    end_plugin_span,
    plugin_method_span,
    start_plugin_span,
)


logger = logging.getLogger("root")
PASSWORD_VALUE_TYPE = "password_value"
PASSWORD_MASK_VALUE = "******"


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

        # 预检：检查是否需要密码解密逻辑
        try:
            inputs_str = json.dumps(data.get_inputs(), default=str) + json.dumps(parent_data.get_inputs(), default=str)
            need_password_handle = PASSWORD_VALUE_TYPE in inputs_str
        except Exception:
            need_password_handle = True  # 检查失败保守处理，执行密码解密逻辑

        input_password_refs = {}
        copy_data = None
        copy_parent_data = None
        copy_data_mask = None
        copy_parent_data_mask = None

        if need_password_handle:
            input_password_refs = self._get_raw_password_map()  # 获取密码变量key-对应的加密后的value

            # 自动解密 inputs 中引用的全局密码变量，使所有插件都支持输入全局密码变量
            copy_data = copy.deepcopy(data)
            copy_parent_data = copy.deepcopy(parent_data)
            self._auto_decrypt_password_inputs(data, input_password_refs=input_password_refs)
            self._auto_decrypt_password_inputs(parent_data, input_password_refs=input_password_refs)

            # 另外拷贝一份出来做掩码处理
            copy_data_mask = copy.deepcopy(copy_data)
            copy_parent_data_mask = copy.deepcopy(copy_parent_data)
            self._auto_decrypt_password_inputs(copy_data_mask, input_password_refs=input_password_refs, mask_flag=True)
            self._auto_decrypt_password_inputs(copy_parent_data_mask, input_password_refs=input_password_refs, mask_flag=True)

        result = False
        try:
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
        finally:
            # 对 data 的 input 做掩码处理,同时 outputs 需要继承解密后的数据，方便后续调用
            if need_password_handle:
                self._sync_new_fields(copy_data.inputs, data.inputs)
                self._sync_new_fields(copy_data_mask.inputs, data.inputs)
                self._deep_update(data.inputs, copy_data_mask.inputs)
                _mask_meta_system_mask_info = {
                    'decrypt_input_data': copy_data.inputs,
                }
                data.inputs._mask_meta_system_mask_info = _mask_meta_system_mask_info

                self._sync_new_fields(copy_parent_data.inputs, parent_data.inputs)
                self._sync_new_fields(copy_parent_data_mask.inputs, parent_data.inputs)
                self._deep_update(parent_data.inputs, copy_parent_data_mask.inputs)
                _mask_meta_system_parent_mask_info = {
                    'decrypt_input_data': copy_parent_data.inputs,
                }
                parent_data.inputs._mask_meta_system_parent_mask_info = _mask_meta_system_parent_mask_info

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

        # schedule 里面每次判断是否有 is_mask ，来恢复 data 的输入数据
        _mask_meta_system_mask_info = data.inputs.get("_mask_meta_system_mask_info")
        if _mask_meta_system_mask_info:
            data.inputs = type(data.inputs)(_mask_meta_system_mask_info.get("decrypt_input_data"))

        # 对于 parent_data 可能需要解密
        _mask_meta_system_parent_mask_info = parent_data.inputs.get("_mask_meta_system_parent_mask_info")
        if _mask_meta_system_parent_mask_info:
            parent_data.inputs = type(parent_data.inputs)(_mask_meta_system_parent_mask_info.get("decrypt_input_data"))

        # 预检：检查是否需要密码解密逻辑
        try:
            inputs_str = json.dumps(data.get_inputs(), default=str) + json.dumps(parent_data.get_inputs(), default=str)
            need_password_handle = PASSWORD_VALUE_TYPE in inputs_str
        except Exception:
            need_password_handle = True  # 如果检查失败，保守处理，执行密码解密逻辑

        input_password_refs = {}
        copy_data = None
        copy_parent_data = None
        copy_data_mask = None
        copy_parent_data_mask = None

        if need_password_handle:
            input_password_refs = self._get_raw_password_map()  # 获取密码变量key-对应的加密后的value

            # 对于 data 进行解密，同时生成一份掩码版本
            copy_data = copy.deepcopy(data)
            copy_data_mask = copy.deepcopy(data)  # 用于 schedule 执行完做掩码处理
            self._auto_decrypt_password_inputs(data, input_password_refs=input_password_refs)
            self._auto_decrypt_password_inputs(copy_data_mask, input_password_refs=input_password_refs, mask_flag=True)

            copy_parent_data = copy.deepcopy(parent_data)
            copy_parent_data_mask = copy.deepcopy(parent_data)
            self._auto_decrypt_password_inputs(parent_data, input_password_refs=input_password_refs)
            self._auto_decrypt_password_inputs(copy_parent_data_mask, input_password_refs=input_password_refs, mask_flag=True)

        result = False
        try:
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
        finally:
            if need_password_handle:
                # 对 data 的 input 做掩码处理,同时 outputs 需要继承解密后的数据，方便后续调用
                self._sync_new_fields(copy_data.inputs, data.inputs)
                self._sync_new_fields(copy_data_mask.inputs, data.inputs)
                self._deep_update(data.inputs, copy_data_mask.inputs)

                _mask_meta_system_mask_info = {
                    'decrypt_input_data': copy_data.inputs,
                }
                data.inputs._mask_meta_system_mask_info = _mask_meta_system_mask_info

                # 更新 parent 相关
                self._sync_new_fields(copy_parent_data.inputs, parent_data.inputs)
                self._sync_new_fields(copy_parent_data_mask.inputs, parent_data.inputs)
                self._deep_update(parent_data.inputs, copy_parent_data_mask.inputs)
                _mask_meta_system_parent_mask_info = {
                    'decrypt_input_data': copy_parent_data.inputs,
                }
                parent_data.inputs._mask_meta_system_parent_mask_info = _mask_meta_system_parent_mask_info

        # 判断是否需要结束主 Span
        # _end_plugin_span 内部已有幂等保护，不会重复结束
        if not result:
            self._end_plugin_span(data, success=False, error_message=self._get_error_message(data))
        elif self.is_schedule_finished():
            self._end_plugin_span(data, success=True)

        return result

    def _get_raw_password_map(self):
        """
        从 BambooDjangoRuntime 获取当前节点原始输入，解析变量引用，
        从全局上下文中查找加密密码值，返回 {var_name: cipher_struct} 映射。
        用于获取所有需要引用密码变量的 key 和加密后的数据，方便后续做密码映射。
        """
        try:
            node_id = self.id
            runtime = BambooDjangoRuntime()

            # 1. 获取当前节点的原始 Data
            raw_data = runtime.get_data(node_id)
            need_render_inputs = raw_data.need_render_inputs()

            # 2. 获取当前节点所属的 top_pipeline_id（根流程 ID）
            state = runtime.get_state(node_id)
            current_node = node_id
            while state.parent_id:
                current_node = state.parent_id
                state = runtime.get_state(current_node)
            pipeline_id = current_node

            # 3. 获取所有变量引用（如 ${customerPassword}）
            refs = set(Template(need_render_inputs).get_reference())
            additional_refs = runtime.get_context_key_references(pipeline_id=pipeline_id, keys=refs)
            inputs_refs = refs.union(additional_refs)

            if not inputs_refs:
                return {}

            # 4. 查询全局上下文中的这些变量
            context_values = runtime.get_context_values(pipeline_id=pipeline_id, keys=inputs_refs)

            # 5. 只保留值是密码结构体的变量
            password_map = {}
            for cv in context_values:
                val = cv.value
                if not isinstance(val, dict):
                    continue
                if val.get("type") != PASSWORD_VALUE_TYPE:
                    continue
                password_map[cv.key] = val

            return password_map
        except Exception:
            logger.warning("[%s] get raw password map failed, fallback to empty map", self.plugin_name)
            return {}

    def _auto_decrypt_password_inputs(self, data, input_password_refs=None, mask_flag=False):
        """
        自动识别并解密 data.inputs 中的密码变量值（包括嵌套结构）。

        :param data: 插件数据对象
        :param input_password_refs: 密码变量引用字典，用于解密密码变量值(只会在value是str类型才会使用)
        :param mask_flag: 本次是否是掩码处理，True 时替换为掩码值而不是明文
        """
        try:
            inputs = data.get_inputs()
        except Exception:
            return

        if not inputs:
            return

        for key, value in list(inputs.items()):
            # 顶层 value 直接是密码结构体
            if isinstance(value, dict) and value.get("type") == PASSWORD_VALUE_TYPE:
                self._try_decrypt_value(value, inputs, key, mask_flag=mask_flag)
            # 容器类型，递归进入查找嵌套密码结构体
            elif isinstance(value, (dict, list)):
                self._decrypt_nested_passwords(value, input_password_refs=input_password_refs, mask_flag=mask_flag)
            elif isinstance(value, str):
                self._try_decrypt_value(value, inputs, key, input_password_refs=input_password_refs, mask_flag=mask_flag)

    def _try_decrypt_value(self, password_struct, container, key_or_index, input_password_refs=None, mask_flag=False):
        """
        尝试解密一个密码结构体,会根据 password_struct 动态处理

        :param password_struct:
            password_struct:dict, 如下结构
                密码结构体 dict，如 {"type": "password_value", "value": "rsa_str:::***"};
            password_struct:str, 如下结构
                密码结构体 string，如 xxxx{"type": "password_value", "value": "rsa_str:::***"}xxxx;
        :param container: 包含这个密码结构体的父容器（dict 或 list）
        :param key_or_index: 密码结构体在容器中的 key（dict）或 index（list）
        :param input_password_refs: 密码变量引用字典，用于解密密码变量值(只会在value是str类型才会使用)
        :param mask_flag: 本次是否是掩码处理，True 时替换为掩码值而不是明文
        """

        def get_decrypt_value(_password_struct):
            cipher = _password_struct.get("value")
            if not cipher or not isinstance(cipher, str):
                return
            try:
                plain = crypto.decrypt(cipher)
            except Exception:
                logger.warning("[%s] auto decrypt password input failed", self.plugin_name)
                return
            return plain

        if isinstance(password_struct, str):
            if not input_password_refs:
                return
            for encrypted_password in input_password_refs.values():
                str_password = json.dumps(encrypted_password).replace('"', "'")

                plain = get_decrypt_value(encrypted_password)
                if plain is None:
                    continue
                replace_value = PASSWORD_MASK_VALUE if mask_flag else plain

                # 使用 str.replace 直接替换加密后的字符串
                if str_password in password_struct:
                    password_struct = password_struct.replace(str_password, replace_value)
            container[key_or_index] = password_struct
        elif isinstance(password_struct, dict):
            plain = get_decrypt_value(password_struct)
            if plain is None:
                return
            # 替换为掩码值或明文
            container[key_or_index] = PASSWORD_MASK_VALUE if mask_flag else plain

    def _decrypt_nested_passwords(self, obj, input_password_refs=None, mask_flag=False):
        """递归遍历 obj（dict 或 list），找到所有密码结构体并解密"""
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                if isinstance(v, dict) and v.get("type") == PASSWORD_VALUE_TYPE:
                    self._try_decrypt_value(v, obj, k, mask_flag=mask_flag)
                elif isinstance(v, (dict, list)):
                    self._decrypt_nested_passwords(v, input_password_refs=input_password_refs, mask_flag=mask_flag)
                elif isinstance(v, str):
                    self._try_decrypt_value(v, obj, k, input_password_refs=input_password_refs, mask_flag=mask_flag)
        elif isinstance(obj, list):
            for idx, v in enumerate(obj):
                if isinstance(v, dict) and v.get("type") == PASSWORD_VALUE_TYPE:
                    self._try_decrypt_value(v, obj, idx, mask_flag=mask_flag)
                elif isinstance(v, (dict, list)):
                    self._decrypt_nested_passwords(v, input_password_refs=input_password_refs, mask_flag=mask_flag)
                elif isinstance(v, str):
                    self._try_decrypt_value(v, obj, idx, input_password_refs=input_password_refs, mask_flag=mask_flag)

    def _sync_new_fields(self, target, source):
        """
        将 source 中新增的字段同步到 target 中。
        只同步 target 中不存在的字段（即插件新增的字段），不更新已有字段。
        支持嵌套的 dict 和 list 结构。

        这个方法的目的是：将插件执行后对 data.inputs 新增的字段同步到掩码副本中，
        这样在做掩码处理时不会丢失插件对 inputs 新增的字段。

        :param target: 需要被更新的数据（如 copy_data.inputs 或 copy_data_mask.inputs）
        :param source: 源数据（如 data.inputs，包含插件新增的字段）
        """
        if isinstance(source, dict) and isinstance(target, dict):
            for key, source_value in source.items():
                if key not in target:
                    # 如果 target 中不存在该 key，说明是插件新增的字段，直接添加
                    target[key] = copy.deepcopy(source_value)
                elif isinstance(source_value, (dict, list)) and isinstance(target.get(key), (dict, list)):
                    # 如果 target 中存在该 key，且值是容器类型，递归处理
                    self._sync_new_fields(target[key], source_value)
        elif isinstance(source, list) and isinstance(target, list):
            # 对于 list，如果长度相同则按索引递归处理，否则不处理（避免误判）
            if len(source) == len(target):
                for i in range(len(source)):
                    if isinstance(source[i], (dict, list)) and isinstance(target[i], (dict, list)):
                        self._sync_new_fields(target[i], source[i])

    def _deep_update(self, target, source):
        """
        递归地深更新 target，将 source 中的字段更新到 target 中。
        对于嵌套的 dict，会递归更新其中的字段；对于 list，会按索引递归更新。
        对于非容器类型的值，直接替换。

        :param target: 需要被更新的数据（如 data.inputs）
        :param source: 用于更新的数据（如 copy_data_mask.inputs）
        """
        if isinstance(source, dict) and isinstance(target, dict):
            for key, source_value in source.items():
                if key in target and isinstance(target[key], dict) and isinstance(source_value, dict):
                    # 如果 target 中存在该 key，且两边都是 dict，递归更新
                    self._deep_update(target[key], source_value)
                elif key in target and isinstance(target[key], list) and isinstance(source_value, list):
                    # 如果 target 中存在该 key，且两边都是 list，递归更新
                    self._deep_update_list(target[key], source_value)
                else:
                    # 否则直接替换
                    target[key] = copy.deepcopy(source_value)
        elif isinstance(source, list) and isinstance(target, list):
            # 对于 list，如果长度相同则按索引递归处理
            if len(source) == len(target):
                for i in range(len(source)):
                    if isinstance(source[i], dict) and isinstance(target[i], dict):
                        self._deep_update(target[i], source[i])
                    elif isinstance(source[i], list) and isinstance(target[i], list):
                        self._deep_update_list(target[i], source[i])
                    else:
                        target[i] = copy.deepcopy(source[i])

    def _deep_update_list(self, target, source):
        """更新 list 类型的数据，处理嵌套结构"""
        if len(source) == len(target):
            for i in range(len(source)):
                if isinstance(source[i], dict) and isinstance(target[i], dict):
                    self._deep_update(target[i], source[i])
                elif isinstance(source[i], list) and isinstance(target[i], list):
                    self._deep_update_list(target[i], source[i])
                else:
                    target[i] = copy.deepcopy(source[i])


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
