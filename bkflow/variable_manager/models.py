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

from django.db import models
from django.utils.translation import ugettext_lazy as _

from bkflow.utils.models import CommonModel


class VariableManager(CommonModel):
    id = models.BigAutoField(primary_key=True)
    space_id = models.BigIntegerField(verbose_name=_("空间 ID"), blank=False)
    name = models.CharField(verbose_name=_("变量名"), max_length=255)
    type = models.CharField(verbose_name=_("变量类型"), max_length=255)
    key = models.CharField(verbose_name=_("变量唯一键"), max_length=255)
    value = models.TextField(verbose_name=_("变量值"))
    desc = models.TextField(verbose_name=_("变量描述"))

    class Meta:
        unique_together = (("space_id", "key"),)
