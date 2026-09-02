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

from bkflow.harness.services.facade import ERROR_CATEGORIES

ENVELOPE_FIELDS = (
    "ok",
    "run_id",
    "revision_id",
    "plan_hash",
    "status",
    "summary",
    "artifact_refs",
    "errors",
    "next_actions",
    "correlation_id",
)
IDENTITY_FIELDS = (
    "platform_key",
    "platform_app",
    "actor",
    "space_id",
    "scope_type",
    "scope_value",
    "target_environment",
    "policy_version",
    "mcp_contract_version",
)


class ClientContextSerializer(serializers.Serializer):
    conversation_ref = serializers.CharField(required=False, allow_blank=True)
    agent_release = serializers.CharField(required=False, allow_blank=True)


class HarnessWriteSerializer(serializers.Serializer):
    run_id = serializers.CharField(required=False)
    revision_id = serializers.CharField(required=False)
    idempotency_key = serializers.CharField(required=True)
    expected_plan_hash = serializers.CharField(required=False)
    client_context = ClientContextSerializer(required=False)

    def validate(self, attrs):
        for field in IDENTITY_FIELDS:
            attrs.pop(field, None)
        return attrs


class HarnessEnvelopeSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    run_id = serializers.CharField(required=False, allow_null=True)
    revision_id = serializers.CharField(required=False, allow_null=True)
    plan_hash = serializers.CharField(required=False, allow_null=True)
    status = serializers.CharField(required=False, allow_null=True)
    summary = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    artifact_refs = serializers.ListField(child=serializers.DictField(), required=False)
    errors = serializers.ListField(child=serializers.DictField(), required=False)
    next_actions = serializers.ListField(child=serializers.DictField(), required=False)
    correlation_id = serializers.CharField(required=False, allow_null=True)

    def validate_errors(self, value):
        for item in value or []:
            if item.get("category") not in ERROR_CATEGORIES:
                raise serializers.ValidationError("unsupported error category")
            for forbidden in ("traceback", "token", "secret", "credential"):
                if forbidden in {key.lower() for key in item.keys()} or forbidden in str(item).lower():
                    raise serializers.ValidationError("error payload contains forbidden secret fields")
        return value
