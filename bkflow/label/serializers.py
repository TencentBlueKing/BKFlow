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

from bkflow.admin.models import ModuleInfo
from bkflow.contrib.api.collections.task import TaskComponentClient

from .models import Label, TemplateLabelRelation


class LabelSerializer(serializers.ModelSerializer):
    """Label read serializer (used for response payloads)."""

    label_scope = serializers.ListField(
        child=serializers.ChoiceField(
            choices=Label.LABEL_SCOPE_CHOICES,
            allow_blank=False,
        ),
        required=False,
    )
    has_children = serializers.BooleanField(read_only=True, help_text="是否有子标签")
    full_path = serializers.ReadOnlyField()

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

    def update(self, instance, validated_data):
        # 更新时禁止更新parent_id
        validated_data.pop("parent_id", None)
        return super().update(instance, validated_data)


class _LabelWriteBaseSerializer(LabelSerializer):
    """Base serializer for write operations (create/update)."""

    def validate_color(self, value):
        if not re.match(r"^#([0-9A-Fa-f]{6})$", value):
            raise serializers.ValidationError(_("颜色格式错误"))
        return value

    def validate_name(self, value):
        """Validate label name non-empty and unique within (space_id, parent_id)."""
        value = value.strip()
        if not value:
            raise serializers.ValidationError(_("标签名称不能为空"))
        if len(value.split("/")) > 2:
            raise serializers.ValidationError(_("标签名称层级不能超过两层"))
        if len(value) > 20:
            raise serializers.ValidationError(_("标签名称长度不能超过20个字符"))

        parent_id = self.initial_data.get("parent_id", None)

        # Create: check duplicates within the same space and same parent
        if self.instance is None:
            space_id = self.initial_data.get("space_id", -1)
            if Label.objects.filter(space_id=space_id, name=value, parent_id=parent_id).exists():
                raise serializers.ValidationError(_(f"该空间下已存在名称为「{value}」的标签"))
        # Update: exclude self
        else:
            space_id = self.initial_data.get("space_id", self.instance.space_id)
            if (
                Label.objects.filter(space_id=space_id, name=value, parent_id=parent_id)
                .exclude(id=self.instance.id)
                .exists()
            ):
                raise serializers.ValidationError(_(f"该空间下已存在名称为「{value}」的标签"))

        return value

    def validate_label_scope(self, value):
        """Validate label scope consistency between parent and children."""
        parent_id = self.initial_data.get("parent_id", None)
        if parent_id:
            # When there is a parent, child scope must be subset of parent scope
            try:
                parent_label = Label.objects.get(id=parent_id)
            except Label.DoesNotExist:
                raise serializers.ValidationError(_("父标签不存在"))
            if not set(value).issubset(set(parent_label.label_scope)):
                raise serializers.ValidationError(_("子标签的范围必须是父标签的子集"))

        # When updating a parent scope, it must cover all descendant scopes
        if self.instance is not None:
            children = self.instance.get_all_children(recursive=True)
            if children:
                children_scope = set()
                for child in children:
                    if isinstance(child.label_scope, (list, tuple, set)):
                        children_scope.update(child.label_scope)
                    elif child.label_scope:
                        # Defensive: tolerate legacy string value
                        children_scope.add(str(child.label_scope))

                if children_scope and not children_scope.issubset(set(value)):
                    raise serializers.ValidationError(_("父标签的范围必须覆盖所有子标签的范围"))

        return value


class LabelCreateSerializer(_LabelWriteBaseSerializer):
    """Label create serializer."""

    label_scope = serializers.ListField(
        child=serializers.ChoiceField(
            choices=Label.LABEL_SCOPE_CHOICES,
            allow_blank=False,
        ),
        min_length=1,
        required=True,
    )

    class Meta(LabelSerializer.Meta):
        pass

    def validate_parent_id(self, value):
        """On create: forbid using a child label as parent, and forbid referenced parents from attaching children."""
        if not value:
            return value

        parent = Label.objects.filter(id=value).only("id", "parent_id").first()
        if parent is None:
            raise serializers.ValidationError(_("父标签不存在"))
        if parent.parent_id is not None:
            raise serializers.ValidationError(_("子标签不能作为父标签"))

        has_template_ref = TemplateLabelRelation.objects.filter(label_id=value).exists()

        space_id = self.initial_data.get("space_id")
        if space_id in [None, "", -1]:
            # space_id is required on create; keep defensive to avoid crashing.
            has_task_ref = False
        else:
            try:
                client = TaskComponentClient(space_id=int(space_id))
            except ModuleInfo.DoesNotExist:
                has_task_ref = False
            else:
                task_result = client.get_task_label_ref_count(int(space_id), str(value))
                if not task_result.get("result"):
                    raise serializers.ValidationError(_(f"获取父标签任务引用失败：{task_result.get('message') or 'unknown error'}"))
                task_count_map = task_result.get("data") or {}
                has_task_ref = int(task_count_map.get(str(value), 0) or 0) > 0

        if has_template_ref or has_task_ref:
            raise serializers.ValidationError(_("父标签已被模板或任务引用，不允许挂载子标签，如需要请先删除父标签的引用"))

        return value


class LabelUpdateSerializer(_LabelWriteBaseSerializer):
    """Label update serializer."""

    label_scope = serializers.ListField(
        child=serializers.ChoiceField(
            choices=Label.LABEL_SCOPE_CHOICES,
            allow_blank=False,
        ),
        required=False,
    )

    class Meta(LabelSerializer.Meta):
        pass

    def validate_name(self, value):
        if len(value.split("/")) >= 2:
            raise serializers.ValidationError(_("标签名称层级不能超过两层"))
        return super().validate_name(value)


class LabelRefSerializer(serializers.Serializer):
    """标签引用序列化器"""

    space_id = serializers.IntegerField(required=True, help_text="空间ID")
    label_ids = serializers.CharField(required=True, help_text="标签ID")

    def validate_label_ids(self, value):
        """
        字段级验证：验证 label_ids 格式（仅允许数字和逗号，或列表/元组类型的数字）
        """
        # 处理列表/元组类型的入参（如果前端传的是列表）
        if isinstance(value, (list, tuple)):
            # 先验证列表中的每个元素都是数字
            for item in value:
                if not isinstance(item, (int, str)) or (isinstance(item, str) and not item.isdigit()):
                    raise serializers.ValidationError("label_ids 列表中仅允许包含数字")
            label_ids_str = ",".join(map(str, value))
        else:
            # 处理字符串类型的入参
            label_ids_str = str(value).strip()  # 去除首尾空格

        # 正则验证：仅包含数字和逗号，且不以逗号开头/结尾，也不是空字符串
        if not label_ids_str:
            raise serializers.ValidationError("label_ids 不能为空")
        if not re.match(r"^[\d,]+$", label_ids_str) or label_ids_str.startswith(",") or label_ids_str.endswith(","):
            raise serializers.ValidationError("label_ids 格式非法，仅允许数字和逗号（如 1,2,3）")

        # 可选：去重 + 排序，保证格式统一
        label_ids_list = list(set(label_ids_str.split(",")))
        label_ids_list.sort()
        return ",".join(label_ids_list)
