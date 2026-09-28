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
    run_id = UUIDStringField(required=False)
    expected_plan_hash = serializers.CharField(required=False, max_length=64)
    idempotency_key = serializers.CharField(max_length=255)
    client_context = ClientContextSerializer(required=False, default=dict)


class CreateDraftSerializer(ClosedSerializer):
    run_id = UUIDStringField()
    revision_id = UUIDStringField()
    plan_hash = serializers.CharField(max_length=64)
    idempotency_key = serializers.CharField(max_length=255)
