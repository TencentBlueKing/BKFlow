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

from django.utils.translation import gettext_lazy as _
from pipeline.conf import settings
from pipeline.core.data.var import LazyVariable

from bkflow.pipeline_plugins.variables.base import (
    FieldExplain,
    SelfExplainVariable,
    Type,
)


class BkUserSelector(LazyVariable, SelfExplainVariable):
    code = "bk_user_selector"
    name = _("人员选择器")
    type = "general"
    tag = "bk_manage_user_selector.bk_user_selector"
    form = "%svariables/bk_user_selector.js" % settings.STATIC_URL

    def get_value(self):
        return self.value

    @classmethod
    def _self_explain(cls, **kwargs) -> List[FieldExplain]:
        return [FieldExplain(key="${KEY}", type=Type.STRING, description="人员列表，以,分隔")]
