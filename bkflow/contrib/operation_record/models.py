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
from django.utils.translation import gettext_lazy as _


class BaseOperateRecord(models.Model):
    id = models.BigAutoField(_("ID"), primary_key=True)
    operator = models.CharField(_("操作人"), max_length=128)
    operate_type = models.CharField(_("操作类型"), max_length=64)
    operate_source = models.CharField(_("操作来源"), max_length=64)
    instance_id = models.BigIntegerField(_("记录对象实例ID"))
    operate_date = models.DateTimeField(_("操作时间"), auto_now_add=True)
    extra_info = models.JSONField(_("额外信息"), default=dict, blank=True, null=True)

    class Meta:
        abstract = True

    def __str__(self):
        return "{}_{}_{}_{}".format(
            self.operator,
            self.operate_type,
            self.instance_id,
            self.operate_date,
        )
