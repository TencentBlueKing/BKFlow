"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
import pytest

from bkflow.harness.exceptions import InvalidStateTransition
from bkflow.harness.models import HarnessRun, ValidationReport, WorkflowPlanRevision
from bkflow.harness.services.state import (
    complete_draft_creation,
    record_validation_outcome,
    transition_run,
)


@pytest.fixture
def harness_run(db):
    """Create a P0 run at the first legal lifecycle state."""
    return HarnessRun.objects.create(
        platform="bkfara",
        platform_app="bkfara_app",
        actor="dannydeng",
        space_id=100,
        scope="project:100",
        environment="stag",
        status="INTENT_CAPTURED",
        policy_version="2026.09",
        mcp_contract_version="p0",
    )


def accepted_revision_and_report(run, sequence=1):
    """Persist the exact accepted validation checkpoint required for a draft."""
    revision = WorkflowPlanRevision.objects.create(
        run=run,
        sequence=sequence,
        intent_spec={"goal": "restart service"},
        canonical_a2flow={"version": "2.0"},
        plan_hash="a" * 64,
    )
    report = ValidationReport.objects.create(
        run=run,
        revision=revision,
        checkpoint="VALIDATE",
        validator_version="2026.09",
        result={"valid": True},
        risk_manifest={},
        errors=[],
        warnings=[],
        correlation_id="validation-{}".format(sequence),
    )
    return revision, report


def release_ready_run(run):
    """Drive the real P0/P2 path to the exact P3 predecessor state."""
    transition_run(run, "PLANNING")
    transition_run(run, "VALIDATING")
    revision, report = accepted_revision_and_report(run)
    complete_draft_creation(run, revision, report)
    transition_run(run, "DEBUGGING")
    transition_run(run, "RELEASE_READY")
    return run


@pytest.mark.django_db
def test_transition_run_persists_only_the_initial_p0_path(harness_run):
    """Catch state updates that do not atomically persist the P0 lifecycle path."""
    planning = transition_run(harness_run, "PLANNING")
    validating = transition_run(harness_run, "VALIDATING")

    harness_run.refresh_from_db()

    assert (planning.previous_status, planning.status, planning.changed) == ("INTENT_CAPTURED", "PLANNING", True)
    assert (validating.previous_status, validating.status, validating.changed) == ("PLANNING", "VALIDATING", True)
    assert harness_run.status == "VALIDATING"


@pytest.mark.django_db
def test_valid_validation_keeps_the_run_validating_until_a_draft_succeeds(harness_run):
    """Catch validation falsely claiming a draft was materialized."""
    transition_run(harness_run, "PLANNING")
    transition_run(harness_run, "VALIDATING")

    validation = record_validation_outcome(harness_run, valid=True)
    harness_run.refresh_from_db()

    assert (validation.previous_status, validation.status, validation.changed) == ("VALIDATING", "VALIDATING", False)
    assert harness_run.status == "VALIDATING"

    revision, report = accepted_revision_and_report(harness_run)
    draft = complete_draft_creation(harness_run, revision, report)
    harness_run.refresh_from_db()

    assert (draft.previous_status, draft.status, draft.changed) == ("VALIDATING", "DRAFT_READY", True)
    assert harness_run.status == "DRAFT_READY"


@pytest.mark.django_db
def test_invalid_validation_moves_only_from_validating_to_needs_repair(harness_run):
    """Catch a failed validation that leaves an invalid plan eligible for drafting."""
    transition_run(harness_run, "PLANNING")
    transition_run(harness_run, "VALIDATING")

    result = record_validation_outcome(harness_run, valid=False)
    harness_run.refresh_from_db()

    assert (result.previous_status, result.status) == ("VALIDATING", "NEEDS_REPAIR")
    assert harness_run.status == "NEEDS_REPAIR"
    assert transition_run(harness_run, "VALIDATING").status == "VALIDATING"


@pytest.mark.django_db
def test_state_service_rejects_skipped_validation_and_all_p1_to_p4_states(harness_run):
    """Catch accidental expansion of the P0 state graph beyond approved transitions."""
    with pytest.raises(InvalidStateTransition):
        transition_run(harness_run, "DRAFT_READY")
    with pytest.raises(InvalidStateTransition):
        transition_run(harness_run, "DEBUGGING")

    transition_run(harness_run, "PLANNING")
    transition_run(harness_run, "VALIDATING")
    with pytest.raises(InvalidStateTransition):
        transition_run(harness_run, "DRAFT_READY")
    revision = WorkflowPlanRevision.objects.create(
        run=harness_run,
        sequence=1,
        intent_spec={},
        canonical_a2flow={"version": "2.0"},
        plan_hash="a" * 64,
    )
    with pytest.raises(InvalidStateTransition):
        complete_draft_creation(harness_run, revision, None)


@pytest.mark.django_db
def test_draft_ready_run_can_reenter_validation_for_a_new_revision(harness_run):
    """A managed draft may be safely revalidated before its next in-place update."""
    transition_run(harness_run, "PLANNING")
    transition_run(harness_run, "VALIDATING")
    revision, report = accepted_revision_and_report(harness_run)
    complete_draft_creation(harness_run, revision, report)

    validating = transition_run(harness_run, "VALIDATING")
    assert (validating.previous_status, validating.status) == ("DRAFT_READY", "VALIDATING")
    assert record_validation_outcome(harness_run, valid=False).status == "NEEDS_REPAIR"


@pytest.mark.django_db
def test_draft_ready_run_can_only_enter_the_p2_debugging_state(harness_run):
    """Task 5 opens exactly DRAFT_READY to DEBUGGING without widening other lifecycle edges."""
    transition_run(harness_run, "PLANNING")
    transition_run(harness_run, "VALIDATING")
    revision, report = accepted_revision_and_report(harness_run)
    complete_draft_creation(harness_run, revision, report)

    with pytest.raises(InvalidStateTransition):
        transition_run(harness_run, "RELEASE_READY")
    result = transition_run(harness_run, "DEBUGGING")

    assert (result.previous_status, result.status) == ("DRAFT_READY", "DEBUGGING")


@pytest.mark.django_db
@pytest.mark.parametrize("target_status", ["DRAFT_READY", "RELEASE_READY"])
def test_debugging_run_can_reach_only_the_p2_debug_outcomes(harness_run, target_status):
    """Task 7 closes Debugging into repair or release without widening other edges."""
    transition_run(harness_run, "PLANNING")
    transition_run(harness_run, "VALIDATING")
    revision, report = accepted_revision_and_report(harness_run)
    complete_draft_creation(harness_run, revision, report)
    transition_run(harness_run, "DEBUGGING")

    result = transition_run(harness_run, target_status)

    assert (result.previous_status, result.status) == ("DEBUGGING", target_status)


@pytest.mark.django_db
def test_draft_completion_rejects_a_stale_or_invalid_validation_report(harness_run):
    """Catch drafting from a report superseded by a newer invalid validation."""
    transition_run(harness_run, "PLANNING")
    transition_run(harness_run, "VALIDATING")
    revision, accepted_report = accepted_revision_and_report(harness_run)
    invalid_report = ValidationReport.objects.create(
        run=harness_run,
        revision=revision,
        checkpoint="VALIDATE",
        validator_version="2026.09",
        result={"valid": False},
        risk_manifest={},
        errors=[{"code": "INVALID_NODE"}],
        warnings=[],
        correlation_id="validation-invalid",
    )

    with pytest.raises(InvalidStateTransition):
        complete_draft_creation(harness_run, revision, accepted_report)
    with pytest.raises(InvalidStateTransition):
        complete_draft_creation(harness_run, revision, invalid_report)


@pytest.mark.django_db
def test_draft_completion_rejects_a_validation_report_bound_to_another_run(harness_run):
    """Catch a cross-run validation report being used to authorize a draft."""
    transition_run(harness_run, "PLANNING")
    transition_run(harness_run, "VALIDATING")
    revision, _ = accepted_revision_and_report(harness_run)
    other_run = HarnessRun.objects.create(
        platform="bkfara",
        platform_app="bkfara_app",
        actor="other_actor",
        space_id=101,
        scope="project:101",
        environment="stag",
        status="VALIDATING",
        policy_version="2026.09",
        mcp_contract_version="p0",
    )
    _, other_report = accepted_revision_and_report(other_run)

    with pytest.raises(InvalidStateTransition):
        complete_draft_creation(harness_run, revision, other_report)


@pytest.mark.django_db
def test_draft_completion_rejects_a_report_bound_to_another_revision(harness_run):
    """Catch a same-run report being reused for a different immutable revision."""
    transition_run(harness_run, "PLANNING")
    transition_run(harness_run, "VALIDATING")
    revision, _ = accepted_revision_and_report(harness_run, sequence=1)
    _, other_revision_report = accepted_revision_and_report(harness_run, sequence=2)

    with pytest.raises(InvalidStateTransition):
        complete_draft_creation(harness_run, revision, other_revision_report)


@pytest.mark.django_db
def test_draft_completion_requires_persisted_revision_and_validation_report(harness_run):
    """Catch draft authorization from caller-owned, unpersisted checkpoint objects."""
    transition_run(harness_run, "PLANNING")
    transition_run(harness_run, "VALIDATING")
    revision = WorkflowPlanRevision(
        run=harness_run,
        sequence=1,
        intent_spec={},
        canonical_a2flow={"version": "2.0"},
        plan_hash="a" * 64,
    )
    report = ValidationReport(
        run=harness_run,
        revision=revision,
        checkpoint="VALIDATE",
        validator_version="2026.09",
        result={"valid": True},
        risk_manifest={},
        errors=[],
        warnings=[],
        correlation_id="unpersisted",
    )

    with pytest.raises(InvalidStateTransition):
        complete_draft_creation(harness_run, revision, report)


@pytest.mark.django_db
def test_invalid_validation_serializes_before_draft_completion(harness_run):
    """Catch a serialized failed validation allowing a later draft completion."""
    transition_run(harness_run, "PLANNING")
    transition_run(harness_run, "VALIDATING")
    revision, report = accepted_revision_and_report(harness_run)

    record_validation_outcome(harness_run, valid=False)

    with pytest.raises(InvalidStateTransition):
        complete_draft_creation(harness_run, revision, report)


@pytest.mark.django_db
@pytest.mark.parametrize("approval_required", [False, True])
@pytest.mark.parametrize("terminal_status", ["SUCCEEDED", "FAILED", "CANCELLED"])
def test_p3_release_execution_path_reaches_evidence_finalized_without_skipping_states(
    harness_run,
    approval_required,
    terminal_status,
):
    """Both approval and no-approval paths preserve publish, execution and terminal checkpoints."""
    release_ready_run(harness_run)
    transitions = []
    if approval_required:
        result = transition_run(harness_run, "APPROVAL_PENDING")
        transitions.append((result.previous_status, result.status))
    result = transition_run(harness_run, "PUBLISHING")
    transitions.append((result.previous_status, result.status))
    for target in ("PUBLISHED", "EXECUTING", terminal_status, "EVIDENCE_FINALIZED"):
        result = transition_run(harness_run, target)
        transitions.append((result.previous_status, result.status))

    expected = []
    if approval_required:
        expected.append(("RELEASE_READY", "APPROVAL_PENDING"))
        publishing_source = "APPROVAL_PENDING"
    else:
        publishing_source = "RELEASE_READY"
    expected.extend(
        [
            (publishing_source, "PUBLISHING"),
            ("PUBLISHING", "PUBLISHED"),
            ("PUBLISHED", "EXECUTING"),
            ("EXECUTING", terminal_status),
            (terminal_status, "EVIDENCE_FINALIZED"),
        ]
    )
    assert transitions == expected
    harness_run.refresh_from_db()
    assert harness_run.status == "EVIDENCE_FINALIZED"


@pytest.mark.django_db
@pytest.mark.parametrize("stale_status", ["RELEASE_READY", "APPROVAL_PENDING"])
def test_stale_p3_plan_returns_to_draft_ready_before_any_publish_side_effect(harness_run, stale_status):
    """A changed plan invalidates release preparation or approval instead of continuing publish."""
    release_ready_run(harness_run)
    if stale_status == "APPROVAL_PENDING":
        transition_run(harness_run, stale_status)

    result = transition_run(harness_run, "DRAFT_READY")

    assert (result.previous_status, result.status) == (stale_status, "DRAFT_READY")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "source,target",
    [
        ("RELEASE_READY", "EXECUTING"),
        ("APPROVAL_PENDING", "PUBLISHED"),
        ("PUBLISHING", "EXECUTING"),
        ("PUBLISHED", "DRAFT_READY"),
        ("EVIDENCE_FINALIZED", "EXECUTING"),
    ],
)
def test_p3_state_service_rejects_every_undeclared_lifecycle_skip(harness_run, source, target):
    """Callers cannot jump around approval, publishing, or final Evidence boundaries."""
    release_ready_run(harness_run)
    paths = {
        "RELEASE_READY": (),
        "APPROVAL_PENDING": ("APPROVAL_PENDING",),
        "PUBLISHING": ("PUBLISHING",),
        "PUBLISHED": ("PUBLISHING", "PUBLISHED"),
        "EVIDENCE_FINALIZED": ("PUBLISHING", "PUBLISHED", "EXECUTING", "SUCCEEDED", "EVIDENCE_FINALIZED"),
    }
    for status in paths[source]:
        transition_run(harness_run, status)

    with pytest.raises(InvalidStateTransition):
        transition_run(harness_run, target)
