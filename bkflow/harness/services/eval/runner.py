"""Hash-addressed Eval packages, deterministic local comparison, and signed result import."""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from bkflow.harness.constants import (
    ImprovementCandidateStatus,
    ImprovementCandidateType,
)
from bkflow.harness.models import (
    HarnessEvalRun,
    ImprovementCandidate,
    KnowledgeCandidate,
)
from bkflow.harness.services.canonical import canonical_json_bytes, sha256_json
from bkflow.harness.services.evidence import (
    is_safe_evidence_ref,
    prepare_evidence_artifact_payload,
    record_evidence,
)
from bkflow.harness.services.knowledge.security import is_bounded_non_secret_text

EVAL_PACKAGE_SCHEMA_VERSION = "p4-eval-package-v1"
SIGNED_RESULT_SCHEMA_VERSION = "p4-bkaidev-eval-result-v1"
MANDATORY_LOCAL_SUITES = (
    "resolver",
    "schema",
    "validation",
    "acl",
    "policy",
    "postcondition",
    "security",
)
MAX_EVAL_PACKAGE_BYTES = 64 * 1024
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_METRIC_KEYS = {
    "case_count",
    "passed_case_count",
    "quality_delta",
    "latency_regression",
    "cost_regression",
    "safety_regressions",
    "sensitive_data_regressions",
    "cross_space_access_regressions",
    "permission_regressions",
}
_COUNT_METRICS = {
    "case_count",
    "passed_case_count",
    "safety_regressions",
    "sensitive_data_regressions",
    "cross_space_access_regressions",
    "permission_regressions",
}


class EvalRunError(ValueError):
    """Stable non-reflective Eval package, execution, or import error."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SignedEvalVerification:
    """Authenticated BKAIDev signer and receipt facts returned by a verifier."""

    signer_ref: str
    receipt_ref: str
    signed_result_ref: str
    signed_result_digest: str


class DenySignedEvalVerifier:
    """Production-safe default until the BKAIDev signing contract is integrated."""

    def verify(self, document):
        raise EvalRunError("SIGNED_EVAL_UNVERIFIED")


def _knowledge_snapshots(candidate):
    if candidate.candidate_type != ImprovementCandidateType.KNOWLEDGE:
        return []
    try:
        knowledge = candidate.knowledge_candidate
    except KnowledgeCandidate.DoesNotExist:
        raise EvalRunError("KNOWLEDGE_TARGET_MISSING") from None
    return [
        {
            "source_ref": knowledge.target_source_ref,
            "base": candidate.current_version,
            "candidate": candidate.target_version,
        }
    ]


def _case_document(case):
    return {
        "case_id": case.case_id,
        "case_version": case.case_version,
        "fixture_hash": case.fixture_hash,
        "tier": case.tier,
        "scope": case.scope,
        "sanitized_input_artifact_ref": case.sanitized_input_artifact_ref,
        "expected_invariants": case.expected_invariants,
        "scoring_schema": case.scoring_schema,
        "safety_tags": list(case.safety_tags),
    }


def build_eval_package(candidate, *, bkaidev_agent_release):
    """Build a reproducible package without embedding raw feedback, knowledge, or credentials."""
    if not isinstance(candidate, ImprovementCandidate) or candidate.pk is None:
        raise EvalRunError("CANDIDATE_INVALID")
    if candidate.status not in {ImprovementCandidateStatus.APPROVED, ImprovementCandidateStatus.PUBLISHED}:
        raise EvalRunError("CANDIDATE_NOT_APPROVED")
    if not is_bounded_non_secret_text(bkaidev_agent_release, 128):
        raise EvalRunError("AGENT_RELEASE_INVALID")
    cases = list(candidate.eval_cases.order_by("case_id", "case_version", "id"))
    if not cases:
        raise EvalRunError("EVAL_CASES_REQUIRED")
    body = {
        "schema_version": EVAL_PACKAGE_SCHEMA_VERSION,
        "candidate_ref": "candidate://improvement/{}".format(candidate.id),
        "candidate_type": candidate.candidate_type,
        "bkaidev_agent_release": bkaidev_agent_release,
        "mcp_contract_version": candidate.source_feedback.run.mcp_contract_version,
        "versions": {"base": candidate.current_version, "candidate": candidate.target_version},
        "knowledge_snapshots": _knowledge_snapshots(candidate),
        "cases": [_case_document(case) for case in cases],
    }
    projected = prepare_evidence_artifact_payload(body)
    if projected != body or len(canonical_json_bytes(body)) > MAX_EVAL_PACKAGE_BYTES:
        raise EvalRunError("EVAL_PACKAGE_UNSAFE")
    body["package_hash"] = sha256_json(body)
    return body


def _suite(case):
    invariants = case.expected_invariants
    return invariants.get("suite") if isinstance(invariants, Mapping) else None


def _assertions_pass(case, observation):
    invariants = case.expected_invariants
    assertions = invariants.get("assertions") if isinstance(invariants, Mapping) else None
    return (
        isinstance(observation, Mapping)
        and isinstance(assertions, Mapping)
        and all(observation.get(key) == expected for key, expected in assertions.items())
    )


def _local_metrics(cases, observations):
    expected_hashes = {case.fixture_hash for case in cases}
    if not isinstance(observations, Mapping) or set(observations) != expected_hashes:
        raise EvalRunError("EVAL_CASE_SET_MISMATCH")
    case_passes = {case.fixture_hash: _assertions_pass(case, observations[case.fixture_hash]) for case in cases}
    suite_results = {}
    for suite in MANDATORY_LOCAL_SUITES:
        suite_cases = [case for case in cases if _suite(case) == suite]
        suite_results[suite] = bool(suite_cases) and all(case_passes[case.fixture_hash] for case in suite_cases)
    failed = [case for case in cases if not case_passes[case.fixture_hash]]
    return {
        "case_count": len(cases),
        "passed_case_count": sum(case_passes.values()),
        "mandatory_suite_pass_rate": sum(suite_results.values()) / len(MANDATORY_LOCAL_SUITES),
        "suite_results": suite_results,
        "safety_regressions": sum(bool(case.safety_tags) for case in failed),
        "sensitive_data_regressions": sum("secret" in case.safety_tags for case in failed),
        "cross_space_access_regressions": sum("cross_space" in case.safety_tags for case in failed),
        "permission_regressions": sum("permission" in case.safety_tags for case in failed),
    }


def _record_eval_event(eval_run, event_type, extra=None):
    payload = {
        "eval_run_ref": "eval-run://harness/{}".format(eval_run.id),
        "candidate_ref": "candidate://improvement/{}".format(eval_run.candidate_id),
        "runner_mode": eval_run.runner_mode,
        "package_hash": eval_run.package_hash,
        "result_hash": eval_run.result_hash,
        "status": eval_run.status,
        "safety_result": eval_run.safety_result,
    }
    payload.update(extra or {})
    return record_evidence(
        run=eval_run.candidate.source_feedback.run,
        revision=eval_run.candidate.source_feedback.revision,
        event_type=event_type,
        action="evaluate_improvement_candidate",
        payload=payload,
        actor=eval_run.candidate.source_feedback.actor,
        correlation_id="candidate-eval-{}".format(eval_run.candidate_id),
    )


@transaction.atomic
def run_local_eval(candidate_id, *, bkaidev_agent_release, observations, thresholds):
    """Compare supplied local service facts to immutable invariants; no model client is accepted or called."""
    candidate = (
        ImprovementCandidate.objects.select_for_update().select_related("source_feedback__run").get(pk=candidate_id)
    )
    package = build_eval_package(candidate, bkaidev_agent_release=bkaidev_agent_release)
    cases = tuple(candidate.eval_cases.order_by("case_id", "case_version", "id"))
    metrics = _local_metrics(cases, observations)
    safety_passed = all(
        metrics[key] == 0
        for key in (
            "safety_regressions",
            "sensitive_data_regressions",
            "cross_space_access_regressions",
            "permission_regressions",
        )
    )
    passed = (
        metrics["passed_case_count"] == metrics["case_count"]
        and metrics["mandatory_suite_pass_rate"] == 1.0
        and safety_passed
    )
    completed_at = timezone.now()
    result_body = {
        "package_hash": package["package_hash"],
        "runner_mode": HarnessEvalRun.RunnerMode.LOCAL_DETERMINISTIC,
        "metrics": metrics,
        "thresholds": thresholds,
    }
    try:
        eval_run = HarnessEvalRun.objects.create(
            candidate=candidate,
            base_release_version=candidate.current_version,
            candidate_release_version=candidate.target_version,
            runner_mode=HarnessEvalRun.RunnerMode.LOCAL_DETERMINISTIC,
            package_hash=package["package_hash"],
            result_hash=sha256_json(result_body),
            aggregate_metrics=metrics,
            safety_result=(HarnessEvalRun.SafetyResult.PASSED if safety_passed else HarnessEvalRun.SafetyResult.FAILED),
            threshold_snapshot=thresholds,
            status=HarnessEvalRun.Status.PASSED if passed else HarnessEvalRun.Status.FAILED,
            started_at=completed_at,
            finalized_at=completed_at,
        )
    except (IntegrityError, ValidationError, TypeError, ValueError):
        raise EvalRunError("LOCAL_EVAL_PERSISTENCE_FAILED") from None
    _record_eval_event(eval_run, "HARNESS_EVAL_COMPLETED")
    return eval_run


def _validate_external_metrics(metrics, expected_case_count, case_results):
    if not isinstance(metrics, Mapping) or set(metrics) != _METRIC_KEYS:
        raise EvalRunError("EVAL_METRIC_SCHEMA_INVALID")
    for key, value in metrics.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise EvalRunError("EVAL_METRIC_SCHEMA_INVALID")
        if key in _COUNT_METRICS and (not isinstance(value, int) or value < 0):
            raise EvalRunError("EVAL_METRIC_SCHEMA_INVALID")
    passed_count = sum(result["passed"] for result in case_results)
    if metrics["case_count"] != expected_case_count or metrics["passed_case_count"] != passed_count:
        raise EvalRunError("EVAL_METRIC_SCHEMA_INVALID")
    if any(
        metrics[key] > metrics["safety_regressions"]
        for key in _COUNT_METRICS - {"case_count", "passed_case_count", "safety_regressions"}
    ):
        raise EvalRunError("EVAL_METRIC_SCHEMA_INVALID")


def _validate_verification(verification):
    if (
        not isinstance(verification, SignedEvalVerification)
        or not is_safe_evidence_ref(verification.signer_ref)
        or not is_safe_evidence_ref(verification.receipt_ref)
        or not is_safe_evidence_ref(verification.signed_result_ref)
        or not isinstance(verification.signed_result_digest, str)
        or _HEX_64.fullmatch(verification.signed_result_digest) is None
    ):
        raise EvalRunError("SIGNED_EVAL_UNVERIFIED")


def import_signed_bkaidev_result(candidate_id, *, document, verifier, thresholds):
    """Verify a complete fixed-release result before persisting only bounded normalized facts."""
    candidate = ImprovementCandidate.objects.select_related("source_feedback__run").get(pk=candidate_id)
    if candidate.status != ImprovementCandidateStatus.APPROVED:
        raise EvalRunError("CANDIDATE_NOT_APPROVED")
    required = {
        "schema_version",
        "candidate_ref",
        "package_hash",
        "bkaidev_agent_release",
        "mcp_contract_version",
        "base_release_version",
        "candidate_release_version",
        "case_results",
        "aggregate_metrics",
        "signature",
    }
    if (
        not isinstance(document, Mapping)
        or set(document) != required
        or document.get("schema_version") != SIGNED_RESULT_SCHEMA_VERSION
    ):
        raise EvalRunError("SIGNED_EVAL_SCHEMA_INVALID")
    if prepare_evidence_artifact_payload(document) != document:
        raise EvalRunError("SIGNED_EVAL_SCHEMA_INVALID")
    if document["candidate_ref"] != "candidate://improvement/{}".format(candidate.id):
        raise EvalRunError("SIGNED_EVAL_CANDIDATE_MISMATCH")
    package = build_eval_package(candidate, bkaidev_agent_release=document["bkaidev_agent_release"])
    if (
        document["package_hash"] != package["package_hash"]
        or document["mcp_contract_version"] != package["mcp_contract_version"]
        or document["base_release_version"] != candidate.current_version
        or document["candidate_release_version"] != candidate.target_version
    ):
        raise EvalRunError("EVAL_PACKAGE_MISMATCH")
    case_results = document["case_results"]
    if not isinstance(case_results, list) or any(
        not isinstance(item, Mapping)
        or set(item) != {"fixture_hash", "passed"}
        or not isinstance(item["fixture_hash"], str)
        or _HEX_64.fullmatch(item["fixture_hash"]) is None
        or not isinstance(item["passed"], bool)
        for item in case_results
    ):
        raise EvalRunError("SIGNED_EVAL_SCHEMA_INVALID")
    expected_hashes = {case["fixture_hash"] for case in package["cases"]}
    result_hashes = [item["fixture_hash"] for item in case_results]
    if len(result_hashes) != len(set(result_hashes)) or set(result_hashes) != expected_hashes:
        raise EvalRunError("EVAL_CASE_SET_MISMATCH")
    _validate_external_metrics(document["aggregate_metrics"], len(expected_hashes), case_results)
    try:
        verification = verifier.verify(document)
    except EvalRunError:
        raise
    except Exception:
        raise EvalRunError("SIGNED_EVAL_UNVERIFIED") from None
    _validate_verification(verification)

    metrics = dict(document["aggregate_metrics"])
    safety_passed = all(
        metrics[key] == 0
        for key in (
            "safety_regressions",
            "sensitive_data_regressions",
            "cross_space_access_regressions",
            "permission_regressions",
        )
    )
    passed = metrics["passed_case_count"] == metrics["case_count"] and safety_passed
    completed_at = timezone.now()
    result_body = {key: value for key, value in document.items() if key != "signature"}
    with transaction.atomic():
        locked = (
            ImprovementCandidate.objects.select_for_update().select_related("source_feedback__run").get(pk=candidate_id)
        )
        if locked.status != ImprovementCandidateStatus.APPROVED:
            raise EvalRunError("CANDIDATE_STATE_CHANGED")
        locked_package = build_eval_package(
            locked,
            bkaidev_agent_release=document["bkaidev_agent_release"],
        )
        if locked_package["package_hash"] != package["package_hash"]:
            raise EvalRunError("EVAL_PACKAGE_CHANGED")
        try:
            eval_run = HarnessEvalRun.objects.create(
                candidate=locked,
                base_release_version=locked.current_version,
                candidate_release_version=locked.target_version,
                runner_mode=HarnessEvalRun.RunnerMode.SIGNED_BKAIDEV,
                package_hash=package["package_hash"],
                result_hash=sha256_json(result_body),
                signed_result_ref=verification.signed_result_ref,
                signed_result_digest=verification.signed_result_digest,
                aggregate_metrics=metrics,
                safety_result=(
                    HarnessEvalRun.SafetyResult.PASSED if safety_passed else HarnessEvalRun.SafetyResult.FAILED
                ),
                threshold_snapshot=thresholds,
                status=HarnessEvalRun.Status.PASSED if passed else HarnessEvalRun.Status.FAILED,
                started_at=completed_at,
                finalized_at=completed_at,
            )
        except (IntegrityError, ValidationError, TypeError, ValueError):
            raise EvalRunError("SIGNED_EVAL_PERSISTENCE_FAILED") from None
        _record_eval_event(
            eval_run,
            "BKAIDEV_EVAL_IMPORTED",
            {
                "signer_ref": verification.signer_ref,
                "receipt_ref": verification.receipt_ref,
                "signed_result_digest": verification.signed_result_digest,
                "bkaidev_agent_release": document["bkaidev_agent_release"],
            },
        )
        return eval_run
