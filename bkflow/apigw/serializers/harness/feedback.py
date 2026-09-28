"""Closed P4 generation-feedback transport contract."""

from collections.abc import Mapping

from rest_framework import serializers

from bkflow.harness.constants import GenerationFeedbackType
from bkflow.harness.services.feedback.contracts import (
    FeedbackIntakeRejected,
    GenerationFeedbackRequest,
)

from .common import ClosedSerializer
from .workflow import UUIDStringField


class SubmitGenerationFeedbackSerializer(ClosedSerializer):
    """Accept observations only; candidate governance remains Owner-controlled."""

    idempotency_header_policy = "match_body"

    run_id = UUIDStringField()
    revision_id = UUIDStringField()
    expected_plan_hash = serializers.RegexField(r"^[a-f0-9]{64}$", min_length=64, max_length=64)
    feedback_type = serializers.ChoiceField(choices=GenerationFeedbackType.values)
    consent_scope = serializers.CharField(min_length=1, max_length=64, trim_whitespace=False)
    idempotency_key = serializers.CharField(min_length=1, max_length=255, trim_whitespace=False)
    rating = serializers.IntegerField(required=False, min_value=1, max_value=5)
    summary = serializers.CharField(required=False, min_length=1, max_length=4096, trim_whitespace=False)
    correction_artifact_ref = serializers.CharField(required=False, min_length=1, max_length=255, trim_whitespace=False)
    execution_id = UUIDStringField(required=False)
    observed_outcome = serializers.JSONField(required=False)

    @staticmethod
    def _validate_domain(value):
        try:
            GenerationFeedbackRequest.from_payload(dict(value))
        except FeedbackIntakeRejected:
            raise serializers.ValidationError({"request": "request is not accepted"}) from None

    def to_internal_value(self, data):
        """Validate strict JSON types before DRF can coerce wire primitives."""
        if isinstance(data, Mapping):
            self._validate_domain(data)
        return super().to_internal_value(data)

    def validate(self, attrs):
        """Keep normalized transport data identical to the domain contract."""
        self._validate_domain(attrs)
        return attrs


__all__ = ["SubmitGenerationFeedbackSerializer"]
