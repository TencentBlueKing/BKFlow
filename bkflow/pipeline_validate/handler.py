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
from typing import Optional

from pipeline.exceptions import PipelineException

from bkflow.constants import ValidateType


class ValidatorHandler:
    """校验器处理器"""

    __hub = {}

    @classmethod
    def register(cls, validator_cls) -> None:
        """注册校验器类"""
        if validator_cls.name is None:
            raise ValueError(f"校验器 {validator_cls.__name__} 的 name 属性不能为 None")
        cls.__hub[validator_cls.name] = validator_cls

    @classmethod
    def validate(cls, web_pipeline_tree: dict, validate_type: Optional[ValidateType] = None):
        validators_to_run = []
        for validator_name, validator_cls in cls.__hub.items():
            # 获取校验器的类型
            validator_validate_type = getattr(validator_cls, "validate_type", None)

            if validate_type is None:
                # 默认行为：执行所有校验器
                validators_to_run.append((validator_name, validator_cls))
            elif validator_validate_type in [validate_type.value, ValidateType.GENERAL.value]:
                # 指定类型：执行匹配类型和通用类型的校验器
                validators_to_run.append((validator_name, validator_cls))

        for validator_name, validator_cls in validators_to_run:
            result = validator_cls.validate(web_pipeline_tree)
            if not result.is_valid:
                raise PipelineException(result.error)
