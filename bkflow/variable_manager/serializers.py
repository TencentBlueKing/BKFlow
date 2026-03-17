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
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from bkflow.constants import VARIABLE_TYPE_SPACE
from bkflow.space.models import Space
from bkflow.variable_manager.models import VariableManager


class VariableManagerSerializer(serializers.ModelSerializer):

    name = serializers.CharField(required=True)
    key = serializers.CharField(required=True)
    variable_type = serializers.CharField(required=True)
    value = serializers.CharField(required=True)
    desc = serializers.CharField(required=False)
    creator = serializers.CharField(read_only=True)
    create_at = serializers.DateTimeField(read_only=True)
    updated_by = serializers.CharField(read_only=True)
    update_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = VariableManager
        partial = True
        fields = [
            "id",
            "space_id",
            "name",
            "key",
            "variable_type",
            "value",
            "desc",
            "creator",
            "create_at",
            "updated_by",
            "update_at",
        ]

    def validate_space_id(self, value):
        if not Space.objects.filter(id=value).exists():
            raise serializers.ValidationError(_("创建失败，对应的空间不存在"))
        return value

    def validate_type(self, value):
        if value not in VARIABLE_TYPE_SPACE:
            raise serializers.ValidationError("类型必须在 {} 中".format(VARIABLE_TYPE_SPACE))
        return value

    def create(self, validated_data):
        validated_data["creator"] = self.context["request"].user.username
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("space_id", None)
        validated_data["updated_by"] = self.context["request"].user.username
        return super().update(instance, validated_data)
