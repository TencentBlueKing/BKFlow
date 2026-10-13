"""Shared bounded Harness request primitives."""
from collections.abc import Mapping

from rest_framework import serializers

from bkflow.harness.services.canonical import canonical_json_bytes

MAX_JSON_DEPTH = 8
MAX_JSON_ITEMS = 100
MAX_JSON_STRING_CHARS = 4096
MAX_JSON_STRING_BYTES = 16384
MAX_JSON_TOTAL_BYTES = 65536


def _reject_unbounded_json(value, depth=0):
    """Raise a generic transport validation error for malformed or oversized JSON."""
    if depth > MAX_JSON_DEPTH:
        raise serializers.ValidationError({"request": "request is not accepted"})
    if isinstance(value, Mapping):
        if len(value) > MAX_JSON_ITEMS:
            raise serializers.ValidationError({"request": "request is not accepted"})
        for key, child in value.items():
            if not isinstance(key, str) or len(key) > 128:
                raise serializers.ValidationError({"request": "request is not accepted"})
            _reject_unbounded_json(child, depth + 1)
        return
    if isinstance(value, list):
        if len(value) > MAX_JSON_ITEMS:
            raise serializers.ValidationError({"request": "request is not accepted"})
        for child in value:
            _reject_unbounded_json(child, depth + 1)
        return
    if isinstance(value, str):
        try:
            value_bytes = len(value.encode("utf-8"))
        except UnicodeError as error:
            raise serializers.ValidationError({"request": "request is not accepted"}) from error
        if len(value) > MAX_JSON_STRING_CHARS or value_bytes > MAX_JSON_STRING_BYTES:
            raise serializers.ValidationError({"request": "request is not accepted"})
        return
    if not isinstance(value, (int, float, bool, type(None))):
        raise serializers.ValidationError({"request": "request is not accepted"})


def validate_bounded_json(value):
    """Validate canonical byte size after recursively rejecting hostile JSON shapes."""
    _reject_unbounded_json(value)
    try:
        if len(canonical_json_bytes(value)) > MAX_JSON_TOTAL_BYTES:
            raise serializers.ValidationError({"request": "request is not accepted"})
    except (TypeError, UnicodeError, ValueError) as error:
        raise serializers.ValidationError({"request": "request is not accepted"}) from error


class ClosedSerializer(serializers.Serializer):
    """Reject unknown model-controlled authority fields rather than ignoring them."""

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({"request": "request is not accepted"})
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({"request": "unknown fields are not accepted"})
        validate_bounded_json(data)
        return super().to_internal_value(data)


class ClientContextSerializer(ClosedSerializer):
    conversation_ref = serializers.CharField(required=False, max_length=255)
    agent_release = serializers.CharField(required=False, max_length=255)
