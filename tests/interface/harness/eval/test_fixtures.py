"""Owner-reviewed, sanitized, immutable Eval fixture derivation."""

import pytest

from bkflow.harness import models as harness_models
from bkflow.harness.services.eval.fixtures import (
    EvalFixtureError,
    derive_regression_case,
)
from tests.interface.harness.eval.p4_eval_support import (
    approved_knowledge_candidate,
    case_spec,
)
from tests.interface.harness.p4_model_support import (
    candidate_values,
    create_run_revision,
    feedback_values,
)


@pytest.mark.django_db
def test_fixture_is_derived_only_after_review_and_contains_no_raw_feedback():
    candidate = approved_knowledge_candidate()

    case = derive_regression_case(candidate.id, operator="candidate-owner", **case_spec("resolver"))

    assert len(case.fixture_hash) == 64
    assert case.source_candidate_id == candidate.id
    assert case.expected_invariants["suite"] == "resolver"
    assert "selected capability" not in str(case.expected_invariants).casefold()


@pytest.mark.django_db
def test_fixture_rejects_unreviewed_candidate_wrong_owner_and_secret_input():
    run, revision = create_run_revision()
    feedback = harness_models.GenerationFeedback.objects.create(**feedback_values(run, revision))
    draft = harness_models.ImprovementCandidate.objects.create(
        **candidate_values(feedback, owner_ref="candidate-owner", reviewer_ref="candidate-reviewer")
    )

    with pytest.raises(EvalFixtureError, match="CANDIDATE_NOT_APPROVED"):
        derive_regression_case(draft.id, operator="candidate-owner", **case_spec("schema"))

    approved = approved_knowledge_candidate()
    with pytest.raises(EvalFixtureError, match="OWNER_REQUIRED"):
        derive_regression_case(approved.id, operator="candidate-reviewer", **case_spec("schema"))
    unsafe = case_spec("schema")
    unsafe["expected_invariants"] = {"suite": "schema", "assertions": {"token": "raw-secret"}}
    with pytest.raises(EvalFixtureError, match="FIXTURE_INVALID"):
        derive_regression_case(approved.id, operator="candidate-owner", **unsafe)
