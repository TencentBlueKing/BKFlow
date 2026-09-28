"""Recursive knowledge payload redaction boundary tests."""

import json

import pytest

from bkflow.harness.services.knowledge import contracts as knowledge_contracts
from bkflow.harness.services.knowledge import redaction as redaction_service
from bkflow.harness.services.knowledge.redaction import (
    REDACTED_VALUE,
    redact_knowledge_payload,
)

REDACTED_CYCLE_VALUE = "[REDACTED_CYCLE]"


@pytest.fixture
def sensitive_payload():
    """Provide complete nested credential shapes observed at provider boundaries."""
    private_key = "-----BEGIN PRIVATE KEY-----\nresolved-private-key\n-----END PRIVATE KEY-----"
    return {
        "title": "Restart guide",
        "access_token": "resolved-access-token",
        "appSecret": "resolved-app-secret",
        "headers": {
            "Authorization": "Bearer resolved-bearer-token",
            "Cookie": "sessionid=resolved-cookie",
            "X-Trace-Id": "safe-trace-id",
        },
        "password": "resolved-password",
        "private_key": private_key,
        "nested": [
            {"credentials": {"username": "service", "secret": "resolved-nested-secret"}},
            {"credential": {"value": "resolved-singular-credential"}},
            {"api-token": "resolved-api-token", "note": "safe-note"},
        ],
        "credential_ref": "credential://id/42",
        "body": "A safe body",
    }


def test_redaction_recursively_removes_sensitive_keys_and_keeps_safe_references(sensitive_payload):
    """Dropping recursive key detection would leak one of the supported credential shapes."""
    original = json.loads(json.dumps(sensitive_payload))

    redacted = redact_knowledge_payload(sensitive_payload, "redaction-policy-v1")

    assert redacted == {
        "title": "Restart guide",
        "access_token": REDACTED_VALUE,
        "appSecret": REDACTED_VALUE,
        "headers": {
            "Authorization": REDACTED_VALUE,
            "Cookie": REDACTED_VALUE,
            "X-Trace-Id": "safe-trace-id",
        },
        "password": REDACTED_VALUE,
        "private_key": REDACTED_VALUE,
        "nested": [
            {"credentials": REDACTED_VALUE},
            {"credential": REDACTED_VALUE},
            {"api-token": REDACTED_VALUE, "note": "safe-note"},
        ],
        "credential_ref": "credential://id/42",
        "body": "A safe body",
    }
    assert sensitive_payload == original


def test_private_key_and_authorization_values_are_redacted_even_under_untrusted_generic_keys():
    """Inspecting keys alone would miss secrets embedded in provider-controlled generic fields."""
    payload = {
        "first": "Bearer resolved-bearer-token",
        "second": "-----BEGIN RSA PRIVATE KEY-----\nresolved-private-key\n-----END RSA PRIVATE KEY-----",
    }

    assert redact_knowledge_payload(payload, "redaction-policy-v1") == {
        "first": REDACTED_VALUE,
        "second": REDACTED_VALUE,
    }


@pytest.mark.parametrize(
    "value,secrets,preserved",
    [
        ("prefix Basic dXNlcjpwYXNz suffix", ["dXNlcjpwYXNz"], ["prefix", "suffix"]),
        ("prefix Bearer resolved-bearer suffix", ["resolved-bearer"], ["prefix", "suffix"]),
        ("before api_token=resolved-api-token after", ["resolved-api-token"], ["before", "after"]),
        ("before password=resolved-password after", ["resolved-password"], ["before", "after"]),
        ("before Cookie: session=resolved-cookie\nafter", ["resolved-cookie"], ["before", "after"]),
        (
            "before -----BEGIN PRIVATE KEY-----\nresolved-key\n-----END PRIVATE KEY----- after",
            ["resolved-key"],
            ["before", "after"],
        ),
    ],
)
def test_redaction_removes_embedded_credentials_without_erasing_surrounding_text(value, secrets, preserved):
    """Matching only at position zero or replacing the whole string would leak credentials or useful context."""
    result = redact_knowledge_payload({"text": value}, "redaction-policy-v1")["text"]

    assert REDACTED_VALUE in result
    assert all(secret not in result for secret in secrets)
    assert all(fragment in result for fragment in preserved)


def test_redaction_keeps_ordinary_basic_guidance_that_is_not_an_authorization_value():
    """Treating every word after 'basic' as a credential would corrupt normal workflow guidance."""
    value = "Follow the basic restart guidance before production changes."

    assert redact_knowledge_payload({"text": value}, "redaction-policy-v1") == {"text": value}


def test_redaction_fails_closed_for_a_truncated_private_key_block():
    """Requiring an end marker would expose a truncated private key returned by a bounded provider response."""
    result = redact_knowledge_payload(
        {"text": "safe prefix -----BEGIN PRIVATE KEY-----\nresolved-truncated-key"},
        "redaction-policy-v1",
    )["text"]

    assert result == "safe prefix {}".format(REDACTED_VALUE)


@pytest.mark.parametrize(
    "value,secret",
    [
        ("access_token=resolved-access", "resolved-access"),
        ("app_secret=resolved-app", "resolved-app"),
        ("api_key=resolved-key", "resolved-key"),
        ("token=resolved-token", "resolved-token"),
        ("secret=resolved-secret", "resolved-secret"),
        ("before AccessToken: resolved-camel after", "resolved-camel"),
        ("before tenant-app-secret=resolved-suffix after", "resolved-suffix"),
        ("before api-token: resolved-api after", "resolved-api"),
        ("before passwd=resolved-passwd after", "resolved-passwd"),
        ("before Authorization: opaque-authorization after", "opaque-authorization"),
        ("before credential=resolved-credential after", "resolved-credential"),
        ("before credentials: resolved-credentials after", "resolved-credentials"),
        ("before private-key=resolved-private after", "resolved-private"),
        ("before set-cookie=session=resolved-set-cookie\nafter", "resolved-set-cookie"),
        ("before cookie=session=resolved-cookie after", "resolved-cookie"),
        ("before service_password=resolved-suffix-password after", "resolved-suffix-password"),
        ("before {}_access_token=resolved-long-prefix after".format("x" * 140), "resolved-long-prefix"),
    ],
)
def test_text_assignments_follow_the_complete_mapping_sensitive_key_family(value, secret):
    """A string key accepted by mapping redaction must not bypass the mandatory text baseline."""
    result = redact_knowledge_payload({"text": value}, "unknown-but-valid-policy-label")["text"]

    assert secret not in result
    assert REDACTED_VALUE in result


@pytest.mark.parametrize("credential", ["Bearer abc$def", "Bearer abc:def"])
def test_bearer_redaction_consumes_the_complete_non_whitespace_credential(credential):
    """Restricting Bearer tokens to a URL-safe subset would expose a provider-controlled suffix."""
    result = redact_knowledge_payload(
        {"text": "ordinary prefix {} ordinary suffix".format(credential)},
        "redaction://workflow-guides/future-policy",
    )["text"]

    assert result == "ordinary prefix {} ordinary suffix".format(REDACTED_VALUE)


def test_every_valid_policy_label_selects_the_same_mandatory_builtin_baseline():
    """Treating an unknown label as no-op would let a binding weaken P1 credential redaction."""
    payload = {"text": "before token=resolved-token after"}

    named = redact_knowledge_payload(payload, "redaction://workflow-guides/v1")
    unknown = redact_knowledge_payload(payload, "unknown-but-valid-policy-label")

    assert knowledge_contracts.KNOWLEDGE_REDACTION_BASELINE == "builtin_credential_redaction_v1"
    assert (
        redaction_service.knowledge_redaction_baseline("redaction://workflow-guides/v1")
        == knowledge_contracts.KNOWLEDGE_REDACTION_BASELINE
    )
    assert (
        redaction_service.knowledge_redaction_baseline("unknown-but-valid-policy-label")
        == knowledge_contracts.KNOWLEDGE_REDACTION_BASELINE
    )
    assert named == unknown == {"text": "before token={} after".format(REDACTED_VALUE)}


@pytest.mark.parametrize(
    "credential_ref, expected",
    [
        ("credential://id/1", "credential://id/1"),
        ("credential://id/42", "credential://id/42"),
        ("credential://id/9999999999999999999", "credential://id/9999999999999999999"),
        ("credential://id/0", REDACTED_VALUE),
        ("credential://id/01", REDACTED_VALUE),
        ("credential://id/-1", REDACTED_VALUE),
        ("credential://id/not-a-number", REDACTED_VALUE),
        ("credential://id/1/extra", REDACTED_VALUE),
        ("credential://id/1?token=resolved-provider-secret", REDACTED_VALUE),
        ("credential://id/1#resolved-provider-secret", REDACTED_VALUE),
        ("credential://id/resolved-provider-secret", REDACTED_VALUE),
        ("resolved-provider-secret", REDACTED_VALUE),
        ("Bearer resolved-provider-secret", REDACTED_VALUE),
        ("password=resolved-provider-secret", REDACTED_VALUE),
        ("credential://id/\ud800", REDACTED_VALUE),
        ("credential://id/" + "9" * 240, REDACTED_VALUE),
    ],
)
def test_credential_ref_is_preserved_only_when_it_matches_validator_canonical_form(credential_ref, expected):
    """Any credential ref outside WorkflowValidator's positive-integer canonical form must be redacted."""
    assert redact_knowledge_payload({"credential_ref": credential_ref}, "redaction-policy-v1") == {
        "credential_ref": expected
    }


def test_redaction_replaces_dict_list_and_tuple_cycles_without_mutating_inputs():
    """Recursing without an active-container identity guard would crash before reaching audit or Envelope boundaries."""
    dict_cycle = {}
    dict_cycle["self"] = dict_cycle
    list_cycle = []
    list_cycle.append(list_cycle)
    mixed_list = []
    mixed_tuple = (mixed_list,)
    mixed_list.append(mixed_tuple)
    payload = {"dict": dict_cycle, "list": list_cycle, "tuple": mixed_tuple}

    redacted = redact_knowledge_payload(payload, "redaction-policy-v1")

    assert redacted == {
        "dict": {"self": REDACTED_CYCLE_VALUE},
        "list": [REDACTED_CYCLE_VALUE],
        "tuple": ([REDACTED_CYCLE_VALUE],),
    }
    assert dict_cycle["self"] is dict_cycle
    assert list_cycle[0] is list_cycle
    assert mixed_list[0] is mixed_tuple


def test_redaction_is_called_before_audit_and_envelope_serialization(sensitive_payload):
    """Serializing the raw provider payload before this boundary would persist resolved secrets."""
    safe_payload = redact_knowledge_payload(sensitive_payload, "redaction-policy-v1")

    persisted_audit_payload = json.loads(json.dumps({"provider_response": safe_payload}, sort_keys=True))
    envelope_json = json.dumps(
        {"artifact_refs": [{"type": "knowledge_search", "payload": safe_payload}]},
        sort_keys=True,
    )

    combined = json.dumps(persisted_audit_payload, sort_keys=True) + envelope_json
    assert "resolved-access-token" not in combined
    assert "resolved-app-secret" not in combined
    assert "resolved-cookie" not in combined
    assert "resolved-bearer-token" not in combined
    assert "resolved-password" not in combined
    assert "resolved-private-key" not in combined
    assert "resolved-nested-secret" not in combined
    assert "resolved-singular-credential" not in combined
    assert combined.count(REDACTED_VALUE) >= 9


@pytest.mark.parametrize("policy_version", [None, "", "x" * 129])
def test_redaction_rejects_missing_or_unbounded_policy_version(policy_version):
    """Allowing an implicit policy would make audit and envelope redaction irreproducible."""
    with pytest.raises(ValueError, match="policy_version"):
        redact_knowledge_payload({"password": "resolved-password"}, policy_version)
