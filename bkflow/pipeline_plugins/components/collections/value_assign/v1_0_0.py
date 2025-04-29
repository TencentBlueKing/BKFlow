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

import json
from enum import Enum

from bamboo_engine.eri import ContextValueType
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from pipeline.component_framework.component import Component
from pipeline.core.flow.io import ObjectItemSchema
from pipeline.eri.runtime import BambooDjangoRuntime

from bkflow.pipeline_plugins.components.collections.base import BKFlowBaseService

__group_name__ = _("蓝鲸服务(BK)")


class ValueConvertType(Enum):
    """

    :param Enum: [description]
    :type Enum: [type]
    """

    STRING = "String"
    INT = "Int"
    OBJECT = "Object"
    BOOL = "Bool"


class ValueAssignService(BKFlowBaseService):

    type_mapping = {
        ValueConvertType.STRING.value: str,
        ValueConvertType.INT.value: int,
        ValueConvertType.BOOL.value: bool,
        ValueConvertType.OBJECT.value: (dict, list),
    }

    def inputs_format(self):
        return [
            self.InputItem(
                name=_("赋值变量或常量与被赋值变量列表"),
                key="bk_assignment_list",
                type="object",
                schema=ObjectItemSchema(
                    description=_("赋值变量或常量与被赋值变量的映射列表"),
                ),
            )
        ]

    def outputs_format(self):
        # 插件返回内容
        return []

    def convert_variable(self, data, data_type):
        # Bool 类型需要特殊处理
        if data_type == ValueConvertType.BOOL.value:
            if not isinstance(data, str):
                raise TypeError("Bool conversion requires a string input.")
            if data.lower() in ("true", "yes", "1"):
                return True
            elif data.lower() in ("false", "no", "0"):
                return False
            raise TypeError(f"Cannot convert {data} to Bool.")

        # 获取映射中的目标类型
        target_type = self.type_mapping.get(data_type, None)

        # Object 类型 仅为 dict list 用 json 包可以直接转换
        if data_type == ValueConvertType.OBJECT.value:
            if not isinstance(data, str):
                raise TypeError("Object conversion requires a JSON string input.")
            try:
                parsed_data = json.loads(data)
                if not isinstance(parsed_data, target_type):
                    raise TypeError(f"Parsed data is not of type {data_type}.")
                return parsed_data
            except json.JSONDecodeError:
                raise TypeError(f"Cannot convert {data} to {data_type} due to JSON parsing error.")

        if target_type is None:
            raise TypeError(f"Unknown data_type {data_type} provided.")
        return target_type(data)

    def plugin_execute(self, data, parent_data):
        runtime = BambooDjangoRuntime()
        contexts = []
        pipeline_id = self.top_pipeline_id
        assign_list = data.get_one_of_inputs("bk_assignment_list")
        self.logger.info("assign_list: %s", assign_list)
        # 构建目标变量集合
        target_var_set = {"${{{}}}".format(assign["key"]) for assign in assign_list}

        try:
            # 批量查询目标变量的上下文值
            context_values = runtime.get_context_values(pipeline_id=pipeline_id, keys=target_var_set)
        except ValueError as e:
            self.logger.exception("get context values error {e}")
            data.outputs.ex_data = str(e)
            return False

        # 构建一个字典以快速访问
        context_dict = {cv.key: cv for cv in context_values}

        for assign in assign_list:
            # 循环处理表格中的内容 检查是否存在/类型问题后再统一事务批量执行
            input_val = assign["value"]
            target_var = assign["key"]
            target_var_type = assign["value_type"]
            target_var_str = "${{{}}}".format(target_var)
            context = context_dict.get(target_var_str)
            if not context:
                err_msg = "target variable {} is not exist".format(target_var)
                self.logger.exception(err_msg)
                data.outputs.ex_data = err_msg
                return False

            # 被赋值变量仅能是 PLAIN 类型
            if context.type != ContextValueType.PLAIN:
                err_msg = "splice or compute variable {} not supported".format(context)
                self.logger.exception(err_msg)
                data.outputs.ex_data = err_msg
                return False

            if target_var_type != ValueConvertType.OBJECT.value and not isinstance(
                context.value, self.type_mapping.get(target_var_type, None)
            ):
                # 由于 bool 是 int 的子类 所以会判断为相同
                err_msg = "expected type {} not match target variable type {}".format(
                    target_var_type, type(context.value)
                )
                self.logger.exception(err_msg)
                data.outputs.ex_data = err_msg
                return False

            try:
                # 尝试将输入转换为期望类型
                input_val = self.convert_variable(input_val, target_var_type)
            except (ValueError, TypeError):
                err_msg = "input variable '{}' cannot be converted to the type of expected {}".format(
                    input_val, target_var_type
                )
                self.logger.exception(err_msg)
                data.outputs.ex_data = err_msg
                return False

            # 更新上下文并放入字典 (包括形式为变量的情况 ex. ${var})
            context.value = input_val
            contexts.append(context)
        runtime.update_context_values(pipeline_id=pipeline_id, context_values=contexts)
        # 批量更新内容 事务原子操作
        return True


class ValueAssignComponent(Component):
    name = _("变量赋值")
    code = "value_assign"
    bound_service = ValueAssignService
    form = settings.STATIC_URL + "components/value_assign/v1_0_0.js"
    version = "v1.0.0"
    desc = """该插件用于对变量进行赋值操作, 并在赋值前进行基础的类型校验, object 类型仅支持键值对和列表
    bool 类型\"True\",\"true\",\"1\",被赋值为True \"False\",\"false\",\"0\",赋值为 False 且 bool 可以被 int 赋值"""
