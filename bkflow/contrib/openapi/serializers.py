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
import json

from rest_framework import serializers


class EmptyBodySerializer(serializers.Serializer):
    data = serializers.DictField(required=True)

    def validate(self, attrs):
        if "operator" not in attrs.get("data"):
            raise serializers.ValidationError("operator is required in data")
        return attrs


class GetNodeDetailQuerySerializer(serializers.Serializer):
    username = serializers.CharField(required=False, default="")
    include_data = serializers.BooleanField(required=False, default=True)
    component_code = serializers.CharField(required=False)
    subprocess_stack = serializers.CharField(required=False, default="[]")
    loop = serializers.IntegerField(required=False)

    def validate_subprocess_stack(self, value):
        try:
            subprocess_stack = json.loads(value)
        except Exception:
            raise serializers.ValidationError("subprocess_stack is not a valid array json")
        return subprocess_stack


class GetNodeLogDetailSerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, default=1)
    page_size = serializers.IntegerField(required=False, default=30)


class GetTasksStatesBodySerializer(serializers.Serializer):
    task_ids = serializers.ListField(required=True, child=serializers.IntegerField())
    space_id = serializers.IntegerField(required=True)


class TaskEngineAdminSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(required=True)
    instance_id = serializers.CharField(required=True)
    action = serializers.CharField(required=True)
    data = serializers.DictField(required=False, default=None)


class TaskBatchDeleteSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(required=True)
    is_full = serializers.BooleanField(required=False, default=False)
    is_mock = serializers.BooleanField(required=False)
    task_ids = serializers.ListField(required=False, child=serializers.IntegerField())

    def validate(self, attrs):
        if attrs.get("is_full") and "is_mock" not in attrs:
            raise serializers.ValidationError("is_mock must exist when delete all tasks")

        return attrs
