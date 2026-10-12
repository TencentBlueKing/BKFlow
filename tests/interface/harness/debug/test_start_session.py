"""Revision-bound start_debug_session service contracts."""

import copy
from types import SimpleNamespace

import pytest

from bkflow.harness.constants import DebugMode, DebugSessionStatus, HarnessRunStatus
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.models import (
    CapabilityBinding,
    DebugSession,
    EvidenceEvent,
    HarnessIdempotencyRecord,
    HarnessRun,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import canonical_scope, sha256_json
from bkflow.harness.services.capability_ref import encode_capability_ref
from bkflow.harness.services.debug.adapter import DebugAdapter
from bkflow.harness.services.debug.facade import start_debug_session_with_context
from bkflow.harness.services.resolver import ProviderInfrastructureError
from bkflow.harness.services.validator import WorkflowValidator
from bkflow.template.models import (
    DebugContext,
    DebugNodeState,
    Template,
    TemplateSnapshot,
)

from .test_adapter_contract import PIPELINE_TREE


class RecordingResolver:
    """Return one current capability while retaining the exact resolve contract."""

    def __init__(self, **overrides):
        self.calls = []
        values = {
            "resolved_version": "1.0.0",
            "schema_hash": "b" * 64,
            "conversion_fingerprint": "c" * 64,
        }
        values.update(overrides)
        self.capability = SimpleNamespace(**values)

    def resolve(self, capability_ref, expected_schema_hash=None):
        self.calls.append((capability_ref, expected_schema_hash))
        if not hasattr(self.capability, "capability_ref"):
            self.capability.capability_ref = capability_ref
        return self.capability


def trusted_context(**overrides):
    """Build the complete trusted context for one managed draft."""
    values = {
        "platform_key": "bkaidev",
        "platform_app": "trusted-app",
        "actor": "dannydeng",
        "space_id": 902,
        "scope_type": "project",
        "scope_value": "902",
        "target_environment": "stag",
        "policy_version": "risk-2026.09",
        "mcp_contract_version": "1.2.0",
        "correlation_id": "start-debug-test",
    }
    values.update(overrides)
    return TrustedHarnessContext(**values)


@pytest.fixture
def start_case(db):
    """Persist a latest validated revision and its exact managed draft artifact."""
    context = trusted_context()
    run = HarnessRun.objects.create(
        platform=context.platform_key,
        platform_app=context.platform_app,
        actor=context.actor,
        space_id=context.space_id,
        scope=canonical_scope(context.scope_type, context.scope_value),
        environment=context.target_environment,
        status=HarnessRunStatus.DRAFT_READY,
        policy_version=context.policy_version,
        mcp_contract_version=context.mcp_contract_version,
    )
    capability_ref = encode_capability_ref("component", None, "test", "1.0.0")
    canonical = {"version": "2.0", "nodes": [{"id": "A", "type": "activity"}]}
    binding_values = {
        "node_id": "A",
        "capability_ref": capability_ref,
        "resolved_version": "1.0.0",
        "schema_hash": "b" * 64,
        "conversion_fingerprint": "c" * 64,
        "credential_ref": None,
        "risk": "L1",
    }
    resolver = RecordingResolver()
    plan_hash = WorkflowValidator(context, resolver=resolver)._plan_hash(canonical, [binding_values])
    revision = WorkflowPlanRevision.objects.create(
        run=run,
        sequence=1,
        intent_spec={"goal": "debug workflow"},
        canonical_a2flow=canonical,
        plan_hash=plan_hash,
    )
    CapabilityBinding.objects.create(revision=revision, **binding_values)
    snapshot = TemplateSnapshot.objects.create(
        template_id=42,
        draft=True,
        md5sum="0" * 32,
        data=copy.deepcopy(PIPELINE_TREE),
    )
    template = Template.objects.create(
        id=42,
        space_id=context.space_id,
        snapshot_id=snapshot.id,
        name="Harness draft",
        scope_type=context.scope_type,
        scope_value=context.scope_value,
        bk_app_code=context.platform_app,
    )
    run.artifact_references = [
        {
            "type": "harness_draft",
            "template_id": template.id,
            "revision_id": str(revision.id),
            "pipeline_tree_hash": sha256_json(PIPELINE_TREE),
        }
    ]
    run.save(update_fields=["artifact_references"])
    ValidationReport.objects.create(
        run=run,
        revision=revision,
        checkpoint="VALIDATE",
        validator_version=WorkflowValidator.VERSION,
        result={
            "valid": True,
            "converter_fingerprint": "converter-v1",
            "pipeline_tree_hash": sha256_json(PIPELINE_TREE),
            "capability_conversion_fingerprints": {"A": "c" * 64},
        },
        risk_manifest={},
        errors=[],
        warnings=[],
        correlation_id=context.correlation_id,
    )
    request = {
        "run_id": str(run.run_id),
        "revision_id": str(revision.id),
        "expected_plan_hash": revision.plan_hash,
        "mode": DebugMode.STEP,
        "idempotency_key": "start-debug-1",
    }
    return context, run, revision, template, request, resolver


@pytest.mark.django_db
def test_start_session_persists_atomic_debug_state_and_replays_exact_response(start_case):
    """A valid start creates one idle session and exact retries create nothing else."""
    context, run, revision, template, request, resolver = start_case

    first = start_debug_session_with_context(context, request, resolver=resolver)
    replay = start_debug_session_with_context(context, request, resolver=resolver)

    assert first == replay
    assert first["ok"] is True
    assert set(first) == {
        "ok",
        "run_id",
        "revision_id",
        "plan_hash",
        "status",
        "summary",
        "artifact_refs",
        "errors",
        "next_actions",
        "correlation_id",
    }
    artifact = first["artifact_refs"][0]
    assert artifact["type"] == "debug_session"
    assert artifact["template_id"] == template.id
    assert artifact["mode"] == DebugMode.STEP
    assert artifact["input_schema"][0]["key"] == "${input}"
    assert [node["node_id"] for node in artifact["node_readiness"]] == ["A", "B"]
    assert artifact["tree_fingerprint"]["nodes"]
    assert first["plan_hash"] == revision.plan_hash
    assert first["status"] == HarnessRunStatus.DEBUGGING
    assert first["next_actions"] == ["run_debug", "get_debug_session"]

    run.refresh_from_db()
    session = DebugSession.objects.get()
    debug_context = DebugContext.objects.get(pk=session.debug_context_id)
    assert run.status == HarnessRunStatus.DEBUGGING
    assert session.status == DebugSessionStatus.ACTIVE
    assert session.current_task_id is None
    assert debug_context.active_task_id is None
    assert session.tree_fingerprint == artifact["tree_fingerprint"]
    assert HarnessIdempotencyRecord.objects.filter(status="COMPLETED").count() == 1
    event = EvidenceEvent.objects.get(event_type="DEBUG_SESSION_STARTED")
    assert event.debug_session == session
    assert event.redacted_payload["session_id"] == str(session.id)
    assert DebugSession.objects.count() == EvidenceEvent.objects.count() == 1
    binding = revision.capability_bindings.get()
    assert resolver.calls == [(binding.capability_ref, binding.schema_hash)]


@pytest.mark.django_db
def test_start_session_replays_when_only_retry_correlation_changes(start_case):
    """A transport trace ID is not part of the durable idempotency identity."""
    context, _run, _revision, _template, request, resolver = start_case
    first = start_debug_session_with_context(context, request, resolver=resolver)

    replay = start_debug_session_with_context(
        trusted_context(correlation_id="retry-trace"),
        request,
        resolver=resolver,
    )

    assert replay == first
    assert DebugSession.objects.count() == 1
    assert EvidenceEvent.objects.count() == 1


@pytest.mark.django_db
def test_start_session_uses_bounded_evidence_for_a_model_bound_large_fingerprint(start_case):
    """Stress the DebugSession fingerprint bound without claiming a P0 end-to-end fixture."""
    context, run, _revision, template, request, resolver = start_case
    pipeline_tree = copy.deepcopy(PIPELINE_TREE)
    pipeline_tree["activities"] = {
        "n{:03d}{}".format(index, "x" * 28): {
            "id": "n{:03d}{}".format(index, "x" * 28),
            "type": "ServiceActivity",
            "component": {"code": "test", "data": {}},
        }
        for index in range(160)
    }
    pipeline_tree["flows"] = {}
    snapshot = TemplateSnapshot.objects.get(pk=template.snapshot_id)
    snapshot.data = pipeline_tree
    snapshot.save(update_fields=["data"])
    pipeline_tree_hash = sha256_json(pipeline_tree)
    artifacts = copy.deepcopy(run.artifact_references)
    artifacts[0]["pipeline_tree_hash"] = pipeline_tree_hash
    run.artifact_references = artifacts
    run.save(update_fields=["artifact_references"])
    report = run.validation_reports.get(checkpoint="VALIDATE")
    report.result["pipeline_tree_hash"] = pipeline_tree_hash
    report.save(update_fields=["result"])

    response = start_debug_session_with_context(context, request, resolver=resolver)

    assert response["ok"] is True
    event = EvidenceEvent.objects.get(event_type="DEBUG_SESSION_STARTED")
    assert event.redacted_payload["tree_fingerprint_node_count"] == 160
    assert len(event.redacted_payload["tree_fingerprint_hash"]) == 64
    assert "tree_fingerprint" not in event.redacted_payload


@pytest.mark.django_db
def test_start_session_rejects_closed_schema_and_different_key_after_start(start_case):
    """Unknown request authority and a second start cannot create another session."""
    context, _run, _revision, _template, request, resolver = start_case
    unexpected = {**request, "template_id": 42}

    invalid = start_debug_session_with_context(context, unexpected, resolver=resolver)
    assert invalid["ok"] is False
    assert invalid["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert DebugSession.objects.count() == 0

    accepted = start_debug_session_with_context(context, request, resolver=resolver)
    conflict = start_debug_session_with_context(
        context, {**request, "idempotency_key": "start-debug-2"}, resolver=resolver
    )
    assert accepted["ok"] is True
    assert conflict["ok"] is False
    assert conflict["errors"][0]["code"] == "DEBUG_CONFLICT"
    assert conflict["errors"][0]["category"] == "DEBUG_CONFLICT"
    assert conflict["errors"][0]["suggested_action"] == "get_debug_session"
    assert DebugSession.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "mutation, expected_code",
    [
        ("foreign_context", "CAPABILITY_FORBIDDEN"),
        ("not_draft_ready", "DEBUG_CONFLICT"),
        ("stale_revision", "VALIDATION_STALE"),
        ("artifact_revision", "VALIDATION_STALE"),
        ("tree_drift", "VALIDATION_STALE"),
        ("stale_report", "VALIDATION_STALE"),
    ],
)
def test_start_session_fails_closed_on_authority_revision_state_or_draft_drift(start_case, mutation, expected_code):
    """Only the latest owned revision and its unchanged managed draft may enter debug."""
    context, run, revision, template, request, resolver = start_case
    if mutation == "foreign_context":
        context = trusted_context(actor="foreign-user")
    elif mutation == "not_draft_ready":
        run.status = HarnessRunStatus.VALIDATING
        run.save(update_fields=["status"])
    elif mutation == "stale_revision":
        WorkflowPlanRevision.objects.create(
            run=run,
            sequence=2,
            parent_revision=revision,
            intent_spec={},
            canonical_a2flow={"version": "2.0", "nodes": []},
            plan_hash="f" * 64,
        )
    elif mutation == "artifact_revision":
        artifacts = copy.deepcopy(run.artifact_references)
        artifacts[0]["revision_id"] = "00000000-0000-0000-0000-000000000000"
        run.artifact_references = artifacts
        run.save(update_fields=["artifact_references"])
    elif mutation == "tree_drift":
        changed = copy.deepcopy(template.pipeline_tree)
        changed["activities"]["A"]["component"]["data"] = {"changed": {"value": True}}
        template.update_snapshot(changed)
    else:
        ValidationReport.objects.create(
            run=run,
            revision=revision,
            checkpoint="VALIDATE",
            validator_version=WorkflowValidator.VERSION,
            result={"valid": False},
            risk_manifest={},
            errors=[{"code": "INVALID_NODE"}],
            warnings=[],
            correlation_id=context.correlation_id,
        )

    response = start_debug_session_with_context(context, request, resolver=resolver)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == expected_code
    assert DebugSession.objects.count() == 0
    assert DebugContext.objects.count() == 0
    assert EvidenceEvent.objects.count() == 0


@pytest.mark.django_db
def test_start_session_rejects_same_key_with_changed_request(start_case):
    """A completed idempotency key cannot be rebound to another debug mode."""
    context, _run, _revision, _template, request, resolver = start_case
    assert start_debug_session_with_context(context, request, resolver=resolver)["ok"] is True

    response = start_debug_session_with_context(context, {**request, "mode": DebugMode.GLOBAL}, resolver=resolver)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "IDEMPOTENCY_CONFLICT"
    assert DebugSession.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "resolver_overrides",
    [
        {"capability_ref": "capability://component/foreign@1.0.0"},
        {"resolved_version": "2.0.0"},
        {"schema_hash": "d" * 64},
        {"conversion_fingerprint": "e" * 64},
    ],
)
def test_start_session_reresolves_every_exact_capability_fact(start_case, resolver_overrides):
    """Version, schema, and conversion drift all invalidate the accepted revision."""
    context, _run, revision, _template, request, _resolver = start_case
    resolver = RecordingResolver(**resolver_overrides)

    response = start_debug_session_with_context(context, request, resolver=resolver)

    binding = revision.capability_bindings.get()
    assert resolver.calls == [(binding.capability_ref, binding.schema_hash)]
    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert DebugSession.objects.count() == 0


@pytest.mark.django_db
def test_start_session_keeps_provider_outage_retryable(start_case):
    """A registry outage is not evidence of schema drift and may be retried."""
    context, _run, _revision, _template, request, _resolver = start_case

    class UnavailableResolver:
        def resolve(self, capability_ref, expected_schema_hash=None):
            raise ProviderInfrastructureError()

    response = start_debug_session_with_context(context, request, resolver=UnavailableResolver())

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert response["errors"][0]["retryable"] is True
    assert DebugSession.objects.count() == 0


@pytest.mark.django_db
def test_start_session_rejects_busy_canvas_context_as_a_debug_conflict(start_case):
    """An existing canvas debug context cannot be adopted by Harness start."""
    context, _run, _revision, template, request, resolver = start_case
    DebugContext.objects.create(template_id=template.id, space_id=context.space_id, status="running")

    response = start_debug_session_with_context(context, request, resolver=resolver)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "DEBUG_CONFLICT"
    assert response["errors"][0]["category"] == "DEBUG_CONFLICT"
    assert response["errors"][0]["suggested_action"] == "get_debug_session"
    assert DebugSession.objects.count() == 0


@pytest.mark.django_db
def test_start_session_requires_persisted_conversion_fingerprint_map(start_case):
    """A validation report without binding conversion facts cannot authorize debug."""
    context, run, _revision, _template, request, resolver = start_case
    report = run.validation_reports.get(checkpoint="VALIDATE")
    report.result.pop("capability_conversion_fingerprints")
    report.save(update_fields=["result"])

    response = start_debug_session_with_context(context, request, resolver=resolver)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert DebugSession.objects.count() == 0


@pytest.mark.django_db
def test_start_failure_rolls_back_clean_baseline_initialization(start_case, mocker):
    """Preparing a clean shared context is part of the atomic session creation."""
    context, _run, _revision, template, request, resolver = start_case
    debug_context = DebugContext.objects.create(
        template_id=template.id,
        space_id=context.space_id,
        global_vars={"${old}": "keep-on-rollback"},
        status="idle",
        last_task_id=7001,
        last_run_type="step",
        last_run_status="finished",
    )
    DebugNodeState.objects.create(
        debug_context=debug_context,
        node_id="A",
        execution_mode="mock",
        mock_outputs={"result": "keep-on-rollback"},
        status="finished",
        outputs={"result": "keep-on-rollback"},
    )
    observed = {}
    original_prepare = DebugAdapter.prepare

    def inspect_clean_baseline(adapter):
        snapshot = original_prepare(adapter)
        prepared = DebugContext.objects.get(pk=debug_context.pk)
        observed["clean"] = (
            prepared.global_vars == {}
            and prepared.last_task_id is None
            and not DebugNodeState.objects.filter(
                debug_context=prepared,
                outputs={"result": "keep-on-rollback"},
            ).exists()
        )
        return snapshot

    mocker.patch.object(DebugAdapter, "prepare", autospec=True, side_effect=inspect_clean_baseline)
    mocker.patch(
        "bkflow.harness.services.debug.session.record_evidence",
        side_effect=RuntimeError("evidence unavailable"),
    )

    response = start_debug_session_with_context(context, request, resolver=resolver)

    debug_context.refresh_from_db()
    node = DebugNodeState.objects.get(debug_context=debug_context, node_id="A")
    assert response["ok"] is False
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert observed == {"clean": True}
    assert debug_context.global_vars == {"${old}": "keep-on-rollback"}
    assert debug_context.last_task_id == 7001
    assert node.execution_mode == "mock"
    assert node.outputs == {"result": "keep-on-rollback"}
    assert DebugSession.objects.count() == 0


@pytest.mark.django_db
def test_start_session_reports_cross_run_template_conflict_before_unique_constraint(start_case):
    """An active template is globally exclusive even when another owned run references it."""
    context, first_run, first_revision, template, first_request, first_resolver = start_case
    assert start_debug_session_with_context(context, first_request, resolver=first_resolver)["ok"] is True

    second_run = HarnessRun.objects.create(
        platform=context.platform_key,
        platform_app=context.platform_app,
        actor=context.actor,
        space_id=context.space_id,
        scope=canonical_scope(context.scope_type, context.scope_value),
        environment=context.target_environment,
        status=HarnessRunStatus.DRAFT_READY,
        policy_version=context.policy_version,
        mcp_contract_version=context.mcp_contract_version,
    )
    binding = first_revision.capability_bindings.get()
    binding_values = {
        "node_id": binding.node_id,
        "capability_ref": binding.capability_ref,
        "resolved_version": binding.resolved_version,
        "schema_hash": binding.schema_hash,
        "conversion_fingerprint": binding.conversion_fingerprint,
        "credential_ref": binding.credential_ref,
        "risk": binding.risk,
    }
    canonical = copy.deepcopy(first_revision.canonical_a2flow)
    second_hash = WorkflowValidator(context, resolver=first_resolver)._plan_hash(canonical, [binding_values])
    second_revision = WorkflowPlanRevision.objects.create(
        run=second_run,
        sequence=1,
        intent_spec={},
        canonical_a2flow=canonical,
        plan_hash=second_hash,
    )
    CapabilityBinding.objects.create(revision=second_revision, **binding_values)
    tree_hash = sha256_json(template.pipeline_tree)
    second_run.artifact_references = [
        {
            "type": "harness_draft",
            "template_id": template.id,
            "revision_id": str(second_revision.id),
            "pipeline_tree_hash": tree_hash,
        }
    ]
    second_run.save(update_fields=["artifact_references"])
    ValidationReport.objects.create(
        run=second_run,
        revision=second_revision,
        checkpoint="VALIDATE",
        validator_version=WorkflowValidator.VERSION,
        result={
            "valid": True,
            "converter_fingerprint": "converter-v1",
            "pipeline_tree_hash": tree_hash,
            "capability_conversion_fingerprints": {"A": "c" * 64},
        },
        risk_manifest={},
        errors=[],
        warnings=[],
        correlation_id=context.correlation_id,
    )
    second_request = {
        **first_request,
        "run_id": str(second_run.run_id),
        "revision_id": str(second_revision.id),
        "idempotency_key": "second-run-start",
    }

    response = start_debug_session_with_context(context, second_request, resolver=RecordingResolver())

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "DEBUG_CONFLICT"
    assert DebugSession.objects.filter(run=first_run).count() == 1
    assert DebugSession.objects.filter(run=second_run).count() == 0
