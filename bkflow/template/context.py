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

from bamboo_engine.context import Context
from bamboo_engine.eri import ContextValue
from bamboo_engine.template import Template
from bamboo_engine.utils.constants import VAR_CONTEXT_MAPPING
from pipeline import exceptions
from pipeline.core.data import var
from pipeline.core.data.library import VariableLibrary
from pipeline.eri.runtime import BambooDjangoRuntime


def get_template_context():
    return {}


def format_data_to_pipeline_inputs(data: dict, pipeline_inputs: dict, change_pipeline_inputs: bool = False):
    """
    将 data 中的数据转换成 pipeline inputs 并添加到 pipeline_inputs 中

    :param data: 待计算的变量
    :param pipeline_inputs: 变量类型确定的，直接放入结果
    :param change_pipeline_inputs: 是否直接修改pipeline_inputs并作为结果返回
    :return:
    """
    ret = copy.deepcopy(pipeline_inputs) if not change_pipeline_inputs else pipeline_inputs
    for key, info in list(data.items()):
        ref = Template(info["value"]).get_reference()
        constant_type = "splice" if ref else "plain"
        # is_param和need_render禁止同时为True
        if info.get("is_param") and info.get("need_render"):
            raise exceptions.DataException("is_param and need_render cannot be selected at the same time")
        ret.setdefault(
            key,
            {
                "type": constant_type,
                "value": info["value"],
                "is_param": info.get("is_param", False),
                "need_render": info.get("need_render", True),
            },
        )

    return ret


def get_constant_values(constants, extra_data):
    constant_values = {}
    custom_constants = {}
    # 获取用户自定义变量
    for key, info in list(constants.items()):
        if info["source_type"] == "component_inputs":
            constant_values[key] = info["value"]
        elif info["source_type"] == "component_outputs":
            constant_values[key] = key
        elif info["custom_type"] and info.get("is_meta") is True:
            constant_values[key] = str(info["value"])
        else:
            custom_constants[key] = info
    # 获取变量类型
    classified_constants = {}
    to_calculate_constants = {}
    # 先计算lazy的情况
    for key, info in custom_constants.items():
        var_cls = VariableLibrary.get_var_class(info["custom_type"])
        if var_cls and issubclass(var_cls, var.LazyVariable):
            classified_constants[key] = {
                "type": "lazy",
                "source_tag": info["source_tag"],
                "custom_type": info["custom_type"],
                "value": info["value"],
            }
        else:
            to_calculate_constants[key] = info
    classified_constants = format_data_to_pipeline_inputs(
        to_calculate_constants, classified_constants, change_pipeline_inputs=True
    )

    # 沿用V2引擎的变量渲染逻辑
    runtime = BambooDjangoRuntime()
    context_values = [
        ContextValue(key=key, type=VAR_CONTEXT_MAPPING[info["type"]], value=info["value"], code=info.get("custom_type"))
        for key, info in classified_constants.items()
    ]
    context = Context(runtime, context_values, extra_data)
    hydrated_context = context.hydrate(mute_error=True)
    return {**constant_values, **hydrated_context}
