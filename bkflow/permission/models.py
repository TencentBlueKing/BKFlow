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
import datetime
import logging
import uuid
from enum import Enum

from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from pytimeparse import parse

from bkflow.space.configs import TokenAutoRenewalConfig, TokenExpirationConfig
from bkflow.space.models import SpaceConfig

logger = logging.getLogger("root")


class ResourceType(Enum):
    # 任务
    TASK = "TASK"
    # 流程
    TEMPLATE = "TEMPLATE"


class PermissionType(Enum):
    VIEW = "VIEW"
    EDIT = "EDIT"
    OPERATE = "OPERATE"
    MOCK = "MOCK"


TASK_PERMISSION_TYPE = [PermissionType.VIEW.value, PermissionType.OPERATE.value]
TEMPLATE_PERMISSION_TYPE = [
    PermissionType.VIEW.value,
    PermissionType.EDIT.value,
    PermissionType.MOCK.value,
]


class Token(models.Model):
    RESOURCE_TYPE = (
        (ResourceType.TASK.value, _("任务")),
        (ResourceType.TEMPLATE.value, _("流程")),
    )

    PERMISSION_TYPE = (
        (PermissionType.VIEW.value, _("查看")),
        (PermissionType.EDIT.value, _("编辑")),
        (PermissionType.OPERATE.value, _("操作")),
        (PermissionType.MOCK.value, _("调试")),
    )
    token = models.CharField(_("Token值"), max_length=32, primary_key=True)
    space_id = models.IntegerField(_("空间ID"))
    user = models.CharField(_("用户名"), max_length=32)
    resource_type = models.CharField(_("资源类型"), max_length=32)
    resource_id = models.CharField(_("资源ID"), max_length=32)
    permission_type = models.CharField(
        help_text=_("权限类型"), choices=PERMISSION_TYPE, max_length=32, default=PermissionType.VIEW.value
    )
    expired_time = models.DateTimeField(_("过期时间"), db_index=True)

    class Meta:
        verbose_name = _("token 表")
        verbose_name_plural = _("token 表")
        index_together = [
            "space_id",
            "user",
            "resource_type",
            "resource_id",
            "permission_type",
            "expired_time",
        ]

    def to_json(self):
        return {
            "space_id": int(self.space_id),
            "user": self.user,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "token": self.token,
            "expired_time": self.expired_time,
        }

    def renewal(self):
        token_auto_renewal = SpaceConfig.get_config(self.space_id, TokenAutoRenewalConfig.name)
        if token_auto_renewal == "true":
            expiration = SpaceConfig.get_config(self.space_id, TokenExpirationConfig.name)
            # 原地补全目标周期
            self.expired_time = datetime.datetime.now() + datetime.timedelta(seconds=parse(expiration))
            self.save(update_fields=["expired_time"])
            return True, ""
        else:
            return False, "续期失败，当前空间未开启token自动续期"

    def has_expired(self):
        return self.expired_time < timezone.now()

    @classmethod
    def generate_token(cls):
        return uuid.uuid3(uuid.uuid1(), uuid.uuid4().hex).hex

    @classmethod
    def verify(cls, space_id, user, resource_type, resource_id, permission_type, token) -> bool:
        """
        校验权限
        """

        query_params = {
            "user": user,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "permission_type": permission_type,
            "token": token,
        }

        if space_id:
            query_params["space_id"] = space_id

        try:
            token = cls.objects.get(**query_params)
        except cls.DoesNotExist:
            logger.info(
                "[Token->verify] the token does not exist, space_id={}, user={},resource_type={},"
                "resource_id={},permission_type={}".format(space_id, user, resource_type, resource_id, permission_type)
            )
            return False

        if token.has_expired():
            return False

        return True
