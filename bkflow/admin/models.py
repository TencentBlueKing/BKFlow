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
from enum import Enum

from django.db import models
from django.utils.translation import gettext_lazy as _


class ModuleType(Enum):
    TASK = "TASK"


class IsolationLevel(Enum):
    ONLY_CALCULATION = "only_calculation"
    ALL_RESOURCE = "all_resource"


class ModuleInfo(models.Model):
    """
    主要为了存储不同模块的校验问题。
    """

    MODULE_TYPE = ((ModuleType.TASK.value, _("任务模块")),)

    ISOLATION_LEVEL = (
        (IsolationLevel.ONLY_CALCULATION.value, _("仅隔离计算")),
        (IsolationLevel.ALL_RESOURCE.value, _("全部隔离")),
    )

    space_id = models.IntegerField(_("空间ID"), unique=True)
    code = models.CharField(_("模块code"), max_length=32)
    url = models.CharField(_("模块提供的地址"), max_length=512, null=False, blank=False)
    token = models.CharField(_("模块的token"), max_length=32, null=False, blank=False)
    type = models.CharField(_("模块类型"), choices=MODULE_TYPE, max_length=32)
    isolation_level = models.CharField(_("隔离类型"), choices=ISOLATION_LEVEL, max_length=32)

    class Meta:
        verbose_name = _("模块信息表")
        verbose_name_plural = _("模块信息表")
