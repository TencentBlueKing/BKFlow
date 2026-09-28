"""Revision-bound deterministic ``prepare_release`` contracts."""

import copy
from types import SimpleNamespace

import pytest
from django.db import DatabaseError
from django.utils import timezone

from bkflow.harness.constants import (
    DebugMode,
    DebugSessionStatus,
    HarnessAction,
    HarnessRunStatus,
)
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.models import (
    ApprovalRequest,
    CapabilityBinding,
    DebugSession,
    EvidenceEvent,
    HarnessIdempotencyRecord,
    HarnessRun,
    ReleaseManifest,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import canonical_scope, sha256_json
from bkflow.harness.services.capability_ref import encode_capability_ref
from bkflow.harness.services.debug.policy import trusted_context_snapshot
from bkflow.harness.services.evidence import record_evidence
from bkflow.harness.services.resolver import ProviderInfrastructureError
from bkflow.harness.services.validator import WorkflowValidator
from bkflow.pipeline_converter.converters.a2flow_v2.data_models import ConversionResult
from bkflow.pipeline_converter.exceptions import (
    A2FlowConvertError,
    A2FlowValidationError,
    ErrorTypes,
)
from bkflow.space.configs import HarnessPublishEnabledConfig, SpaceConfigValueType
from bkflow.space.models import SpaceConfig
from bkflow.template.debug.dependency import compute_tree_fingerprint
from bkflow.template.models import Template, TemplateSnapshot
from tests.interface.harness.debug.test_adapter_contract import PIPELINE_TREE

RELEASE_PIPELINE_TREE = copy.deepcopy(PIPELINE_TREE)
RELEASE_PIPELINE_TREE.update(
    {
        "id": "release-pipeline",
        "start_event": {
            "id": "start",
            "type": "EmptyStartEvent",
            "incoming": "",
            "outgoing": "f0",
            "name": "",
        },
        "end_event": {
            "id": "end",
            "type": "EmptyEndEvent",
            "incoming": ["f2"],
            "outgoing": "",
            "name": "",
        },
        "outputs": [],
    }
)
RELEASE_PIPELINE_TREE["activities"]["A"].update({"incoming": ["f0"], "outgoing": "f1", "name": "A"})
RELEASE_PIPELINE_TREE["activities"]["B"].update({"incoming": ["f1"], "outgoing": "f2", "name": "B"})
RELEASE_PIPELINE_TREE["flows"].update(
    {
        "f0": {"id": "f0", "source": "start", "target": "A", "is_default": False},
        "f1": {"id": "f1", "source": "A", "target": "B", "is_default": False},
        "f2": {"id": "f2", "source": "B", "target": "end", "is_default": False},
    }
)


POSTCONDITION_SPEC = {
    "version": "harness-postconditions-p3-v1",
    "operator": "all",
    "predicates": [{"type": "OUTPUT_EXISTS", "node_id": "A", "output_key": "result"}],
}


class ReleaseResolver:
    """Return current exact capability facts and retain every fresh lookup."""

    def __init__(self, **overrides):
        self.calls = []
        self.overrides = overrides

    def resolve(self, capability_ref, expected_schema_hash=None):
        self.calls.append((capability_ref, expected_schema_hash))
        values = {
            "capability_ref": capability_ref,
            "resolved_version": "1.0.0",
            "schema_hash": "b" * 64,
            "conversion_fingerprint": "c" * 64,
            "risk_level": "L1",
        }
        values.update(self.overrides)
        return SimpleNamespace(**values)


class UnavailableResolver:
    """Represent a fresh catalog failure without exposing provider details."""

    def resolve(self, capability_ref, expected_schema_hash=None):
        raise ProviderInfrastructureError()


class ReleaseConverter:
    """Deterministically re-convert the immutable fixture revision."""

    pipeline_tree = RELEASE_PIPELINE_TREE
    converter_fingerprint = "converter-v1"

    def __init__(self, a2flow_data, **kwargs):
        self.a2flow_data = a2flow_data
        self.kwargs = kwargs

    def convert_with_metadata(self):
        return ConversionResult(
            pipeline_tree=copy.deepcopy(self.pipeline_tree),
            converter_fingerprint=self.converter_fingerprint,
            source_map={"A": "A"},
        )


class TreeDriftConverter(ReleaseConverter):
    """Represent a converter whose current output no longer matches the draft."""

    pipeline_tree = copy.deepcopy(RELEASE_PIPELINE_TREE)
    pipeline_tree["activities"]["A"]["name"] = "converter-drift"


class FingerprintDriftConverter(ReleaseConverter):
    """Represent a converter implementation-version drift."""

    converter_fingerprint = "converter-v2"


class ValidationFailureConverter(ReleaseConverter):
    """Raise the structured validation failure used by the production converter."""

    def convert_with_metadata(self):
        raise A2FlowValidationError(
            [
                A2FlowConvertError(
                    ErrorTypes.INVALID_REFERENCE,
                    "current converter rejected immutable revision",
                    node_id="A",
                )
            ]
        )


class ProgrammingFailureConverter(ReleaseConverter):
    """Represent an unexpected converter implementation failure."""

    def convert_with_metadata(self):
        raise RuntimeError("unexpected converter failure")


def trusted_context(**overrides):
    """Build the complete trusted P3 release context."""
    values = {
        "platform_key": "bkaidev",
        "platform_app": "trusted-app",
        "actor": "dannydeng",
        "space_id": 905,
        "scope_type": "project",
        "scope_value": "905",
        "target_environment": "stag",
        "policy_version": "risk-2026.09",
        "mcp_contract_version": "1.3.0",
        "correlation_id": "prepare-release-test",
    }
    values.update(overrides)
    return TrustedHarnessContext(**values)


@pytest.fixture
def release_case(db):
    """Build one latest validated managed draft with configurable debug proof."""

    def build(
        *,
        debug_mode=DebugMode.GLOBAL,
        with_terminal_evidence=True,
        run_status=HarnessRunStatus.RELEASE_READY,
        terminal_reason="debug_completed",
        terminal_payload=None,
    ):
        context = trusted_context()
        SpaceConfig.objects.update_or_create(
            space_id=context.space_id,
            name=HarnessPublishEnabledConfig.name,
            defaults={"value_type": SpaceConfigValueType.TEXT.value, "text_value": "true"},
        )
        run = HarnessRun.objects.create(
            platform=context.platform_key,
            platform_app=context.platform_app,
            actor=context.actor,
            space_id=context.space_id,
            scope=canonical_scope(context.scope_type, context.scope_value),
            environment=context.target_environment,
            status=run_status,
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
        plan_hash = WorkflowValidator(context, resolver=object())._plan_hash(canonical, [binding_values])
        revision = WorkflowPlanRevision.objects.create(
            run=run,
            sequence=1,
            intent_spec={"goal": "release a verified workflow"},
            canonical_a2flow=canonical,
            plan_hash=plan_hash,
        )
        CapabilityBinding.objects.create(revision=revision, **binding_values)
        snapshot = TemplateSnapshot.objects.create(
            template_id=42,
            draft=True,
            md5sum="0" * 32,
            data=copy.deepcopy(RELEASE_PIPELINE_TREE),
        )
        template = Template.objects.create(
            id=42,
            space_id=context.space_id,
            snapshot_id=snapshot.id,
            name="Harness release draft",
            scope_type=context.scope_type,
            scope_value=context.scope_value,
            bk_app_code=context.platform_app,
        )
        pipeline_tree_hash = sha256_json(RELEASE_PIPELINE_TREE)
        run.artifact_references = [
            {
                "type": "harness_draft",
                "template_id": template.id,
                "revision_id": str(revision.id),
                "pipeline_tree_hash": pipeline_tree_hash,
            }
        ]
        run.save(update_fields=["artifact_references"])
        validation_report = ValidationReport.objects.create(
            run=run,
            revision=revision,
            checkpoint="VALIDATE",
            validator_version=WorkflowValidator.VERSION,
            result={
                "valid": True,
                "converter_fingerprint": "converter-v1",
                "pipeline_tree_hash": pipeline_tree_hash,
                "capability_conversion_fingerprints": {"A": "c" * 64},
            },
            risk_manifest={"capability_risks": {"A": "L1"}},
            errors=[],
            warnings=[],
            correlation_id=context.correlation_id,
        )
        tree_fingerprint = compute_tree_fingerprint(RELEASE_PIPELINE_TREE)
        debug_session = DebugSession.objects.create(
            run=run,
            revision=revision,
            template_id=template.id,
            debug_context_id=1,
            mode=debug_mode,
            status=DebugSessionStatus.COMPLETED,
            plan_hash=revision.plan_hash,
            tree_fingerprint=tree_fingerprint,
            actor=context.actor,
            policy_version=context.policy_version,
            trusted_context_snapshot=trusted_context_snapshot(context),
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
            last_heartbeat_at=timezone.now(),
            terminal_reason=terminal_reason,
        )
        terminal_event = None
        if with_terminal_evidence:
            evidence_payload = (
                copy.deepcopy(terminal_payload)
                if terminal_payload is not None
                else {
                    "session_id": str(debug_session.id),
                    "status": DebugSessionStatus.COMPLETED,
                    "reason": "debug_completed",
                }
            )
            if evidence_payload.get("session_id") == "placeholder":
                evidence_payload["session_id"] = str(debug_session.id)
            terminal_event = record_evidence(
                run=run,
                revision=revision,
                debug_session=debug_session,
                event_type="DEBUG_SESSION_COMPLETED",
                action="get_debug_session",
                payload=evidence_payload,
                actor=context.actor,
                correlation_id=context.correlation_id,
            )
        request = {
            "run_id": str(run.run_id),
            "revision_id": str(revision.id),
            "expected_plan_hash": revision.plan_hash,
            "idempotency_key": "prepare-release-1",
        }
        return SimpleNamespace(
            context=context,
            run=run,
            revision=revision,
            template=template,
            snapshot=snapshot,
            validation_report=validation_report,
            debug_session=debug_session,
            terminal_event=terminal_event,
            request=request,
            resolver=ReleaseResolver(),
            converter_class=ReleaseConverter,
        )

    return build


def prepare(case, **kwargs):
    """Invoke the public release facade while keeping injectable policies explicit."""
    from bkflow.harness.services.release.facade import prepare_release_with_context
    from bkflow.harness.services.release.policy import ReleasePolicy

    values = {
        "resolver": case.resolver,
        "release_policy": ReleasePolicy(profiles={case.context.policy_version: POSTCONDITION_SPEC}),
        "converter_class": case.converter_class,
    }
    values.update(kwargs)
    return prepare_release_with_context(case.context, case.request, **values)


@pytest.mark.django_db
def test_prepare_persists_one_immutable_manifest_and_replays_without_approval_instances(release_case):
    """Prepare hashes canonical facts and requirements, but concrete approvals wait for later actions."""
    case = release_case()

    first = prepare(case)
    replay = prepare(case)

    assert first == replay
    assert first["ok"] is True
    assert first["status"] == HarnessRunStatus.APPROVAL_PENDING
    assert first["next_actions"] == [HarnessAction.PUBLISH_WORKFLOW]
    manifest = ReleaseManifest.objects.get()
    assert first["artifact_refs"] == [
        {
            "type": "release_manifest",
            "manifest_id": str(manifest.id),
            "manifest_hash": manifest.manifest_hash,
            "draft_template_id": case.template.id,
            "draft_snapshot_id": case.snapshot.id,
            "target_environment": case.context.target_environment,
            "required_approvals": manifest.required_approvals,
            "validation_evidence_refs": manifest.validation_evidence_refs,
            "debug_evidence_refs": manifest.debug_evidence_refs,
            "postcondition_spec": POSTCONDITION_SPEC,
            "risk_manifest": manifest.risk_manifest,
        }
    ]
    assert manifest.required_approvals == [
        {
            "action": HarnessAction.PUBLISH_WORKFLOW,
            "risk_level": "L2",
            "policy_ref": "policy://risk-2026.09/publish_workflow/l2",
        },
        {
            "action": HarnessAction.START_WORKFLOW_EXECUTION,
            "risk_level": "L2",
            "policy_ref": "policy://risk-2026.09/start_workflow_execution/l2",
        },
    ]
    assert all("action_digest" not in item and "id" not in item for item in manifest.required_approvals)
    assert manifest.postcondition_spec == POSTCONDITION_SPEC
    assert manifest.draft_tree_fingerprint == compute_tree_fingerprint(RELEASE_PIPELINE_TREE)
    assert manifest.capability_snapshot == [
        {
            "capability_ref": case.revision.capability_bindings.get().capability_ref,
            "conversion_fingerprint": "c" * 64,
            "node_id": "A",
            "resolved_version": "1.0.0",
            "risk_level": "L1",
            "schema_hash": "b" * 64,
        }
    ]
    assert ApprovalRequest.objects.count() == 0
    assert ReleaseManifest.objects.count() == 1
    assert EvidenceEvent.objects.filter(event_type="RELEASE_PREPARED", run=case.run).count() == 1
    assert HarnessIdempotencyRecord.objects.filter(tool_name="prepare_release", status="COMPLETED").count() == 1
    case.run.refresh_from_db()
    assert case.run.status == HarnessRunStatus.APPROVAL_PENDING


@pytest.mark.django_db
@pytest.mark.parametrize(
    "run_status,next_action",
    [
        (HarnessRunStatus.DRAFT_READY, "start_debug_session"),
        (HarnessRunStatus.DEBUGGING, "get_debug_session"),
    ],
)
def test_prepare_requires_p2_lifecycle_and_returns_one_exact_next_action(release_case, run_status, next_action):
    """Prepare cannot bypass draft debugging or converge a running debug session itself."""
    case = release_case(run_status=run_status)

    response = prepare(case)

    assert response["ok"] is False
    assert response["next_actions"] == [next_action]
    assert ReleaseManifest.objects.count() == 0
    assert HarnessIdempotencyRecord.objects.filter(tool_name="prepare_release").count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "debug_mode,with_terminal_evidence",
    [(DebugMode.STEP, True), (DebugMode.GLOBAL, False)],
)
def test_prepare_requires_completed_global_session_and_its_terminal_evidence(
    release_case,
    debug_mode,
    with_terminal_evidence,
):
    """Neither step completion nor a terminal status without Evidence satisfies the release gate."""
    case = release_case(debug_mode=debug_mode, with_terminal_evidence=with_terminal_evidence)

    report_count = ValidationReport.objects.count()
    response = prepare(case)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "DEBUG_SESSION"
    assert response["next_actions"] == ["start_debug_session"]
    assert ReleaseManifest.objects.count() == 0
    case.run.refresh_from_db()
    assert case.run.status == HarnessRunStatus.DRAFT_READY
    assert ValidationReport.objects.count() == report_count
    assert ValidationReport.objects.filter(run=case.run, checkpoint="PREPARE_RELEASE").count() == 0


@pytest.mark.django_db
def test_release_revalidation_is_read_only_and_uses_current_exact_schema(release_case):
    """The reusable release guard does not create a Revision or ValidationReport."""
    from bkflow.harness.services.release.prepare import revalidate_revision_for_release

    case = release_case()
    counts = (WorkflowPlanRevision.objects.count(), ValidationReport.objects.count())
    facts = revalidate_revision_for_release(
        case.context,
        case.run,
        case.revision,
        case.template,
        case.snapshot,
        resolver=case.resolver,
        lock_rows=False,
        converter_class=case.converter_class,
    )

    assert facts.draft_tree_fingerprint == compute_tree_fingerprint(RELEASE_PIPELINE_TREE)
    assert facts.debug_session_id == case.debug_session.id
    assert case.resolver.calls == [(case.revision.capability_bindings.get().capability_ref, "b" * 64)]
    assert (WorkflowPlanRevision.objects.count(), ValidationReport.objects.count()) == counts


@pytest.mark.django_db
@pytest.mark.parametrize("converter_class", [TreeDriftConverter, FingerprintDriftConverter])
def test_prepare_rejects_current_converter_tree_or_fingerprint_drift(release_case, converter_class):
    """Release re-conversion must match both the persisted draft and accepted converter Evidence."""
    case = release_case()
    counts = (WorkflowPlanRevision.objects.count(), ValidationReport.objects.count())

    response = prepare(case, converter_class=converter_class)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert ReleaseManifest.objects.count() == 0
    assert (WorkflowPlanRevision.objects.count(), ValidationReport.objects.count()) == counts


@pytest.mark.django_db
def test_consistently_tampered_snapshot_artifact_and_report_still_fail_current_reconversion(release_case):
    """Three mutually consistent persisted hashes cannot replace a fresh converter result."""
    case = release_case()
    changed_tree = copy.deepcopy(RELEASE_PIPELINE_TREE)
    changed_tree["activities"]["A"]["name"] = "persisted-tamper"
    changed_hash = sha256_json(changed_tree)
    case.snapshot.data = changed_tree
    case.snapshot.save(update_fields=["data"])
    case.run.artifact_references[0]["pipeline_tree_hash"] = changed_hash
    case.run.save(update_fields=["artifact_references"])
    result = copy.deepcopy(case.validation_report.result)
    result["pipeline_tree_hash"] = changed_hash
    case.validation_report.result = result
    case.validation_report.save(update_fields=["result"])
    counts = (WorkflowPlanRevision.objects.count(), ValidationReport.objects.count())

    response = prepare(case)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert ReleaseManifest.objects.count() == 0
    assert (WorkflowPlanRevision.objects.count(), ValidationReport.objects.count()) == counts


@pytest.mark.django_db
def test_current_converter_validation_failure_is_stale_and_read_only(release_case):
    """A deterministic current-converter rejection invalidates release without writing validation state."""
    case = release_case()
    counts = (WorkflowPlanRevision.objects.count(), ValidationReport.objects.count())

    response = prepare(case, converter_class=ValidationFailureConverter)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert ReleaseManifest.objects.count() == 0
    assert (WorkflowPlanRevision.objects.count(), ValidationReport.objects.count()) == counts
    case.run.refresh_from_db()
    assert case.run.status == HarnessRunStatus.DRAFT_READY


@pytest.mark.django_db
def test_unknown_converter_failure_remains_retryable_infrastructure(release_case):
    """Unknown programming faults must not be mislabeled as deterministic validation drift."""
    case = release_case()

    response = prepare(case, converter_class=ProgrammingFailureConverter)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert ReleaseManifest.objects.count() == 0
    case.run.refresh_from_db()
    assert case.run.status == HarnessRunStatus.RELEASE_READY


@pytest.mark.django_db
@pytest.mark.parametrize(
    "terminal_reason,terminal_payload",
    [
        ("manual_completion", None),
        (
            "debug_completed",
            {"session_id": "placeholder", "status": DebugSessionStatus.COMPLETED},
        ),
        (
            "debug_completed",
            {
                "session_id": "placeholder",
                "status": DebugSessionStatus.COMPLETED,
                "reason": "wrong_reason",
            },
        ),
        (
            "debug_completed",
            {
                "session_id": "placeholder",
                "status": DebugSessionStatus.COMPLETED,
                "reason": "debug_completed",
                "extra": "not-authority",
            },
        ),
    ],
)
def test_prepare_requires_closed_debug_completion_reason_evidence(release_case, terminal_reason, terminal_payload):
    """Only the exact server terminal reason and three-field completion payload authorize release."""
    case = release_case(terminal_reason=terminal_reason, terminal_payload=terminal_payload)

    response = prepare(case)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "DEBUG_SESSION"
    assert ReleaseManifest.objects.count() == 0


@pytest.mark.django_db
def test_locked_run_lifecycle_drift_blocks_resolver_manifest_evidence_and_replay(release_case, mocker):
    """The authoritative post-lock state gate runs before freshness work or completed replay."""
    from bkflow.harness.services.release import prepare as prepare_module

    case = release_case()
    assert prepare(case)["ok"] is True
    case.resolver.calls.clear()
    evidence_count = EvidenceEvent.objects.count()

    def drift_after_lock(run):
        run.status = HarnessRunStatus.DEBUGGING
        run.save(update_fields=["status"])

    mocker.patch.object(prepare_module, "test_after_run_lock_hook", drift_after_lock, create=True)

    response = prepare(case)

    assert response["ok"] is False
    assert response["next_actions"] == ["get_debug_session"]
    assert case.resolver.calls == []
    assert ReleaseManifest.objects.count() == 1
    assert EvidenceEvent.objects.count() == evidence_count


@pytest.mark.django_db
def test_prepare_rejects_closed_schema_before_any_release_side_effect(release_case):
    """Caller identity and postconditions cannot be smuggled into the prepare request."""
    case = release_case()

    for payload in (
        {**case.request, "actor": case.context.actor},
        {**case.request, "postcondition_spec": POSTCONDITION_SPEC},
        {**case.request, "revision_id": 123},
        {**case.request, "expected_plan_hash": "bad"},
    ):
        response = prepare(SimpleNamespace(**{**vars(case), "request": payload}))
        assert response["ok"] is False
        assert response["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"

    assert ReleaseManifest.objects.count() == 0
    assert HarnessIdempotencyRecord.objects.filter(tool_name="prepare_release").count() == 0


@pytest.mark.django_db
def test_same_key_replay_revalidates_managed_draft_and_never_returns_stale_success(release_case):
    """A completed idempotency snapshot cannot outlive the managed draft identity it authorized."""
    case = release_case()
    assert prepare(case)["ok"] is True
    case.run.refresh_from_db()
    artifacts = copy.deepcopy(case.run.artifact_references)
    artifacts[0]["pipeline_tree_hash"] = "f" * 64
    case.run.artifact_references = artifacts
    case.run.save(update_fields=["artifact_references"])

    response = prepare(case)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert ReleaseManifest.objects.count() == 1
    assert EvidenceEvent.objects.filter(event_type="RELEASE_PREPARED", run=case.run).count() == 1
    case.run.refresh_from_db()
    assert case.run.status == HarnessRunStatus.DRAFT_READY


@pytest.mark.django_db
def test_prepare_rejects_superseded_revision_before_replaying_same_key(release_case):
    """A newer immutable revision invalidates an otherwise completed prepare response."""
    case = release_case()
    assert prepare(case)["ok"] is True
    WorkflowPlanRevision.objects.create(
        run=case.run,
        sequence=2,
        parent_revision=case.revision,
        intent_spec={"goal": "newer plan"},
        canonical_a2flow={"version": "2.0", "nodes": []},
        plan_hash="f" * 64,
    )

    response = prepare(case)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert ReleaseManifest.objects.count() == 1
    case.run.refresh_from_db()
    assert case.run.status == HarnessRunStatus.DRAFT_READY


@pytest.mark.django_db
def test_schema_drift_returns_summary_without_report_and_provider_outage_is_retryable(release_case):
    """Deterministic drift returns repair guidance without creating a new validation checkpoint."""
    drift = release_case()
    drift.resolver = ReleaseResolver(schema_hash="d" * 64)
    report_count = ValidationReport.objects.count()

    stale = prepare(drift)

    assert stale["ok"] is False
    assert stale["errors"][0]["code"] == "VALIDATION_STALE"
    assert ValidationReport.objects.count() == report_count
    assert ValidationReport.objects.filter(run=drift.run, checkpoint="PREPARE_RELEASE").count() == 0
    drift.run.refresh_from_db()
    assert drift.run.status == HarnessRunStatus.DRAFT_READY
    assert ReleaseManifest.objects.count() == 0


@pytest.mark.django_db
def test_prepare_rejects_same_idempotency_key_with_different_payload(release_case):
    """A completed key cannot be reused for another immutable plan payload."""
    case = release_case()
    assert prepare(case)["ok"] is True
    conflicting_request = {**case.request, "expected_plan_hash": "f" * 64}

    response = prepare(SimpleNamespace(**{**vars(case), "request": conflicting_request}))

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "IDEMPOTENCY_CONFLICT"
    assert ReleaseManifest.objects.count() == 1


@pytest.mark.django_db
def test_prepare_rejects_trusted_context_ownership_mismatch(release_case):
    """Trusted actor, application, scope and environment must still own the run."""
    case = release_case()
    forged = SimpleNamespace(**{**vars(case), "context": trusted_context(actor="another-user")})

    response = prepare(forged)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "CAPABILITY_FORBIDDEN"
    assert ReleaseManifest.objects.count() == 0
    assert HarnessIdempotencyRecord.objects.filter(tool_name="prepare_release").count() == 0


@pytest.mark.django_db
def test_provider_outage_keeps_release_ready_and_does_not_persist_semantic_failure(release_case):
    """Catalog uncertainty is retryable and cannot be recorded as a workflow defect."""
    case = release_case()
    case.resolver = UnavailableResolver()

    response = prepare(case)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    case.run.refresh_from_db()
    assert case.run.status == HarnessRunStatus.RELEASE_READY
    assert ValidationReport.objects.filter(run=case.run, checkpoint="PREPARE_RELEASE").count() == 0
    assert HarnessIdempotencyRecord.objects.get(tool_name="prepare_release").status == "FAILED"
    assert ReleaseManifest.objects.count() == 0


@pytest.mark.django_db
def test_unconfigured_postcondition_policy_fails_closed_without_manifest(release_case):
    """Request text cannot substitute for a server-owned versioned postcondition policy."""
    from bkflow.harness.services.release.policy import ReleasePolicy

    case = release_case()
    response = prepare(case, release_policy=ReleasePolicy(profiles={}))

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "RELEASE_POLICY_UNAVAILABLE"
    assert ReleaseManifest.objects.count() == 0
    assert ApprovalRequest.objects.count() == 0


@pytest.mark.django_db
def test_database_failure_rolls_back_manifest_status_and_release_evidence(release_case, mocker):
    """Pure database preparation retries from a failed idempotency row without partial authority."""
    case = release_case()
    mocker.patch(
        "bkflow.harness.services.release.prepare.record_evidence",
        side_effect=DatabaseError("unsafe raw database detail"),
    )

    response = prepare(case)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert "unsafe raw database detail" not in str(response)
    assert ReleaseManifest.objects.count() == 0
    assert ApprovalRequest.objects.count() == 0
    assert EvidenceEvent.objects.filter(event_type="RELEASE_PREPARED", run=case.run).count() == 0
    case.run.refresh_from_db()
    assert case.run.status == HarnessRunStatus.RELEASE_READY
    assert HarnessIdempotencyRecord.objects.get(tool_name="prepare_release").status == "FAILED"
