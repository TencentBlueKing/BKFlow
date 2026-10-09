"""P2 revision-bound debug transport contracts."""

from collections.abc import Mapping

from rest_framework import serializers

from bkflow.harness.services.debug.policy import (
    DebugStartRejected,
    validate_control_request,
    validate_get_request,
    validate_run_request,
    validate_start_request,
)

from .common import ClosedSerializer
from .workflow import UUIDStringField


class _DomainValidatedSerializer(ClosedSerializer):
    """Keep APIGW transport fields identical to the domain tagged contracts."""

    domain_validator = None
    idempotency_header_policy = "ignore"

    def _validate_domain(self, value):
        try:
            self.domain_validator(dict(value))
        except DebugStartRejected:
            raise serializers.ValidationError({"request": "request is not accepted"}) from None

    def to_internal_value(self, data):
        """Apply the strict domain types before DRF can coerce wire scalars."""
        if isinstance(data, Mapping):
            self._validate_domain(data)
        return super().to_internal_value(data)

    def validate(self, attrs):
        """Recheck the normalized value as defense in depth."""
        self._validate_domain(attrs)
        return attrs


class _DebugWriteSerializer(_DomainValidatedSerializer):
    """Require an optional transport idempotency header to match the body."""

    idempotency_header_policy = "match_body"


class StartDebugSessionSerializer(_DebugWriteSerializer):
    """Create one step or global session for an exact validated revision."""

    domain_validator = staticmethod(validate_start_request)

    run_id = UUIDStringField()
    revision_id = UUIDStringField()
    expected_plan_hash = serializers.RegexField(r"^[a-f0-9]{64}$", min_length=64, max_length=64)
    mode = serializers.ChoiceField(choices=("step", "global"))
    idempotency_key = serializers.CharField(min_length=1, max_length=255)


class RunDebugSerializer(_DebugWriteSerializer):
    """Accept exactly one tagged step or global debug request."""

    domain_validator = staticmethod(validate_run_request)

    session_id = UUIDStringField()
    expected_plan_hash = serializers.RegexField(r"^[a-f0-9]{64}$", min_length=64, max_length=64)
    mode = serializers.ChoiceField(choices=("step", "global"))
    execution_mode = serializers.ChoiceField(choices=("mock", "real"))
    node_id = serializers.CharField(required=False, max_length=255)
    input_overrides = serializers.JSONField(required=False)
    mock_result = serializers.ChoiceField(required=False, choices=("success", "fail"))
    mock_outputs = serializers.JSONField(required=False)
    mock_error = serializers.CharField(required=False, allow_blank=True, max_length=4096)
    approval_receipt_ref = serializers.CharField(required=False, max_length=255)
    inputs = serializers.JSONField(required=False)
    idempotency_key = serializers.CharField(min_length=1, max_length=255)


class GetDebugSessionSerializer(_DomainValidatedSerializer):
    """Read a bounded page of one owned session and its Evidence."""

    domain_validator = staticmethod(validate_get_request)
    idempotency_header_policy = "reject"

    session_id = UUIDStringField()
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100, default=20)
    cursor = serializers.RegexField(r"^[A-Za-z0-9_-]+$", required=False, max_length=512)
    node_limit = serializers.IntegerField(required=False, min_value=1, max_value=20)
    node_cursor = serializers.RegexField(r"^[A-Za-z0-9_-]+$", required=False, max_length=512)
    node_id = serializers.CharField(required=False, min_length=1, max_length=255)


class ControlDebugSessionSerializer(_DebugWriteSerializer):
    """Accept exactly one tagged reset, terminate, Mock, or context update."""

    domain_validator = staticmethod(validate_control_request)

    session_id = UUIDStringField()
    expected_plan_hash = serializers.RegexField(r"^[a-f0-9]{64}$", min_length=64, max_length=64)
    action = serializers.ChoiceField(choices=("reset", "terminate", "set_node_mock", "set_context_var"))
    idempotency_key = serializers.CharField(min_length=1, max_length=255)
    node_ids = serializers.ListField(required=False, child=serializers.CharField(max_length=255), max_length=100)
    node_id = serializers.CharField(required=False, max_length=255)
    enabled = serializers.BooleanField(required=False)
    mock_result = serializers.ChoiceField(required=False, choices=("success", "fail"))
    mock_outputs = serializers.JSONField(required=False)
    mock_error = serializers.CharField(required=False, allow_blank=True, max_length=4096)
    key = serializers.CharField(required=False, max_length=131)
    value = serializers.JSONField(required=False, allow_null=True)
