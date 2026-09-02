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
import re

from bkflow.pipeline_converter.converters.a2flow_v2.data_models import A2FlowVariable


def build_constant(var: A2FlowVariable, index: int) -> dict:
    if var.validation and var.value:
        try:
            matched = bool(re.match(var.validation, var.value))
        except re.error as e:
            raise ValueError(f"变量 '{var.key}' 的 validation 不是合法的正则表达式: '{var.validation}'，错误: {e}")
        if not matched:
            raise ValueError(f"变量 '{var.key}' 的值 '{var.value}' 不满足校验规则 '{var.validation}'")

    return {
        "key": var.key,
        "name": var.name,
        "value": var.value,
        "desc": var.description,
        "custom_type": var.custom_type,
        "source_type": var.source_type,
        "source_tag": "",
        "source_info": var.source_info,
        "show_type": var.show_type,
        "validation": var.validation,
        "index": index,
        "version": "legacy",
        "form_schema": {},
        "hook": False,
        "need_render": True,
    }
