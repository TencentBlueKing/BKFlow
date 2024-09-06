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
import logging

from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from bkflow.exceptions import ValidationError
from bkflow.space.configs import SpaceConfigHandler, SpaceConfigValueType
from bkflow.space.credential import CredentialDispatcher
from bkflow.space.models import Credential, Space, SpaceConfig

logger = logging.getLogger(__name__)


class SpaceSerializer(serializers.ModelSerializer):
    create_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S%z", read_only=True)
    update_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S%z", read_only=True)
    platform_url = serializers.URLField(help_text=_("平台地址"), required=True, max_length=128)

    class Meta:
        model = Space
        fields = "__all__"


class SpaceConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpaceConfig
        fields = "__all__"

    def validate(self, attrs):
        try:
            SpaceConfigHandler.validate(
                attrs["name"],
                attrs["text_value"] if attrs["value_type"] == SpaceConfigValueType.TEXT.value else attrs["json_value"],
            )
        except ValidationError as e:
            raise serializers.ValidationError(e)
        return attrs


class SpaceConfigBaseQuerySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))


class SpaceConfigBatchApplySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    configs = serializers.DictField(help_text=_("空间配置"))

    def validate_configs(self, configs):
        try:
            SpaceConfigHandler.validate_configs(configs)
        except ValidationError as e:
            logger.exception(f"[validate_configs] error: {e}")
            raise serializers.ValidationError(e.message)


class CredentialSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super(CredentialSerializer, self).to_representation(instance)
        credential = CredentialDispatcher(credential_type=instance.type, data=instance.content)
        if credential:
            data["data"] = credential.display_value()
        else:
            data["data"] = {}

        return data

    class Meta:
        model = Credential
        fields = "__all__"
