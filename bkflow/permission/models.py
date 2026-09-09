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
import logging
import uuid
from enum import Enum
from typing import Tuple

from django.db import models
from django.db.models.query import QuerySet
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from bkflow.permission.grants import Grant, canonical_grants, grant_hash, grant_set_hash

logger = logging.getLogger("root")


class ResourceType(Enum):
    # 任务
    TASK = "TASK"
    # 流程
    TEMPLATE = "TEMPLATE"
    # 作用域
    SCOPE = "SCOPE"
    # 标签
    LABEL = "LABEL"


class TokenPermissionType(Enum):
    """Token 可签发、持久化和参与鉴权的操作类型。"""

    VIEW = "VIEW"
    EDIT = "EDIT"
    OPERATE = "OPERATE"
    MOCK = "MOCK"


class TaskAuthCode(Enum):
    """任务详情 auth 的展示标记，不作为 Token 签发或鉴权的参数类型。"""

    VIEW = "VIEW"
    EDIT = "EDIT"
    OPERATE = "OPERATE"
    MOCK = "MOCK"
    FLOW_VIEW = "FLOW_VIEW"
    FLOW_EDIT = "FLOW_EDIT"
    FLOW_MOCK = "FLOW_MOCK"


# 管理员的任务详情展示集合；作用域票据还可能贡献 EDIT、MOCK 标记。
TASK_AUTH_CODES = [
    TaskAuthCode.VIEW.value,
    TaskAuthCode.OPERATE.value,
    TaskAuthCode.FLOW_VIEW.value,
    TaskAuthCode.FLOW_EDIT.value,
    TaskAuthCode.FLOW_MOCK.value,
]

TEMPLATE_PERMISSION_TO_TASK_AUTH = {
    TokenPermissionType.VIEW.value: TaskAuthCode.FLOW_VIEW.value,
    TokenPermissionType.EDIT.value: TaskAuthCode.FLOW_EDIT.value,
    TokenPermissionType.MOCK.value: TaskAuthCode.FLOW_MOCK.value,
}

TEMPLATE_PERMISSION_TYPE = [
    TokenPermissionType.VIEW.value,
    TokenPermissionType.EDIT.value,
    TokenPermissionType.MOCK.value,
]


class TokenManager(models.Manager):
    def get_resource_tokens(self, token_id: str, resource_params: dict, user=None, space_id=None) -> QuerySet:
        """校验整张票据后按旧资源筛选规则返回不重复的 QuerySet。"""
        from bkflow.permission.services import get_valid_token

        # 旧内部调用可省略身份，HTTP 消费者必须提供认证用户与可信空间。
        if user is None:
            user = self.filter(pk=token_id).values_list("user", flat=True).first()
        token = get_valid_token(token_id, user, space_id)
        if token is None:
            return self.none()
        selectors = set()
        if resource_params.get("scope_type") and resource_params.get("scope_value"):
            selectors.add(("SCOPE", f"{resource_params['scope_type']}_{resource_params['scope_value']}"))
        if "template_id" in resource_params:
            selectors.add(("TEMPLATE", str(resource_params["template_id"])))
        elif "task_id" in resource_params:
            selectors.add(("TASK", str(resource_params["task_id"])))
        if selectors and not any((grant.resource_type, grant.resource_id) in selectors for grant in token.get_grants()):
            return self.none()
        return self.filter(pk=token.pk).distinct()


class Token(models.Model):
    RESOURCE_TYPE = (
        (ResourceType.TASK.value, _("任务")),
        (ResourceType.TEMPLATE.value, _("流程")),
        (ResourceType.SCOPE.value, _("作用域")),
        (ResourceType.LABEL.value, _("标签")),
    )

    PERMISSION_TYPE = (
        (TokenPermissionType.VIEW.value, _("查看")),
        (TokenPermissionType.EDIT.value, _("编辑")),
        (TokenPermissionType.OPERATE.value, _("操作")),
        (TokenPermissionType.MOCK.value, _("调试")),
    )
    token = models.CharField(_("Token值"), max_length=32, primary_key=True)
    space_id = models.IntegerField(_("空间ID"))
    user = models.CharField(_("用户名"), max_length=32)
    resource_type = models.CharField(_("资源类型"), max_length=32)
    resource_id = models.CharField(_("资源ID"), max_length=32)
    permission_type = models.CharField(
        help_text=_("权限类型"), choices=PERMISSION_TYPE, max_length=32, default=TokenPermissionType.VIEW.value
    )
    expired_time = models.DateTimeField(_("过期时间"), db_index=True)
    grant_set_hash = models.CharField(_("授权集合摘要"), max_length=64, null=True)

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
        indexes = [
            models.Index(fields=["space_id", "user", "grant_set_hash", "expired_time"], name="perm_tok_s_u_g_exp_idx")
        ]

    @property
    def is_composite(self) -> bool:
        """判断票据是否使用组合授权明细。"""
        return self.grant_set_hash is not None

    def get_grants(self) -> Tuple[Grant, ...]:
        """读取票据唯一权威的授权集合，完整性异常时拒绝全部授权。"""
        if not self.is_composite:
            return (Grant(self.resource_type, self.resource_id, self.permission_type),)

        details = tuple(self.grants.all())
        if len(details) < 2:
            return ()

        resource_types = {resource_type.value for resource_type in ResourceType}
        permission_types = {permission_type.value for permission_type in TokenPermissionType}
        grants = []
        for detail in details:
            fields = (detail.resource_type, detail.resource_id, detail.permission_type)
            if any(not isinstance(field, str) or not field or len(field) > 32 for field in fields):
                return ()
            if detail.resource_type not in resource_types or detail.permission_type not in permission_types:
                return ()

            grant = Grant(*fields)
            if detail.grant_hash != grant_hash(grant):
                return ()
            grants.append(grant)

        canonical = canonical_grants(grants)
        if len(canonical) != len(grants) or grant_set_hash(canonical) != self.grant_set_hash:
            return ()
        return canonical

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
        """通过持锁服务续期，保留旧二元组接口并同步实例到期时间。"""
        from bkflow.permission.services import renew_token

        result, message, token = renew_token(self.pk, user=self.user)
        if token is not None:
            self.expired_time = token.expired_time
        return result, message

    def has_expired(self):
        """票据到期时间必须严格晚于当前时刻。"""
        return self.expired_time <= timezone.now()

    @classmethod
    def generate_token(cls):
        return uuid.uuid3(uuid.uuid1(), uuid.uuid4().hex).hex

    @classmethod
    def verify(
        cls,
        space_id,
        user,
        resource_type,
        resource_id,
        permission_type,
        token,
        target_resource_type=None,
        request=None,
    ) -> bool:
        """校验主票据后，由一条完整授权独立满足资源类型、范围与操作。"""
        from bkflow.permission.resource_matching import matches_resource
        from bkflow.permission.services import get_valid_token

        db_token = get_valid_token(token, user, space_id, request)
        if db_token is None:
            return False
        return any(
            grant.resource_type == resource_type
            and grant.permission_type == permission_type
            and matches_resource(grant, db_token.space_id, resource_id, target_resource_type, db_token.is_composite)
            for grant in db_token.get_grants()
        )


class TokenGrant(models.Model):
    """组合票据的一项授权明细。"""

    token = models.ForeignKey(Token, related_name="grants", on_delete=models.CASCADE, verbose_name=_("Token"))
    resource_type = models.CharField(_("资源类型"), max_length=32)
    resource_id = models.CharField(_("资源ID"), max_length=32)
    permission_type = models.CharField(_("权限类型"), choices=Token.PERMISSION_TYPE, max_length=32)
    grant_hash = models.CharField(_("授权摘要"), max_length=64)

    class Meta:
        verbose_name = _("token 授权明细")
        verbose_name_plural = _("token 授权明细")
        constraints = [models.UniqueConstraint(fields=["token", "grant_hash"], name="perm_grant_tok_hash_uniq")]
        indexes = [
            models.Index(
                fields=["resource_type", "resource_id", "permission_type", "token"],
                name="perm_grant_res_perm_tok_idx",
            )
        ]
