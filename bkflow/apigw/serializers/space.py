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

from bkflow.exceptions import ValidationError
from bkflow.space.configs import SpaceConfigHandler
from bkflow.space.models import Space


class CreateSpaceSerializer(serializers.Serializer):
    """
    创建空间的序列化器
    """

    name = serializers.CharField(help_text=_("空间名称"), max_length=32, required=True)
    desc = serializers.CharField(help_text=_("空间描述"), max_length=128, required=False)
    platform_url = serializers.URLField(help_text=_("平台提供服务的地址"), max_length=256, required=True)
    app_code = serializers.CharField(help_text=_("app id"), max_length=32, required=True)

    config = serializers.DictField(help_text=_("配置信息"), required=False)

    def validate_name(self, name):
        if Space.objects.filter(name=name).exists():
            raise serializers.ValidationError(f"Space with name {name} already exist")
        return name.strip()

    def validate_config(self, config):
        support_choices = list(SpaceConfigHandler.get_all_configs().keys())
        if set(config.keys()) - set(support_choices):
            raise serializers.ValidationError(_(f"配置信息中存在不支持的配置项, 支持的配置有: {support_choices}"))

        try:
            SpaceConfigHandler.validate_configs(config)
        except ValidationError as e:
            raise serializers.ValidationError(e)
        return config

    def validate_app_code(self, app_code):
        if Space.objects.is_app_code_reach_limit(app_code):
            raise serializers.ValidationError(
                f"space number of app code {app_code} exceeds limit {Space.objects.MAX_APP_CODE_LIMIT}"
            )
        return app_code
