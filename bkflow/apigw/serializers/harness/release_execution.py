"""Closed P3 release and execution transport contracts."""

from collections.abc import Mapping

from rest_framework import serializers

from bkflow.harness.services.execution.contracts import (
    StartExecutionRejected,
    validate_control_execution_request,
    validate_get_execution_request,
    validate_start_execution_request,
)
from bkflow.harness.services.release.facade import (
    ReleasePreparationRejected,
    validate_prepare_request,
)
from bkflow.harness.services.release.publish import (
    WorkflowPublicationRejected,
    validate_publish_request,
)

from .common import ClosedSerializer
from .workflow import UUIDStringField


class _DomainValidatedSerializer(ClosedSerializer):
    """Validate the original JSON types before DRF may coerce primitives."""

    domain_validator = None
    idempotency_header_policy = "ignore"

    def _validate_domain(self, value):
        try:
            self.domain_validator(dict(value))
        except (ReleasePreparationRejected, WorkflowPublicationRejected, StartExecutionRejected):
            raise serializers.ValidationError({"request": "request is not accepted"}) from None

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            self._validate_domain(data)
        return super().to_internal_value(data)

    def validate(self, attrs):
        self._validate_domain(attrs)
        return attrs


class _P3WriteSerializer(_DomainValidatedSerializer):
    idempotency_header_policy = "match_body"


class _ApprovedWriteSerializer(_P3WriteSerializer):
    approval_request_id = UUIDStringField(required=False)
    approval_receipt_ref = serializers.CharField(required=False, min_length=1, max_length=255, trim_whitespace=False)


class PrepareReleaseSerializer(_P3WriteSerializer):
    domain_validator = staticmethod(validate_prepare_request)

    run_id = UUIDStringField()
    revision_id = UUIDStringField()
    expected_plan_hash = serializers.RegexField(r"^[a-f0-9]{64}$", min_length=64, max_length=64)
    idempotency_key = serializers.CharField(min_length=1, max_length=255, trim_whitespace=False)


class PublishWorkflowSerializer(_ApprovedWriteSerializer):
    domain_validator = staticmethod(validate_publish_request)

    run_id = UUIDStringField()
    manifest_id = UUIDStringField()
    manifest_hash = serializers.RegexField(r"^[a-f0-9]{64}$", min_length=64, max_length=64)
    version = serializers.CharField(min_length=1, max_length=32, trim_whitespace=False)
    description = serializers.CharField(required=True, allow_blank=True, max_length=255, trim_whitespace=False)
    idempotency_key = serializers.CharField(min_length=1, max_length=255, trim_whitespace=False)


class StartWorkflowExecutionSerializer(_ApprovedWriteSerializer):
    domain_validator = staticmethod(validate_start_execution_request)

    run_id = UUIDStringField()
    manifest_id = UUIDStringField()
    publication_id = UUIDStringField()
    expected_plan_hash = serializers.RegexField(r"^[a-f0-9]{64}$", min_length=64, max_length=64)
    name = serializers.CharField(min_length=1, max_length=128, trim_whitespace=False)
    constants = serializers.JSONField()
    idempotency_key = serializers.CharField(min_length=1, max_length=128, trim_whitespace=False)


class GetWorkflowExecutionSerializer(_DomainValidatedSerializer):
    domain_validator = staticmethod(validate_get_execution_request)
    idempotency_header_policy = "reject"

    execution_id = UUIDStringField()
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100, default=20)
    cursor = serializers.CharField(required=False, min_length=1, max_length=512, trim_whitespace=False)


class ControlWorkflowExecutionSerializer(_ApprovedWriteSerializer):
    domain_validator = staticmethod(validate_control_execution_request)

    execution_id = UUIDStringField()
    expected_manifest_hash = serializers.RegexField(r"^[a-f0-9]{64}$", min_length=64, max_length=64)
    action = serializers.ChoiceField(
        choices=("pause", "resume", "revoke", "retry", "skip", "callback", "forced_fail", "skip_exg", "skip_cpg")
    )
    idempotency_key = serializers.CharField(min_length=1, max_length=128, trim_whitespace=False)
    template_node_id = serializers.CharField(required=False, min_length=1, max_length=255)
    loop = serializers.BooleanField(required=False)
    inputs = serializers.JSONField(required=False)
    callback_data = serializers.JSONField(required=False)
    reason_code = serializers.ChoiceField(required=False, choices=("operator_requested",))
    template_gateway_id = serializers.CharField(required=False, min_length=1, max_length=255)
    template_flow_id = serializers.CharField(required=False, min_length=1, max_length=255)
    template_flow_ids = serializers.ListField(
        required=False,
        min_length=1,
        max_length=32,
        child=serializers.CharField(min_length=1, max_length=255),
    )
    template_converge_gateway_id = serializers.CharField(required=False, min_length=1, max_length=255)


__all__ = [
    "ControlWorkflowExecutionSerializer",
    "GetWorkflowExecutionSerializer",
    "PrepareReleaseSerializer",
    "PublishWorkflowSerializer",
    "StartWorkflowExecutionSerializer",
]
