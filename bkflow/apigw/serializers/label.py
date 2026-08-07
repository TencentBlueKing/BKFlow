"""APIGW serializers for label endpoints."""

from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from bkflow.label.models import Label


class LabelListFilterSerializer(serializers.Serializer):
    offset = serializers.IntegerField(help_text=_("偏移量"), required=False, default=0)
    limit = serializers.IntegerField(help_text=_("返回数量"), required=False, default=100)
    label_scope = serializers.ChoiceField(
        help_text=_("标签范围"),
        choices=[c[0] for c in Label.LABEL_SCOPE_CHOICES],
        required=False,
    )
    parent_id = serializers.IntegerField(help_text=_("父标签ID"), required=False)
    name = serializers.CharField(help_text=_("标签名称"), required=False, allow_blank=False)
    is_default = serializers.BooleanField(help_text=_("是否默认标签"), required=False)
    order_by = serializers.CharField(help_text=_("排序字段"), required=False, default="-updated_at")
    # 是否包含子标签
    include_children = serializers.BooleanField(help_text=_("是否包含子标签"), required=False, default=False)

    def validate_order_by(self, value):
        allow = {
            "created_at",
            "updated_at",
            "name",
            "-created_at",
            "-updated_at",
            "-name",
        }
        if value not in allow:
            raise serializers.ValidationError(_("排序字段非法"))
        return value


class LabelRefCountSerializer(serializers.Serializer):
    label_ids = serializers.CharField(required=True, help_text=_("标签ID列表，逗号分隔"))

    def validate_label_ids(self, value):
        label_ids_str = str(value).strip()
        if not label_ids_str:
            raise serializers.ValidationError("label_ids 不能为空")
        # only digits and comma, and not start/end with comma
        if (
            not all(ch.isdigit() or ch == "," for ch in label_ids_str)
            or label_ids_str.startswith(",")
            or label_ids_str.endswith(",")
        ):
            raise serializers.ValidationError("label_ids 格式非法，仅允许数字和逗号（如 1,2,3）")

        # de-dup + keep stable order
        parts = [p for p in label_ids_str.split(",") if p]
        uniq = []
        seen = set()
        for p in parts:
            if p not in seen:
                seen.add(p)
                uniq.append(p)
        return ",".join(uniq)


class LabelTreeFilterSerializer(serializers.Serializer):
    label_scope = serializers.ChoiceField(
        help_text=_("标签范围"),
        choices=[c[0] for c in Label.LABEL_SCOPE_CHOICES],
        required=False,
    )
    offset = serializers.IntegerField(help_text=_("偏移量"), required=False, min_value=0)
    limit = serializers.IntegerField(help_text=_("返回数量"), required=False, min_value=0)
