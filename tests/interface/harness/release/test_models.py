"""Persistence contracts for P3 release aggregates."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from bkflow.harness import models as harness_models
from bkflow.harness.constants import HarnessAction, HarnessRunStatus, RiskLevel
from bkflow.harness.services.canonical import canonical_scope


@pytest.fixture
def release_graph(db):
    """Persist the trusted run and revision used by release model tests."""
    run = harness_models.HarnessRun.objects.create(
        platform="bkaidev",
        platform_app="trusted-app",
        actor="dannydeng",
        space_id=903,
        scope=canonical_scope("project", "903"),
        environment="stag",
        status=HarnessRunStatus.RELEASE_READY,
        policy_version="risk-2026.09",
        mcp_contract_version="1.3.0",
    )
    revision = harness_models.WorkflowPlanRevision.objects.create(
        run=run,
        sequence=1,
        intent_spec={"goal": "restart service"},
        canonical_a2flow={"version": "2.0", "nodes": []},
        plan_hash="a" * 64,
    )
    return run, revision


def manifest_values(run, revision, **overrides):
    """Build one complete release manifest payload."""
    values = {
        "run": run,
        "revision": revision,
        "plan_hash": revision.plan_hash,
        "draft_template_id": 42,
        "draft_snapshot_id": 84,
        "draft_tree_fingerprint": {"sha256": "b" * 64, "node_count": 1},
        "capability_snapshot": [],
        "validation_evidence_refs": ["evidence://validation/report-1"],
        "debug_evidence_refs": ["evidence://debug/session-1"],
        "postcondition_spec": {"kind": "task_state", "expected": "FINISHED"},
        "risk_manifest": {"highest": RiskLevel.L2},
        "required_approvals": [
            {
                "action": HarnessAction.PUBLISH_WORKFLOW,
                "risk_level": RiskLevel.L2,
                "policy_ref": "policy://release/publish-l2",
            },
            {
                "action": HarnessAction.START_WORKFLOW_EXECUTION,
                "risk_level": RiskLevel.L2,
                "policy_ref": "policy://execution/start-l2",
            },
        ],
        "policy_version": run.policy_version,
        "target_environment": run.environment,
    }
    values.update(overrides)
    return values


def approval_values(manifest, **overrides):
    """Build one pending action-bound approval request."""
    requested_at = timezone.now()
    values = {
        "manifest": manifest,
        "run": manifest.run,
        "revision": manifest.revision,
        "plan_hash": manifest.plan_hash,
        "action": HarnessAction.PUBLISH_WORKFLOW,
        "action_digest": "d" * 64,
        "platform": manifest.run.platform,
        "platform_app": manifest.run.platform_app,
        "actor": manifest.run.actor,
        "space_id": manifest.run.space_id,
        "scope": manifest.run.scope,
        "target_environment": manifest.target_environment,
        "policy_version": manifest.policy_version,
        "risk_level": RiskLevel.L2,
        "risk_summary": {"reasons": ["publish writes a version"]},
        "status": harness_models.ApprovalRequest.Status.PENDING,
        "requested_at": requested_at,
        "expires_at": None,
        "verifier_version": None,
    }
    values.update(overrides)
    return values


@pytest.mark.django_db
def test_manifest_hash_excludes_generated_approval_ids_and_is_append_only(release_graph):
    """Hash normalized requirements before ApprovalRequest rows exist and retain the immutable result."""
    run, revision = release_graph
    first = harness_models.ReleaseManifest.objects.create(**manifest_values(run, revision))
    second = harness_models.ReleaseManifest(**manifest_values(run, revision))
    second.full_clean(validate_unique=False)

    assert len(first.manifest_hash) == 64
    assert second.manifest_hash == first.manifest_hash
    assert all("id" not in requirement for requirement in first.required_approvals)
    first.policy_version = "forged-policy"
    with pytest.raises(ValidationError):
        first.save()
    with pytest.raises(ValidationError):
        harness_models.ReleaseManifest.objects.filter(pk=first.pk).update(policy_version="forged")
    with pytest.raises(ValidationError):
        first.delete()
    with pytest.raises(ValidationError):
        first.hard_delete()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "overrides",
    [
        {"plan_hash": "not-a-hash"},
        {"draft_template_id": 0},
        {"policy_version": "token=raw-secret"},
        {"target_environment": ""},
        {"required_approvals": [{"id": "approval-1", "action": HarnessAction.PUBLISH_WORKFLOW}]},
        {"validation_evidence_refs": ["https://credential.example.test/report"]},
        {"postcondition_spec": {"token": "raw-secret"}},
    ],
)
def test_manifest_rejects_unbound_hash_approval_id_secret_or_unsafe_reference(release_graph, overrides):
    """A direct ORM insert cannot widen or poison immutable release authority."""
    run, revision = release_graph
    with pytest.raises(ValidationError):
        harness_models.ReleaseManifest.objects.create(**manifest_values(run, revision, **overrides))


@pytest.mark.django_db
def test_approval_binds_manifest_without_hash_cycle_and_verifies_once(release_graph):
    """A receipt can verify one manifest action but cannot rewrite its authority facts."""
    run, revision = release_graph
    manifest = harness_models.ReleaseManifest.objects.create(**manifest_values(run, revision))
    approval = harness_models.ApprovalRequest.objects.create(**approval_values(manifest))

    assert approval.manifest_id == manifest.id
    assert approval.active_approval_key
    approval.status = approval.Status.VERIFIED
    approval.approver = "release-reviewer"
    approval.receipt_provider = "bkaidev"
    approval.receipt_ref = "approval://receipt/release-1"
    approval.receipt_digest = "e" * 64
    approval.verified_at = timezone.now()
    approval.expires_at = timezone.now() + timezone.timedelta(minutes=10)
    approval.verifier_version = "approval-v1"
    approval.save(
        update_fields=[
            "status",
            "approver",
            "receipt_provider",
            "receipt_ref",
            "receipt_digest",
            "verified_at",
            "expires_at",
            "verifier_version",
            "active_approval_key",
        ]
    )
    approval.action_digest = "f" * 64
    with pytest.raises(ValidationError):
        approval.save(update_fields=["action_digest"])

    approval.refresh_from_db()
    approval.receipt_ref = "approval://receipt/forged"
    with pytest.raises(ValidationError):
        approval.save(update_fields=["receipt_ref"])

    approval.refresh_from_db()
    approval.status = approval.Status.REVOKED
    approval.save(update_fields=["status", "active_approval_key"])
    assert approval.active_approval_key is None
    approval.status = approval.Status.VERIFIED
    with pytest.raises(ValidationError):
        approval.save(update_fields=["status", "active_approval_key"])

    rejected = harness_models.ApprovalRequest.objects.create(**approval_values(manifest, action_digest="f" * 64))
    rejected.status = rejected.Status.REJECTED
    rejected.receipt_ref = "token=raw-secret"
    with pytest.raises(ValidationError):
        rejected.save(update_fields=["status", "receipt_ref", "active_approval_key"])


@pytest.mark.django_db
def test_approval_expiry_and_verifier_are_set_once_only_while_verifying(release_graph):
    """Verifier metadata is filled by PENDING-to-VERIFIED and cannot be prefilled or rewritten."""
    run, revision = release_graph
    manifest = harness_models.ReleaseManifest.objects.create(**manifest_values(run, revision))
    approval = harness_models.ApprovalRequest.objects.create(**approval_values(manifest))

    approval.expires_at = timezone.now() + timezone.timedelta(minutes=5)
    with pytest.raises(ValidationError):
        approval.save(update_fields=["expires_at"])

    approval.refresh_from_db()
    approval.status = approval.Status.VERIFIED
    approval.approver = "release-reviewer"
    approval.receipt_provider = "bkaidev"
    approval.receipt_ref = "approval://receipt/set-once"
    approval.receipt_digest = "e" * 64
    approval.verified_at = timezone.now()
    approval.expires_at = timezone.now() + timezone.timedelta(minutes=5)
    approval.verifier_version = "approval-v1"
    approval.save(
        update_fields=[
            "status",
            "approver",
            "receipt_provider",
            "receipt_ref",
            "receipt_digest",
            "verified_at",
            "expires_at",
            "verifier_version",
            "active_approval_key",
        ]
    )

    approval.expires_at += timezone.timedelta(minutes=1)
    approval.verifier_version = "approval-v2"
    with pytest.raises(ValidationError):
        approval.save(update_fields=["expires_at", "verifier_version"])


@pytest.mark.django_db
@pytest.mark.parametrize("missing_field", ["expires_at", "verifier_version"])
def test_verified_approval_requires_both_set_once_verifier_lifecycle_fields(release_graph, missing_field):
    """PENDING-to-VERIFIED cannot persist only half of the verifier lifecycle authority."""
    run, revision = release_graph
    manifest = harness_models.ReleaseManifest.objects.create(**manifest_values(run, revision))
    approval = harness_models.ApprovalRequest.objects.create(**approval_values(manifest))
    approval.status = approval.Status.VERIFIED
    approval.approver = "release-reviewer"
    approval.receipt_provider = "bkaidev"
    approval.receipt_ref = "approval://receipt/lifecycle-pair"
    approval.receipt_digest = "e" * 64
    approval.verified_at = timezone.now()
    approval.expires_at = timezone.now() + timezone.timedelta(minutes=5)
    approval.verifier_version = "approval-v1"
    setattr(approval, missing_field, None)

    with pytest.raises(ValidationError):
        approval.save(
            update_fields=[
                "status",
                "approver",
                "receipt_provider",
                "receipt_ref",
                "receipt_digest",
                "verified_at",
                "expires_at",
                "verifier_version",
                "active_approval_key",
            ]
        )


@pytest.mark.django_db
def test_only_one_live_approval_exists_for_the_same_manifest_action_digest(release_graph):
    """Use a nullable portable unique key instead of a conditional unique index."""
    run, revision = release_graph
    manifest = harness_models.ReleaseManifest.objects.create(**manifest_values(run, revision))
    harness_models.ApprovalRequest.objects.create(**approval_values(manifest))
    with pytest.raises((ValidationError, IntegrityError)), transaction.atomic():
        harness_models.ApprovalRequest.objects.create(**approval_values(manifest))


@pytest.mark.django_db
def test_publication_is_one_append_only_response_loss_anchor(release_graph):
    """Persist the exact published snapshot independently from a later start request."""
    run, revision = release_graph
    manifest = harness_models.ReleaseManifest.objects.create(**manifest_values(run, revision))
    with pytest.raises(ValidationError):
        harness_models.ReleasePublication.objects.create(
            manifest=manifest,
            published_template_id=0,
            published_snapshot_id=85,
            published_version="2026.09.05.0",
            publish_idempotency_ref="idempotency://publish/invalid-coordinate",
            published_at=timezone.now(),
        )
    publication = harness_models.ReleasePublication.objects.create(
        manifest=manifest,
        published_template_id=42,
        published_snapshot_id=85,
        published_version="2026.09.05.1",
        publish_idempotency_ref="idempotency://publish/release-1",
        published_at=timezone.now(),
    )
    assert publication.manifest_id == manifest.id
    with pytest.raises((ValidationError, IntegrityError)), transaction.atomic():
        harness_models.ReleasePublication.objects.create(
            manifest=manifest,
            published_template_id=42,
            published_snapshot_id=86,
            published_version="2026.09.05.2",
            publish_idempotency_ref="idempotency://publish/release-2",
            published_at=timezone.now(),
        )
    publication.published_snapshot_id = 999
    with pytest.raises(ValidationError):
        publication.save()
