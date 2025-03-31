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
from datetime import datetime

from rest_framework import serializers

from bkflow.bk_plugin.models import (
    AuthStatus,
    BKPlugin,
    BKPluginAuthorization,
    get_default_config,
)
from bkflow.constants import ALL_SPACE, WHITE_LIST


class BKPluginSerializer(serializers.ModelSerializer):
    class Meta:
        model = BKPlugin
        fields = "__all__"


class BKPluginAuthSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True, max_length=100)
    status = serializers.IntegerField()
    config = serializers.JSONField(default=get_default_config())
    operator = serializers.CharField(read_only=True, max_length=255, allow_blank=True)

    class PluginConfigSerializer(serializers.Serializer):
        white_list = serializers.ListField(required=True, allow_null=False)

        def validate_white_list(self, value):
            if not value:
                raise serializers.ValidationError(f"{WHITE_LIST}不能为空")
            for space_id in value:
                if space_id == ALL_SPACE:
                    # 如果存在 *，直接覆盖
                    return [ALL_SPACE]
            return value

    def validate_config(self, value):
        ser = self.PluginConfigSerializer(data=value)
        ser.is_valid(raise_exception=True)
        return ser.validated_data

    def validate_status(self, value):
        if value not in [AuthStatus.authorized, AuthStatus.unauthorized]:
            raise serializers.ValidationError(f"status must be {AuthStatus.authorized} or {AuthStatus.unauthorized}")
        return value

    def update(self, instance, validated_data):
        update_fields = ["config"]
        instance.config = validated_data["config"]
        if "status" in validated_data:
            instance.status = validated_data["status"]
            if instance.status == AuthStatus.authorized:
                instance.authorized_time = datetime.now()
                instance.operator = self.context.get("username", "")
            update_fields.extend(["status", "operator", "authorized_time"])
        instance.save(update_fields=update_fields)
        return instance

    class Meta:
        model = BKPluginAuthorization
        fields = "__all__"


class AuthQuerySerializer(serializers.Serializer):
    tag = serializers.IntegerField(required=True)
    space_id = serializers.IntegerField(required=True)


class AuthListSerializer(serializers.Serializer):
    code = serializers.CharField(read_only=True, max_length=100)
    name = serializers.CharField(max_length=100)
    manager = serializers.CharField(max_length=255)
    authorization = serializers.SerializerMethodField()

    class Meta:
        model = BKPlugin
        fields = "code,name,manager"

    def get_authorization(self, obj):
        authorization = BKPluginAuthorization.objects.filter(code=obj.code).first()
        if not authorization:
            return BKPluginAuthorization(code=obj.code).to_json()
        return authorization.to_json()
