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
        if validator_cls.code is None:
            raise ValueError(f"校验器 {validator_cls.__name__} 的 code 属性不能为 None")
        if validator_cls.code in cls.__hub:
            existing_cls = cls.__hub[validator_cls.code]
            raise ValueError(f"校验器代码 '{validator_cls.code}' 已被 {existing_cls.__name__} 注册，")
        cls.__hub[validator_cls.code] = validator_cls

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
                raise PipelineException(
                    f"流程校验未通过（校验器 {validator_cls.__name__}，code={validator_cls.code}）：{result.error}"
                )

    @classmethod
    def validate_by_codes(cls, web_pipeline_tree: dict, validator_codes: list):
        """指定校验器名称列表进行校验

        @param web_pipeline_tree: 流程树
        @param validator_codes: 需要执行的校验器代码列表（对应各校验器类的 code 属性）
        """
        if not validator_codes:
            return

        unknown_codes = [code for code in validator_codes if code not in cls.__hub]
        if unknown_codes:
            raise ValueError(f"存在未注册的校验器代码: {unknown_codes}")

        for validator_code in validator_codes:
            validator_cls = cls.__hub[validator_code]
            result = validator_cls.validate(web_pipeline_tree)
            if not result.is_valid:
                raise PipelineException(
                    f"流程校验未通过（校验器 {validator_cls.__name__}，code={validator_cls.code}）：{result.error}"
                )
