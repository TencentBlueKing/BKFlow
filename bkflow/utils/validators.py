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
from typing import Dict

from bamboo_engine.context import Context
from bamboo_engine.eri import ContextValue, ContextValueType
from jsonschema import Draft4Validator
from mako.codegen import RESERVED_NAMES
from pipeline.eri.runtime import BambooDjangoRuntime
from pipeline.eri.utils import CONTEXT_VALUE_TYPE_MAP
from pipeline.exceptions import PipelineException
from pipeline.validators import validate_pipeline_tree

from bkflow.constants import ValidateType
from bkflow.pipeline_web.parser.format import classify_constants
from bkflow.pipeline_web.parser.schemas import KEY_PATTERN_RE, WEB_PIPELINE_SCHEMA
from bkflow.pipeline_web.parser.validator import ValidatorHandler
from bkflow.utils.pipeline import validate_pipeline_tree_constants


class ValidatorResult:
    def __init__(self, is_valid: bool, error: str = None):
        self.is_valid = is_valid
        self.error = error


class BasePipelineValidator:
    name = None
    validate_type = None

    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)

        # 检查继承的类中是否有 validate 方法
        if not hasattr(cls, "validate"):
            raise ValueError(f"[{cls.__name__}] Missing required method: validate")

        necessary_attrs = ["name", "validate_type"]
        for attr in necessary_attrs:
            if not hasattr(cls, attr) or getattr(cls, attr) is None:
                raise ValueError(f"[{cls.__name__}] Missing required attribute: {attr}")

        ValidatorHandler.register(cls)

    @classmethod
    def validate(cls, web_pipeline_tree: Dict) -> ValidatorResult:
        raise NotImplementedError("子类必须实现 validate 方法")


def _get_constant_display_name(const: dict, key: str) -> str:
    """获取变量的显示名称，优先使用 name 字段"""
    name = const.get("name", "")
    if name:
        return f"「{name}」({key})"
    return f"「{key}」"


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


class ContextHydrateValidator(BasePipelineValidator):
    name = "context_hydrate_validator"
    validate_type = ValidateType.TASK.value

    @classmethod
    def validate(cls, web_pipeline_tree: dict) -> ValidatorResult:
        context_values = []
        classification = classify_constants(web_pipeline_tree["constants"], is_subprocess=False)

        try:
            validate_pipeline_tree_constants(web_pipeline_tree["constants"])
        except PipelineException as e:
            error_message = f"变量预渲染失败: {str(e)}"
            return ValidatorResult(is_valid=False, error=error_message)

        for key, const in web_pipeline_tree["constants"].items():
            key_value = const.get("key")

            # Skip constants that are not in data_inputs (e.g., component_outputs with empty source_info)
            if key_value not in classification["data_inputs"]:
                continue

            data_type = classification["data_inputs"][key_value]["type"]
            context_type = ContextValueType(CONTEXT_VALUE_TYPE_MAP[data_type])
            context_values.append(
                ContextValue(key=key_value, type=context_type, value=const["value"], code=const.get("custom_type", ""))
            )

        runtime = BambooDjangoRuntime()
        try:
            Context(runtime, context_values, {}).hydrate()
            return ValidatorResult(is_valid=True)
        except Exception as e:
            error_message = f"变量预渲染失败: {str(e)}"
            return ValidatorResult(is_valid=False, error=error_message)


class PipelineTreeValidator(BasePipelineValidator):
    name = "pipeline_tree_validator"
    validate_type = ValidateType.GENERAL.value

    @classmethod
    def validate(cls, web_pipeline_tree: dict) -> ValidatorResult:
        try:
            validate_pipeline_tree(web_pipeline_tree, cycle_tolerate=True)
            return ValidatorResult(is_valid=True)
        except Exception as e:
            error_message = f"流程树校验失败: {str(e)}"
            return ValidatorResult(is_valid=False, error=error_message)


class MakoKeywordValidator(BasePipelineValidator):
    name = "mako_keyword_validator"
    validate_type = ValidateType.TASK.value

    @classmethod
    def validate(cls, web_pipeline_tree: dict) -> ValidatorResult:
        validation_errors = []

        # 遍历所有常量变量
        for key, const in web_pipeline_tree["constants"].items():
            # key 格式为 ${variable_name}，需提取内部变量名再与 Mako 保留关键字比对
            match = KEY_PATTERN_RE.match(key)
            if not match:
                continue
            # 提取 ${ 和 } 之间的变量名
            var_name = key[2:-1]
            if var_name in RESERVED_NAMES:
                validation_errors.append(key)

        if validation_errors:
            error_message = "变量命名校验失败: 变量 {} 使用了Mako模板引擎的保留关键字".format("; ".join(validation_errors))
            return ValidatorResult(is_valid=False, error=error_message)

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
            if enabled_count >= 2:
                enabled_configs = []
                if timeout_enabled:
                    enabled_configs.append("超时控制")
                if auto_retry_enabled:
                    enabled_configs.append("自动重试")
                if skip_enabled:
                    enabled_configs.append("自动跳过")

                error_message = "节点 {} 同时开启了 {} 配置，自动跳过、自动重试和超时控制不能同时开启两个或两个以上".format(
                    act_id, "、".join(enabled_configs)
                )
                return ValidatorResult(is_valid=False, error=error_message)

        return ValidatorResult(is_valid=True)
