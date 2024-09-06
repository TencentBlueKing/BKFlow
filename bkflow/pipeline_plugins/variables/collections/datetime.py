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

from django.utils.translation import ugettext_lazy as _
from pipeline.core.flow.io import StringItemSchema

import settings
from bkflow.pipeline_plugins.variables.base import (
    CommonPlainVariable,
    FieldExplain,
    SelfExplainVariable,
    Type,
)


class Datetime(CommonPlainVariable, SelfExplainVariable):
    code = "datetime"
    name = _("日期时间")
    type = "general"
    tag = "datetime.datetime"
    form = "%svariables/%s.js" % (settings.STATIC_URL, code)
    schema = StringItemSchema(description=_("日期时间变量"))
    desc = _("输出格式: 2000-04-19 14:45:16")

    @classmethod
    def _self_explain(cls, **kwargs) -> List[FieldExplain]:
        return [
            FieldExplain(key="${KEY}", type=Type.STRING, description="用户选择的时间，输出格式: 2000-04-19 14:45:16")
        ]
