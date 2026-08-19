"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from rest_framework import serializers


class PluginDetailRequestSerializer(serializers.Serializer):
    """校验获取插件详情所需的上下文和插件定位信息。"""

    space_id = serializers.CharField()
    template_id = serializers.CharField()
    plugin_type = serializers.ChoiceField(choices=("component", "remote_plugin", "uniform_api"))
    plugin_code = serializers.CharField()
    plugin_version = serializers.CharField()
    source_key = serializers.CharField(required=False, allow_blank=True, default="")
    scope_type = serializers.CharField(required=False, allow_blank=True, default="")
    scope_value = serializers.CharField(required=False, allow_blank=True, default="")

    def to_internal_value(self, data):
        """拒绝契约外字段，避免请求参数被静默忽略。"""
        unknown_fields = set(data) - set(self.fields)
        if unknown_fields:
            raise serializers.ValidationError({field: "This field is not allowed." for field in unknown_fields})
        return super().to_internal_value(data)

    def validate(self, attrs):
        """校验来源和业务范围。"""
        if attrs["plugin_type"] == "uniform_api" and not attrs["source_key"]:
            raise serializers.ValidationError({"source_key": "uniform_api plugin requires source_key"})
        if attrs["scope_type"] in ("biz", "cmdb_biz") and attrs["scope_value"]:
            try:
                int(attrs["scope_value"])
            except (TypeError, ValueError):
                raise serializers.ValidationError({"scope_value": "must be an integer for business scope"})
        return attrs
