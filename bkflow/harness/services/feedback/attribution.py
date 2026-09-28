"""Versioned, deterministic attribution over typed Harness Evidence only."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from bkflow.harness.constants import (
    FeedbackAttributionCategory,
    ImprovementCandidateType,
)
from bkflow.harness.models import GenerationFeedback
from bkflow.harness.services.canonical import sha256_json
from bkflow.harness.services.evidence import record_evidence

DEFAULT_RULES_PATH = Path(__file__).resolve().parents[2] / "data" / "attribution_rules.yaml"
_TYPED_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


@dataclass(frozen=True)
class AttributionRule:
    """One literal-code rule with no executable expression surface."""

    rule_id: str
    priority: int
    category: str
    source: str
    typed_codes: tuple
    event_types: tuple
    confidence: float
    high_risk: bool
    candidate_types: tuple


@dataclass(frozen=True)
class AttributionRuleSet:
    """Validated immutable rules plus the pre-registered triage threshold."""

    version: str
    human_triage_threshold: float
    rules: tuple


@dataclass(frozen=True)
class AttributionResult:
    """One ordered cause backed by stable Evidence references."""

    category: object
    evidence_refs: tuple
    confidence: float
    ambiguous: bool
    ambiguity_reasons: tuple
    recommended_candidate_types: tuple
    requires_human_triage: bool
    rule_version: str
    rule_id: object
    result_hash: str


def _closed_mapping(value, keys, label):
    if not isinstance(value, Mapping) or set(value) != set(keys):
        raise ValueError("invalid {} schema".format(label))


def _typed_code_list(value, *, allow_empty=False):
    if (
        not isinstance(value, list)
        or (not value and not allow_empty)
        or len(value) > 50
        or len(value) != len(set(value))
        or not all(isinstance(item, str) and _TYPED_CODE.fullmatch(item) for item in value)
    ):
        raise ValueError("invalid typed attribution codes")
    return tuple(value)


@lru_cache(maxsize=4)
def load_attribution_rules(path=None):
    """Load a closed literal-data table and reject executable or unknown fields."""
    rules_path = Path(path) if path is not None else DEFAULT_RULES_PATH
    with rules_path.open("r", encoding="utf-8") as rules_file:
        document = yaml.safe_load(rules_file)
    _closed_mapping(document, {"version", "human_triage_threshold", "rules"}, "attribution rules")
    version = document["version"]
    threshold = document["human_triage_threshold"]
    if not isinstance(version, str) or _TYPED_CODE.fullmatch(version.upper().replace("-", "_")) is None:
        raise ValueError("invalid attribution rule version")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 < threshold <= 1:
        raise ValueError("invalid attribution threshold")
    rows = document["rules"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("attribution rules are required")
    rule_keys = {
        "rule_id",
        "priority",
        "category",
        "source",
        "typed_codes",
        "event_types",
        "confidence",
        "high_risk",
        "candidate_types",
    }
    parsed = []
    for row in rows:
        _closed_mapping(row, rule_keys, "attribution rule")
        if not isinstance(row["rule_id"], str) or re.fullmatch(r"[a-z][a-z0-9-]{0,63}", row["rule_id"]) is None:
            raise ValueError("invalid attribution rule id")
        if isinstance(row["priority"], bool) or not isinstance(row["priority"], int) or row["priority"] < 0:
            raise ValueError("invalid attribution rule priority")
        if row["category"] not in FeedbackAttributionCategory.values:
            raise ValueError("invalid attribution category")
        if row["source"] not in {"validation_report", "evidence_event", "any"}:
            raise ValueError("invalid attribution source")
        typed_codes = _typed_code_list(row["typed_codes"])
        event_types = _typed_code_list(row["event_types"], allow_empty=True)
        if row["source"] == "evidence_event" and not event_types:
            raise ValueError("evidence attribution requires event types")
        confidence = row["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise ValueError("invalid attribution confidence")
        if not isinstance(row["high_risk"], bool):
            raise ValueError("invalid attribution risk flag")
        candidate_types = tuple(row["candidate_types"])
        if (
            not candidate_types
            or len(candidate_types) != len(set(candidate_types))
            or any(candidate not in ImprovementCandidateType.values for candidate in candidate_types)
        ):
            raise ValueError("invalid attribution candidate types")
        if row["high_risk"] and candidate_types[:2] != (
            ImprovementCandidateType.VALIDATOR_POLICY,
            ImprovementCandidateType.EVAL,
        ):
            raise ValueError("high-risk attribution must recommend safeguards first")
        parsed.append(
            AttributionRule(
                rule_id=row["rule_id"],
                priority=row["priority"],
                category=row["category"],
                source=row["source"],
                typed_codes=typed_codes,
                event_types=event_types,
                confidence=float(confidence),
                high_risk=row["high_risk"],
                candidate_types=candidate_types,
            )
        )
    if len({rule.rule_id for rule in parsed}) != len(parsed) or len({rule.priority for rule in parsed}) != len(parsed):
        raise ValueError("attribution rule ids and priorities must be unique")
    if {rule.category for rule in parsed} != set(FeedbackAttributionCategory.values):
        raise ValueError("attribution rules must cover the closed taxonomy")
    return AttributionRuleSet(
        version=version,
        human_triage_threshold=float(threshold),
        rules=tuple(sorted(parsed, key=lambda rule: (rule.priority, rule.rule_id))),
    )


def _value(item, key, default=None):
    return item.get(key, default) if isinstance(item, Mapping) else getattr(item, key, default)


def _valid_code(value):
    return value if isinstance(value, str) and _TYPED_CODE.fullmatch(value) else None


def _report_signals(reports):
    """Extract only explicit error codes and stable report references."""
    signals = {}
    for report in reports:
        report_id = _value(report, "id")
        errors = _value(report, "errors", [])
        if report_id is None or not isinstance(errors, list):
            continue
        ref = "validation-report://harness/{}".format(report_id)
        for error in errors:
            code = _valid_code(_value(error, "code"))
            if code is not None:
                signals.setdefault(code, set()).add(ref)
    return signals


def _payload_codes(value, depth=0):
    """Read literal typed-code fields only; ordinary text never becomes a signal."""
    if depth > 6:
        return set()
    if isinstance(value, Mapping):
        result = set()
        for key, child in value.items():
            if key in {"code", "error_code", "postcondition_code"}:
                code = _valid_code(child)
                if code is not None:
                    result.add(code)
            elif isinstance(child, (Mapping, list)):
                result.update(_payload_codes(child, depth + 1))
        return result
    if isinstance(value, list):
        result = set()
        for child in value[:100]:
            result.update(_payload_codes(child, depth + 1))
        return result
    return set()


def _event_signals(events):
    """Return code -> event type -> refs for concrete runtime Evidence."""
    signals = {}
    for event in events:
        event_id = _value(event, "id")
        event_type = _valid_code(_value(event, "event_type"))
        payload = _value(event, "redacted_payload", {})
        if event_id is None or event_type is None:
            continue
        ref = "evidence://event/{}".format(event_id)
        for code in _payload_codes(payload):
            signals.setdefault(code, {}).setdefault(event_type, set()).add(ref)
    return signals


def _rule_evidence_refs(rule, report_signals, event_signals):
    refs = set()
    if rule.source in {"validation_report", "any"}:
        for code in rule.typed_codes:
            refs.update(report_signals.get(code, ()))
    if rule.source in {"evidence_event", "any"}:
        for code in rule.typed_codes:
            by_event_type = event_signals.get(code, {})
            if rule.event_types:
                for event_type in rule.event_types:
                    refs.update(by_event_type.get(event_type, ()))
            else:
                for event_refs in by_event_type.values():
                    refs.update(event_refs)
    return tuple(sorted(refs))


def _result_hash(rule_set, rule, evidence_refs, ambiguity_reasons, candidate_types):
    return sha256_json(
        {
            "rule_version": rule_set.version,
            "rule_id": rule.rule_id,
            "category": rule.category,
            "confidence": rule.confidence,
            "evidence_refs": evidence_refs,
            "ambiguity_reasons": ambiguity_reasons,
            "candidate_types": candidate_types,
        }
    )


def _insufficient_result(rule_set):
    ambiguity_reasons = ("INSUFFICIENT_TYPED_EVIDENCE",)
    result_hash = sha256_json(
        {
            "rule_version": rule_set.version,
            "rule_id": None,
            "category": None,
            "confidence": 0.0,
            "evidence_refs": (),
            "ambiguity_reasons": ambiguity_reasons,
            "candidate_types": (),
        }
    )
    return AttributionResult(
        category=None,
        evidence_refs=(),
        confidence=0.0,
        ambiguous=True,
        ambiguity_reasons=ambiguity_reasons,
        recommended_candidate_types=(),
        requires_human_triage=True,
        rule_version=rule_set.version,
        rule_id=None,
        result_hash=result_hash,
    )


def attribute_feedback(feedback, *, validation_reports=None, evidence_events=None, rule_set=None):
    """Return stable ordered causes from typed reports/events, ignoring feedback prose."""
    if not isinstance(feedback, GenerationFeedback) or feedback.pk is None:
        raise ValueError("attribution requires persisted feedback")
    active_rules = rule_set or load_attribution_rules()
    reports = (
        feedback.run.validation_reports.filter(revision=feedback.revision)
        if validation_reports is None
        else validation_reports
    )
    events = (
        feedback.run.evidence_events.filter(revision=feedback.revision) if evidence_events is None else evidence_events
    )
    report_signals = _report_signals(reports)
    event_signals = _event_signals(events)
    matches = []
    for rule in active_rules.rules:
        refs = _rule_evidence_refs(rule, report_signals, event_signals)
        if refs:
            matches.append((rule, refs))
    if not matches:
        return (_insufficient_result(active_rules),)
    competing = len(matches) > 1
    results = []
    for rule, refs in matches:
        below_threshold = rule.confidence < active_rules.human_triage_threshold
        ambiguity_reasons = ("COMPETING_TYPED_EVIDENCE",) if competing else ()
        if below_threshold:
            ambiguity_reasons += ("BELOW_HUMAN_TRIAGE_THRESHOLD",)
        candidate_types = () if below_threshold else rule.candidate_types
        results.append(
            AttributionResult(
                category=rule.category,
                evidence_refs=refs,
                confidence=rule.confidence,
                ambiguous=bool(ambiguity_reasons),
                ambiguity_reasons=ambiguity_reasons,
                recommended_candidate_types=candidate_types,
                requires_human_triage=bool(ambiguity_reasons),
                rule_version=active_rules.version,
                rule_id=rule.rule_id,
                result_hash=_result_hash(active_rules, rule, refs, ambiguity_reasons, candidate_types),
            )
        )
    return tuple(results)


def persist_attribution_results(feedback, results, *, correlation_id):
    """Append the exact rule version, refs, and hashes selected by an attribution worker."""
    if not isinstance(feedback, GenerationFeedback) or feedback.pk is None:
        raise ValueError("attribution persistence requires persisted feedback")
    if (
        not isinstance(results, tuple)
        or not results
        or not all(isinstance(item, AttributionResult) for item in results)
    ):
        raise ValueError("attribution persistence requires typed results")
    payload = {
        "feedback_ref": "feedback://generation/{}".format(feedback.id),
        "results": [
            {
                "category": result.category,
                "evidence_refs": list(result.evidence_refs),
                "confidence": result.confidence,
                "ambiguous": result.ambiguous,
                "ambiguity_reasons": list(result.ambiguity_reasons),
                "recommended_candidate_types": list(result.recommended_candidate_types),
                "requires_human_triage": result.requires_human_triage,
                "rule_version": result.rule_version,
                "rule_id": result.rule_id,
                "result_hash": result.result_hash,
            }
            for result in results
        ],
    }
    return record_evidence(
        run=feedback.run,
        revision=feedback.revision,
        event_type="FEEDBACK_ATTRIBUTION_RECORDED",
        action="attribute_generation_feedback",
        payload=payload,
        actor=feedback.actor,
        correlation_id=correlation_id,
    )
