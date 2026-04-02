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
from rest_framework import serializers

VALID_PLUGIN_TYPES = ("component", "remote_plugin", "uniform_api")


class ListPluginsSerializer(serializers.Serializer):
    keyword = serializers.CharField(required=False, allow_blank=True, help_text="模糊搜索 code 或 name")
    plugin_type = serializers.ChoiceField(
        required=False, choices=[(t, t) for t in VALID_PLUGIN_TYPES], help_text="按类型过滤"
    )
    with_detail = serializers.BooleanField(required=False, default=False, help_text="true 返回完整 schema")
    scope_type = serializers.CharField(required=False, help_text="scope 类型")
    scope_id = serializers.CharField(required=False, help_text="scope ID")
    limit = serializers.IntegerField(required=False, default=100, min_value=1, max_value=200, help_text="分页大小")
    offset = serializers.IntegerField(required=False, default=0, min_value=0, help_text="分页偏移")


class GetPluginSchemaSerializer(serializers.Serializer):
    code = serializers.CharField(required=True, help_text="插件 code")
    version = serializers.CharField(required=False, help_text="插件版本，不传取最新")
    plugin_type = serializers.ChoiceField(required=False, choices=[(t, t) for t in VALID_PLUGIN_TYPES], help_text="消歧用")
    scope_type = serializers.CharField(required=False, help_text="scope 类型")
    scope_id = serializers.CharField(required=False, help_text="scope ID")


class ValidateA2FlowSerializer(serializers.Serializer):
    a2flow = serializers.JSONField(required=True, help_text="a2flow v2 JSON 定义")
    scope_type = serializers.CharField(required=False, help_text="scope 类型")
    scope_value = serializers.CharField(required=False, help_text="scope 值")
