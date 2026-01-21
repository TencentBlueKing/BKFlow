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
import logging
import traceback

from bkflow.apigw.exceptions import PaginateParamsException
from bkflow.space.models import SpaceConfig

logger = logging.getLogger("root")


def get_space_config_presentation(space_id: int):
    """
    @summary: 获取space_id对应的空间相关配置信息
    @param space_id: 空间ID
    @return: 所有空间相关配置信息
    {
        "space_id": 1,
        "config": [{"key": "key1", "value": "value1"}]
    }
    """
    return {"space_id": int(space_id), "config": SpaceConfig.objects.get_space_config_info(space_id=space_id)}


def paginate_list_data(request, queryset):
    """
    @summary: 读取request中的offset和limit参数，对筛选出的queryset进行分页
    @return: 分页结果列表, 分页前数据总数
    """
    try:
        offset = int(request.GET.get("offset", 0))
        limit = int(request.GET.get("limit", 100))
        # limit 最大数量为200
        limit = 200 if limit > 200 else limit
        count = queryset.count()

        if offset < 0 or limit < 0:
            raise PaginateParamsException("offset and limit must be greater or equal to 0.")
        else:
            results = queryset[offset : offset + limit]
        return results, count
    except Exception as e:
        message = "[API] pagination error: {}".format(e)
        logger.error(message + "\n traceback: {}".format(traceback.format_exc()))
        raise Exception(message)


def _constant_to_json_schema_property(constant_info):
    """
    将 pipeline_tree 中的 constant 变量转换为 JSON Schema 的 property 格式

    @param constant_info: constant 变量信息字典
    @return: JSON Schema property 字典
    """
    # 根据 custom_type 或 source_tag 推断类型
    custom_type = constant_info.get("custom_type", "")
    value = constant_info.get("value", "")

    # 根据值类型或自定义类型推断 JSON Schema 类型
    if custom_type in ["int", "integer"]:
        schema_type = "integer"
    elif custom_type in ["float", "number"]:
        schema_type = "number"
    elif custom_type in ["bool", "boolean"]:
        schema_type = "boolean"
    elif custom_type in ["list", "array"]:
        schema_type = "array"
    elif custom_type in ["dict", "object"]:
        schema_type = "object"
    elif isinstance(value, bool):
        schema_type = "boolean"
    elif isinstance(value, int):
        schema_type = "integer"
    elif isinstance(value, float):
        schema_type = "number"
    elif isinstance(value, list):
        schema_type = "array"
    elif isinstance(value, dict):
        schema_type = "object"
    else:
        schema_type = "string"

    prop = {
        "title": constant_info.get("name", ""),
        "type": schema_type,
    }

    # 添加描述
    if constant_info.get("desc"):
        prop["description"] = constant_info.get("desc")

    # 添加默认值
    if value not in ("", None) and not (isinstance(value, str) and value.startswith("${")):
        prop["default"] = value

    return prop


def _parse_inputs_from_pipeline_tree(pipeline_tree):
    """
    从 pipeline_tree 中解析输入参数（用户需要填写的参数）

    @param pipeline_tree: 流程树
    @return: JSON Schema 格式的 inputs
    """
    constants = pipeline_tree.get("constants", {})
    properties = {}
    required = []

    for key, info in constants.items():
        # 输入参数：show_type 为 show 且不是组件输出
        if info.get("show_type") == "show" and info.get("source_type") != "component_outputs":
            # 移除 key 中的 ${} 包装
            clean_key = key.strip("${}")
            properties[clean_key] = _constant_to_json_schema_property(info)

            # 如果没有默认值，则为必填
            value = info.get("value", "")
            if value in ("", None) or (isinstance(value, str) and value.startswith("${")):
                required.append(clean_key)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "definitions": {},
    }


def _parse_outputs_from_pipeline_tree(pipeline_tree):
    """
    从 pipeline_tree 中解析输出参数

    @param pipeline_tree: 流程树
    @return: JSON Schema 格式的 outputs
    """
    constants = pipeline_tree.get("constants", {})
    output_keys = pipeline_tree.get("outputs", [])
    properties = {}
    required = []

    for key in output_keys:
        if key in constants:
            info = constants[key]
            # 移除 key 中的 ${} 包装
            clean_key = key.strip("${}")
            properties[clean_key] = _constant_to_json_schema_property(info)
            required.append(clean_key)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "definitions": {},
    }


def _get_context_inputs_schema():
    """
    获取上下文输入参数的 JSON Schema

    context_inputs 是运行时由系统注入的上下文变量
    @return: JSON Schema 格式的 context_inputs
    """
    properties = {
        "executor": {"title": "任务执行人", "type": "string"},
        "task_name": {"title": "任务名称", "type": "string"},
        "task_id": {"title": "任务ID", "type": "string"},
        "task_space_id": {"title": "任务空间ID", "type": "string"},
    }

    return {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
        "definitions": {},
    }


def parse_pipeline_tree_to_plugin_schema(pipeline_tree):
    """
    从 pipeline_tree 中解析插件格式的 inputs、outputs 和 context_inputs

    @param pipeline_tree: 流程树字典
    @return: 包含 inputs、outputs、context_inputs 的字典
    """
    pipeline_tree = pipeline_tree or {}

    # 从 pipeline_tree 中解析 inputs 和 outputs
    inputs = _parse_inputs_from_pipeline_tree(pipeline_tree)
    outputs = _parse_outputs_from_pipeline_tree(pipeline_tree)
    context_inputs = _get_context_inputs_schema()

    return {
        "inputs": inputs,
        "outputs": outputs,
        "context_inputs": context_inputs,
    }
