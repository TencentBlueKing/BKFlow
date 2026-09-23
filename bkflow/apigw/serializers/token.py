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

from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from bkflow.apigw.exceptions import CreateTokenException
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.permission.grants import Grant, canonical_grants
from bkflow.permission.models import Token
from bkflow.template.models import Template

logger = logging.getLogger("root")


class TokenResourceValidator:
    def __init__(self, space_id, resource_type, resource_id):
        self.space_id = space_id
        self.resource_type = resource_type
        self.resource_id = resource_id

    def task_exists(self, task_id):
        client = TaskComponentClient(space_id=self.space_id)
        query_data = {"id": task_id, "space_id": self.space_id, "limit": 1, "offset": 0}
        resp = client.task_list(data=query_data)
        if not resp.get("result"):
            logger.info(
                "[TokenResourceValidator] query task list error, code=%s, message=%s",
                resp.get("code"),
                resp.get("message"),
            )
            return False

        count = (resp.get("data") or {}).get("count", 0)
        logger.info(
            "[TokenResourceValidator] query task list success, task_id=%s, space_id=%s, count=%s",
            task_id,
            self.space_id,
            count,
        )
        return count == 1

    def template_exists(self, template_id):
        return Template.exists(template_id, self.space_id)

    def scope_exists(self, scope_data):
        try:
            if "_" not in scope_data or scope_data.count("_") > 1:
                return False

            scope_parts = scope_data.split("_")
            if len(scope_parts) < 2:
                return False

            scope_type, scope_value = scope_parts[0], scope_parts[1]
            return Template.objects.filter(
                space_id=self.space_id, scope_type=scope_type, scope_value=scope_value
            ).exists()
        except (ValueError, IndexError):
            return False

    def validate(self):
        resource_map = {"TEMPLATE": self.template_exists, "TASK": self.task_exists, "SCOPE": self.scope_exists}

        is_exists_func = resource_map.get(self.resource_type, None)
        if is_exists_func is None:
            raise CreateTokenException(_("token申请失败，不支持的资源类型"))

        if not is_exists_func(self.resource_id):
            raise CreateTokenException(_("token申请失败，对应的资源不存在"))


class ApiGwTokenSerializer(serializers.Serializer):
    """
    创建token
    """

    resource_type = serializers.ChoiceField(help_text=_("资源类型"), choices=Token.RESOURCE_TYPE, required=True)
    resource_id = serializers.CharField(help_text=_("资源ID"), max_length=32, required=True)
    permission_type = serializers.ChoiceField(help_text=_("权限类型"), choices=Token.PERMISSION_TYPE, required=True)


class CompositeTokenSerializer(serializers.Serializer):
    """校验组合申请；所有资源检查完成后才允许签发或续期。"""

    MAX_GRANTS = 32
    grants = serializers.JSONField(help_text=_("授权列表"))

    def validate_grants(self, value):
        """先检查原始长度，再逐项校验并按资源缓存存在性检查。"""
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError(_("grants 必须是非空列表"))
        if len(value) > self.MAX_GRANTS:
            raise serializers.ValidationError(_("grants 原始条目数不能超过 %(limit)s") % {"limit": self.MAX_GRANTS})

        grants = []
        for index, item in enumerate(value):
            serializer = ApiGwTokenSerializer(data=item)
            try:
                serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as exc:
                raise serializers.ValidationError(f"grants[{index}]: {exc.detail}") from exc
            grants.append(Grant(**serializer.validated_data))

        validated_resources = set()
        for index, grant in enumerate(grants):
            resource = (grant.resource_type, grant.resource_id)
            if resource in validated_resources:
                continue
            try:
                TokenResourceValidator(self.context["space_id"], *resource).validate()
            except Exception as exc:
                raise CreateTokenException(f"grants[{index}]: {exc}") from exc
            validated_resources.add(resource)
        return canonical_grants(grants)


class ApiGwTokenRevokeSerializer(serializers.Serializer):
    """撤销 token"""

    token = serializers.CharField(help_text=_("token"), max_length=32, required=False)
    user = serializers.CharField(help_text=_("user"), max_length=32, required=False)
    resource_type = serializers.ChoiceField(help_text=_("资源类型"), choices=Token.RESOURCE_TYPE, required=False)
    resource_id = serializers.CharField(help_text=_("资源ID"), max_length=32, required=False)
    permission_type = serializers.ChoiceField(help_text=_("权限类型"), choices=Token.PERMISSION_TYPE, required=False)
