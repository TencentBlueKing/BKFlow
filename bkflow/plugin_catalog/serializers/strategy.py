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


class StrategyQuerySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))


class StrategySaveSerializer(serializers.Serializer):
    """
    只强校验 space_id，策略本体（mode/visible_after_pass/conditions/fallback 等）整体透传给
    `PluginAdmissionStrategyConfig.validate()` 做结构校验，不在 serializer 层重复定义一遍字段，
    避免两处校验逻辑漂移。
    """

    space_id = serializers.IntegerField(help_text=_("空间ID"))

    def to_internal_value(self, data):
        validated = super().to_internal_value(data)
        validated["strategy"] = {key: value for key, value in data.items() if key != "space_id"}
        return validated


class SourceGroupQuerySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    exclude_directory_id = serializers.IntegerField(
        help_text=_("编辑某一级目录自身绑定时传入，排除自身已绑定的来源"), required=False, allow_null=True
    )
