"""Locked Owner/Reviewer controls for improvement candidate lifecycle and revisions."""

from collections.abc import Mapping

from django.db import transaction

from bkflow.harness.constants import (
    ImprovementCandidateStatus,
    ImprovementCandidateType,
)
from bkflow.harness.models import (
    IMPROVEMENT_CANDIDATE_GOVERNANCE_TOKEN,
    ImprovementCandidate,
    KnowledgeCandidate,
    KnowledgeSourceBinding,
)
from bkflow.harness.services.evidence import record_evidence


class CandidateGovernanceError(ValueError):
    """Non-reflective governance rejection safe for commands and administrative UI."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


_REVISION_FIELDS = frozenset(
    {
        "proposal_artifact_ref",
        "target_system",
        "risk",
        "confidence",
        "regression_case_refs",
        "impact_artifact_ref",
        "rollback_artifact_ref",
        "source_version",
        "current_version",
        "target_version",
        "target_binding",
    }
)


def _event(candidate, event_type, operator, payload):
    body = {
        "candidate_ref": "candidate://improvement/{}".format(candidate.id),
        "candidate_revision": candidate.revision_number,
        "operator": operator,
    }
    body.update(payload)
    return record_evidence(
        run=candidate.source_feedback.run,
        revision=candidate.source_feedback.revision,
        event_type=event_type,
        action="govern_improvement_candidate",
        payload=body,
        actor=candidate.source_feedback.actor,
        correlation_id="candidate-governance-{}".format(candidate.id),
    )


def _save_status(candidate, status, *, receipt_digest=None):
    candidate.status = status
    fields = ["status"]
    if receipt_digest is not None:
        candidate.promotion_receipt_digest = receipt_digest
        fields.append("promotion_receipt_digest")
    candidate.save(
        update_fields=fields,
        _governance_token=IMPROVEMENT_CANDIDATE_GOVERNANCE_TOKEN,
    )
    return candidate


@transaction.atomic
def submit_candidate(candidate_id, *, operator):
    """Let only the routed Owner submit a complete DRAFT for independent review."""
    candidate = (
        ImprovementCandidate.objects.select_for_update().select_related("source_feedback__run").get(pk=candidate_id)
    )
    if candidate.status != ImprovementCandidateStatus.DRAFT:
        raise CandidateGovernanceError("CANDIDATE_NOT_DRAFT")
    if candidate.owner_ref is None or operator != candidate.owner_ref:
        raise CandidateGovernanceError("OWNER_REQUIRED")
    _save_status(candidate, ImprovementCandidateStatus.IN_REVIEW)
    _event(candidate, "IMPROVEMENT_CANDIDATE_SUBMITTED", operator, {"status": candidate.status})
    return candidate


@transaction.atomic
def review_candidate(candidate_id, *, operator, decision):
    """Apply one independent reviewer decision without accepting arbitrary transitions."""
    candidate = (
        ImprovementCandidate.objects.select_for_update().select_related("source_feedback__run").get(pk=candidate_id)
    )
    if candidate.status != ImprovementCandidateStatus.IN_REVIEW:
        raise CandidateGovernanceError("CANDIDATE_NOT_IN_REVIEW")
    if candidate.reviewer_ref is None or operator != candidate.reviewer_ref or operator == candidate.owner_ref:
        raise CandidateGovernanceError("REVIEWER_REQUIRED")
    transitions = {
        "APPROVE": ImprovementCandidateStatus.APPROVED,
        "REJECT": ImprovementCandidateStatus.REJECTED,
    }
    status = transitions.get(decision)
    if status is None:
        raise CandidateGovernanceError("REVIEW_DECISION_INVALID")
    _save_status(candidate, status)
    _event(
        candidate,
        "IMPROVEMENT_CANDIDATE_REVIEWED",
        operator,
        {"decision": decision, "status": candidate.status},
    )
    return candidate


def _candidate_copy(parent):
    return {
        "source_feedback": parent.source_feedback,
        "source_evidence_bundle": parent.source_evidence_bundle,
        "candidate_type": parent.candidate_type,
        "attribution": parent.attribution,
        "proposal_artifact_ref": parent.proposal_artifact_ref,
        "owner_ref": parent.owner_ref,
        "reviewer_ref": parent.reviewer_ref,
        "target_system": parent.target_system,
        "target_tier": parent.target_tier,
        "target_platform_key": parent.target_platform_key,
        "target_space_id": parent.target_space_id,
        "target_scope_type": parent.target_scope_type,
        "target_scope_value": parent.target_scope_value,
        "status": ImprovementCandidateStatus.DRAFT,
        "risk": parent.risk,
        "confidence": parent.confidence,
        "regression_case_refs": list(parent.regression_case_refs),
        "impact_artifact_ref": parent.impact_artifact_ref,
        "rollback_artifact_ref": parent.rollback_artifact_ref,
        "source_version": parent.source_version,
        "current_version": parent.current_version,
        "target_version": parent.target_version,
        "promotion_receipt_digest": None,
        "parent_candidate": parent,
        "revision_number": parent.revision_number + 1,
    }


def _apply_target_binding(values, binding):
    if not isinstance(binding, KnowledgeSourceBinding) or binding.pk is None:
        raise CandidateGovernanceError("TARGET_BINDING_INVALID")
    values.update(
        {
            "target_system": "{}-knowledge".format(binding.provider),
            "target_tier": binding.tier,
            "target_platform_key": binding.platform_key,
            "target_space_id": binding.space_id,
            "target_scope_type": binding.scope_type,
            "target_scope_value": binding.scope_value,
            "source_version": binding.snapshot_version,
            "current_version": binding.snapshot_version,
        }
    )


@transaction.atomic
def revise_candidate(candidate_id, *, operator, changes):
    """Create a new DRAFT revision so prior approval and publication evidence remain historical."""
    parent = (
        ImprovementCandidate.objects.select_for_update().select_related("source_feedback__run").get(pk=candidate_id)
    )
    if parent.status not in {ImprovementCandidateStatus.APPROVED, ImprovementCandidateStatus.PUBLISHED}:
        raise CandidateGovernanceError("CANDIDATE_REVISION_NOT_ALLOWED")
    if operator != parent.owner_ref:
        raise CandidateGovernanceError("OWNER_REQUIRED")
    if not isinstance(changes, Mapping) or not changes or set(changes) - _REVISION_FIELDS:
        raise CandidateGovernanceError("REVISION_FIELDS_INVALID")

    values = _candidate_copy(parent)
    target_binding = changes.get("target_binding")
    for field_name, value in changes.items():
        if field_name != "target_binding":
            values[field_name] = value
    if target_binding is not None:
        if parent.candidate_type != ImprovementCandidateType.KNOWLEDGE:
            raise CandidateGovernanceError("TARGET_BINDING_INVALID")
        _apply_target_binding(values, target_binding)
    revised = ImprovementCandidate.objects.create(**values)

    if parent.candidate_type == ImprovementCandidateType.KNOWLEDGE:
        try:
            prior_knowledge = parent.knowledge_candidate
        except KnowledgeCandidate.DoesNotExist:
            raise CandidateGovernanceError("TARGET_BINDING_INVALID") from None
        binding = target_binding or prior_knowledge.target_binding
        KnowledgeCandidate.objects.create(
            candidate=revised,
            target_binding=binding,
            target_source_ref=binding.source_ref,
            proposed_snapshot_lineage={"parent": binding.snapshot_version, "proposed": revised.target_version},
            citation_refs=list(prior_knowledge.citation_refs),
            conflict_set=list(prior_knowledge.conflict_set),
        )
    _event(
        revised,
        "IMPROVEMENT_CANDIDATE_REVISED",
        operator,
        {
            "parent_candidate_ref": "candidate://improvement/{}".format(parent.id),
            "changed_fields": sorted(changes),
            "status": revised.status,
        },
    )
    return revised
