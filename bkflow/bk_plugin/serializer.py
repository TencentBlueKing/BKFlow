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
    get_default_list_config,
    logger,
)
from bkflow.constants import ALL_SPACE, WHITE_LIST


class BKPluginSerializer(serializers.ModelSerializer):
    class Meta:
        model = BKPlugin
        fields = "__all__"


class PluginConfigSerializer(serializers.Serializer):
    white_list = serializers.ListField(required=True, child=serializers.CharField())

    def validate_white_list(self, value):
        if not value:
            logger.exception(f"{WHITE_LIST}参数校验失败，{WHITE_LIST}不能为空")
            raise serializers.ValidationError(f"{WHITE_LIST}不能为空")
        for space_id in value:
            if space_id is ALL_SPACE and len(value) > 1:
                logger.exception(f"{WHITE_LIST}参数校验失败，{ALL_SPACE}不能与其他空间ID同时存在")
                raise serializers.ValidationError(f"{ALL_SPACE}不能与其他空间ID同时存在")
        return value


class BKPluginAuthSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True, max_length=100)
    status = serializers.IntegerField(required=False)
    config = PluginConfigSerializer(required=False)
    status_updator = serializers.CharField(read_only=True, max_length=255, allow_blank=True)

    def validate_status(self, value):
        if value not in [AuthStatus.authorized, AuthStatus.unauthorized]:
            raise serializers.ValidationError(f"status must be {AuthStatus.authorized} or {AuthStatus.unauthorized}")
        return value

    def update(self, instance, validated_data):
        update_fields = []
        if "config" in validated_data:
            update_fields.append("config")
            instance.config = validated_data["config"]
        if "status" in validated_data:
            instance.status = validated_data["status"]
            instance.status_update_time = datetime.now()
            instance.status_updator = self.context.get("username", "")
            update_fields.extend(["status", "status_updator", "status_update_time"])
        instance.save(update_fields=update_fields)
        return instance

    class Meta:
        model = BKPluginAuthorization
        fields = "__all__"


class AuthConfigSerializer(serializers.Serializer):
    white_list = serializers.ListField(required=True, child=serializers.DictField())

    def validate_white_list(self, value):
        for item in value:
            if not item.get("id") or item.get("name") is None:
                raise serializers.ValidationError("white_list中的id和name不能为空")
            item["id"] = str(item["id"])
        return value


class AuthListSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=100)
    managers = serializers.ListField(child=serializers.CharField())
    status = serializers.IntegerField(required=False, default=AuthStatus.unauthorized.value)
    config = AuthConfigSerializer(required=False, default=get_default_list_config)
    status_updator = serializers.CharField(max_length=255, allow_blank=True, default="")
    status_update_time = serializers.CharField(required=False, allow_null=True)


class AuthListQuerySerializer(serializers.Serializer):
    status = serializers.IntegerField(required=False)
    status_updator = serializers.CharField(required=False, max_length=255, allow_blank=True)

    def validate_status(self, value):
        if value not in [AuthStatus.authorized.value, AuthStatus.unauthorized.value]:
            raise serializers.ValidationError(f"status必须为 {AuthStatus.authorized} or {AuthStatus.unauthorized}")
        return value
