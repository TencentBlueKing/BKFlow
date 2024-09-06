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
from pipeline.core.data.var import LazyVariable
from pipeline.core.flow.io import StringItemSchema

from bkflow.pipeline_plugins.variables.base import (
    FieldExplain,
    SelfExplainVariable,
    Type,
)


class Select(LazyVariable, SelfExplainVariable):
    code = "select"
    name = _("下拉框")
    type = "meta"
    tag = "select.select"
    meta_tag = "select.select_meta"
    form = "%svariables/%s.js" % (settings.STATIC_URL, code)
    schema = StringItemSchema(description=_("下拉框变量"))
    desc = _(
        "单选模式下输出选中的 value，多选模式下输出选中 value 以 ',' 拼接的字符串\n该变量默认不支持输入任意值，仅在子流程节点配置填参时支持输入任意值"
    )

    @classmethod
    def _self_explain(cls, **kwargs) -> List[FieldExplain]:
        return [
            FieldExplain(
                key="${KEY}", type=Type.STRING, description="选中的 value，多选模式下输出选中 value 以 ',' 拼接的字符串"
            )
        ]

    def get_value(self):
        # multiple select
        if isinstance(self.value, list):
            return ",".join([str(v) for v in self.value])
        # single select
        else:
            return self.value
