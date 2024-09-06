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
from rest_framework import serializers

from bkflow.decision_table.models import DecisionTable
from bkflow.template.models import Template


class DecisionTableSerializer(serializers.ModelSerializer):
    create_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S%z", read_only=True)
    update_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S%z", read_only=True)

    def validate(self, attrs):
        if not Template.objects.filter(space_id=attrs["space_id"], id=attrs["template_id"], is_enabled=True).exists():
            raise serializers.ValidationError(
                f'template {attrs["template_id"]} does not exist in space {attrs["space_id"]}'
            )
        return attrs

    class Meta:
        model = DecisionTable
        fields = "__all__"
        read_only_fields = ("creator", "updated_by", "is_deleted")


class DecisionTableEvaluationSerializer(serializers.Serializer):
    facts = serializers.DictField(help_text="the facts for evaluation")
    strict_mode = serializers.BooleanField(help_text="whether evaluate with strict mode", default=True)
