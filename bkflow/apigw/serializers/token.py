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
        if not resp["result"]:
            logger.info("[TokenResourceValidator] query task error , resp = {}".format(resp))
            return False

        logger.info("[TokenResourceValidator] query task success, resp = {}".format(resp))
        if resp.get("data", {}).get("count", []) == 1:
            return True

        return False

    def template_exists(self, template_id):
        return Template.exists(template_id)

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


class ApiGwTokenRevokeSerializer(serializers.Serializer):
    """撤销 token"""

    token = serializers.CharField(help_text=_("token"), max_length=32, required=False)
    user = serializers.CharField(help_text=_("user"), max_length=32, required=False)
    resource_type = serializers.ChoiceField(help_text=_("资源类型"), choices=Token.RESOURCE_TYPE, required=False)
    resource_id = serializers.CharField(help_text=_("资源ID"), max_length=32, required=False)
    permission_type = serializers.ChoiceField(help_text=_("权限类型"), choices=Token.PERMISSION_TYPE, required=False)
