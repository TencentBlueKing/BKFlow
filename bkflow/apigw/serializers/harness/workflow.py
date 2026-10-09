"""Workflow control transport contracts."""

from rest_framework import serializers

from .common import ClientContextSerializer, ClosedSerializer


class UUIDStringField(serializers.UUIDField):
    """Validate a UUID while retaining the JSON-string domain contract."""

    def to_internal_value(self, data):
        return str(super().to_internal_value(data))


class ValidateWorkflowSerializer(ClosedSerializer):
    intent_spec = serializers.JSONField()
    a2flow = serializers.JSONField()
    bindings = serializers.ListField()
    run_id = UUIDStringField(
        required=False,
        help_text=("首次生成必须省略 run_id（不要生成 UUID、复制示例或传 null），由服务端分配。" "后续修订仅原样使用本会话服务端返回的 run_id；被拒绝时停止，不换 ID 或删除引用重试。"),
    )
    expected_plan_hash = serializers.CharField(required=False, max_length=64)
    idempotency_key = serializers.CharField(max_length=255)
    client_context = ClientContextSerializer(required=False, default=dict)


class CreateDraftSerializer(ClosedSerializer):
    run_id = UUIDStringField()
    revision_id = UUIDStringField()
    plan_hash = serializers.CharField(max_length=64)
    idempotency_key = serializers.CharField(max_length=255)
