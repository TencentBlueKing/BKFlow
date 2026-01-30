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
import re

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import Label


class LabelSerializer(serializers.ModelSerializer):
    """标签序列化器"""

    label_scope = serializers.ListField(
        child=serializers.ChoiceField(
            choices=Label.LABEL_SCOPE_CHOICES,
            allow_blank=False,
        ),
        min_length=1,
        required=True,
    )
    has_children = serializers.BooleanField(read_only=True, help_text="是否有子标签")
    full_path = serializers.ReadOnlyField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 检查是否是创建场景 (instance 为 None)
        if self.instance is None:
            # 1. 必填字段设置
            required_fields = ["name", "space_id", "color", "label_scope"]
            for field_name in required_fields:
                if field_name in self.fields:
                    self.fields[field_name].required = True

            # 2. 可选字段设置
            optional_fields = ["description", "parent_id"]
            for field_name in optional_fields:
                if field_name in self.fields:
                    field = self.fields[field_name]
                    field.required = False
                    field.allow_null = True

                    # 只有字符串类型的字段才设置 allow_blank
                    if isinstance(field, (serializers.CharField)):
                        field.allow_blank = True

    class Meta:
        model = Label
        fields = [
            "id",
            "name",
            "creator",
            "updated_by",
            "space_id",
            "color",
            "description",
            "created_at",
            "updated_at",
            "label_scope",
            "is_default",
            "has_children",
            "full_path",
            "parent_id",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "is_default",
            "creator",
            "updated_by",
            "has_children",
            "full_path",
        ]

    def validate_color(self, value):
        if not re.match(r"^#([0-9A-Fa-f]{6})$", value):
            raise serializers.ValidationError(_("颜色格式错误"))
        return value

    def validate_name(self, value):
        """验证标签名称非空且去重（结合 space_id）"""
        value = value.strip()
        if not value:
            raise serializers.ValidationError(_("标签名称不能为空"))
        # 新增时：检查同一 space_id 下名称是否重复
        if self.instance is None:
            space_id = self.initial_data.get("space_id", -1)
            if Label.objects.filter(space_id=space_id, name=value).exists():
                raise serializers.ValidationError(_(f"该空间下已存在名称为「{value}」的标签"))
        # 修改时：排除自身，检查同一 space_id 下名称是否重复
        else:
            space_id = self.initial_data.get("space_id", self.instance.space_id)
            if Label.objects.filter(space_id=space_id, name=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError(_(f"该空间下已存在名称为「{value}」的标签"))
        return value


class LabelRefSerializer(serializers.Serializer):
    """标签引用序列化器"""

    space_id = serializers.IntegerField(required=True, help_text="空间ID")
    label_ids = serializers.CharField(required=True, help_text="标签ID")
