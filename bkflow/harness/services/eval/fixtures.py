"""Owner-reviewed derivation of sanitized immutable Eval fixtures."""

from collections.abc import Mapping

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from bkflow.harness.constants import ImprovementCandidateStatus
from bkflow.harness.models import HarnessEvalCase, ImprovementCandidate

ALLOWED_SUITES = frozenset({"resolver", "schema", "validation", "acl", "policy", "postcondition", "security"})
ALLOWED_SAFETY_TAGS = frozenset({"permission", "cross_space", "secret"})


class EvalFixtureError(ValueError):
    """Stable rejection for unreviewed or unsafe fixture input."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _closed_fixture_contract(expected_invariants, scoring_schema, safety_tags):
    if (
        not isinstance(expected_invariants, Mapping)
        or set(expected_invariants) != {"suite", "assertions"}
        or expected_invariants.get("suite") not in ALLOWED_SUITES
        or not isinstance(expected_invariants.get("assertions"), Mapping)
        or not expected_invariants["assertions"]
    ):
        raise EvalFixtureError("FIXTURE_INVALID")
    if (
        not isinstance(scoring_schema, Mapping)
        or set(scoring_schema) != {"required", "version"}
        or not isinstance(scoring_schema.get("required"), list)
        or not scoring_schema["required"]
        or not all(isinstance(item, str) and item for item in scoring_schema["required"])
        or not isinstance(scoring_schema.get("version"), str)
    ):
        raise EvalFixtureError("FIXTURE_INVALID")
    if (
        not isinstance(safety_tags, list)
        or len(safety_tags) != len(set(safety_tags))
        or set(safety_tags) - ALLOWED_SAFETY_TAGS
    ):
        raise EvalFixtureError("FIXTURE_INVALID")


@transaction.atomic
def derive_regression_case(
    candidate_id,
    *,
    operator,
    case_id,
    case_version,
    sanitized_input_artifact_ref,
    expected_invariants,
    scoring_schema,
    safety_tags,
):
    """Persist only explicit sanitized artifacts and invariants after independent approval."""
    candidate = ImprovementCandidate.objects.select_for_update().get(pk=candidate_id)
    if candidate.status != ImprovementCandidateStatus.APPROVED:
        raise EvalFixtureError("CANDIDATE_NOT_APPROVED")
    if candidate.owner_ref is None or operator != candidate.owner_ref:
        raise EvalFixtureError("OWNER_REQUIRED")
    _closed_fixture_contract(expected_invariants, scoring_schema, safety_tags)
    try:
        return HarnessEvalCase.objects.create(
            case_id=case_id,
            case_version=case_version,
            source_candidate=candidate,
            tier=candidate.target_tier,
            scope=candidate.source_feedback.scope,
            sanitized_input_artifact_ref=sanitized_input_artifact_ref,
            expected_invariants=dict(expected_invariants),
            scoring_schema=dict(scoring_schema),
            safety_tags=list(safety_tags),
        )
    except (IntegrityError, ValidationError, TypeError, ValueError):
        raise EvalFixtureError("FIXTURE_INVALID") from None
