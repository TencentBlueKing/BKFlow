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

from mako.codegen import RESERVED_NAMES

from bkflow.constants import ValidateType, ValidatorCode
from bkflow.pipeline_validate.validators.base import (
    BasePipelineValidator,
    ValidatorResult,
)
from bkflow.pipeline_web.parser.schemas import KEY_PATTERN_RE


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
        - 循环变量不能与全局变量冲突
        """
        from bkflow.pipeline_web.preview_base import PipelineTemplateWebPreviewer

        result = PipelineTemplateWebPreviewer.validate_loop_variables(web_pipeline_tree)
        if not result.get("is_valid"):
            return ValidatorResult(is_valid=False, error=result.get("error_message", ""))

        return ValidatorResult(is_valid=True)


class MakoKeywordValidator(BasePipelineValidator):
    code = ValidatorCode.TEMPLATE_MAKO_KEYWORD.value
    validate_type = ValidateType.TEMPLATE.value

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
