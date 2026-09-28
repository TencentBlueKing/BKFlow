"""Static governance checks for the non-executable P4 attribution rule table."""

import pytest

from bkflow.harness.constants import (
    FeedbackAttributionCategory,
    ImprovementCandidateType,
)
from bkflow.harness.services.feedback.attribution import load_attribution_rules


def test_rule_table_is_versioned_closed_and_covers_every_category():
    """The deployed table has one inspectable schema and complete taxonomy coverage."""
    rules = load_attribution_rules()

    assert rules.version == "p4-attribution-v1"
    assert rules.human_triage_threshold == 0.7
    assert {rule.category for rule in rules.rules} == set(FeedbackAttributionCategory.values)
    assert len({rule.rule_id for rule in rules.rules}) == len(rules.rules)
    assert len({rule.priority for rule in rules.rules}) == len(rules.rules)
    assert all(rule.typed_codes for rule in rules.rules)
    assert all(0 <= rule.confidence <= 1 for rule in rules.rules)


def test_rules_are_exact_typed_data_without_regex_or_executable_expressions():
    """Rule loading exposes only closed fields and literal codes/event requirements."""
    rules = load_attribution_rules()

    for rule in rules.rules:
        assert not hasattr(rule, "expression")
        assert not hasattr(rule, "regex")
        assert all(code.replace("_", "").isalnum() and code == code.upper() for code in rule.typed_codes)
        assert all(event.replace("_", "").isalnum() and event == event.upper() for event in rule.event_types)


def test_runtime_rules_require_evidence_events_and_high_risk_rules_block_first():
    """Plugin/environment need runtime events while high-risk rules produce safeguards."""
    rules = load_attribution_rules()
    by_category = {rule.category: rule for rule in rules.rules}

    for category in ("PLUGIN", "ENVIRONMENT"):
        assert by_category[category].source == "evidence_event"
        assert by_category[category].event_types
    for category in ("PERMISSION", "SCHEMA", "VALIDATOR", "POSTCONDITION"):
        rule = by_category[category]
        if rule.high_risk:
            assert rule.candidate_types[:2] == (
                ImprovementCandidateType.VALIDATOR_POLICY,
                ImprovementCandidateType.EVAL,
            )


def test_loader_rejects_expression_or_unknown_rule_fields(tmp_path):
    """A poisoning attempt cannot add executable matching logic to the rule table."""
    path = tmp_path / "poisoned-rules.yaml"
    path.write_text(
        """version: p4-attribution-v1
human_triage_threshold: 0.7
rules:
  - rule_id: injected
    priority: 1
    category: KNOWLEDGE
    source: any
    typed_codes: [KNOWLEDGE_MISS]
    event_types: []
    confidence: 1.0
    high_risk: false
    candidate_types: [KNOWLEDGE]
    expression: __import__('os').system('false')
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_attribution_rules(str(path))
