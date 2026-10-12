"""Approval-bound, idempotent Harness workflow publication contracts."""

import copy
import hashlib
from types import SimpleNamespace

import pytest
from django.db import DatabaseError, connection
from django.utils import timezone

from bkflow.harness.constants import HarnessAction, HarnessRunStatus
from bkflow.harness.models import (
    ApprovalRequest,
    EvidenceEvent,
    HarnessIdempotencyRecord,
    ReleaseManifest,
    ReleasePublication,
)
from bkflow.harness.services.approval import (
    ApprovalDecision,
    ApprovalVerifier,
    InMemoryApprovalReplayGuard,
)
from bkflow.harness.services.canonical import sha256_json
from bkflow.harness.services.release.policy import ActionDecision
from bkflow.space.configs import FlowVersioning, SpaceConfigValueType
from bkflow.space.models import SpaceConfig
from bkflow.template.models import TemplateOperationRecord, TemplateSnapshot
from bkflow.template.services.release import TemplateReleaseService
from tests.interface.harness.release import (
    test_prepare_release as prepare_release_cases,
)

POSTCONDITION_SPEC = prepare_release_cases.POSTCONDITION_SPEC
ReleaseConverter = prepare_release_cases.ReleaseConverter

RECEIPT_REF = "approval://bkaidev/publish-receipt"


class ReceiptBackend:
    """Return one closed approval response and record the transaction boundary."""

    def __init__(self, claims, *, allowed=True):
        self.claims = copy.deepcopy(claims)
        self.allowed = allowed
        self.transaction_states = []

    def verify(self, receipt_ref):
        self.transaction_states.append(connection.in_atomic_block)
        return {
            "allowed": self.allowed,
            "provider": "bkaidev",
            "receipt_ref": receipt_ref,
            "claims": copy.deepcopy(self.claims),
            "expires_at": timezone.now() + timezone.timedelta(minutes=5),
            "revoked": False,
            "reason": "approved" if self.allowed else "rejected",
            "verifier_version": "bkaidev-v1",
        }


class NoApprovalActionPolicy:
    """Server-injected low-risk policy used to cover the ungated branch."""

    def requirements_for(self, actions, policy_version):
        return []

    def evaluate(self, *, action, manifest_hash, plan_hash, target_resource, normalized_params, policy_version):
        return ActionDecision(
            action=action,
            risk_level="L1",
            requires_approval=False,
            action_digest=sha256_json(
                {
                    "action": action,
                    "manifest_hash": manifest_hash,
                    "normalized_params": normalized_params,
                    "plan_hash": plan_hash,
                    "policy_version": policy_version,
                    "target_resource": target_resource,
                }
            ),
            policy_version=policy_version,
        )


class ForgedDecisionVerifier:
    """Return a structurally plausible decision that is not bound to the receipt."""

    def __init__(self, expected):
        self.expected = expected

    def verify(self, receipt_ref, expected_claims):
        return ApprovalDecision(
            allowed=True,
            provider="bkaidev",
            receipt_digest="f" * 64,
            claims_digest=sha256_json(self.expected),
            reason="approved",
            verifier_version="bkaidev-v1",
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
        )


@pytest.fixture
def release_case_builder(db):
    """Reuse the Task 5 scenario builder without shadowing an imported fixture."""
    return prepare_release_cases.release_case.__wrapped__(db)


@pytest.fixture
def publish_case(release_case_builder):
    """Prepare one exact release Manifest while leaving its draft unpublished."""
    from bkflow.harness.services.release.policy import ReleasePolicy
    from bkflow.harness.services.release.prepare import (
        prepare_release,
        validate_prepare_request,
    )

    case = release_case_builder()
    SpaceConfig.objects.update_or_create(
        space_id=case.context.space_id,
        name=FlowVersioning.name,
        defaults={"value_type": SpaceConfigValueType.TEXT.value, "text_value": "true"},
    )
    response = prepare_release(
        case.context,
        validate_prepare_request(case.request),
        resolver=case.resolver,
        release_policy=ReleasePolicy(profiles={case.context.policy_version: POSTCONDITION_SPEC}),
        converter_class=ReleaseConverter,
    )
    assert response["ok"] is True
    case.run.refresh_from_db()
    manifest = ReleaseManifest.objects.get(run=case.run)
    request = {
        "run_id": str(case.run.run_id),
        "manifest_id": str(manifest.id),
        "manifest_hash": manifest.manifest_hash,
        "version": "1.0.0",
        "description": "Harness publication",
        "idempotency_key": "publish-workflow-1",
    }
    return SimpleNamespace(**vars(case), manifest=manifest, publish_request=request)


def publish(case, payload=None, **kwargs):
    """Call the public Harness publication boundary with explicit local dependencies."""
    from bkflow.harness.services.release.policy import ReleasePolicy
    from bkflow.harness.services.release.publish import publish_workflow_with_context

    values = {
        "resolver": case.resolver,
        "release_policy": ReleasePolicy(profiles={case.context.policy_version: POSTCONDITION_SPEC}),
        "converter_class": ReleaseConverter,
    }
    values.update(kwargs)
    return publish_workflow_with_context(case.context, payload or case.publish_request, **values)


def expected_claims(case, approval):
    """Build the literal closed authority required from the approval provider."""
    return {
        "actor": case.context.actor,
        "platform_app": case.context.platform_app,
        "space_id": case.context.space_id,
        "scope": case.run.scope,
        "environment": case.context.target_environment,
        "plan_hash": case.manifest.plan_hash,
        "action": HarnessAction.PUBLISH_WORKFLOW,
        "action_digest": approval.action_digest,
    }


@pytest.mark.django_db
def test_first_publish_call_creates_one_pending_approval_without_release_side_effects(publish_case):
    """The first gated call returns an opaque approval handle and never publishes the draft."""
    case = publish_case

    response = publish(case)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "APPROVAL_REQUIRED"
    approval = ApprovalRequest.objects.get()
    assert response["approval_request_id"] == str(approval.id)
    assert approval.action == HarnessAction.PUBLISH_WORKFLOW
    assert approval.status == ApprovalRequest.Status.PENDING
    assert approval.expires_at is None
    assert approval.verifier_version is None
    assert ReleasePublication.objects.count() == 0
    assert TemplateOperationRecord.objects.filter(instance_id=case.template.id, operate_type="release").count() == 0
    case.snapshot.refresh_from_db()
    assert case.snapshot.draft is True
    assert HarnessIdempotencyRecord.objects.filter(tool_name=HarnessAction.PUBLISH_WORKFLOW).count() == 0


@pytest.mark.django_db(transaction=True)
def test_verified_second_call_publishes_exact_snapshot_and_replays_without_secret(publish_case):
    """A verified second call atomically anchors one publication and safely replays it."""
    case = publish_case
    first = publish(case)
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    backend = ReceiptBackend(expected_claims(case, approval))
    verifier = ApprovalVerifier(backend=backend, replay_guard=InMemoryApprovalReplayGuard())
    payload = {
        **case.publish_request,
        "approval_request_id": str(approval.id),
        "approval_receipt_ref": RECEIPT_REF,
    }

    response = publish(case, payload, approval_verifier=verifier)
    replay = publish(case, payload, approval_verifier=verifier)

    assert response == replay
    assert response["ok"] is True
    assert response["status"] == HarnessRunStatus.PUBLISHED
    assert RECEIPT_REF not in repr(response)
    publication = ReleasePublication.objects.get(manifest=case.manifest)
    assert publication.published_snapshot_id == case.snapshot.id
    assert publication.published_version == "1.0.0"
    assert len(response["artifact_refs"]) == 1
    assert response["artifact_refs"][0]["publication_hash"] == publication.publication_hash
    assert TemplateSnapshot.objects.filter(template_id=case.template.id).count() == 1
    assert EvidenceEvent.objects.filter(run=case.run, event_type="WORKFLOW_PUBLISHED").count() == 1
    assert TemplateOperationRecord.objects.filter(instance_id=case.template.id, operate_type="release").count() == 1
    approval.refresh_from_db()
    assert approval.status == ApprovalRequest.Status.VERIFIED
    assert approval.expires_at is not None
    assert approval.verifier_version == "bkaidev-v1"
    assert backend.transaction_states == [False]
    assert approval.receipt_ref == RECEIPT_REF
    assert approval.receipt_digest == hashlib.sha256(RECEIPT_REF.encode("utf-8")).hexdigest()
    assert RECEIPT_REF not in repr(EvidenceEvent.objects.filter(run=case.run).values())
    assert RECEIPT_REF not in repr(
        HarnessIdempotencyRecord.objects.get(tool_name=HarnessAction.PUBLISH_WORKFLOW).response_snapshot
    )


@pytest.mark.django_db
def test_receipt_without_verifier_or_durable_guard_fails_closed(publish_case):
    """Receipt text cannot authorize publication without both verifier backend and durable replay guard."""
    case = publish_case
    first = publish(case)
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    payload = {
        **case.publish_request,
        "approval_request_id": str(approval.id),
        "approval_receipt_ref": RECEIPT_REF,
    }

    missing = publish(case, payload)
    no_guard = publish(
        case,
        payload,
        approval_verifier=ApprovalVerifier(backend=ReceiptBackend(expected_claims(case, approval))),
    )

    assert missing["ok"] is False
    assert missing["errors"][0]["code"] == "APPROVAL_REQUIRED"
    assert no_guard["ok"] is False
    assert no_guard["errors"][0]["code"] == "APPROVAL_INVALID"
    assert ReleasePublication.objects.count() == 0


@pytest.mark.django_db
def test_custom_verifier_decision_is_rebound_to_the_exact_receipt(publish_case):
    """Dependency injection cannot bypass receipt-digest normalization at the facade boundary."""
    case = publish_case
    first = publish(case)
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    payload = {
        **case.publish_request,
        "approval_request_id": str(approval.id),
        "approval_receipt_ref": RECEIPT_REF,
    }

    response = publish(
        case,
        payload,
        approval_verifier=ForgedDecisionVerifier(expected_claims(case, approval)),
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "APPROVAL_INVALID"
    approval.refresh_from_db()
    assert approval.status == ApprovalRequest.Status.PENDING
    assert ReleasePublication.objects.count() == 0


@pytest.mark.django_db
def test_publish_request_is_closed_and_harness_cannot_force_release(publish_case):
    """Caller authority, force, and lone approval fields are rejected before any side effect."""
    case = publish_case

    for payload in (
        {**case.publish_request, "force": True},
        {**case.publish_request, "actor": case.context.actor},
        {**case.publish_request, "approval_request_id": "not-a-uuid"},
        {**case.publish_request, "approval_receipt_ref": RECEIPT_REF},
    ):
        response = publish(case, payload)
        assert response["ok"] is False
        assert response["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"

    assert ApprovalRequest.objects.count() == 0
    assert ReleasePublication.objects.count() == 0


@pytest.mark.django_db
def test_stale_draft_revokes_pending_approval_and_returns_run_to_draft_ready(publish_case):
    """A converter-visible draft drift invalidates both release readiness and pending approval authority."""
    case = publish_case
    first = publish(case)
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    changed = copy.deepcopy(case.snapshot.data)
    changed["activities"]["A"]["name"] = "tampered"
    changed_hash = sha256_json(changed)
    case.snapshot.data = changed
    case.snapshot.save(update_fields=["data"])
    artifacts = copy.deepcopy(case.run.artifact_references)
    artifacts[0]["pipeline_tree_hash"] = changed_hash
    case.run.artifact_references = artifacts
    case.run.save(update_fields=["artifact_references"])
    result = copy.deepcopy(case.validation_report.result)
    result["pipeline_tree_hash"] = changed_hash
    case.validation_report.result = result
    case.validation_report.save(update_fields=["result"])

    response = publish(case)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    approval.refresh_from_db()
    assert approval.status == ApprovalRequest.Status.REVOKED
    case.run.refresh_from_db()
    assert case.run.status == HarnessRunStatus.DRAFT_READY
    assert ReleasePublication.objects.count() == 0


@pytest.mark.django_db
def test_server_policy_drift_revokes_existing_publish_authority(publish_case):
    """A changed server-owned release policy invalidates its Manifest and pending approval."""
    from bkflow.harness.services.release.policy import ReleasePolicy

    case = publish_case
    first = publish(case)
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    drifted_postconditions = copy.deepcopy(POSTCONDITION_SPEC)
    drifted_postconditions["predicates"].append({"type": "OUTPUT_EXISTS", "node_id": "A", "output_key": "new_result"})

    response = publish(
        case,
        release_policy=ReleasePolicy(profiles={case.context.policy_version: drifted_postconditions}),
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    approval.refresh_from_db()
    case.run.refresh_from_db()
    assert approval.status == ApprovalRequest.Status.REVOKED
    assert case.run.status == HarnessRunStatus.DRAFT_READY


@pytest.mark.django_db
def test_caller_manifest_hash_mismatch_cannot_invalidate_existing_authority(publish_case):
    """An untrusted hash mismatch is rejected without revoking valid server-side state."""
    case = publish_case
    first = publish(case)
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])

    response = publish(case, {**case.publish_request, "manifest_hash": "0" * 64})

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    approval.refresh_from_db()
    case.run.refresh_from_db()
    assert approval.status == ApprovalRequest.Status.PENDING
    assert case.run.status == HarnessRunStatus.APPROVAL_PENDING


@pytest.mark.django_db
def test_multiple_live_drafts_invalidate_manifest_bound_publish_authority(publish_case):
    """A second draft is drift, never an arbitrary choice by the publish domain service."""
    case = publish_case
    first = publish(case)
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    TemplateSnapshot.objects.create(
        template_id=case.template.id,
        draft=True,
        data={"id": "ambiguous-draft"},
        md5sum="d" * 32,
    )

    response = publish(case)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    approval.refresh_from_db()
    case.run.refresh_from_db()
    assert approval.status == ApprovalRequest.Status.REVOKED
    assert case.run.status == HarnessRunStatus.DRAFT_READY


@pytest.mark.django_db
def test_wrong_action_approval_cannot_authorize_publish(publish_case):
    """An approval ID for start execution never authorizes the publish action."""
    case = publish_case
    first = publish(case)
    publish_approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    start_approval = ApprovalRequest.objects.create(
        manifest=case.manifest,
        run=case.run,
        revision=case.revision,
        plan_hash=case.manifest.plan_hash,
        action=HarnessAction.START_WORKFLOW_EXECUTION,
        action_digest="f" * 64,
        platform=case.run.platform,
        platform_app=case.run.platform_app,
        actor=case.run.actor,
        space_id=case.run.space_id,
        scope=case.run.scope,
        target_environment=case.run.environment,
        policy_version=case.run.policy_version,
        risk_level="L2",
        risk_summary={"action": HarnessAction.START_WORKFLOW_EXECUTION},
    )
    payload = {
        **case.publish_request,
        "approval_request_id": str(start_approval.id),
        "approval_receipt_ref": RECEIPT_REF,
    }

    response = publish(case, payload)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "APPROVAL_INVALID"
    assert publish_approval.status == ApprovalRequest.Status.PENDING
    assert ReleasePublication.objects.count() == 0


@pytest.mark.django_db
def test_publish_flag_and_trusted_identity_fail_closed(publish_case):
    """Disabled publication or a foreign trusted actor cannot inspect or publish a Manifest."""
    from tests.interface.harness.release.test_prepare_release import trusted_context

    case = publish_case
    SpaceConfig.objects.filter(space_id=case.context.space_id, name="harness_publish_enabled").update(
        text_value="false"
    )
    disabled = publish(case)
    SpaceConfig.objects.filter(space_id=case.context.space_id, name="harness_publish_enabled").update(text_value="true")
    foreign_case = SimpleNamespace(**{**vars(case), "context": trusted_context(actor="other-user")})
    foreign = publish(foreign_case)

    assert disabled["ok"] is False
    assert disabled["errors"][0]["code"] == "HARNESS_TOOL_UNAVAILABLE"
    assert foreign["ok"] is False
    assert foreign["errors"][0]["code"] == "CAPABILITY_FORBIDDEN"
    assert ApprovalRequest.objects.count() == 0


@pytest.mark.django_db
def test_version_collision_after_approval_does_not_publish(publish_case):
    """The domain lock rechecks a version collision after an approval handle was issued."""
    case = publish_case
    first = publish(case)
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    TemplateSnapshot.objects.create(
        template_id=case.template.id,
        draft=False,
        version="1.0.0",
        data={"id": "other"},
        md5sum="d" * 32,
    )
    backend = ReceiptBackend(expected_claims(case, approval))
    payload = {
        **case.publish_request,
        "approval_request_id": str(approval.id),
        "approval_receipt_ref": RECEIPT_REF,
    }

    response = publish(
        case,
        payload,
        approval_verifier=ApprovalVerifier(backend=backend, replay_guard=InMemoryApprovalReplayGuard()),
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VERSION_CONFLICT"
    case.snapshot.refresh_from_db()
    case.run.refresh_from_db()
    approval.refresh_from_db()
    assert case.snapshot.draft is True
    assert case.run.status == HarnessRunStatus.APPROVAL_PENDING
    assert approval.status == ApprovalRequest.Status.VERIFIED
    assert ReleasePublication.objects.count() == 0


@pytest.mark.django_db
def test_invalid_version_does_not_invalidate_verified_action_authority(publish_case):
    """A version-format error blocks release but does not misclassify the Manifest as drifted."""
    case = publish_case
    invalid_request = {**case.publish_request, "version": "not-semver"}
    first = publish(case, invalid_request)
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    backend = ReceiptBackend(expected_claims(case, approval))
    payload = {
        **invalid_request,
        "approval_request_id": str(approval.id),
        "approval_receipt_ref": RECEIPT_REF,
    }

    response = publish(
        case,
        payload,
        approval_verifier=ApprovalVerifier(backend=backend, replay_guard=InMemoryApprovalReplayGuard()),
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    case.run.refresh_from_db()
    approval.refresh_from_db()
    assert case.run.status == HarnessRunStatus.APPROVAL_PENDING
    assert approval.status == ApprovalRequest.Status.VERIFIED
    assert ReleasePublication.objects.count() == 0


@pytest.mark.django_db
def test_ungated_policy_publishes_directly_and_same_key_changed_payload_conflicts(release_case_builder):
    """A server-owned low-risk policy skips approval while preserving payload idempotency."""
    from bkflow.harness.services.release.policy import ReleasePolicy
    from bkflow.harness.services.release.prepare import (
        prepare_release,
        validate_prepare_request,
    )

    case = release_case_builder()
    policy = NoApprovalActionPolicy()
    release_policy = ReleasePolicy(profiles={case.context.policy_version: POSTCONDITION_SPEC})
    SpaceConfig.objects.update_or_create(
        space_id=case.context.space_id,
        name=FlowVersioning.name,
        defaults={"value_type": SpaceConfigValueType.TEXT.value, "text_value": "true"},
    )
    prepare_release(
        case.context,
        validate_prepare_request(case.request),
        resolver=case.resolver,
        release_policy=release_policy,
        action_policy=policy,
        converter_class=ReleaseConverter,
    )
    case.run.refresh_from_db()
    manifest = ReleaseManifest.objects.get(run=case.run)
    request = {
        "run_id": str(case.run.run_id),
        "manifest_id": str(manifest.id),
        "manifest_hash": manifest.manifest_hash,
        "version": "1.0.0",
        "description": "Ungated publication",
        "idempotency_key": "publish-ungated-1",
    }

    response = publish(
        SimpleNamespace(**vars(case), manifest=manifest, publish_request=request),
        action_policy=policy,
    )
    conflict = publish(
        SimpleNamespace(**vars(case), manifest=manifest, publish_request=request),
        {**request, "description": "Different exact action"},
        action_policy=policy,
    )

    assert response["ok"] is True
    assert conflict["ok"] is False
    assert conflict["errors"][0]["code"] == "IDEMPOTENCY_CONFLICT"
    assert ApprovalRequest.objects.count() == 0
    assert ReleasePublication.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_crash_before_publication_anchor_preserves_verified_receipt_for_retry(publish_case, monkeypatch):
    """The short approval commit survives while every publication fact rolls back and retries locally."""
    case = publish_case
    first = publish(case)
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    backend = ReceiptBackend(expected_claims(case, approval))
    payload = {
        **case.publish_request,
        "approval_request_id": str(approval.id),
        "approval_receipt_ref": RECEIPT_REF,
    }

    def crash_before_anchor(**kwargs):
        raise DatabaseError("injected publication anchor failure")

    verifier = ApprovalVerifier(backend=backend, replay_guard=InMemoryApprovalReplayGuard())
    with monkeypatch.context() as patcher:
        patcher.setattr(ReleasePublication.objects, "create", crash_before_anchor)
        response = publish(case, payload, approval_verifier=verifier)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    case.snapshot.refresh_from_db()
    case.run.refresh_from_db()
    approval.refresh_from_db()
    assert case.snapshot.draft is True
    assert case.run.status == HarnessRunStatus.APPROVAL_PENDING
    assert approval.status == ApprovalRequest.Status.VERIFIED
    assert TemplateOperationRecord.objects.filter(instance_id=case.template.id, operate_type="release").count() == 0
    assert EvidenceEvent.objects.filter(run=case.run, event_type="WORKFLOW_PUBLISHED").count() == 0
    assert HarnessIdempotencyRecord.objects.filter(tool_name=HarnessAction.PUBLISH_WORKFLOW).count() == 0

    retry = publish(case, payload, approval_verifier=verifier)

    assert retry["ok"] is True
    assert backend.transaction_states == [False]
    assert ReleasePublication.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_response_loss_reconciles_only_exact_manifest_bound_published_snapshot(publish_case):
    """A matching former draft can be anchored after service response loss without a second release."""
    case = publish_case
    first = publish(case)
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    TemplateReleaseService.release(
        case.template,
        {"version": "1.0.0", "desc": "Harness publication", "force": False},
        case.context.actor,
        "api",
        emit_webhook=False,
        expected_draft_snapshot_id=case.snapshot.id,
    )
    case.run.status = HarnessRunStatus.PUBLISHING
    case.run.save(update_fields=["status"])
    backend = ReceiptBackend(expected_claims(case, approval))
    payload = {
        **case.publish_request,
        "approval_request_id": str(approval.id),
        "approval_receipt_ref": RECEIPT_REF,
    }

    response = publish(
        case,
        payload,
        approval_verifier=ApprovalVerifier(backend=backend, replay_guard=InMemoryApprovalReplayGuard()),
    )

    assert response["ok"] is True
    publication = ReleasePublication.objects.get()
    assert publication.published_snapshot_id == case.manifest.draft_snapshot_id
    assert TemplateOperationRecord.objects.filter(instance_id=case.template.id, operate_type="release").count() == 1
    assert EvidenceEvent.objects.filter(run=case.run, event_type="WORKFLOW_PUBLISHED").count() == 1


@pytest.mark.django_db(transaction=True)
def test_response_loss_rejects_non_exact_published_snapshot(publish_case):
    """Published-looking state is not enough when the exact operator fact differs."""
    case = publish_case
    first = publish(case)
    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    case.snapshot.draft = False
    case.snapshot.version = "1.0.0"
    case.snapshot.operator = "different-operator"
    case.snapshot.save(update_fields=["draft", "version", "operator"])
    case.run.status = HarnessRunStatus.PUBLISHING
    case.run.save(update_fields=["status"])
    backend = ReceiptBackend(expected_claims(case, approval))
    payload = {
        **case.publish_request,
        "approval_request_id": str(approval.id),
        "approval_receipt_ref": RECEIPT_REF,
    }

    response = publish(
        case,
        payload,
        approval_verifier=ApprovalVerifier(backend=backend, replay_guard=InMemoryApprovalReplayGuard()),
    )

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "VALIDATION_STALE"
    assert ReleasePublication.objects.count() == 0
