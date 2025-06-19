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

from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from bkflow.space.models import Space
from bkflow.template.models import Template, Trigger


class TriggerSerializer(serializers.ModelSerializer):
    create_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    update_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = Trigger
        fields = "__all__"


class ListTriggerSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"), required=True)
    template_id = serializers.IntegerField(help_text=_("模板ID"), required=False)


class CreateTriggerSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text="空间ID", required=True)
    template_id = serializers.IntegerField(help_text="模板ID", required=True)
    is_enabled = serializers.BooleanField(help_text="是否启用", required=False, default=True)
    name = serializers.CharField(max_length=100, help_text="名称", required=True)
    condition = serializers.CharField(help_text="条件", required=True)
    config = serializers.JSONField(help_text="配置", required=False)
    type = serializers.CharField(max_length=20, help_text="触发类型", required=True)
    token = serializers.CharField(help_text="远程密钥", required=False)

    def validate_type(self, value):
        valid_types = {choice[0] for choice in Trigger.TYPE_CHOICES}
        if value not in valid_types:
            raise serializers.ValidationError(f"Invalid type. Expected one of: {valid_types}")
        return value

    def validate(self, data):
        # remote 类型必须有 token
        type_value = data.get("type")
        token_value = data.get("token")

        space_id = data.get("space_id")
        template_id = data.get("template_id")

        if type_value == Trigger.TYPE_REMOTE and not token_value:
            raise serializers.ValidationError({"token": "Token is required when type is remote"})

        if not Space.exists(space_id) or not Template.objects.filter(id=template_id, space_id=space_id).exists():
            raise serializers.ValidationError(f"对应 空间 {space_id} 或 流程 {template_id} 不存在")
        return data


class RemoteTriggerSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text="空间ID", required=True)
    template_id = serializers.IntegerField(help_text="模板ID", required=True)
    condition = serializers.JSONField(help_text="触发条件", required=True)
    trigger_id = serializers.IntegerField(help_text="触发器ID", required=True)
    creator = serializers.CharField(help_text="执行人", required=True)

    def validate_condition(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Condition must be a JSON object.")
        return value
