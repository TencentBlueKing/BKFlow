"""Fail-closed real-step approval and Token boundaries."""

import datetime
import hashlib
import uuid
from dataclasses import replace
from unittest.mock import PropertyMock

import pytest
from django.utils import timezone

import bkflow.harness.constants as harness_constants
from bkflow.harness.models import DebugSession, EvidenceEvent
from bkflow.harness.services.debug import policy as debug_policy
from bkflow.harness.services.debug.approval import (
    DebugApprovalDecision,
    DebugApprovalVerifier,
)
from bkflow.harness.services.debug.facade import (
    run_debug_with_context,
    start_debug_session_with_context,
)
from bkflow.harness.services.token_broker import ActiveTokenHandle, TokenBroker
from bkflow.space.models import Space, SpaceConfig

from .test_run_debug import _step_request

pytest_plugins = ("tests.interface.harness.debug.test_start_session",)


class RecordingVerifier(DebugApprovalVerifier):
    def __init__(self, decision):
        self.decision = decision
        self.calls = []

    def verify(self, receipt_ref, expected_claims):
        self.calls.append((receipt_ref, expected_claims))
        return self.decision


def _set_flag(space_id, name, enabled):
    SpaceConfig.objects.update_or_create(
        space_id=space_id,
        name=name,
        defaults={"text_value": "true" if enabled else "false"},
    )


def _global_decision(context, plan_hash, **overrides):
    decision_class = getattr(debug_policy, "GlobalRealApprovalDecision", None)
    assert decision_class is not None
    values = {
        "allowed": True,
        "action": "run_debug_global_real",
        "release_manifest_id": str(uuid.UUID("00000000-0000-0000-0000-000000000123")),
        "plan_hash": plan_hash,
        "target_environment": context.target_environment,
    }
    values.update(overrides)
    return decision_class(**values)


def _global_environment_policy(*environments):
    policy_class = getattr(debug_policy, "GlobalRealEnvironmentPolicy", None)
    assert policy_class is not None
    return policy_class(allowed_environments=environments)


@pytest.mark.parametrize(
    "environments",
    [
        (),
        ("stag", "stag"),
        tuple("env-{}".format(index) for index in range(33)),
        ("unsafe environment",),
    ],
)
def test_global_real_environment_policy_rejects_unbounded_or_ambiguous_values(environments):
    """Only a finite, unique server-owned environment allowlist can authorize Real."""
    policy_class = getattr(debug_policy, "GlobalRealEnvironmentPolicy", None)
    assert policy_class is not None

    with pytest.raises(ValueError):
        policy_class(allowed_environments=environments)


@pytest.fixture
def real_case(start_case, monkeypatch):
    context, _run, _revision, _template, request, resolver = start_case
    Space.objects.create(
        id=context.space_id,
        app_code=context.platform_app,
        platform_url="http://example.test",
        name="run-real-space",
    )
    monkeypatch.setattr("bkflow.permission.token_issuer.TokenResourceValidator.validate", lambda _self: None)
    assert start_debug_session_with_context(context, request, resolver=resolver)["ok"] is True
    return context, DebugSession.objects.get(), resolver


@pytest.mark.django_db
def test_default_deny_real_requires_approval_before_verifier_broker_or_debug(real_case, mocker):
    context, session, resolver = real_case
    verifier = mocker.MagicMock()
    broker = mocker.MagicMock()
    debug = mocker.patch("bkflow.template.debug.service.DebugService.step_run")

    response = run_debug_with_context(
        context,
        _step_request(
            session,
            execution_mode="real",
            mock_result="success",
            mock_outputs={},
            approval_receipt_ref="approval://trusted/receipt-1",
        ),
        resolver=resolver,
        approval_verifier=verifier,
        token_broker=broker,
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "APPROVAL_REQUIRED"
    assert response["errors"][0]["category"] == "APPROVAL"
    verifier.verify.assert_not_called()
    broker.acquire_debug_lease.assert_not_called()
    debug.assert_not_called()


@pytest.mark.django_db
def test_missing_receipt_fails_before_any_real_side_effect(real_case, mocker):
    context, session, resolver = real_case
    broker = mocker.MagicMock()
    debug = mocker.patch("bkflow.template.debug.service.DebugService.step_run")
    request = _step_request(session, execution_mode="real", mock_result="success", mock_outputs={})

    response = run_debug_with_context(context, request, resolver=resolver, token_broker=broker)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "APPROVAL_REQUIRED"
    broker.acquire_debug_lease.assert_not_called()
    debug.assert_not_called()


@pytest.mark.django_db
def test_receipt_claims_are_complete_and_invalid_decision_is_not_persisted(real_case, mocker):
    context, session, resolver = real_case
    verifier = RecordingVerifier(
        DebugApprovalDecision(
            allowed=False,
            provider="test-provider",
            receipt_digest="a" * 64,
            claims_digest="b" * 64,
            reason="claim_mismatch",
        )
    )
    broker = mocker.MagicMock()
    debug = mocker.patch("bkflow.template.debug.service.DebugService.step_run")
    enabled = mocker.patch("bkflow.harness.services.debug.run.is_harness_real_step_enabled", return_value=True)
    request = _step_request(
        session,
        execution_mode="real",
        mock_result="success",
        mock_outputs={},
        approval_receipt_ref="approval://trusted/receipt-1",
    )

    response = run_debug_with_context(
        context,
        request,
        resolver=resolver,
        approval_verifier=verifier,
        token_broker=broker,
        allow_real=True,
    )

    assert enabled.called
    assert response["ok"] is False
    assert response["errors"][0]["code"] == "APPROVAL_INVALID"
    assert response["errors"][0]["category"] == "APPROVAL"
    claims = verifier.calls[0][1]
    expires_after = claims.pop("expires_after")
    assert expires_after <= timezone.now()
    assert claims == {
        "platform_app": context.platform_app,
        "actor": context.actor,
        "space_id": context.space_id,
        "scope_type": context.scope_type,
        "scope_value": context.scope_value,
        "environment": context.target_environment,
        "plan_hash": session.plan_hash,
        "action": "run_debug_real_step",
        "node_id": "A",
    }
    broker.acquire_debug_lease.assert_not_called()
    debug.assert_not_called()
    assert not EvidenceEvent.objects.filter(action="run_debug").exists()
    serialized = str(list(EvidenceEvent.objects.values()))
    assert "receipt-1" not in serialized


@pytest.mark.django_db
def test_valid_receipt_without_preexisting_live_lease_fails_before_broker_or_debug(real_case, mocker):
    context, session, resolver = real_case
    verifier = RecordingVerifier(
        DebugApprovalDecision(
            True,
            "test-provider",
            hashlib.sha256(b"approval://trusted/receipt-2").hexdigest(),
            "b" * 64,
            "approved",
        )
    )
    broker = mocker.MagicMock()
    debug = mocker.patch("bkflow.template.debug.service.DebugService.step_run")
    mocker.patch("bkflow.harness.services.debug.run.is_harness_real_step_enabled", return_value=True)

    response = run_debug_with_context(
        context,
        _step_request(
            session,
            execution_mode="real",
            mock_outputs={},
            approval_receipt_ref="approval://trusted/receipt-2",
            idempotency_key="run-real-no-lease",
        ),
        resolver=resolver,
        approval_verifier=verifier,
        token_broker=broker,
        allow_real=True,
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "TOKEN_LEASE"
    broker.acquire_debug_lease.assert_not_called()
    debug.assert_not_called()


@pytest.mark.django_db
def test_allowed_real_step_consumes_handle_only_in_adapter_and_returns_no_secret(real_case, mocker, caplog):
    context, session, resolver = real_case
    broker = TokenBroker()
    issued = broker.acquire_debug_lease(context, session)
    secret_property = mocker.patch.object(
        ActiveTokenHandle,
        "secret",
        new_callable=PropertyMock,
        return_value=issued.secret,
    )
    receipt_digest = hashlib.sha256(b"approval://trusted/receipt-3").hexdigest()
    verifier = RecordingVerifier(DebugApprovalDecision(True, "test-provider", receipt_digest, "b" * 64, "approved"))
    client = mocker.MagicMock()
    client.create_task.return_value = {"result": True, "data": {"id": 8001}}
    client.get_node_id_map.return_value = {"result": True, "data": {"A": "runtime-A"}}
    client.operate_task.return_value = {"result": True}
    mocker.patch("bkflow.template.debug.service.DebugService._task_client", return_value=client)
    mocker.patch("bkflow.harness.services.debug.run.is_harness_real_step_enabled", return_value=True)

    response = run_debug_with_context(
        context,
        _step_request(
            session,
            execution_mode="real",
            mock_outputs={},
            approval_receipt_ref="approval://trusted/receipt-3",
            idempotency_key="run-real-valid",
        ),
        resolver=resolver,
        approval_verifier=verifier,
        token_broker=broker,
        allow_real=True,
    )

    assert response["ok"] is True
    assert response["artifact_refs"][0]["status"] == "running"
    assert secret_property.call_count == 0
    event = EvidenceEvent.objects.get(event_type="DEBUG_RUN_STARTED", action="run_debug")
    assert event.redacted_payload["approval"] == {
        "allowed": True,
        "provider": "test-provider",
        "receipt_digest": receipt_digest,
        "claims_digest": "b" * 64,
        "reason": "approved",
    }
    serialized = str(response) + str(list(EvidenceEvent.objects.values())) + caplog.text
    assert issued.secret not in serialized
    assert "receipt-3" not in serialized


@pytest.mark.django_db
@pytest.mark.parametrize("verifier_result", [object(), RuntimeError("verifier down")])
def test_malformed_or_failed_verifier_fails_closed_before_broker_and_debug(real_case, mocker, verifier_result):
    context, session, resolver = real_case
    verifier = mocker.MagicMock()
    if isinstance(verifier_result, Exception):
        verifier.verify.side_effect = verifier_result
    else:
        verifier.verify.return_value = verifier_result
    broker = mocker.MagicMock()
    debug = mocker.patch("bkflow.template.debug.service.DebugService.step_run")
    mocker.patch("bkflow.harness.services.debug.run.is_harness_real_step_enabled", return_value=True)

    response = run_debug_with_context(
        context,
        _step_request(
            session,
            execution_mode="real",
            mock_outputs={},
            approval_receipt_ref="approval://trusted/malformed",
            idempotency_key="run-real-malformed",
        ),
        resolver=resolver,
        approval_verifier=verifier,
        token_broker=broker,
        allow_real=True,
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "APPROVAL_INVALID"
    broker.acquire_debug_lease.assert_not_called()
    debug.assert_not_called()


def test_debug_approval_verifier_without_backend_fails_closed():
    decision = DebugApprovalVerifier().verify(
        "approval://trusted/receipt-1",
        {"expires_after": timezone.now() + datetime.timedelta(seconds=1)},
    )

    assert decision.allowed is False
    assert decision.reason == "verifier_unavailable"
    assert decision.receipt_digest == "4be4376eea99ede7791b924066dd7173a8fea79dfddacf6a2b7cff9ae32dd1e3"
    assert "receipt-1" not in repr(decision)


def test_p3_action_and_risk_vocabularies_are_exact_and_stable():
    """Policy cannot invent undeclared release or runtime actions at call time."""
    action = getattr(harness_constants, "HarnessAction", None)
    assert action is not None
    assert list(action.values) == [
        "prepare_release",
        "publish_workflow",
        "start_workflow_execution",
        "get_workflow_execution",
        "pause",
        "resume",
        "revoke",
        "retry",
        "skip",
        "callback",
        "forced_fail",
        "skip_exg",
        "skip_cpg",
        "run_debug_global_real",
    ]
    assert list(harness_constants.RiskLevel.values) == ["L0", "L1", "L2", "L3"]


@pytest.mark.django_db
def test_global_real_requires_all_flags_environment_allowlist_and_release_bound_approval(real_case):
    """A normalized release approval is required in addition to every server-side gate."""
    context, session, _resolver = real_case
    context = replace(context, mcp_contract_version="1.3.0")
    for name in (
        "harness_debug_enabled",
        "harness_real_step_enabled",
        "harness_global_real_enabled",
    ):
        _set_flag(context.space_id, name, True)
    allowed = getattr(debug_policy, "is_global_real_debug_allowed", None)
    assert allowed is not None

    assert (
        allowed(
            context,
            expected_plan_hash=session.plan_hash,
            expected_release_manifest_id="00000000-0000-0000-0000-000000000123",
            environment_policy=_global_environment_policy("stag"),
            approval_decision=_global_decision(context, session.plan_hash),
        )
        is True
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "case",
    (
        "parent_flag_off",
        "predecessor_contract",
        "environment_not_allowlisted",
        "allowlist_is_untrusted_list",
        "allowlist_is_untrusted_text",
        "allowlist_is_untrusted_mapping",
        "approval_is_request_text",
        "approval_is_request_mapping",
        "approval_denied",
        "approval_wrong_action",
        "approval_without_manifest",
        "approval_wrong_manifest",
        "approval_wrong_plan",
        "approval_wrong_environment",
    ),
)
def test_global_real_fails_closed_when_any_release_bound_predicate_is_missing(real_case, case):
    """No request-shaped approval or partial predicate can authorize global Real execution."""
    context, session, _resolver = real_case
    context = replace(context, mcp_contract_version="1.3.0")
    for name in (
        "harness_debug_enabled",
        "harness_real_step_enabled",
        "harness_global_real_enabled",
    ):
        _set_flag(context.space_id, name, True)
    allowed = getattr(debug_policy, "is_global_real_debug_allowed", None)
    assert allowed is not None
    environment_policy = _global_environment_policy("stag")
    decision = _global_decision(context, session.plan_hash)
    expected_plan_hash = session.plan_hash
    expected_release_manifest_id = decision.release_manifest_id

    if case == "parent_flag_off":
        _set_flag(context.space_id, "harness_real_step_enabled", False)
    elif case == "predecessor_contract":
        context = replace(context, mcp_contract_version="1.2.0")
    elif case == "environment_not_allowlisted":
        environment_policy = _global_environment_policy("test")
    elif case == "allowlist_is_untrusted_list":
        environment_policy = ["stag"]
    elif case == "allowlist_is_untrusted_text":
        environment_policy = "stag"
    elif case == "allowlist_is_untrusted_mapping":
        environment_policy = {"allowed_environments": ["stag"]}
    elif case == "approval_is_request_text":
        decision = "approved"
    elif case == "approval_is_request_mapping":
        decision = {"approved": True, "release_manifest_id": "from-request"}
    elif case == "approval_denied":
        decision = _global_decision(context, session.plan_hash, allowed=False)
    elif case == "approval_wrong_action":
        decision = _global_decision(context, session.plan_hash, action="publish_workflow")
    elif case == "approval_without_manifest":
        decision = _global_decision(context, session.plan_hash, release_manifest_id="")
    elif case == "approval_wrong_manifest":
        expected_release_manifest_id = "00000000-0000-0000-0000-000000000456"
    elif case == "approval_wrong_plan":
        decision = _global_decision(context, "b" * 64)
    elif case == "approval_wrong_environment":
        decision = _global_decision(context, session.plan_hash, target_environment="prod")

    assert (
        allowed(
            context,
            expected_plan_hash=expected_plan_hash,
            expected_release_manifest_id=expected_release_manifest_id,
            environment_policy=environment_policy,
            approval_decision=decision,
        )
        is False
    )
