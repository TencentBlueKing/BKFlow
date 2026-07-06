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


class TemplateIdQuerySerializer(serializers.Serializer):
    space_id = serializers.IntegerField()
    template_id = serializers.IntegerField()


class GlobalRunSerializer(serializers.Serializer):
    space_id = serializers.IntegerField()
    template_id = serializers.IntegerField()
    inputs = serializers.JSONField(default=dict)


class StepRunSerializer(serializers.Serializer):
    space_id = serializers.IntegerField()
    template_id = serializers.IntegerField()
    node_id = serializers.CharField()
    mode = serializers.ChoiceField(choices=["real", "mock"], required=False)
    input_overrides = serializers.JSONField(required=False)
    mock_result = serializers.ChoiceField(choices=["success", "fail"], required=False, default="success")
    mock_outputs = serializers.JSONField(required=False, default=dict)
    mock_error = serializers.CharField(required=False, allow_blank=True, default="")


class NodeMockSerializer(serializers.Serializer):
    space_id = serializers.IntegerField()
    template_id = serializers.IntegerField()
    node_id = serializers.CharField()
    enable = serializers.BooleanField(required=False, default=True)
    mock_result = serializers.ChoiceField(choices=["success", "fail"], required=False, default="success")
    mock_outputs = serializers.JSONField(required=False, default=dict)
    mock_error = serializers.CharField(required=False, allow_blank=True, default="")


class ContextVarSerializer(serializers.Serializer):
    space_id = serializers.IntegerField()
    template_id = serializers.IntegerField()
    key = serializers.CharField()
    value = serializers.JSONField()


class ResetSerializer(serializers.Serializer):
    space_id = serializers.IntegerField()
    template_id = serializers.IntegerField()
    node_ids = serializers.ListField(child=serializers.CharField(), required=False)


class TerminateSerializer(serializers.Serializer):
    space_id = serializers.IntegerField()
    template_id = serializers.IntegerField()
    node_id = serializers.CharField(required=False)
