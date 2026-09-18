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
from django.conf import settings
from jsonschema import Draft4Validator

from bkflow.constants import ValidateType, ValidatorCode
from bkflow.pipeline_validate.validators.base import (
    BasePipelineValidator,
    ValidatorResult,
    _get_constant_display_name,
)
from bkflow.pipeline_web.parser.format import classify_constants
from bkflow.pipeline_web.parser.schemas import KEY_PATTERN_RE, WEB_PIPELINE_SCHEMA


class SchemaValidator(BasePipelineValidator):
    code = ValidatorCode.TEMPLATE_SCHEMA.value
    validate_type = ValidateType.TEMPLATE.value

    @classmethod
    def validate(cls, web_pipeline_tree: dict) -> ValidatorResult:
        valid = Draft4Validator(WEB_PIPELINE_SCHEMA)
        errors = []
        for error in sorted(valid.iter_errors(web_pipeline_tree), key=str):
            errors.append("{}: {}".format("→".join(map(str, error.absolute_path)), error.message))

        if errors:
            error_message = "流程结构校验失败，请检查流程配置是否完整: {}".format("; ".join(errors))
            return ValidatorResult(is_valid=False, error=error_message)

        return ValidatorResult(is_valid=True)


class ConstantsKeyPatternValidator(BasePipelineValidator):
    code = ValidatorCode.TEMPLATE_CONSTANTS_KEY_PATTERN.value
    validate_type = ValidateType.TEMPLATE.value

    @classmethod
    def validate(cls, web_pipeline_tree: dict) -> ValidatorResult:
        key_validation_errors = []

        for key, const in web_pipeline_tree["constants"].items():
            key_value = const.get("key")
            display_name = _get_constant_display_name(const, key)

            if key != key_value:
                key_validation_errors.append(display_name)
                continue

            if not KEY_PATTERN_RE.match(key):
                key_validation_errors.append(display_name)

        if key_validation_errors:
            err_message = "变量 {} 的 key 格式不合法或与属性 key 不匹配，请检查变量配置".format(", ".join(key_validation_errors))
            return ValidatorResult(is_valid=False, error=err_message)

        return ValidatorResult(is_valid=True)


class ConstantsSourceInfoValidator(BasePipelineValidator):
    code = ValidatorCode.TEMPLATE_CONSTANTS_SOURCE_INFO.value
    validate_type = ValidateType.TEMPLATE.value

    @classmethod
    def validate(cls, web_pipeline_tree: dict) -> ValidatorResult:
        """执行Constants Source Info校验"""
        key_validation_errors = []
        classification = classify_constants(web_pipeline_tree["constants"], is_subprocess=False)

        for key, const in web_pipeline_tree["constants"].items():
            key_value = const.get("key")
            display_name = _get_constant_display_name(const, key)

            # Skip constants that are not in data_inputs (e.g., component_outputs with empty source_info)
            if key_value not in classification["data_inputs"]:
                # If it's a component_outputs type with invalid source_info, report error
                if const.get("source_type") == "component_outputs":
                    source_info = const.get("source_info")
                    # source_info is empty dict or all values are empty lists
                    if not source_info or not any(v for v in source_info.values() if v):
                        key_validation_errors.append(display_name)

        if key_validation_errors:
            err_message = "输出变量 {} 配置无效：该变量类型为组件输出，但未选择有效的输出字段，" "请在对应节点中重新勾选输出变量或删除该变量".format(
                ", ".join(key_validation_errors)
            )
            return ValidatorResult(is_valid=False, error=err_message)

        return ValidatorResult(is_valid=True)


class OutputsKeyPatternValidator(BasePipelineValidator):
    code = ValidatorCode.TEMPLATE_OUTPUTS_KEY_PATTERN.value
    validate_type = ValidateType.TEMPLATE.value

    @classmethod
    def validate(cls, web_pipeline_tree: dict) -> ValidatorResult:
        key_validation_errors = []

        for output_key in web_pipeline_tree["outputs"]:
            if not KEY_PATTERN_RE.match(output_key):
                key_validation_errors.append(output_key)

        if key_validation_errors:
            return ValidatorResult(is_valid=False, error=f"输出变量 {'，'.join(key_validation_errors)} 的 key 格式不合法")

        return ValidatorResult(is_valid=True)


class MutualExclusionValidator(BasePipelineValidator):
    code = ValidatorCode.TEMPLATE_MUTUAL_EXCLUSION.value
    validate_type = ValidateType.TEMPLATE.value

    @classmethod
    def validate(cls, web_pipeline_tree: dict) -> ValidatorResult:
        """校验节点配置：自动跳过、自动重试和超时控制不能同时打开两个或两个以上"""

        error_nodes = []
        for act_id, act in list(web_pipeline_tree["activities"].items()):
            # 获取三个配置的状态
            timeout_enabled = act.get("timeout_config", {}).get("enable", False)
            auto_retry_enabled = act.get("auto_retry", {}).get("enable", False)
            skip_enabled = act.get("error_ignorable", False)
            # 统计同时开启的配置数量
            enabled_count = sum([timeout_enabled, auto_retry_enabled, skip_enabled])
            # 如果同时开启两个或两个以上配置，则校验失败
            if enabled_count >= 2:
                error_nodes.append(act_id)

        if error_nodes:
            error_message = "节点 {} 配置不合法：自动跳过、自动重试和超时控制不能同时开启两个或两个以上".format(", ".join(error_nodes))
            return ValidatorResult(is_valid=False, error=error_message)

        return ValidatorResult(is_valid=True)


class LoopVariableValidator(BasePipelineValidator):
    code = ValidatorCode.TEMPLATE_LOOP_VARIABLE.value
    validate_type = ValidateType.TEMPLATE.value

    @classmethod
    def validate(cls, web_pipeline_tree: dict) -> ValidatorResult:
        """校验循环变量使用情况

        - 循环次数不能超过最大值
        - 数组循环时，循环次数需与各循环变量参数数量匹配
        - 同一循环变量不能被多个节点使用
        - 循环变量不能与全局变量冲突
        """
        loop_variable_usage = {}
        global_variable_keys = set(web_pipeline_tree.get("constants", {}).keys())

        conflicting_variables = []
        conflicting_global_variables = []
        loop_variables = []
        exceeded_loop_times_nodes = []

        for node_id, activity in web_pipeline_tree["activities"].items():
            loop_config = activity.get("loop_config", {})
            if not loop_config.get("enable", False):
                continue

            loop_times = loop_config.get("loop_times")
            # 校验循环次数是否超过最大值
            if loop_times and loop_times > settings.MAX_LOOP_TIMES:
                exceeded_loop_times_nodes.append(activity["name"])

            if loop_config.get("type") != "array_loop":
                continue

            loop_params = loop_config.get("loop_params", {})

            if loop_times:
                # 统计当前节点的循环变量（各参数值按逗号分隔后的元素数量）
                valid_loop_params = [
                    len([item for item in param_value.split(",") if item.strip()])
                    for param_value in loop_params.values()
                ]
                # 验证循环次数与循环变量数量匹配（取最短值列表长度）
                if valid_loop_params and loop_times != min(valid_loop_params):
                    loop_variables.append(activity["name"])

            # 统计循环变量使用情况
            for param_key in loop_params:
                # 检查是否与全局变量冲突
                if param_key in global_variable_keys:
                    conflicting_global_variables.append(param_key)

                # 检查是否被多个节点使用
                if param_key in loop_variable_usage:
                    conflicting_variables.append(param_key)
                else:
                    loop_variable_usage[param_key] = node_id

        if exceeded_loop_times_nodes:
            return ValidatorResult(
                is_valid=False, error=f"节点 {'; '.join(exceeded_loop_times_nodes)} 的循环次数超过最大值{settings.MAX_LOOP_TIMES}"
            )

        if loop_variables:
            return ValidatorResult(is_valid=False, error=f"节点 {'; '.join(loop_variables)} 的循环次数与循环变量参数不匹配")
        if conflicting_global_variables:
            return ValidatorResult(is_valid=False, error=f"循环变量与全局变量冲突: {'; '.join(conflicting_global_variables)}")

        return ValidatorResult(is_valid=True)
