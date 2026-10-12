"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""

import json
import re

import pytest

from bkflow.harness.models import CapabilityBinding, HarnessRun, WorkflowPlanRevision
from bkflow.harness.services.canonical import (
    canonical_json_bytes,
    canonical_scope,
    plan_hash,
    schema_hash,
    sha256_json,
)


def plan_inputs(**overrides):
    """Build independent, trusted inputs for a workflow-plan hash."""
    inputs = {
        "canonical_a2flow": {"version": "2.0", "nodes": [{"id": "node_1", "inputs": {"host": "srv-1"}}]},
        "capability_bindings": [
            {
                "node_id": "node_2",
                "capability_ref": "cap:restart",
                "resolved_version": "2.1.0",
                "schema_hash": "b" * 64,
                "credential_ref": "credential://ops/restart",
                "risk": "L1",
            },
            {
                "node_id": "node_1",
                "capability_ref": "cap:lookup",
                "resolved_version": "1.0.0",
                "schema_hash": "a" * 64,
                "credential_ref": None,
                "risk": "L0",
            },
        ],
        "space_id": 42,
        "scope": '["project","42"]',
        "environment": "stag",
        "credential_authorization_scope": {"allow": ["credential://ops/restart"]},
        "execution_policy": {"mode": "draft_only"},
        "risk_policy": {"max_risk": "L1"},
        "retry_policy": {"max_attempts": 2},
        "timeout_policy": {"seconds": 30},
        "compensation_policy": {"on_failure": "none"},
        "postconditions": [{"path": "result.ok", "equals": True}],
    }
    inputs.update(overrides)
    return inputs


def test_canonical_scope_has_one_space_wide_and_scoped_representation():
    """Keep persistence, hashing, replay and draft authorization on one scope representation."""
    assert canonical_scope(None, None) == ""
    assert canonical_scope("project", "42") == '["project","42"]'


def test_canonical_scope_is_reversible_and_does_not_collide_on_delimiters():
    """A delimiter moving between scope fields must never preserve trusted scope identity."""
    left = canonical_scope("a:b", "c")
    right = canonical_scope("a", "b:c")

    assert left == '["a:b","c"]'
    assert right == '["a","b:c"]'
    assert left != right
    assert json.loads(left) == ["a:b", "c"]
    assert json.loads(right) == ["a", "b:c"]


def test_canonical_scope_round_trips_unicode_quotes_backslashes_and_controls():
    """JSON escaping must stay reversible without ASCII-escaping trusted Unicode text."""
    scope_type = '项目:"\\\n'
    scope_value = '值:😀"\\\t'
    serialized = canonical_scope(scope_type, scope_value)

    assert json.loads(serialized) == [scope_type, scope_value]
    assert "项目" in serialized
    assert "😀" in serialized


@pytest.mark.parametrize("scope_type,scope_value", [(None, "42"), ("project", None), ("", "42")])
def test_canonical_scope_rejects_partial_bindings(scope_type, scope_value):
    """Mixed-null or empty scope facts must not be serialized into an ambiguous identity."""
    with pytest.raises(ValueError):
        canonical_scope(scope_type, scope_value)


def test_canonical_scope_enforces_character_and_utf8_boundaries():
    """Accept the persisted 255-character maximum by characters and reject overflow or surrogate text."""
    maximum = canonical_scope("类" * 64, "😀" * 184)

    assert len(maximum) == 255
    assert len(maximum.encode("utf-8")) > 255
    assert json.loads(maximum) == ["类" * 64, "😀" * 184]
    with pytest.raises(ValueError, match="persistence limit"):
        canonical_scope("类" * 64, "😀" * 185)
    with pytest.raises(ValueError, match="invalid text"):
        canonical_scope("project", "bad\ud800")


@pytest.mark.django_db
def test_canonical_scope_character_maximum_fits_harness_run_model():
    """The canonical guard and Django CharField must share one character-count limit."""
    run = HarnessRun(
        platform="bkfara",
        platform_app="bkfara_app",
        actor="dannydeng",
        space_id=42,
        scope=canonical_scope("t" * 64, "v" * 184),
        environment="stag",
        status="VALIDATING",
        policy_version="2026.09",
        mcp_contract_version="p0",
        client_context={"source": "test"},
        artifact_references=[{"type": "test"}],
    )

    run.full_clean()


def test_plan_hash_distinguishes_scopes_that_used_to_share_one_delimited_string():
    """The plan fingerprint must keep delimiter-bearing trusted scopes isolated."""
    left = canonical_scope("a:b", "c")
    right = canonical_scope("a", "b:c")

    assert plan_hash(**plan_inputs(scope=left)) != plan_hash(**plan_inputs(scope=right))


def test_canonical_json_bytes_sorts_mapping_keys_with_exact_wire_form():
    """Catch a canonical serializer that changes the approved JSON wire form."""
    assert canonical_json_bytes({"z": [3, 2], "a": {"name": "值"}}) == b'{"a":{"name":"\xe5\x80\xbc"},"z":[3,2]}'


def test_sha256_json_is_stable_for_reordered_keys_but_not_for_list_order():
    """Catch hashing that treats ordered lists as unordered data."""
    assert sha256_json({"b": 2, "a": ["first", "second"]}) == sha256_json({"a": ["first", "second"], "b": 2})
    assert sha256_json({"a": ["first", "second"], "b": 2}) != sha256_json({"a": ["second", "first"], "b": 2})


def test_hashes_are_lowercase_sha256_hex_and_unicode_is_not_escaped():
    """Catch lossy Unicode encoding or a non-SHA256 digest representation."""
    digest = schema_hash({"description": "重启服务"})

    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert canonical_json_bytes({"description": "重启服务"}) == '{"description":"重启服务"}'.encode()


def test_plan_hash_is_stable_when_capability_binding_order_changes():
    """Catch plan fingerprints that depend on incidental registry result order."""
    inputs = plan_inputs()
    reversed_bindings = list(reversed(inputs["capability_bindings"]))

    assert plan_hash(**inputs) == plan_hash(**plan_inputs(capability_bindings=reversed_bindings))


def test_plan_hash_changes_for_each_approved_security_or_execution_input():
    """Catch omitted scope, binding, or execution-policy inputs in a plan fingerprint."""
    baseline = plan_hash(**plan_inputs())
    binding_mutations = (
        ("node_id", "node_2_changed"),
        ("capability_ref", "cap:restart-other"),
        ("resolved_version", "2.2.0"),
        ("schema_hash", "c" * 64),
        ("credential_ref", "credential://ops/other"),
        ("risk", "L2"),
    )
    changed_inputs = (
        {"canonical_a2flow": {"version": "2.0", "nodes": [{"id": "node_1", "inputs": {"host": "srv-2"}}]}},
        {"space_id": 43},
        {"scope": "project:43"},
        {"environment": "prod"},
        {"credential_authorization_scope": {"allow": ["credential://ops/other"]}},
        {"execution_policy": {"mode": "preview"}},
        {"risk_policy": {"max_risk": "L0"}},
        {"retry_policy": {"max_attempts": 3}},
        {"timeout_policy": {"seconds": 31}},
        {"compensation_policy": {"on_failure": "manual"}},
        {"postconditions": [{"path": "result.ok", "equals": False}]},
    )

    assert all(plan_hash(**plan_inputs(**changed)) != baseline for changed in changed_inputs)
    for field, value in binding_mutations:
        bindings = [dict(binding) for binding in plan_inputs()["capability_bindings"]]
        bindings[0][field] = value
        assert plan_hash(**plan_inputs(capability_bindings=bindings)) != baseline


@pytest.mark.django_db
def test_plan_hash_round_trips_mapping_to_persisted_capability_binding():
    """Catch a plan fingerprint that changes after the binding is persisted."""
    run = HarnessRun.objects.create(
        platform="bkfara",
        platform_app="bkfara_app",
        actor="dannydeng",
        space_id=42,
        scope='["project","42"]',
        environment="stag",
        status="VALIDATING",
        policy_version="2026.09",
        mcp_contract_version="p0",
    )
    revision = WorkflowPlanRevision.objects.create(
        run=run,
        sequence=1,
        intent_spec={},
        canonical_a2flow={"version": "2.0"},
        plan_hash="a" * 64,
    )
    mapping = plan_inputs()["capability_bindings"][0]
    binding = CapabilityBinding.objects.create(revision=revision, **mapping)

    assert plan_hash(**plan_inputs(capability_bindings=[mapping])) == plan_hash(
        **plan_inputs(capability_bindings=[binding])
    )


def test_plan_hash_rejects_missing_required_capability_binding_facts():
    """Catch a malformed binding being coerced into a hash with null security facts."""
    required_fields = ("node_id", "capability_ref", "resolved_version", "schema_hash", "risk")
    for field in required_fields:
        binding = dict(plan_inputs()["capability_bindings"][0])
        binding.pop(field)
        with pytest.raises(ValueError, match=field):
            plan_hash(**plan_inputs(capability_bindings=[binding]))

        binding = dict(plan_inputs()["capability_bindings"][0])
        binding[field] = ""
        with pytest.raises(ValueError, match=field):
            plan_hash(**plan_inputs(capability_bindings=[binding]))


def test_plan_hash_excludes_model_prompt_token_and_transient_metadata():
    """Catch sensitive or non-semantic context leaking into a durable plan fingerprint."""
    baseline = plan_hash(**plan_inputs())
    excluded_context = {
        "model_name": "model-a",
        "conversation_wording": "Please restart the service",
        "display_copy": "Restarting service",
        "token_plaintext": "secret-token",
        "trace_metadata": {"correlation_id": "trace-1"},
    }
    changed_excluded_context = {
        "model_name": "model-b",
        "conversation_wording": "完全不同的对话措辞",
        "display_copy": "different display text",
        "token_plaintext": "another-secret-token",
        "trace_metadata": {"correlation_id": "trace-2", "latency_ms": 99},
    }

    assert plan_hash(**plan_inputs(**excluded_context)) == baseline
    assert plan_hash(**plan_inputs(**changed_excluded_context)) == baseline
