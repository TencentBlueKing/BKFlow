"""Deterministic Harness workflow validation contracts."""

from dataclasses import dataclass, replace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.db import DatabaseError

from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.exceptions import IdempotencyConflict, IdempotencyInFlight
from bkflow.harness.services.canonical import canonical_scope, schema_hash, sha256_json
from bkflow.harness.services.capability_ref import encode_capability_ref
from bkflow.harness.services.resolver import CapabilityResolver, ResolvedCapability
from bkflow.harness.services.validator import WorkflowValidator, recompute_p0_plan_hash
from bkflow.pipeline_converter.converters.a2flow_v2.data_models import ConversionResult
from bkflow.plugin.models import OpenPluginCatalogIndex, SpaceOpenPluginAvailability
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService
from bkflow.space.models import Credential, CredentialScopeLevel, CredentialType
from bkflow.utils.api_client import HttpRequestResult


@dataclass
class FixtureResolver:
    """A fresh exact resolver fixture with a single permitted capability."""

    capability: ResolvedCapability
    calls: list

    def resolve(self, capability_ref, expected_schema_hash=None):
        """Return only the selected exact fact while recording the assertion."""
        self.calls.append((capability_ref, expected_schema_hash))
        if capability_ref != self.capability.capability_ref:
            from bkflow.harness.services.resolver import CapabilityResolutionError

            raise CapabilityResolutionError()
        if expected_schema_hash is not None and expected_schema_hash != self.capability.schema_hash:
            from bkflow.harness.services.resolver import SchemaDriftError

            raise SchemaDriftError()
        return self.capability


class FixtureConverter:
    """Conversion fixture that preserves the Harness metadata boundary."""

    def __init__(self, a2flow_data, **kwargs):
        self.a2flow_data = a2flow_data

    def convert_with_metadata(self):
        return ConversionResult(
            pipeline_tree={
                "activities": {"internal-node-1": {}},
                "gateways": {},
                "flows": {},
                "start_event": {},
                "end_event": {},
                "constants": {},
            },
            converter_fingerprint="converter-v2-fixture",
            source_map={"internal-node-1": "node_1"},
        )


@pytest.fixture
def context():
    """Build only server-derived authority facts for a validation request."""
    return TrustedHarnessContext(
        platform_key="bkfara",
        platform_app="bkfara_app",
        actor="dannydeng",
        space_id=42,
        scope_type="project",
        scope_value="42",
        target_environment="stag",
        policy_version="2026.09",
        mcp_contract_version="1.0.0",
        correlation_id="trace-6",
    )


@pytest.fixture
def resolved_capability():
    """Return one Schema-pinned component capability."""
    capability_ref = encode_capability_ref("component", None, "restart", "1.0.0")
    schema = {
        "inputs": [
            {"key": "host", "type": "string", "required": True},
            {"key": "port", "type": "int", "required": False},
        ],
        "outputs": [],
    }
    return ResolvedCapability(
        capability_ref=capability_ref,
        plugin_type="component",
        code="restart",
        source_key=None,
        resolved_version="1.0.0",
        schema_hash=schema_hash(schema),
        schema=schema,
        risk_level="L1",
        conversion_metadata={"kind": "component", "wrapper_code": "restart", "wrapper_version": "1.0.0"},
        conversion_fingerprint=schema_hash(
            {"kind": "component", "wrapper_code": "restart", "wrapper_version": "1.0.0"}
        ),
    )


@pytest.fixture
def request_data(resolved_capability):
    """Build a minimal valid P0 request without client authority fields."""
    return {
        "intent_spec": {"goal": "restart service"},
        "a2flow": {
            "version": "2.0",
            "name": "restart",
            "nodes": [
                {
                    "id": "node_1",
                    "name": "restart",
                    "code": "restart",
                    "plugin_type": "component",
                    "inputs": {"host": "srv-1"},
                    "next": "end",
                }
            ],
        },
        "bindings": [
            {
                "node_id": "node_1",
                "capability_ref": resolved_capability.capability_ref,
                "schema_hash": resolved_capability.schema_hash,
                "credential_ref": None,
            }
        ],
        "idempotency_key": "validation-key-1",
        "client_context": {"conversation_ref": "opaque"},
    }


@pytest.mark.django_db
def test_validate_workflow_persists_exact_revision_report_and_replays_first_write(
    context, resolved_capability, request_data
):
    """Catch a validation path that skips pins, report metadata, or first-write replay."""
    resolver = FixtureResolver(resolved_capability, [])
    validator = WorkflowValidator(
        context, resolver=resolver, converter_class=FixtureConverter, pipeline_validator=lambda tree: None
    )

    accepted = validator.validate_workflow(request_data)
    replayed = validator.validate_workflow(request_data)

    assert accepted["ok"] is True
    assert accepted["status"] == "VALIDATING"
    assert accepted["revision_id"]
    assert accepted["plan_hash"]
    assert accepted["artifact_refs"] == [
        {
            "validator_version": validator.VERSION,
            "converter_fingerprint": "converter-v2-fixture",
            "pipeline_tree_hash": accepted["artifact_refs"][0]["pipeline_tree_hash"],
            "report_id": accepted["artifact_refs"][0]["report_id"],
        }
    ]
    assert replayed == accepted
    assert resolver.calls == [(resolved_capability.capability_ref, None)]
    from bkflow.harness.models import CapabilityBinding, ValidationReport

    binding = CapabilityBinding.objects.get()
    assert binding.conversion_fingerprint == resolved_capability.conversion_fingerprint
    assert ValidationReport.objects.get().result["capability_conversion_fingerprints"] == {
        "node_1": resolved_capability.conversion_fingerprint
    }


@pytest.mark.django_db
def test_failed_first_validation_keeps_a_run_level_report_and_replays(context, resolved_capability, request_data):
    """Catch failures that roll back the implicit run or create a draft/revision."""
    request_data["a2flow"]["nodes"][0]["inputs"] = {}
    validator = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    )

    failed = validator.validate_workflow(request_data)
    replayed = validator.validate_workflow(request_data)

    assert failed["ok"] is False
    assert failed["status"] == "NEEDS_REPAIR"
    assert failed["revision_id"] is None
    assert failed["errors"] == [
        {
            "category": "VALIDATION",
            "code": "SCHEMA_VALIDATION_ERROR",
            "path": "nodes.node_1.inputs.host",
            "repairable": True,
            "retryable": False,
            "message": "The workflow input does not match its schema.",
            "suggested_action": "repair_a2flow",
        }
    ]
    assert replayed == failed
    from bkflow.harness.models import ValidationReport, WorkflowPlanRevision

    assert WorkflowPlanRevision.objects.count() == 0
    assert ValidationReport.objects.get().revision is None


@pytest.mark.django_db
def test_repair_creates_a_new_child_revision_without_mutating_the_accepted_parent(
    context, resolved_capability, request_data
):
    """Catch repair logic that overwrites the immutable accepted plan."""
    validator = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    )
    first = validator.validate_workflow(request_data)
    repair = dict(request_data, run_id=first["run_id"], idempotency_key="validation-key-2")
    repair["a2flow"] = dict(request_data["a2flow"], name="restart again")

    second = validator.validate_workflow(repair)

    from bkflow.harness.models import WorkflowPlanRevision

    revisions = list(WorkflowPlanRevision.objects.order_by("sequence"))
    assert second["revision_id"] != first["revision_id"]
    assert [revision.sequence for revision in revisions] == [1, 2]
    assert str(revisions[1].parent_revision_id) == first["revision_id"]
    assert revisions[0].canonical_a2flow["name"] == "restart"


@pytest.mark.django_db
def test_plan_hash_assertion_is_optimistic_and_never_client_authority(context, resolved_capability, request_data):
    """Catch a mismatched client plan assertion or forged authority becoming durable facts."""
    request_data["expected_plan_hash"] = "0" * 64
    request_data.update({"space_id": 999, "actor": "forged", "platform_app": "forged"})
    validator = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    )

    failed = validator.validate_workflow(request_data)

    assert failed["ok"] is False
    assert failed["errors"][0]["code"] == "PLAN_HASH_MISMATCH"
    from bkflow.harness.models import HarnessRun

    run = HarnessRun.objects.get()
    assert (run.space_id, run.actor, run.platform_app) == (42, "dannydeng", "bkfara_app")


@pytest.mark.django_db
def test_resolves_every_reference_before_rejecting_duplicate_bindings(context, resolved_capability, request_data):
    """Catch schema drift checks that run before complete fresh reference resolution."""
    duplicate = dict(request_data["bindings"][0], schema_hash="0" * 64)
    request_data["bindings"].append(duplicate)
    resolver = FixtureResolver(resolved_capability, [])
    validator = WorkflowValidator(
        context,
        resolver=resolver,
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    )

    failed = validator.validate_workflow(request_data)

    assert resolver.calls == [
        (resolved_capability.capability_ref, None),
        (resolved_capability.capability_ref, None),
    ]
    assert failed["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"


@pytest.mark.django_db
def test_untrusted_run_id_returns_a_permission_envelope(context, resolved_capability, request_data):
    """Catch a cross-run probe escaping the stable, secret-free validation Envelope."""
    request_data["run_id"] = "00000000-0000-0000-0000-000000000001"
    validator = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    )

    rejected = validator.validate_workflow(request_data)

    assert rejected["ok"] is False
    assert rejected["errors"][0]["code"] == "CAPABILITY_FORBIDDEN"
    assert rejected["errors"][0]["category"] == "PERMISSION"


@pytest.mark.django_db
def test_malformed_run_id_returns_a_closed_permission_envelope(context, resolved_capability, request_data):
    """Non-string UUID input must never reach Django's UUID conversion path."""
    request_data["run_id"] = ["not-a-uuid"]
    response = WorkflowValidator(
        context, resolver=FixtureResolver(resolved_capability, []), converter_class=FixtureConverter
    ).validate_workflow(request_data)

    assert response["ok"] is False
    assert response["errors"] == [
        {
            "category": "PERMISSION",
            "code": "CAPABILITY_FORBIDDEN",
            "path": "run_id",
            "repairable": False,
            "retryable": False,
            "message": "The selected capability is not permitted.",
            "suggested_action": "search_workflow_capabilities",
        }
    ]


@pytest.mark.django_db
@patch("bkflow.harness.services.validator.HarnessRun.objects.get", side_effect=DatabaseError("sentinel-db"))
def test_trusted_run_storage_error_returns_retryable_envelope(_get, context, resolved_capability, request_data):
    """The public entry point must contain pre-idempotency trusted-run storage failures."""
    request_data["run_id"] = "00000000-0000-0000-0000-000000000001"
    response = WorkflowValidator(
        context, resolver=FixtureResolver(resolved_capability, []), converter_class=FixtureConverter
    ).validate_workflow(request_data)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert response["errors"][0]["retryable"] is True


@pytest.mark.django_db
@patch("bkflow.harness.services.validator.execute_idempotent", side_effect=IdempotencyInFlight())
def test_idempotency_inflight_returns_public_retryable_envelope(_execute, context, resolved_capability, request_data):
    """An in-flight record is a stable retryable public response, not an exception."""
    response = WorkflowValidator(
        context, resolver=FixtureResolver(resolved_capability, []), converter_class=FixtureConverter
    ).validate_workflow(request_data)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert response["errors"][0]["retryable"] is True


@pytest.mark.django_db
@patch("bkflow.harness.models.HarnessIdempotencyRecord.objects.select_related", side_effect=DatabaseError("db"))
@patch("bkflow.harness.services.validator.execute_idempotent", side_effect=IdempotencyConflict())
def test_idempotency_conflict_lookup_storage_error_returns_retryable_envelope(
    _execute, _lookup, context, resolved_capability, request_data
):
    """Conflict diagnostics must not let its own storage query escape the Envelope."""
    response = WorkflowValidator(
        context, resolver=FixtureResolver(resolved_capability, []), converter_class=FixtureConverter
    ).validate_workflow(request_data)

    assert response["ok"] is False
    assert response["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert response["errors"][0]["retryable"] is True


@pytest.mark.django_db
def test_binding_identity_must_match_the_activity_before_conversion(context, resolved_capability, request_data):
    """Catch a converter being allowed to select a different activity than the resolved pin."""
    request_data["a2flow"]["nodes"][0]["code"] = "sleep_timer"
    validator = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    )

    rejected = validator.validate_workflow(request_data)

    assert rejected["ok"] is False
    assert rejected["errors"][0]["code"] == "SCHEMA_DRIFT"
    assert rejected["errors"][0]["path"] == "nodes.node_1.code"


@pytest.mark.django_db
def test_nested_secret_is_never_written_to_a_durable_artifact(context, resolved_capability, request_data):
    """Catch recursive secret-bearing input or intent data reaching revision/report JSON."""
    sentinel = "do-not-persist-raw-secret"
    request_data["intent_spec"] = {"request": {"Authorization": sentinel}}
    validator = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    )

    rejected = validator.validate_workflow(request_data)

    from bkflow.harness.models import ValidationReport, WorkflowPlanRevision

    assert rejected["ok"] is False
    assert sentinel not in str(rejected)
    assert WorkflowPlanRevision.objects.count() == 0
    assert sentinel not in str(ValidationReport.objects.values("result", "errors", "warnings").first())


@pytest.mark.django_db
def test_existing_run_requires_every_trusted_context_dimension(context, resolved_capability, request_data):
    """Catch reuse of a run after a server-derived deployment context changes."""
    validator = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    )
    accepted = validator.validate_workflow(request_data)
    changed_context = TrustedHarnessContext(
        platform_key=context.platform_key,
        platform_app=context.platform_app,
        actor=context.actor,
        space_id=context.space_id,
        scope_type=context.scope_type,
        scope_value=context.scope_value,
        target_environment="prod",
        policy_version=context.policy_version,
        mcp_contract_version=context.mcp_contract_version,
        correlation_id="trace-context-drift",
    )
    retry = dict(request_data, run_id=accepted["run_id"], idempotency_key="context-drift")

    rejected = WorkflowValidator(
        changed_context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    ).validate_workflow(retry)

    assert rejected["ok"] is False
    assert rejected["errors"][0]["category"] == "PERMISSION"
    assert rejected["errors"][0]["code"] == "TRUSTED_CONTEXT_STALE"


def test_run_context_match_rejects_scopes_that_only_share_delimited_text(context):
    """Run reuse must compare the injective trusted scope rather than an ambiguous concatenation."""
    run = SimpleNamespace(
        platform=context.platform_key,
        platform_app=context.platform_app,
        actor=context.actor,
        space_id=context.space_id,
        scope=canonical_scope("a:b", "c"),
        environment=context.target_environment,
        policy_version=context.policy_version,
        mcp_contract_version=context.mcp_contract_version,
    )
    changed_context = replace(context, scope_type="a", scope_value="b:c")

    assert WorkflowValidator(changed_context)._run_matches_context(run) is False


@pytest.mark.django_db
def test_pre_run_idempotency_does_not_replay_across_formerly_colliding_scopes(
    context, resolved_capability, request_data
):
    """A same-key request in another delimiter-bearing scope must not replay the first scope's run."""
    first_context = replace(context, scope_type="a:b", scope_value="c")
    second_context = replace(context, scope_type="a", scope_value="b:c")
    first = WorkflowValidator(
        first_context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    ).validate_workflow(request_data)

    rejected = WorkflowValidator(
        second_context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    ).validate_workflow(request_data)

    from bkflow.harness.models import HarnessRun

    assert first["ok"] is True
    assert rejected["ok"] is False
    assert rejected["run_id"] is None
    assert rejected["errors"][0]["code"] == "TRUSTED_CONTEXT_STALE"
    assert HarnessRun.objects.count() == 1


@pytest.mark.django_db
def test_client_policy_cannot_change_a_reproducible_plan_hash(context, resolved_capability, request_data):
    """Catch client policy JSON becoming a discarded but hash-significant plan fact."""
    validator = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    )
    first = validator.validate_workflow(request_data)
    policy_attempt = dict(request_data, idempotency_key="client-policy")
    policy_attempt["execution_policy"] = {"mode": "execute_now"}
    policy_attempt["retry_policy"] = {"times": 999}
    second = validator.validate_workflow(policy_attempt)

    assert first["ok"] is second["ok"] is True
    assert second["plan_hash"] == first["plan_hash"]

    from bkflow.harness.models import WorkflowPlanRevision

    revision = WorkflowPlanRevision.objects.get(id=first["revision_id"])
    assert recompute_p0_plan_hash(revision) == first["plan_hash"]


@pytest.mark.django_db
def test_nested_json_schema_and_hook_wrapper_keep_the_exact_repair_path(context, resolved_capability, request_data):
    """Catch dropped enum/object constraints or a valid dynamic-template wrapper being erased."""
    schema = {
        "inputs": [
            {
                "key": "host",
                "required": True,
                "schema": {
                    "type": "object",
                    "properties": {"port": {"type": "number", "minimum": 1}, "mode": {"enum": ["safe"]}},
                    "required": ["port", "mode"],
                    "additionalProperties": False,
                },
            }
        ],
        "outputs": [],
    }
    capability = ResolvedCapability(
        capability_ref=resolved_capability.capability_ref,
        plugin_type="component",
        code="restart",
        source_key=None,
        resolved_version="1.0.0",
        schema_hash=schema_hash(schema),
        schema=schema,
        risk_level="L1",
    )
    request_data["bindings"][0]["schema_hash"] = capability.schema_hash
    request_data["a2flow"]["nodes"][0]["inputs"] = {"host": {"port": 0, "mode": "unsafe"}}
    validator = WorkflowValidator(
        context,
        resolver=FixtureResolver(capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    )

    rejected = validator.validate_workflow(request_data)

    assert rejected["errors"][0]["path"].startswith("nodes.node_1.inputs.host")


@pytest.mark.django_db
def test_error_contract_has_safe_message_and_suggested_action(context, resolved_capability, request_data):
    """Catch repair responses that omit the action data a bounded repair loop needs."""
    request_data["a2flow"]["nodes"][0]["inputs"] = {}
    rejected = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    ).validate_workflow(request_data)

    error = rejected["errors"][0]
    assert error["message"]
    assert error["suggested_action"] == "repair_a2flow"


@pytest.mark.django_db
@pytest.mark.parametrize("secret_key", ["apiToken", "accessToken", "clientSecret", "authHeaders", "TOKEN.raw-secret"])
def test_sensitive_aliases_are_rejected_without_echoing_untrusted_key(
    context, resolved_capability, request_data, secret_key
):
    """A normalized sensitive alias must never reach an error path or durable JSON."""
    sentinel = "sentinel-never-durable"
    request_data["intent_spec"] = {"nested": {secret_key: sentinel}}
    validator = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    )

    rejected = validator.validate_workflow(request_data)

    assert rejected["ok"] is False
    assert sentinel not in str(rejected)
    assert secret_key not in str(rejected)
    assert rejected["errors"][0]["path"] == "intent_spec.<field>"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "target,value",
    [
        ("intent", "Bearer C2-SENTINEL"),
        ("a2flow", "x_bkapi_authorization: C2-SENTINEL"),
        ("client_context", "credential://id/C2-SENTINEL"),
        ("intent", "access_token=C2-SENTINEL"),
        ("intent", 'clientSecret: "C2-SENTINEL"'),
    ],
)
def test_secret_shaped_values_under_innocuous_keys_stop_before_resolution_and_persistence(
    context, resolved_capability, request_data, target, value
):
    """Value-level secret forms cannot bypass the existing sensitive-key policy."""
    if target == "intent":
        request_data["intent_spec"] = {"goal": value}
    elif target == "a2flow":
        request_data["a2flow"]["name"] = value
    else:
        request_data["client_context"] = {"conversation_ref": value}
    resolver = FixtureResolver(resolved_capability, [])
    validator = WorkflowValidator(
        context,
        resolver=resolver,
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    )

    rejected = validator.validate_workflow(request_data)

    from bkflow.harness.models import (
        HarnessIdempotencyRecord,
        HarnessRun,
        ValidationReport,
        WorkflowPlanRevision,
    )

    assert rejected["ok"] is False
    assert rejected["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert "C2-SENTINEL" not in str(rejected)
    assert resolver.calls == []
    assert HarnessRun.objects.count() == 0
    assert WorkflowPlanRevision.objects.count() == 0
    assert ValidationReport.objects.count() == 0
    assert HarnessIdempotencyRecord.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "idempotency_key",
    [
        "Bearer C2-IDEMPOTENCY-SENTINEL",
        "authorization=C2-IDEMPOTENCY-SENTINEL",
        "bad\ud800",
        "x" * 256,
    ],
)
def test_unsafe_validation_idempotency_key_is_rejected_before_it_is_hashed_or_stored(
    context, resolved_capability, request_data, idempotency_key
):
    """The raw idempotency namespace must satisfy the secret, UTF-8 and model bounds itself."""
    request_data["idempotency_key"] = idempotency_key
    resolver = FixtureResolver(resolved_capability, [])
    rejected = WorkflowValidator(
        context,
        resolver=resolver,
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    ).validate_workflow(request_data)

    from bkflow.harness.models import HarnessIdempotencyRecord, HarnessRun

    assert rejected["ok"] is False
    assert rejected["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert rejected["errors"][0]["path"] == "idempotency_key"
    assert "C2-IDEMPOTENCY-SENTINEL" not in str(rejected)
    assert resolver.calls == []
    assert HarnessRun.objects.count() == 0
    assert HarnessIdempotencyRecord.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field,value,path",
    [
        ("intent_spec", {"goal": "x" * 1000000}, "intent_spec.<field>"),
        ("a2flow", {"name": "x" * 1000000, "version": "2.0", "nodes": []}, "a2flow.<field>"),
        ("intent_spec", {"items": list(range(1000))}, "intent_spec.<field>"),
    ],
)
def test_durable_json_is_bounded_before_run_or_report_creation(
    context, resolved_capability, request_data, field, value, path
):
    """Oversized persisted JSON must fail before any immutable artifact is written."""
    request_data[field] = value
    validator = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    )

    rejected = validator.validate_workflow(request_data)

    from bkflow.harness.models import HarnessRun, ValidationReport, WorkflowPlanRevision

    assert rejected["ok"] is False
    assert rejected["errors"][0]["path"] == path
    assert HarnessRun.objects.count() == 0
    assert WorkflowPlanRevision.objects.count() == 0
    assert ValidationReport.objects.count() == 0


@pytest.mark.django_db
def test_resolves_bounded_binding_references_before_canonical_a2flow_parse(context, resolved_capability, request_data):
    """Registry freshness must precede later Pydantic-only structural rejection."""
    request_data["a2flow"]["unknown_wire_field"] = True
    resolver = FixtureResolver(resolved_capability, [])
    rejected = WorkflowValidator(
        context, resolver=resolver, converter_class=FixtureConverter, pipeline_validator=lambda tree: None
    ).validate_workflow(request_data)

    assert resolver.calls == [(resolved_capability.capability_ref, None)]
    assert rejected["errors"][0]["code"] == "A2FLOW_CONVERSION_ERROR"


@pytest.mark.django_db
def test_missing_activity_code_is_in_the_binding_universe_before_canonical_parse(
    context, resolved_capability, request_data
):
    """Every Activity ID needs a binding even when its later semantic code is malformed."""
    request_data["a2flow"]["nodes"][0].pop("code")
    request_data["bindings"] = []
    resolver = FixtureResolver(resolved_capability, [])
    rejected = WorkflowValidator(
        context, resolver=resolver, converter_class=FixtureConverter, pipeline_validator=lambda tree: None
    ).validate_workflow(request_data)

    assert resolver.calls == []
    assert rejected["errors"][0]["path"] == "bindings.node_1"


@pytest.mark.django_db
def test_duplicate_activity_ids_and_binding_ids_are_resolved_before_identity_checks(
    context, resolved_capability, request_data
):
    """The bounded resolver pass is complete even when later wire identity checks fail."""
    request_data["a2flow"]["nodes"].append(dict(request_data["a2flow"]["nodes"][0]))
    request_data["bindings"].append(dict(request_data["bindings"][0]))
    resolver = FixtureResolver(resolved_capability, [])

    rejected = WorkflowValidator(
        context, resolver=resolver, converter_class=FixtureConverter, pipeline_validator=lambda tree: None
    ).validate_workflow(request_data)

    assert resolver.calls == [(resolved_capability.capability_ref, None)] * 2
    assert rejected["errors"][0]["path"] == "nodes.node_1.id"


@pytest.mark.django_db
def test_hook_wrapper_keeps_legacy_plain_value_and_validates_declared_variable_references(
    context, resolved_capability, request_data
):
    """Hook values are legacy opaque values unless they contain a declared variable reference."""
    request_data["a2flow"]["nodes"][0]["inputs"] = {"host": {"hook": True, "need_render": False, "value": "test"}}
    request_data["a2flow"]["variables"] = [{"key": "${host}", "name": "host", "custom_type": ""}]
    validator = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    )

    accepted = validator.validate_workflow(request_data)
    assert accepted["ok"] is True

    missing = dict(request_data, idempotency_key="missing-hook-variable")
    missing["a2flow"] = dict(request_data["a2flow"])
    missing["a2flow"]["nodes"] = [dict(request_data["a2flow"]["nodes"][0])]
    missing["a2flow"]["nodes"][0]["inputs"] = {"host": {"hook": True, "need_render": False, "value": "${missing}"}}
    rejected = validator.validate_workflow(missing)
    assert rejected["errors"][0]["path"] == "nodes.node_1.inputs.host.value"


@pytest.mark.django_db
def test_legacy_two_key_hook_wrapper_is_accepted_and_canonicalized(context, resolved_capability, request_data):
    """The converter-compatible legacy hook form keeps working while durable a2flow is canonical."""
    request_data["a2flow"]["nodes"][0]["inputs"] = {"host": {"hook": False, "value": "srv-1"}}
    accepted = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    ).validate_workflow(request_data)

    from bkflow.harness.models import WorkflowPlanRevision

    assert accepted["ok"] is True
    assert WorkflowPlanRevision.objects.get().canonical_a2flow["nodes"][0]["data"]["host"] == {
        "hook": False,
        "need_render": True,
        "value": "srv-1",
    }


@pytest.mark.django_db
def test_binding_dto_rejects_unknown_sensitive_key_before_hash_or_resolution(
    context, resolved_capability, request_data
):
    """Binding extras are outside the request contract and must not enter idempotency hashing."""
    request_data["bindings"][0]["apiToken"] = "RAW-SENTINEL"
    resolver = FixtureResolver(resolved_capability, [])
    rejected = WorkflowValidator(
        context, resolver=resolver, converter_class=FixtureConverter, pipeline_validator=lambda tree: None
    ).validate_workflow(request_data)

    from bkflow.harness.models import HarnessIdempotencyRecord

    assert rejected["ok"] is False
    assert rejected["errors"][0]["path"] == "bindings.<index>"
    assert "RAW-SENTINEL" not in str(rejected)
    assert resolver.calls == []
    assert HarnessIdempotencyRecord.objects.count() == 0


def test_closed_binding_dto_is_canonical_equivalent_for_request_hash(context, resolved_capability, request_data):
    """Semantically identical binding wire order cannot produce distinct idempotency identities."""
    validator = WorkflowValidator(
        context, resolver=FixtureResolver(resolved_capability, []), converter_class=FixtureConverter
    )
    reversed_binding = {
        "credential_ref": None,
        "schema_hash": resolved_capability.schema_hash,
        "capability_ref": resolved_capability.capability_ref,
        "node_id": "node_1",
    }

    assert validator._closed_bindings(request_data["bindings"]) == validator._closed_bindings([reversed_binding])


def test_retryable_input_envelope_uses_the_frozen_code_category(context, resolved_capability, request_data):
    """A retryable code cannot be relabeled as ordinary validation by the envelope helper."""
    validator = WorkflowValidator(
        context, resolver=FixtureResolver(resolved_capability, []), converter_class=FixtureConverter
    )

    response = validator._input_failure(request_data, "RETRYABLE_INFRA", path="validation", retryable=True)

    assert response["errors"] == [
        {
            "category": "RETRYABLE_INFRA",
            "code": "RETRYABLE_INFRA",
            "path": "validation",
            "repairable": True,
            "retryable": True,
            "message": "Validation infrastructure is temporarily unavailable.",
            "suggested_action": "retry_validation",
        }
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "schema,value",
    [
        ({"type": "integer"}, 3),
        ({"type": "object", "properties": {"host": {"type": "string"}}, "required": ["host"]}, {"host": "a"}),
        ({"type": "array", "items": {"type": "string"}}, ["a", "b"]),
    ],
)
def test_hook_false_validates_full_json_schema_for_scalar_object_and_array(
    context, resolved_capability, request_data, schema, value
):
    """The closed legacy wrapper cannot bypass the selected input JSON Schema."""
    resolved_schema = {"inputs": [{"key": "host", "required": True, "schema": schema}], "outputs": []}
    resolved_capability = replace(resolved_capability, schema=resolved_schema, schema_hash=schema_hash(resolved_schema))
    request_data["bindings"][0]["schema_hash"] = resolved_capability.schema_hash
    request_data["a2flow"]["nodes"][0]["inputs"] = {"host": {"hook": False, "need_render": True, "value": value}}
    accepted = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    ).validate_workflow(request_data)

    assert accepted["ok"] is True


@pytest.mark.django_db
def test_same_key_different_request_is_user_input_conflict_not_context_drift(
    context, resolved_capability, request_data
):
    """Payload collision and a stale trusted run are distinct repair actions."""
    validator = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    )
    assert validator.validate_workflow(request_data)["ok"] is True
    conflicting = dict(request_data)
    conflicting["a2flow"] = dict(request_data["a2flow"], name="different request")

    rejected = validator.validate_workflow(conflicting)

    assert rejected["errors"][0]["code"] == "IDEMPOTENCY_CONFLICT"
    assert rejected["errors"][0]["category"] == "USER_INPUT"
    assert rejected["next_actions"] == ["start_new_validation"]


@pytest.mark.django_db
def test_completed_pre_run_idempotency_record_with_changed_server_context_is_permission_stale(
    context, resolved_capability, request_data
):
    """Only a completed pre-run record whose attached run changed context is trusted-context stale."""
    validator = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    )
    assert validator.validate_workflow(request_data)["ok"] is True
    changed_context = replace(context, target_environment="prod", correlation_id="pre-run-context-drift")

    rejected = WorkflowValidator(
        changed_context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    ).validate_workflow(request_data)

    assert rejected["errors"][0]["code"] == "TRUSTED_CONTEXT_STALE"
    assert rejected["errors"][0]["category"] == "PERMISSION"


@pytest.mark.django_db
def test_credential_reference_is_existing_same_space_scope_authorized_and_never_persists_a_secret(
    context, resolved_capability, request_data
):
    """Only the trusted canonical credential ID may cross the durable Harness boundary."""
    credential = Credential.objects.create(
        space_id=context.space_id,
        name="harness-test-credential",
        type=CredentialType.BK_APP.value,
        content={"bk_app_code": "app", "bk_app_secret": "sentinel-never-durable"},
        scope_level=CredentialScopeLevel.ALL.value,
    )
    request_data["bindings"][0]["credential_ref"] = "credential://id/{}".format(credential.id)
    accepted = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    ).validate_workflow(request_data)

    from bkflow.harness.models import (
        CapabilityBinding,
        HarnessIdempotencyRecord,
        ValidationReport,
    )

    assert accepted["ok"] is True
    assert CapabilityBinding.objects.get().credential_ref == "credential://id/{}".format(credential.id)
    durable = "{}{}{}".format(
        CapabilityBinding.objects.values("credential_ref").first(),
        ValidationReport.objects.values("result", "errors").first(),
        HarnessIdempotencyRecord.objects.values("response_snapshot").first(),
    )
    assert "sentinel-never-durable" not in durable


@pytest.mark.django_db
@pytest.mark.parametrize(
    "space_id,scope_level", [(99, CredentialScopeLevel.ALL.value), (42, CredentialScopeLevel.NONE.value)]
)
def test_credential_reference_rejects_foreign_or_unusable_credential(
    context, resolved_capability, request_data, space_id, scope_level
):
    """A syntactically valid opaque reference cannot borrow another space or disabled credential."""
    credential = Credential.objects.create(
        space_id=space_id,
        name="blocked-credential-{}".format(space_id),
        type=CredentialType.BK_APP.value,
        content={"bk_app_code": "app", "bk_app_secret": "secret"},
        scope_level=scope_level,
    )
    request_data["bindings"][0]["credential_ref"] = "credential://id/{}".format(credential.id)
    rejected = WorkflowValidator(
        context,
        resolver=FixtureResolver(resolved_capability, []),
        converter_class=FixtureConverter,
        pipeline_validator=lambda tree: None,
    ).validate_workflow(request_data)

    assert rejected["errors"][0]["code"] == "CAPABILITY_FORBIDDEN"


@pytest.mark.django_db
def test_provider_infrastructure_failure_is_retryable_and_the_same_key_can_succeed(
    context, resolved_capability, request_data
):
    """Only proven exact-version drift becomes semantic repair; a transient provider error is retryable."""
    from bkflow.harness.constants import IdempotencyRecordStatus
    from bkflow.harness.models import HarnessIdempotencyRecord
    from bkflow.harness.services.resolver import ProviderInfrastructureError

    class FlakyResolver(FixtureResolver):
        def __init__(self, capability, calls):
            super().__init__(capability, calls)
            self.unavailable = True

        def resolve(self, capability_ref, expected_schema_hash=None):
            if self.unavailable:
                self.unavailable = False
                raise ProviderInfrastructureError()
            return super().resolve(capability_ref, expected_schema_hash)

    resolver = FlakyResolver(resolved_capability, [])
    validator = WorkflowValidator(
        context, resolver=resolver, converter_class=FixtureConverter, pipeline_validator=lambda tree: None
    )

    transient = validator.validate_workflow(request_data)

    assert transient["errors"][0]["code"] == "RETRYABLE_INFRA"
    assert transient["errors"][0]["retryable"] is True
    assert HarnessIdempotencyRecord.objects.get().status == IdempotencyRecordStatus.FAILED.value
    recovered = validator.validate_workflow(request_data)
    assert recovered["ok"] is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "plugin_type,source_key,code,version,inputs,conversion_metadata",
    [
        (
            "component",
            None,
            "sleep_timer",
            "v1.0.0",
            {"bk_timing": 1},
            {"kind": "component", "wrapper_code": "sleep_timer", "wrapper_version": "v1.0.0"},
        ),
        (
            "remote_plugin",
            None,
            "remote_test",
            "2.0.0",
            {},
            {
                "kind": "remote_plugin",
                "wrapper_code": "remote_plugin",
                "wrapper_version": "1.0.0",
                "remote_plugin_version": "2.0.0",
            },
        ),
        (
            "uniform_api",
            "source-a",
            "uniform_test",
            "4.2.0",
            {},
            {
                "kind": "uniform_api",
                "wrapper_code": "uniform_api",
                "wrapper_version": "v4.0.0",
                "source_key": "source-a",
                "plugin_id": "uniform_test",
                "plugin_version": "4.2.0",
                "url": "https://registry.example/api",
                "method": "POST",
                "credential_key": "gateway-key",
            },
        ),
    ],
)
def test_real_resolver_converter_and_validator_handler_keep_exact_governed_identity(
    context, plugin_type, source_key, code, version, inputs, conversion_metadata
):
    """The Task5 registry boundary is the only fake in the end-to-end Harness validation path."""
    capability_ref = encode_capability_ref(plugin_type, source_key, code, version)
    schema = {
        "version": version,
        "resolved_version": version,
        "inputs": [{"key": key, "required": True, "type": "int"} for key in inputs],
        "outputs": [],
        "conversion_metadata": conversion_metadata,
    }

    class RegistryBoundary:
        def list_plugins(self, limit=100, offset=0, **kwargs):
            plugins = [{"plugin_type": plugin_type, "source_key": source_key, "code": code, "version": version}]
            return plugins[offset : offset + limit], len(plugins)

        def get_plugin_schema(self, **kwargs):
            assert kwargs["code"] == code
            assert kwargs["source_key"] == source_key
            assert kwargs["include_conversion_metadata"] is True
            return schema

        def manifest_identity_exists(self, *args):
            return True

    resolver = CapabilityResolver(
        RegistryBoundary(),
        manifest={
            "manifest_version": "p0-v1",
            "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "unknown"},
            "capabilities": [],
        },
    )
    request = {
        "intent_spec": {"goal": "integration"},
        "a2flow": {
            "version": "2.0",
            "name": "real-task5-chain",
            "nodes": [
                {
                    "id": "node_1",
                    "name": code,
                    "code": code,
                    "plugin_type": plugin_type,
                    "inputs": inputs,
                    "next": "end",
                }
            ],
        },
        "bindings": [
            {
                "node_id": "node_1",
                "capability_ref": capability_ref,
                "schema_hash": schema_hash({"inputs": schema["inputs"], "outputs": []}),
                "credential_ref": None,
            }
        ],
        "idempotency_key": "real-chain-{}".format(plugin_type),
        "client_context": {"conversation_ref": "integration"},
    }

    accepted = WorkflowValidator(context, resolver=resolver).validate_workflow(request)

    from bkflow.harness.models import (
        CapabilityBinding,
        ValidationReport,
        WorkflowPlanRevision,
    )

    assert accepted["ok"] is True
    binding = CapabilityBinding.objects.get()
    report = ValidationReport.objects.get()
    revision = WorkflowPlanRevision.objects.get()
    assert binding.capability_ref == capability_ref
    assert binding.resolved_version == version
    assert binding.conversion_fingerprint == schema_hash(conversion_metadata)
    assert report.result["capability_conversion_fingerprints"]["node_1"] == schema_hash(conversion_metadata)
    tree = (
        WorkflowValidator(context, resolver=resolver)
        ._convert(revision.canonical_a2flow, [{"node_id": "node_1", "capability": resolver.resolve(capability_ref)}])
        .pipeline_tree
    )
    activity = next(iter(tree["activities"]))
    component_data = tree["activities"][activity]["component"]["data"]
    if plugin_type == "uniform_api":
        assert component_data["uniform_api_plugin_id"]["value"] == code
        assert component_data["uniform_api_plugin_version"]["value"] == version
        assert component_data["uniform_api_plugin_source_key"]["value"] == source_key


@pytest.mark.django_db
@patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig.get_config")
@patch("bkflow.plugin.services.plugin_schema_service.UniformAPIClient")
def test_real_plugin_schema_service_selects_exact_v4_source_and_persists_actual_conversion_tree(
    mock_client_cls, mock_space_config, context
):
    """Real Task5 service must not borrow same-code metadata from another V4 source."""
    for source_key, version in (("source-a", "1.0.0"), ("source-b", "2.0.0")):
        OpenPluginCatalogIndex.objects.create(
            space_id=context.space_id,
            source_key=source_key,
            plugin_id="same-code",
            plugin_code="run",
            plugin_name="run",
            plugin_source="builtin",
            wrapper_version="v4.0.0",
            default_version=version,
            latest_version=version,
            versions=[version],
            meta_url_template="https://registry.example/{}/{{version}}".format(source_key),
            status="available",
        )
        SpaceOpenPluginAvailability.objects.create(
            space_id=context.space_id, source_key=source_key, plugin_id="same-code", enabled=True
        )
    credential = Credential.objects.create(
        space_id=context.space_id,
        name="gateway",
        type=CredentialType.BK_APP.value,
        content={"bk_app_code": "app", "bk_app_secret": "secret"},
        scope_level=CredentialScopeLevel.ALL.value,
    )
    # The real strict catalogue also checks the legacy catalogue.  It is absent
    # in this space; only the V4 meta request needs the APIGW credential.
    mock_space_config.side_effect = lambda **kwargs: (
        credential.name if kwargs["config_name"] == "api_gateway_credential_name" else None
    )
    mock_client = MagicMock()
    mock_client.gen_default_apigw_header.return_value = {}
    mock_client.request.return_value = HttpRequestResult(
        result=True,
        message="",
        json_resp={
            "result": True,
            "data": {
                "url": "https://runtime.example/source-a",
                "methods": ["POST"],
                "id": "same-code",
                "name": "run",
                "plugin_version": "1.0.0",
                "inputs": [],
                "outputs": [],
            },
        },
    )
    mock_client_cls.return_value = mock_client
    service = PluginSchemaService(space_id=context.space_id, username=context.actor)
    resolver = CapabilityResolver(
        service,
        manifest={
            "manifest_version": "p0-v1",
            "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "unknown"},
            "capabilities": [],
        },
    )
    capability_ref = encode_capability_ref("uniform_api", "source-a", "same-code", "1.0.0")
    capability = resolver.resolve(capability_ref)
    request = {
        "intent_spec": {"goal": "real service"},
        "a2flow": {
            "version": "2.0",
            "name": "real",
            "nodes": [
                {
                    "id": "node_1",
                    "name": "run",
                    "code": "same-code",
                    "plugin_type": "uniform_api",
                    "inputs": {},
                    "next": "end",
                }
            ],
        },
        "bindings": [
            {
                "node_id": "node_1",
                "capability_ref": capability_ref,
                "schema_hash": capability.schema_hash,
                "credential_ref": None,
            }
        ],
        "idempotency_key": "real-service-v4",
        "client_context": {"conversation_ref": "real"},
    }
    accepted = WorkflowValidator(context, resolver=resolver).validate_workflow(request)
    from bkflow.harness.models import (
        CapabilityBinding,
        ValidationReport,
        WorkflowPlanRevision,
    )

    report, revision, binding = (
        ValidationReport.objects.get(),
        WorkflowPlanRevision.objects.get(),
        CapabilityBinding.objects.get(),
    )
    tree = (
        WorkflowValidator(context, resolver=resolver)
        ._convert(revision.canonical_a2flow, [{"node_id": "node_1", "capability": capability}])
        .pipeline_tree
    )
    assert accepted["ok"] is True
    assert capability.source_key == "source-a"
    assert binding.conversion_fingerprint == capability.conversion_fingerprint
    converted = WorkflowValidator(context, resolver=resolver)._convert(
        revision.canonical_a2flow, [{"node_id": "node_1", "capability": capability}]
    )
    assert report.result["converter_fingerprint"] == converted.converter_fingerprint
    assert report.result["source_map"] == converted.source_map
    assert report.result["capability_conversion_fingerprints"] == {"node_1": capability.conversion_fingerprint}
    assert report.result["pipeline_tree_hash"] == sha256_json(tree)
    component_data = next(iter(tree["activities"].values()))["component"]["data"]
    assert component_data["uniform_api_plugin_source_key"]["value"] == "source-a"


def _assert_real_plugin_service_validation(context, resolver, capability_ref, code, plugin_type, inputs=None):
    """Exercise the production service, resolver, converter and pipeline validator as one chain."""
    from bkflow.harness.models import (
        CapabilityBinding,
        ValidationReport,
        WorkflowPlanRevision,
    )

    capability = resolver.resolve(capability_ref)
    validator = WorkflowValidator(context, resolver=resolver)
    validation_request = {
        "intent_spec": {"goal": "real plugin service"},
        "a2flow": {
            "version": "2.0",
            "name": "real-service-chain",
            "nodes": [
                {
                    "id": "node_1",
                    "name": code,
                    "code": code,
                    "plugin_type": plugin_type,
                    "inputs": inputs or {},
                    "next": "end",
                }
            ],
        },
        "bindings": [
            {
                "node_id": "node_1",
                "capability_ref": capability_ref,
                "schema_hash": capability.schema_hash,
                "credential_ref": None,
            }
        ],
        "idempotency_key": "real-plugin-{}".format(plugin_type),
        "client_context": {"conversation_ref": "real-plugin-service"},
    }
    accepted = validator.validate_workflow(validation_request)
    assert accepted["ok"] is True
    binding = CapabilityBinding.objects.get()
    report = ValidationReport.objects.get()
    revision = WorkflowPlanRevision.objects.get()
    converted = validator._convert(revision.canonical_a2flow, [{"node_id": "node_1", "capability": capability}])
    assert binding.conversion_fingerprint == capability.conversion_fingerprint
    assert report.result["converter_fingerprint"] == converted.converter_fingerprint
    assert report.result["source_map"] == converted.source_map
    assert report.result["capability_conversion_fingerprints"] == {"node_1": capability.conversion_fingerprint}
    assert report.result["pipeline_tree_hash"] == sha256_json(converted.pipeline_tree)
    from bkflow.harness.services.draft import create_workflow_draft
    from bkflow.template.models import TemplateSnapshot

    draft = create_workflow_draft(
        context,
        {
            "run_id": str(revision.run.run_id),
            "revision_id": str(revision.id),
            "plan_hash": revision.plan_hash,
            "idempotency_key": "real-draft-{}".format(plugin_type),
        },
        plugin_schema_service=resolver.plugin_schema_service,
    )
    snapshot = TemplateSnapshot.objects.get(template_id=draft["artifact_refs"][0]["template_id"])
    assert snapshot.draft is True
    assert snapshot.version is None
    assert snapshot.data == converted.pipeline_tree
    assert draft["artifact_refs"][0]["pipeline_tree_hash"] == report.result["pipeline_tree_hash"]

    validation_request["run_id"] = str(revision.run.run_id)
    validation_request["idempotency_key"] = "real-plugin-repair-{}".format(plugin_type)
    repaired = validator.validate_workflow(validation_request)
    repaired_revision = WorkflowPlanRevision.objects.order_by("-sequence").first()
    repaired_report = ValidationReport.objects.order_by("-id").first()
    repaired_draft = create_workflow_draft(
        context,
        {
            "run_id": str(revision.run.run_id),
            "revision_id": str(repaired_revision.id),
            "plan_hash": repaired_revision.plan_hash,
            "idempotency_key": "real-draft-repair-{}".format(plugin_type),
        },
        plugin_schema_service=resolver.plugin_schema_service,
    )
    assert repaired["ok"] is True
    assert repaired_draft["artifact_refs"][0]["template_id"] == draft["artifact_refs"][0]["template_id"]
    assert repaired_draft["artifact_refs"][0]["pipeline_tree_hash"] == repaired_report.result["pipeline_tree_hash"]
    return capability, converted.pipeline_tree


@pytest.mark.django_db
@patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig.get_config", return_value=None)
@patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
def test_real_plugin_schema_service_uses_non_latest_component_identity(mock_library, _config, context):
    """A real component catalogue must replay the requested older version, not its latest row."""
    from pipeline.component_framework.models import ComponentModel

    ComponentModel.objects.create(code="real_component", version="v1.0.0", name="group-real", status=True)
    ComponentModel.objects.create(code="real_component", version="v2.0.0", name="group-real", status=True)
    component = MagicMock()
    component.desc = "real component"
    component.inputs_format.return_value = [{"key": "count", "type": "int", "required": True}]
    component.outputs_format.return_value = []
    mock_library.get_component_class.return_value = component
    resolver = CapabilityResolver(
        PluginSchemaService(space_id=context.space_id, username=context.actor),
        manifest={
            "manifest_version": "p0-v1",
            "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "unknown"},
            "capabilities": [],
        },
    )
    capability_ref = encode_capability_ref("component", None, "real_component", "v1.0.0")
    capability, _tree = _assert_real_plugin_service_validation(
        context, resolver, capability_ref, "real_component", "component", {"count": 1}
    )
    assert capability.resolved_version == "v1.0.0"
    assert capability.conversion_metadata == {
        "kind": "component",
        "wrapper_code": "real_component",
        "wrapper_version": "v1.0.0",
    }
    assert mock_library.get_component_class.call_args_list[-1].args == ("real_component", "v1.0.0")


@pytest.mark.django_db
@patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig.get_config", return_value=None)
@patch("bkflow.plugin.services.plugin_schema_service.PluginServiceApiClient")
def test_real_plugin_schema_service_uses_remote_provider_exact_version(mock_client_cls, _config, context):
    """Remote schema identity comes from the actual provider response, through the fixed wrapper."""
    from bkflow.bk_plugin.models import AuthStatus, BKPlugin, BKPluginAuthorization

    BKPlugin.objects.create(code="real_remote", name="remote", tag=1, logo_url="", introduction="", managers=[])
    BKPluginAuthorization.objects.create(
        code="real_remote", status=AuthStatus.authorized.value, config={"white_list": ["*"]}
    )
    mock_client_cls.return_value.get_meta.return_value = {
        "result": True,
        "data": {"versions": ["1.0.0", "2.3.0"], "inputs": [], "outputs": []},
    }
    resolver = CapabilityResolver(
        PluginSchemaService(space_id=context.space_id, username=context.actor),
        manifest={
            "manifest_version": "p0-v1",
            "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "unknown"},
            "capabilities": [],
        },
    )
    capability_ref = encode_capability_ref("remote_plugin", None, "real_remote", "2.3.0")
    capability, tree = _assert_real_plugin_service_validation(
        context, resolver, capability_ref, "real_remote", "remote_plugin"
    )
    assert capability.conversion_metadata == {
        "kind": "remote_plugin",
        "wrapper_code": "remote_plugin",
        "wrapper_version": "1.0.0",
        "remote_plugin_version": "2.3.0",
    }
    assert next(iter(tree["activities"].values()))["component"]["code"] == "remote_plugin"


@pytest.mark.django_db
@patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig.get_config")
@patch("bkflow.plugin.services.plugin_schema_service.UniformAPIClient")
def test_real_plugin_schema_service_keeps_legacy_uniform_source_none(mock_client_cls, mock_space_config, context):
    """Legacy remote Uniform API stays source-less while its transport facts remain server-owned."""
    credential = Credential.objects.create(
        space_id=context.space_id,
        name="gateway",
        type=CredentialType.BK_APP.value,
        content={"bk_app_code": "app", "bk_app_secret": "secret"},
        scope_level=CredentialScopeLevel.ALL.value,
    )
    mock_space_config.side_effect = lambda **kwargs: (
        {
            "api": {
                "default": {
                    "meta_apis": "https://registry.example/list",
                    "api_categories": "https://registry.example/categories",
                    "display_name": "legacy",
                }
            }
        }
        if kwargs["config_name"] == "uniform_api"
        else credential.name
        if kwargs["config_name"] == "api_gateway_credential_name"
        else None
    )
    client = MagicMock()
    client.gen_default_apigw_header.return_value = {}

    def uniform_response(**kwargs):
        if kwargs["url"].endswith("/list"):
            return HttpRequestResult(
                result=True,
                message="",
                json_resp={
                    "data": {
                        "total": 1,
                        "apis": [
                            {
                                "id": "legacy",
                                "name": "legacy",
                                "wrapper_version": "v3.0.0",
                                "meta_url": "https://registry.example/meta",
                            }
                        ],
                    }
                },
            )
        return HttpRequestResult(
            result=True,
            message="",
            json_resp={
                "result": True,
                "data": {
                    "id": "legacy",
                    "name": "legacy",
                    "url": "https://runtime.example/legacy",
                    "methods": ["POST"],
                    "api_key": "gateway",
                    "inputs": [],
                    "outputs": [],
                },
            },
        )

    client.request.side_effect = uniform_response
    mock_client_cls.return_value = client
    resolver = CapabilityResolver(
        PluginSchemaService(space_id=context.space_id, username=context.actor),
        manifest={
            "manifest_version": "p0-v1",
            "defaults": {"lifecycle": "VERIFIED", "risk_level": "L1", "side_effects": "unknown"},
            "capabilities": [],
        },
    )
    capability_ref = encode_capability_ref("uniform_api", None, "legacy", "unversioned")
    capability, tree = _assert_real_plugin_service_validation(
        context, resolver, capability_ref, "legacy", "uniform_api"
    )
    assert capability.source_key is None
    assert capability.conversion_metadata["source_key"] is None
    assert capability.conversion_metadata["url"] == "https://runtime.example/legacy"
