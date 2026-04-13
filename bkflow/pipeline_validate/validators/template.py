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
from jsonschema import Draft4Validator

from bkflow.constants import ValidateType
from bkflow.pipeline_validate.validators.base import (
    BasePipelineValidator,
    ValidatorResult,
    _get_constant_display_name,
)
from bkflow.pipeline_web.parser.format import classify_constants
from bkflow.pipeline_web.parser.schemas import KEY_PATTERN_RE, WEB_PIPELINE_SCHEMA


class SchemaValidator(BasePipelineValidator):
    name = "schema_validator"
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
    name = "constants_key_pattern_validator"
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
    name = "constants_source_info_validator"
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
    name = "outputs_key_pattern_validator"
    validate_type = ValidateType.TEMPLATE.value

    @classmethod
    def validate(cls, web_pipeline_tree: dict) -> ValidatorResult:
        key_validation_errors = []

        for output_key in web_pipeline_tree["outputs"]:
            if not KEY_PATTERN_RE.match(output_key):
                key_validation_errors.append(output_key)

        if key_validation_errors:
            return ValidatorResult(is_valid=False, error=f"输出变量 {''.join(key_validation_errors)} 的 key 格式不合法")

        return ValidatorResult(is_valid=True)


class MutualExclusionValidator(BasePipelineValidator):
    name = "mutual_exclusion_validator"
    validate_type = ValidateType.TEMPLATE.value

    @classmethod
    def validate(cls, web_pipeline_tree: dict) -> ValidatorResult:
        """校验节点配置：自动跳过、自动重试和超时控制不能同时打开两个或两个以上"""

        for act_id, act in list(web_pipeline_tree["activities"].items()):
            # 获取三个配置的状态
            timeout_enabled = act.get("timeout_config", {}).get("enable", False)
            auto_retry_enabled = act.get("auto_retry", {}).get("enable", False)
            skip_enabled = act.get("error_ignorable", False)

            # 统计同时开启的配置数量
            enabled_count = sum([timeout_enabled, auto_retry_enabled, skip_enabled])

            # 如果同时开启两个或两个以上配置，则校验失败
            error_nodes = []
            if enabled_count >= 2:
                error_nodes.append(act_id)

            if error_nodes:
                error_message = "节点 {} 配置不合法：自动跳过、自动重试和超时控制不能同时开启两个或两个以上".format(", ".join(error_nodes))
                return ValidatorResult(is_valid=False, error=error_message)

        return ValidatorResult(is_valid=True)
