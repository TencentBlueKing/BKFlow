"""Deterministic Owner and knowledge-tier routing for P4 improvement drafts."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field

from django.db import transaction

from bkflow.harness.constants import (
    ImprovementCandidateStatus,
    ImprovementCandidateType,
    KnowledgeTier,
)
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.models import (
    GenerationFeedback,
    ImprovementCandidate,
    KnowledgeCandidate,
)
from bkflow.harness.services.feedback.attribution import AttributionResult
from bkflow.harness.services.knowledge.eligibility import eligible_bindings
from bkflow.harness.services.knowledge.security import is_bounded_non_secret_text

_TIER_SPECIFICITY = {
    KnowledgeTier.GLOBAL: 0,
    KnowledgeTier.PUBLIC: 1,
    KnowledgeTier.PLATFORM: 2,
    KnowledgeTier.SPACE: 3,
    KnowledgeTier.SCOPE: 4,
}


@dataclass(frozen=True)
class OwnerAssignment:
    """One independently reviewed owner pair supplied by a trusted Owner map."""

    owner_ref: str
    reviewer_ref: str

    def __post_init__(self):
        if (
            not is_bounded_non_secret_text(self.owner_ref, 128)
            or not is_bounded_non_secret_text(self.reviewer_ref, 128)
            or self.owner_ref == self.reviewer_ref
        ):
            raise ValueError("invalid owner assignment")


@dataclass(frozen=True)
class ImprovementOwnerMap:
    """Explicit control-plane ownership; an absent entry is never inferred."""

    registry_owners: Mapping = field(default_factory=dict)
    bkflow_owners: tuple = ()
    bkaidev_release_owners: tuple = ()
    harness_eval_owners: tuple = ()

    def __post_init__(self):
        if not isinstance(self.registry_owners, Mapping):
            raise ValueError("registry owners must be a mapping")
        for capability_ref, assignments in self.registry_owners.items():
            if not is_bounded_non_secret_text(capability_ref, 255) or not _valid_assignments(assignments):
                raise ValueError("invalid registry owner map")
        for assignments in (self.bkflow_owners, self.bkaidev_release_owners, self.harness_eval_owners):
            if not _valid_assignments(assignments):
                raise ValueError("invalid owner map")


@dataclass(frozen=True)
class CandidateRoutingResult:
    """Persisted draft plus an explicit non-secret routing decision."""

    candidate: ImprovementCandidate
    knowledge_candidate: object
    routing_reason: str


def _valid_assignments(assignments):
    return isinstance(assignments, tuple) and all(isinstance(item, OwnerAssignment) for item in assignments)


def _trusted_context(feedback):
    try:
        scope_type, scope_value = json.loads(feedback.scope) if feedback.scope else (None, None)
    except (TypeError, ValueError):
        raise ValueError("feedback has invalid trusted scope") from None
    return TrustedHarnessContext(
        platform_key=feedback.platform,
        platform_app=feedback.platform_app,
        actor=feedback.actor,
        space_id=feedback.space_id,
        scope_type=scope_type,
        scope_value=scope_value,
        target_environment=feedback.target_environment,
        policy_version=feedback.policy_version,
        mcp_contract_version=feedback.run.mcp_contract_version,
        correlation_id="candidate-routing-{}".format(feedback.id),
    )


def _knowledge_route(feedback, classification, source_tier):
    if source_tier not in KnowledgeTier.values:
        raise ValueError("source knowledge tier is required")
    bindings = eligible_bindings(_trusted_context(feedback), classification)
    minimum = _TIER_SPECIFICITY[source_tier]
    permitted = tuple(binding for binding in bindings if _TIER_SPECIFICITY[binding.tier] >= minimum)
    if not permitted:
        reason = "KNOWLEDGE_TIER_BROADENING_BLOCKED" if bindings else "KNOWLEDGE_BINDING_MISSING"
        return None, (), reason
    most_specific = max(_TIER_SPECIFICITY[binding.tier] for binding in permitted)
    selected = next(binding for binding in permitted if _TIER_SPECIFICITY[binding.tier] == most_specific)
    assignments = (OwnerAssignment(selected.owner, selected.reviewer),) if selected.owner and selected.reviewer else ()
    return selected, assignments, "ROUTED_TO_KNOWLEDGE_BINDING"


def _control_route(candidate_type, owner_map, capability_ref):
    routes = {
        ImprovementCandidateType.VALIDATOR_POLICY: (
            "bkflow",
            owner_map.bkflow_owners,
            "ROUTED_TO_BKFLOW_OWNER",
        ),
        ImprovementCandidateType.PROMPT_SKILL: (
            "bkaidev-agent-release",
            owner_map.bkaidev_release_owners,
            "ROUTED_TO_BKAIDEV_RELEASE_OWNER",
        ),
        ImprovementCandidateType.EVAL: (
            "harness-eval",
            owner_map.harness_eval_owners,
            "ROUTED_TO_HARNESS_EVAL_OWNER",
        ),
    }
    if candidate_type == ImprovementCandidateType.REGISTRY:
        if not is_bounded_non_secret_text(capability_ref, 255):
            raise ValueError("registry candidate requires capability ref")
        return (
            "capability-registry",
            owner_map.registry_owners.get(capability_ref, ()),
            "ROUTED_TO_CAPABILITY_OWNER",
        )
    return routes[candidate_type]


def _resolved_assignment(assignments, routed_reason):
    if not assignments:
        return None, "OWNER_MISSING"
    if len(assignments) != 1:
        return None, "OWNER_AMBIGUOUS"
    return assignments[0], routed_reason


@transaction.atomic
def route_improvement_candidate(
    *,
    feedback,
    attribution,
    candidate_type,
    proposal_artifact_ref,
    source_version,
    current_version,
    target_version,
    risk,
    regression_case_refs,
    owner_map,
    impact_artifact_ref=None,
    rollback_artifact_ref=None,
    capability_ref=None,
    source_knowledge_tier=None,
    knowledge_classification=None,
):
    """Create one DRAFT and route it without inventing authority or widening knowledge scope."""
    if not isinstance(feedback, GenerationFeedback) or feedback.pk is None:
        raise ValueError("routing requires persisted feedback")
    if not isinstance(attribution, AttributionResult) or attribution.category is None:
        raise ValueError("routing requires typed attribution")
    if candidate_type not in attribution.recommended_candidate_types:
        raise ValueError("candidate type was not recommended by attribution")
    if candidate_type not in ImprovementCandidateType.values:
        raise ValueError("invalid candidate type")
    if not isinstance(owner_map, ImprovementOwnerMap):
        raise ValueError("routing requires trusted owner map")

    binding = None
    target_system = None
    target = {
        "target_tier": None,
        "target_platform_key": None,
        "target_space_id": None,
        "target_scope_type": None,
        "target_scope_value": None,
    }
    if candidate_type == ImprovementCandidateType.KNOWLEDGE:
        binding, assignments, routed_reason = _knowledge_route(
            feedback,
            knowledge_classification,
            source_knowledge_tier,
        )
        target_system = "{}-knowledge".format(binding.provider) if binding is not None else "knowledge-unresolved"
        if binding is not None:
            target = {
                "target_tier": binding.tier,
                "target_platform_key": binding.platform_key,
                "target_space_id": binding.space_id,
                "target_scope_type": binding.scope_type,
                "target_scope_value": binding.scope_value,
            }
    else:
        target_system, assignments, routed_reason = _control_route(candidate_type, owner_map, capability_ref)

    assignment, reason = _resolved_assignment(assignments, routed_reason)
    if binding is None and candidate_type == ImprovementCandidateType.KNOWLEDGE:
        reason = routed_reason
    candidate = ImprovementCandidate.objects.create(
        source_feedback=feedback,
        source_evidence_bundle=feedback.evidence_bundle,
        candidate_type=candidate_type,
        attribution=attribution.category,
        proposal_artifact_ref=proposal_artifact_ref,
        owner_ref=assignment.owner_ref if assignment else None,
        reviewer_ref=assignment.reviewer_ref if assignment else None,
        target_system=target_system,
        status=ImprovementCandidateStatus.DRAFT,
        risk=risk,
        confidence=attribution.confidence,
        regression_case_refs=list(regression_case_refs),
        impact_artifact_ref=impact_artifact_ref,
        rollback_artifact_ref=rollback_artifact_ref,
        source_version=source_version,
        current_version=current_version,
        target_version=target_version,
        **target,
    )
    knowledge_candidate = None
    if binding is not None:
        knowledge_candidate = KnowledgeCandidate.objects.create(
            candidate=candidate,
            target_binding=binding,
            target_source_ref=binding.source_ref,
            proposed_snapshot_lineage={"parent": binding.snapshot_version, "proposed": target_version},
            citation_refs=list(attribution.evidence_refs),
            conflict_set=[],
        )
    return CandidateRoutingResult(candidate=candidate, knowledge_candidate=knowledge_candidate, routing_reason=reason)
