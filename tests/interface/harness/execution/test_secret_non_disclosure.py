"""P3 Harness secret non-disclosure and authority-denial gate."""

import dataclasses
import json
from unittest import mock

import pytest

from bkflow.harness.constants import HarnessAction
from bkflow.harness.models import (
    ApprovalRequest,
    EvidenceEvent,
    ExecutionRun,
    HarnessIdempotencyRecord,
)
from bkflow.harness.services.approval import (
    ApprovalVerifier,
    InMemoryApprovalReplayGuard,
)
from tests.interface.harness import p3_golden_support as golden
from tests.interface.harness.execution import test_start_execution as start_cases
from tests.interface.harness.release import test_prepare_release as prepare_cases
from tests.interface.harness.release import test_publish_workflow as publish_cases

SECRET_SENTINEL = "P3_GOLDEN_DOWNSTREAM_SECRET_SENTINEL"


@pytest.fixture
def golden_secret_case(db):
    return start_cases.execution_case.__wrapped__(db)


def _runtime(case):
    return {
        "run_id": str(case.run.run_id),
        "revision_id": str(case.revision.id),
        "plan_hash": case.revision.plan_hash,
        "manifest_id": str(case.manifest.id),
        "manifest_hash": case.manifest.manifest_hash,
        "publication_id": str(case.publication.id),
    }


def _execute_denial(fixture_case, case):
    golden.assert_case_declarations(fixture_case)
    tool, payload = golden.materialize_request(fixture_case, **_runtime(case))
    context = case.context
    if fixture_case["setup"]["phase"] == "cross_space":
        foreign_space = fixture_case["setup"]["foreign_space_id"]
        context = dataclasses.replace(context, space_id=foreign_space, scope_value=str(foreign_space))
    golden.apply_declared_policy(context.space_id, fixture_case)
    adapter = start_cases.RecordingAdapter()
    credentials = start_cases.RecordingCredentialResolver()
    verifier = mock.Mock()
    before_ids = set(EvidenceEvent._base_manager.values_list("id", flat=True))
    before = golden.snapshot_counts()
    trace = []
    response = golden.invoke_service(
        trace,
        tool,
        context,
        payload,
        resolver=case.resolver,
        release_policy=case.release_policy,
        converter_class=prepare_cases.ReleaseConverter,
        credential_resolver=credentials,
        approval_verifier=verifier,
        adapter=adapter,
    )
    after = golden.snapshot_counts()
    verifier.verify.assert_not_called()
    assert credentials.calls == []
    assert adapter.calls == []
    assert after["execution"] == before["execution"]
    assert after["idempotency"] == before["idempotency"]
    assert after["evidence"] == before["evidence"]
    return golden.ScenarioResult(
        response=response,
        context=context,
        run=case.run,
        revision=case.revision,
        template=case.template,
        snapshot=case.snapshot,
        tool=tool,
        payload=payload,
        event_types=golden.new_event_types(before_ids, run=case.run),
        mutation_counts={"publish": 0, "create": 0, "start": 0, "control": 0, "read": 0},
        execution=None,
        token_lease_result="none",
        service_trace=tuple(trace),
    )


@pytest.mark.django_db
@pytest.mark.parametrize("fixture_case", golden.SECRET_CASES, ids=lambda case: case["id"])
def test_secret_and_cross_space_cases_drive_real_start_denial_without_side_effects(
    fixture_case, golden_secret_case, caplog
):
    caplog.set_level("INFO")
    result = _execute_denial(fixture_case, golden_secret_case)
    golden.assert_common_contract(fixture_case, result)
    rendered_logs = json.dumps(
        [{"message": record.getMessage(), "args": record.args} for record in caplog.records],
        default=str,
        sort_keys=True,
    )
    for marker in fixture_case["forbidden_markers"]:
        assert marker not in rendered_logs


@pytest.mark.django_db
def test_secret_denial_leaves_no_execution_or_idempotency_anchor(golden_secret_case):
    result = _execute_denial(golden.SECRET_CASES[1], golden_secret_case)
    assert result.response["ok"] is False
    assert ExecutionRun.objects.filter(run=result.run).count() == 0
    assert (
        HarnessIdempotencyRecord.objects.filter(
            run=result.run, tool_name=HarnessAction.START_WORKFLOW_EXECUTION
        ).count()
        == 0
    )


@pytest.mark.django_db(transaction=True)
def test_downstream_secret_bearing_create_failure_is_projected_and_replay_does_not_redispatch(
    golden_secret_case, caplog
):
    caplog.set_level("INFO")
    case = golden_secret_case
    first = start_cases.start(case)
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    verifier = ApprovalVerifier(
        backend=publish_cases.ReceiptBackend(start_cases.start_claims(case, approval)),
        replay_guard=InMemoryApprovalReplayGuard(),
    )
    payload = start_cases.approved_payload(case, first)
    adapter = start_cases.RecordingAdapter(create_error=RuntimeError(SECRET_SENTINEL))
    credentials = start_cases.RecordingCredentialResolver({"A": {"api_key": SECRET_SENTINEL}})
    trace = []
    response = golden.invoke_service(
        trace,
        "start_workflow_execution",
        case.context,
        payload,
        resolver=case.resolver,
        release_policy=case.release_policy,
        converter_class=prepare_cases.ReleaseConverter,
        credential_resolver=credentials,
        approval_verifier=verifier,
        adapter=adapter,
    )
    replay = golden.invoke_service(
        trace,
        "start_workflow_execution",
        case.context,
        payload,
        resolver=case.resolver,
        release_policy=case.release_policy,
        converter_class=prepare_cases.ReleaseConverter,
        credential_resolver=credentials,
        approval_verifier=verifier,
        adapter=adapter,
    )
    assert response["ok"] is False
    assert replay == response
    assert [call[0] for call in adapter.calls] == ["create"]
    rendered_logs = json.dumps(
        [{"message": record.getMessage(), "args": record.args} for record in caplog.records],
        default=str,
        sort_keys=True,
    )
    assert SECRET_SENTINEL not in rendered_logs
    secret_contract = {"forbidden_markers": [SECRET_SENTINEL]}
    golden.assert_no_forbidden_markers(secret_contract, response)
