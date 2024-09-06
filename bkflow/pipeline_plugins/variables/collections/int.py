# -*- coding: utf-8 -*-
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
from typing import List

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from pipeline.core.flow.io import IntItemSchema

from bkflow.pipeline_plugins.variables.base import (
    CommonPlainVariable,
    FieldExplain,
    SelfExplainVariable,
    Type,
)


class Int(CommonPlainVariable, SelfExplainVariable):
    code = "int"
    name = _("整数")
    type = "general"
    tag = "int.int"
    form = "%svariables/%s.js" % (settings.STATIC_URL, code)
    schema = IntItemSchema(description=_("整数变量"))

    @classmethod
    def _self_explain(cls, **kwargs) -> List[FieldExplain]:
        return [FieldExplain(key="${KEY}", type=Type.INT, description="用户输入的数值")]
