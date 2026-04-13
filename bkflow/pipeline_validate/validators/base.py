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

from bkflow.pipeline_validate.handler import ValidatorHandler


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
