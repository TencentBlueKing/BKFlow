"""Bounded, sanitized, hash-addressed P4 improvement review packages."""

from bkflow.harness.models import ImprovementCandidate
from bkflow.harness.services.canonical import canonical_json_bytes, sha256_json
from bkflow.harness.services.evidence import (
    is_safe_evidence_ref,
    validate_redacted_evidence_payload,
)

PACKAGE_SCHEMA_VERSION = "p4-improvement-package-v1"
MAX_PACKAGE_BYTES = 64 * 1024


def _attribution_evidence_refs(candidate):
    feedback_ref = "feedback://generation/{}".format(candidate.source_feedback_id)
    refs = set()
    events = candidate.source_feedback.run.evidence_events.filter(
        revision_id=candidate.source_feedback.revision_id,
        event_type="FEEDBACK_ATTRIBUTION_RECORDED",
    )
    for event in events:
        payload = event.redacted_payload
        if not isinstance(payload, dict) or payload.get("feedback_ref") != feedback_ref:
            continue
        for result in payload.get("results", []):
            if not isinstance(result, dict) or result.get("category") != candidate.attribution:
                continue
            for ref in result.get("evidence_refs", []):
                if is_safe_evidence_ref(ref):
                    refs.add(ref)
    return sorted(refs)


def _target_dimensions(candidate):
    return {
        "tier": candidate.target_tier,
        "platform_key": candidate.target_platform_key,
        "space_id": candidate.target_space_id,
        "scope_type": candidate.target_scope_type,
        "scope_value": candidate.target_scope_value,
    }


def build_candidate_review_package(candidate):
    """Project only governed metadata; raw feedback and knowledge bodies never enter the package."""
    if not isinstance(candidate, ImprovementCandidate) or candidate.pk is None:
        raise ValueError("review package requires persisted candidate")
    feedback = candidate.source_feedback
    body = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "candidate": {
            "candidate_ref": "candidate://improvement/{}".format(candidate.id),
            "candidate_type": candidate.candidate_type,
            "status": candidate.status,
            "attribution": candidate.attribution,
            "confidence": candidate.confidence,
            "revision_number": candidate.revision_number,
        },
        "provenance": {
            "feedback_ref": "feedback://generation/{}".format(feedback.id),
            "run_ref": "harness-run://generation/{}".format(feedback.run_id),
            "revision_ref": "workflow-revision://generation/{}".format(feedback.revision_id),
            "plan_hash": feedback.plan_hash,
            "evidence_bundle_ref": (
                "evidence-bundle://harness/{}".format(candidate.source_evidence_bundle_id)
                if candidate.source_evidence_bundle_id
                else None
            ),
        },
        "route": {
            "target_system": candidate.target_system,
            "target_dimensions": _target_dimensions(candidate),
            "owner_ref": candidate.owner_ref,
            "reviewer_ref": candidate.reviewer_ref,
            "governance_blockers": [] if candidate.owner_ref else ["OWNER_UNRESOLVED"],
        },
        "proposal": {"artifact_ref": candidate.proposal_artifact_ref, "content_inline": False},
        "evidence_citations": _attribution_evidence_refs(candidate),
        "versions": {
            "source": candidate.source_version,
            "current": candidate.current_version,
            "proposed": candidate.target_version,
        },
        "applicability": {
            "platform": feedback.platform,
            "platform_app": feedback.platform_app,
            "space_id": feedback.space_id,
            "scope": feedback.scope,
            "environment": feedback.target_environment,
            "target": _target_dimensions(candidate),
        },
        "exclusions": [
            "NO_CROSS_SPACE_APPLICATION",
            "NO_AUTOMATIC_PUBLICATION",
            "NO_RAW_USER_CONTENT",
            "NO_RUNTIME_CREDENTIALS",
        ],
        "risk": {
            "level": candidate.risk,
            "blast_radius_artifact_ref": candidate.impact_artifact_ref,
            "owner_assessment_required": candidate.impact_artifact_ref is None,
        },
        "regression_case_refs": list(candidate.regression_case_refs),
        "evaluation_requirements": {
            "case_refs": list(candidate.regression_case_refs),
            "zero_regression_required": True,
            "external_quality_gate_required": True,
        },
        "rollback_steps": {
            "artifact_ref": candidate.rollback_artifact_ref,
            "owner_definition_required": candidate.rollback_artifact_ref is None,
        },
    }
    if not validate_redacted_evidence_payload(body):
        raise ValueError("candidate package is not bounded and sanitized")
    body["package_hash"] = sha256_json(body)
    if len(canonical_json_bytes(body)) > MAX_PACKAGE_BYTES:
        raise ValueError("candidate package exceeds export budget")
    return body
