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
from pipeline.exceptions import PipelineException
from pipeline.validators import validate_pipeline_tree

from bkflow.constants import ValidateType, ValidatorCode
from bkflow.pipeline_validate.validators.base import (
    BasePipelineValidator,
    ValidatorResult,
    _get_constant_display_name,
)
from bkflow.pipeline_web.parser.format import classify_constants
from bkflow.pipeline_web.parser.schemas import KEY_PATTERN_RE, WEB_PIPELINE_SCHEMA
from bkflow.utils.pipeline import validate_pipeline_tree_constants


class SchemaValidator(BasePipelineValidator):
    code = ValidatorCode.GENERAL_SCHEMA.value
    validate_type = ValidateType.GENERAL.value
    # 必须最先执行：保证流程树结构合法，避免后续校验器因缺字段抛 KeyError 导致 500
    order = 0

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
    code = ValidatorCode.GENERAL_CONSTANTS_KEY_PATTERN.value
    validate_type = ValidateType.GENERAL.value

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
    code = ValidatorCode.GENERAL_CONSTANTS_SOURCE_INFO.value
    validate_type = ValidateType.GENERAL.value

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
    code = ValidatorCode.GENERAL_OUTPUTS_KEY_PATTERN.value
    validate_type = ValidateType.GENERAL.value

    @classmethod
    def validate(cls, web_pipeline_tree: dict) -> ValidatorResult:
        key_validation_errors = []

        for output_key in web_pipeline_tree["outputs"]:
            if not KEY_PATTERN_RE.match(output_key):
                key_validation_errors.append(output_key)

        if key_validation_errors:
            return ValidatorResult(is_valid=False, error=f"输出变量 {'，'.join(key_validation_errors)} 的 key 格式不合法")

        return ValidatorResult(is_valid=True)


class PipelineTreeValidator(BasePipelineValidator):
    code = ValidatorCode.GENERAL_PIPELINE_TREE.value
    validate_type = ValidateType.GENERAL.value

    @classmethod
    def validate(cls, web_pipeline_tree: dict) -> ValidatorResult:
        try:
            validate_pipeline_tree(web_pipeline_tree, cycle_tolerate=True)
            return ValidatorResult(is_valid=True)
        except Exception as e:
            error_message = f"流程树校验失败: {str(e)}"
            return ValidatorResult(is_valid=False, error=error_message)


class ConstantsValidator(BasePipelineValidator):
    """变量引用校验器，校验 pipeline tree 中 constants 的引用是否合法"""

    code = ValidatorCode.GENERAL_CONSTANTS.value
    validate_type = ValidateType.GENERAL.value

    @classmethod
    def validate(cls, web_pipeline_tree: dict) -> ValidatorResult:
        try:
            validate_pipeline_tree_constants(web_pipeline_tree["constants"])
            return ValidatorResult(is_valid=True)
        except PipelineException as e:
            error_message = f"变量引用错误: {str(e)}"
            return ValidatorResult(is_valid=False, error=error_message)
