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

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from pipeline.core.data.var import LazyVariable
from pipeline.core.flow.io import StringItemSchema

from bkflow.pipeline_plugins.variables.base import SelfExplainVariable


class Loop(LazyVariable, SelfExplainVariable):
    code = "loop"
    name = _("循环变量")
    type = "general"
    tag = "loop.loop"
    form = "{}variables/{}.js".format(settings.STATIC_URL, code)
    schema = StringItemSchema(description=_("循环变量"))

    def get_value(self):
        # 循环节点因引用
        if hasattr(self, "inner_loop") and self.inner_loop != -1:
            return self.value.split(",")[self.inner_loop - 1]
        # 普通节点引用
        return self.value
