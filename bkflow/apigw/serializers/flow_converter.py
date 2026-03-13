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

from bkflow.constants import MAX_LEN_OF_TEMPLATE_NAME, USER_NAME_MAX_LENGTH


class ImportSimpleFlowSerializer(serializers.Serializer):
    name = serializers.CharField(help_text=_("模板名称"), max_length=MAX_LEN_OF_TEMPLATE_NAME, required=True)
    simple_flow = serializers.JSONField(help_text=_("简化流程 JSON 数组"))
    creator = serializers.CharField(help_text=_("创建人"), max_length=USER_NAME_MAX_LENGTH, required=False)
    scope_type = serializers.CharField(help_text=_("流程范围类型"), max_length=128, required=False)
    scope_value = serializers.CharField(help_text=_("流程范围值"), max_length=128, required=False)
    auto_release = serializers.BooleanField(help_text=_("是否自动发布"), required=False, default=False)
    desc = serializers.CharField(help_text=_("描述"), max_length=256, required=False, allow_blank=True, allow_null=True)

    def validate_simple_flow(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(_("simple_flow 必须是 JSON 数组"))
        if not value:
            raise serializers.ValidationError(_("simple_flow 不能为空"))
        return value

    def validate(self, attrs):
        scope_type = attrs.get("scope_type")
        scope_value = attrs.get("scope_value")

        if (scope_type is not None) != (scope_value is not None):
            raise serializers.ValidationError(_("作用域类型和作用域值必须同时填写，或同时不填写"))

        return attrs
