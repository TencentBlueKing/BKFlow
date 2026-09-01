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

from bkflow.apigw.serializers.harness.common import HarnessWriteSerializer


class ValidateWorkflowSerializer(HarnessWriteSerializer):
    intent = serializers.JSONField(required=False)
    a2flow = serializers.JSONField(required=True)
    bindings = serializers.ListField(child=serializers.DictField(), required=True)


class CreateWorkflowDraftSerializer(HarnessWriteSerializer):
    run_id = serializers.CharField(required=True)
    revision_id = serializers.CharField(required=True)
    plan_hash = serializers.CharField(required=False)
    expected_plan_hash = serializers.CharField(required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get("plan_hash") and not attrs.get("expected_plan_hash"):
            raise serializers.ValidationError("plan_hash or expected_plan_hash is required")
        if attrs.get("expected_plan_hash") and not attrs.get("plan_hash"):
            attrs["plan_hash"] = attrs["expected_plan_hash"]
        return attrs
