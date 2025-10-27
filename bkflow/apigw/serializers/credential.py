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
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from bkflow.space.credential import CredentialDispatcher
from bkflow.space.models import Credential, CredentialScopeLevel
from bkflow.space.serializers import CredentialScopeSerializer


class CredentialSerializer(serializers.ModelSerializer):
    create_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    update_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        credential = CredentialDispatcher(credential_type=instance.type, data=instance.content)
        if credential:
            data["content"] = credential.display_value()
        else:
            data["content"] = {}

        return data

    class Meta:
        model = Credential
        fields = "__all__"


class CreateCredentialSerializer(serializers.Serializer):
    name = serializers.CharField(help_text=_("凭证名称"), max_length=32, required=True)
    desc = serializers.CharField(help_text=_("凭证描述"), max_length=128, required=False, allow_blank=True, allow_null=True)
    type = serializers.CharField(help_text=_("凭证类型"), max_length=32, required=True)
    content = serializers.JSONField(help_text=_("凭证内容"), required=True)
    scope_level = serializers.ChoiceField(
        help_text=_("作用域级别"),
        required=False,
        default=CredentialScopeLevel.NONE.value,
        choices=Credential.CREDENTIAL_SCOPE_LEVEL_CHOICES,
    )
    scopes = serializers.ListField(
        child=CredentialScopeSerializer(), help_text=_("凭证作用域列表"), required=False, default=list
    )

    def validate(self, attrs):
        # 动态验证content根据type
        credential_type = attrs.get("type")
        content = attrs.get("content")

        if attrs.get("scope_level") == CredentialScopeLevel.PART.value and not attrs.get("scopes"):
            raise serializers.ValidationError(_("作用域不能为空"))

        try:
            credential = CredentialDispatcher(credential_type, data=content)
            credential.validate_data()
        except Exception as e:
            raise serializers.ValidationError({"content": str(e)})

        return attrs


class UpdateCredentialSerializer(serializers.Serializer):
    name = serializers.CharField(help_text=_("凭证名称"), max_length=32, required=False)
    desc = serializers.CharField(help_text=_("凭证描述"), max_length=128, required=False, allow_blank=True, allow_null=True)
    type = serializers.CharField(help_text=_("凭证类型"), max_length=32, required=False)
    content = serializers.JSONField(help_text=_("凭证内容"), required=False)
    scope_level = serializers.ChoiceField(
        help_text=_("作用域级别"),
        required=False,
        default=CredentialScopeLevel.NONE.value,
        choices=Credential.CREDENTIAL_SCOPE_LEVEL_CHOICES,
    )
    scopes = serializers.ListField(child=CredentialScopeSerializer(), help_text=_("凭证作用域列表"), required=False)

    def validate(self, attrs):
        if attrs.get("scope_level") == CredentialScopeLevel.PART.value and not attrs.get("scopes"):
            raise serializers.ValidationError(_("作用域不能为空"))

        # 如果提供了type和content，需要验证content
        if "content" in attrs:
            # 如果有type字段使用type，否则需要从实例获取
            credential_type = attrs.get("type")
            if not credential_type and hasattr(self, "instance"):
                credential_type = self.instance.type

            if credential_type:
                content = attrs.get("content")
                try:
                    credential = CredentialDispatcher(credential_type, data=content)
                    credential.validate_data()
                except Exception as e:
                    raise serializers.ValidationError({"content": str(e)})

        return attrs
