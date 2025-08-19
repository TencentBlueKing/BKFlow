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
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from bkflow.exceptions import ValidationError
from bkflow.space.configs import SpaceConfigHandler


class RenewSpaceConfigSerializer(serializers.Serializer):
    config = serializers.DictField(help_text=_("配置信息"), required=True)

    def validate_config(self, config):
        support_choices = list(SpaceConfigHandler.get_all_configs().keys())
        if set(config.keys()) - set(support_choices):
            raise serializers.ValidationError(_(f"配置信息中存在不支持的配置项, 支持的配置有: {support_choices}"))

        try:
            SpaceConfigHandler.validate_configs(config)
        except ValidationError as e:
            raise serializers.ValidationError(e)
        return config
