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
from django.db.models.query import QuerySet
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from pytimeparse import parse

from bkflow.contrib.api.collections.task import TaskComponentClient
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


class TokenManager(models.Manager):
    def get_resource_tokens(self, token_id: str, resource_kwargs: dict) -> QuerySet:
        """获取资源的token列表

        :param resource_kwargs: 资源配置
        :return: token queryset
        """
        if "template_id" in resource_kwargs:
            return self.objects.filter(resource_type=ResourceType.TEMPLATE.value, token=token_id)
        elif "task_id" in resource_kwargs:
            return self.objects.filter(resource_type=ResourceType.TASK.value, **resource_kwargs)
        else:
            raise ValueError("参数中必须包含template_id或task_id")


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

    objects = TokenManager()

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
            "permission_type": permission_type,
            "token": token,
        }

        if space_id:
            query_params["space_id"] = space_id

        try:
            db_token = cls.objects.get(**query_params)
        except cls.DoesNotExist:
            logger.info(
                "[Token->verify] the token does not exist, space_id={}, user={},resource_type={},"
                "resource_id={},permission_type={}".format(space_id, user, resource_type, resource_id, permission_type)
            )
            return False

        if db_token.has_expired():
            return False

        # todo: 此处在递归中查询接口，如果出现子流程嵌套多层导致性能问题，需要优化
        def check_parent_task_id(db_token, current_task_id):
            client = TaskComponentClient(space_id=db_token.space_id)
            result = client.get_task_detail(current_task_id)

            if not result.get("result"):
                logger.warning(
                    f"[Token->verify] Failed to get task detail, task_id={current_task_id}, "
                    f"space_id={db_token.space_id}"
                )
                return False

            parent_task_info = result["data"].get("parent_task_info")
            if not parent_task_info:
                return False

            parent_task_id = parent_task_info["task_id"]
            if db_token.resource_id == str(parent_task_id):
                return True

            return check_parent_task_id(db_token, parent_task_id)

        if db_token.resource_id != resource_id:
            if not check_parent_task_id(db_token, resource_id):
                return False
        return True
