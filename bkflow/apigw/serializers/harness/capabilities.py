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

from bkflow.apigw.serializers.harness.common import (
    IDENTITY_FIELDS,
    ClientContextSerializer,
)


class SearchWorkflowCapabilitiesSerializer(serializers.Serializer):
    query = serializers.CharField(required=True)
    top_k = serializers.IntegerField(required=False, default=10, min_value=1, max_value=20)
    run_id = serializers.CharField(required=False)
    client_context = ClientContextSerializer(required=False)

    def validate(self, attrs):
        for field in IDENTITY_FIELDS:
            attrs.pop(field, None)
        return attrs


class GetPluginSchemaSerializer(serializers.Serializer):
    capability_ref = serializers.CharField(required=True)
    expected_schema_hash = serializers.CharField(required=False)
    run_id = serializers.CharField(required=False)
    client_context = ClientContextSerializer(required=False)

    def validate(self, attrs):
        for field in IDENTITY_FIELDS:
            attrs.pop(field, None)
        return attrs
