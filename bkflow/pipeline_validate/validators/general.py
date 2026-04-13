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
from pipeline.validators import validate_pipeline_tree

from bkflow.constants import ValidateType
from bkflow.pipeline_validate.validators.base import (
    BasePipelineValidator,
    ValidatorResult,
)


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
