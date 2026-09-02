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
from bamboo_engine.context import Context
from bamboo_engine.eri import ContextValue, ContextValueType
from pipeline.eri.runtime import BambooDjangoRuntime
from pipeline.eri.utils import CONTEXT_VALUE_TYPE_MAP

from bkflow.constants import ValidateType
from bkflow.pipeline_validate.validators.base import (
    BasePipelineValidator,
    ValidatorResult,
)
from bkflow.pipeline_web.parser.format import classify_constants


class ContextHydrateValidator(BasePipelineValidator):
    name = "context_hydrate_validator"
    validate_type = ValidateType.TASK.value

    @classmethod
    def validate(cls, web_pipeline_tree: dict) -> ValidatorResult:
        context_values = []
        classification = classify_constants(web_pipeline_tree["constants"], is_subprocess=False)

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
