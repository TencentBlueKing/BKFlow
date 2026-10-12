"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.

P0 security-negative release gates measure public-boundary observations.
"""

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache
from django.db import close_old_connections, connection
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.apigw.serializers.harness.capabilities import (
    PluginSchemaSerializer,
    SearchCapabilitiesSerializer,
)
from bkflow.apigw.serializers.harness.workflow import (
    CreateDraftSerializer,
    ValidateWorkflowSerializer,
)
from bkflow.apigw.urls import urlpatterns as apigw_urlpatterns
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.harness.models import (
    CapabilityBinding,
    HarnessIdempotencyRecord,
    HarnessRun,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import schema_hash
from bkflow.harness.services.capability_ref import (
    MAX_CAPABILITY_REF_LENGTH,
    decode_capability_ref,
    encode_capability_ref,
)
from bkflow.harness.services.facade import P0_TOOL_OPERATION_MAP, HarnessFacade
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService
from bkflow.space.configs import (
    ApiGatewayCredentialConfig,
    HarnessDeploymentConfig,
    HarnessEnabledConfig,
    SpaceConfigValueType,
    SpacePluginConfig,
    SuperusersConfig,
)
from bkflow.space.models import (
    Credential,
    CredentialScopeLevel,
    CredentialType,
    Space,
    SpaceConfig,
)
from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugContext, Template, TemplateSnapshot
from tests.interface.harness.golden_runner import GoldenCatalog

_PATHS = {
    "search": "search_workflow_capabilities",
    "schema": "get_plugin_schema",
    "validate": "validate_workflow",
    "draft": "create_workflow_draft",
}
_PERSISTED_MODELS = (
    HarnessRun,
    WorkflowPlanRevision,
    ValidationReport,
    HarnessIdempotencyRecord,
    CapabilityBinding,
    Template,
    TemplateSnapshot,
)
_SENTINEL = "credential://id/991-B1-SENTINEL-provider-error-token"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _disable_template_statistics_delivery(monkeypatch):
    """Keep the test at the database boundary instead of contacting the local broker."""
    monkeypatch.setattr("bkflow.statistics.tasks.template_post_save_statistics_task.delay", Mock())


def _security_space(app_code, *, scope_type="project", scope_value="security"):
    """Build the real permission and trusted-context configuration for one space."""
    space = Space.objects.create(
        name="Security " + hashlib.sha256(app_code.encode()).hexdigest()[:20],
        app_code=app_code,
        platform_url="https://bkflow.example.invalid",
        creator="security-user",
        updated_by="security-user",
    )
    configs = (
        (HarnessEnabledConfig.name, SpaceConfigValueType.TEXT.value, "true", {}),
        (SuperusersConfig.name, SpaceConfigValueType.JSON.value, "", ["security-user"]),
        (
            HarnessDeploymentConfig.name,
            SpaceConfigValueType.JSON.value,
            "",
            {
                "platform_key": "bkaidev",
                "allowed_scope_types": ["project"],
                "scope_type": scope_type,
                "scope_value": scope_value,
                "target_environment": "test",
                "risk_policy_version": "security-p0",
                "mcp_contract_version": "1.0.0",
            },
        ),
    )
    for name, value_type, text_value, json_value in configs:
        SpaceConfig.objects.create(
            space_id=space.id,
            name=name,
            value_type=value_type,
            text_value=text_value,
            json_value=json_value,
        )
    return space


def test_public_scope_excludes_component_from_search_schema_and_validation():
    """Dropping trusted scope must not expose or resolve a same-space denied component."""
    space = _security_space("security-scope-component")
    SpaceConfig.objects.create(
        space_id=space.id,
        name=SpacePluginConfig.name,
        value_type=SpaceConfigValueType.JSON.value,
        json_value={
            "default": {"mode": "deny_list", "plugin_codes": []},
            "project_security": {"mode": "deny_list", "plugin_codes": ["scope_blocked_component"]},
        },
    )
    snapshot = {
        "plugin_type": "component",
        "source_key": None,
        "code": "scope_blocked_component",
        "version": "1.0.0",
        "input_key": "host",
    }
    capability_ref = encode_capability_ref("component", None, snapshot["code"], snapshot["version"])
    expected_schema_hash = schema_hash({"inputs": [{"key": "host", "type": "string", "required": True}], "outputs": []})
    card = {
        "capability_ref": capability_ref,
        "plugin_type": "component",
        "schema_hash": expected_schema_hash,
    }
    schema = {"inputs": [{"key": "host", "type": "string", "required": True}], "outputs": []}

    with GoldenCatalog(snapshot, space_id=space.id, username="security-user"):
        search = _route(space, "search", {"query": "scope blocked component"})
        schema_response = _route(
            space,
            "schema",
            {"capability_ref": capability_ref, "expected_schema_hash": expected_schema_hash},
        )
        validation = _route(
            space,
            "validate",
            _workflow_payload(card, schema, idempotency_key="scope-blocked-validation"),
        )

    assert search["artifact_refs"][0]["payload"] == []
    assert schema_response["errors"][0]["code"] == "CAPABILITY_FORBIDDEN"
    assert validation["errors"][0]["code"] == "CAPABILITY_FORBIDDEN"
    assert WorkflowPlanRevision.objects.count() == 0
    assert Template.objects.count() == 0


def test_public_scoped_uniform_chain_uses_only_scoped_credential_on_every_fresh_resolution():
    """A same-space default credential must never replace the trusted scope credential."""
    space = _security_space("security-scope-uniform")
    default_credential = Credential.objects.create(
        space_id=space.id,
        name="default-scope-credential",
        type=CredentialType.BK_APP.value,
        content={"bk_app_code": "default-app", "bk_app_secret": "default-secret"},
        scope_level=CredentialScopeLevel.ALL.value,
    )
    scoped_credential = Credential.objects.create(
        space_id=space.id,
        name="project-scope-credential",
        type=CredentialType.BK_APP.value,
        content={"bk_app_code": "scoped-app", "bk_app_secret": "scoped-secret"},
        scope_level=CredentialScopeLevel.ALL.value,
    )
    SpaceConfig.objects.create(
        space_id=space.id,
        name=ApiGatewayCredentialConfig.name,
        value_type=SpaceConfigValueType.JSON.value,
        json_value={
            "default": default_credential.name,
            "project_security": scoped_credential.name,
        },
    )
    snapshot = {
        "plugin_type": "uniform_api",
        "source_key": "scope-source",
        "code": "scope_uniform_plugin",
        "version": "1.0.0",
        "input_key": "region",
        "use_database_credentials": True,
    }

    with GoldenCatalog(snapshot, space_id=space.id, username="security-user") as catalog:
        search = _route(space, "search", {"query": "scope uniform plugin", "plugin_source": "golden"})
        card = _search_card(search)
        schema = _schema_payload(
            _route(
                space,
                "schema",
                {"capability_ref": card["capability_ref"], "expected_schema_hash": card["schema_hash"]},
            )
        )
        accepted = _route(
            space,
            "validate",
            _workflow_payload(card, schema, idempotency_key="scoped-uniform-validation"),
        )
        draft_request = {
            "run_id": accepted["run_id"],
            "revision_id": accepted["revision_id"],
            "plan_hash": accepted["plan_hash"],
            "idempotency_key": "scoped-uniform-draft",
        }
        draft = _route(space, "draft", draft_request)

    assert accepted["ok"] is True, accepted
    assert draft["ok"] is True, draft
    assert len(catalog.uniform_header_calls) >= 4
    assert {call["app_code"] for call in catalog.uniform_header_calls} == {"scoped-app"}
    run = HarnessRun.objects.get(run_id=accepted["run_id"])
    template = Template.objects.get(pk=draft["artifact_refs"][0]["template_id"])
    assert run.scope == '["project","security"]'
    assert "scope" not in accepted
    assert run.scope not in str(accepted)
    assert (template.scope_type, template.scope_value) == ("project", "security")


def test_public_space_wide_chain_round_trips_one_empty_canonical_scope():
    """Space-wide validation and draft must agree on the null/null scope representation."""
    space = _security_space("security-space-wide", scope_type=None, scope_value=None)
    snapshot = {
        "plugin_type": "component",
        "source_key": None,
        "code": "space_wide_component",
        "version": "1.0.0",
        "input_key": "host",
    }

    with GoldenCatalog(snapshot, space_id=space.id, username="security-user"):
        accepted = _valid_public_revision(space, snapshot, "space-wide-validation")
        draft_request = {
            "run_id": accepted["run_id"],
            "revision_id": accepted["revision_id"],
            "plan_hash": accepted["plan_hash"],
            "idempotency_key": "space-wide-draft",
        }
        draft = _route(space, "draft", draft_request)

    assert accepted["ok"] is True, accepted
    assert draft["ok"] is True, draft
    run = HarnessRun.objects.get(run_id=accepted["run_id"])
    template = Template.objects.get(pk=draft["artifact_refs"][0]["template_id"])
    assert run.scope == ""
    assert (template.scope_type, template.scope_value) == (None, None)
    assert HarnessIdempotencyRecord.objects.filter(run=run, status="COMPLETED").count() == 2


def test_public_maximum_capability_reference_round_trips_search_schema_validation_and_draft():
    """Every P0 Tool must consume the longest opaque reference that search can issue."""
    space = _security_space("security-maximum-reference")
    snapshot = {
        "plugin_type": "component",
        "source_key": None,
        "code": "😀" * 255,
        "version": "😀" * 64,
        "display_name": "maximum reference component",
        "input_key": "host",
    }

    with GoldenCatalog(snapshot, space_id=space.id, username="security-user"):
        search = _route(space, "search", {"query": "maximum reference component"})
        card = _search_card(search)
        assert len(card["capability_ref"]) == MAX_CAPABILITY_REF_LENGTH
        schema = _schema_payload(
            _route(
                space,
                "schema",
                {"capability_ref": card["capability_ref"], "expected_schema_hash": card["schema_hash"]},
            )
        )
        accepted = _route(
            space,
            "validate",
            _workflow_payload(card, schema, idempotency_key="maximum-reference-validation"),
        )
        draft_request = {
            "run_id": accepted["run_id"],
            "revision_id": accepted["revision_id"],
            "plan_hash": accepted["plan_hash"],
            "idempotency_key": "maximum-reference-draft",
        }
        draft = _route(space, "draft", draft_request)

    assert accepted["ok"] is True, accepted
    assert draft["ok"] is True, draft
    binding = CapabilityBinding.objects.get(revision_id=accepted["revision_id"])
    assert binding.capability_ref == card["capability_ref"]
    assert len(binding.capability_ref) == MAX_CAPABILITY_REF_LENGTH


def test_public_capability_reference_max_plus_one_is_typed_rejection():
    """A max-plus-one reference must stop at both Schema transport and validation domain boundaries."""
    space = _security_space("security-oversized-reference")
    oversized = "x" * (MAX_CAPABILITY_REF_LENGTH + 1)
    schema_response = _route(
        space,
        "schema",
        {"capability_ref": oversized, "expected_schema_hash": "a" * 64},
    )
    payload = {
        "intent_spec": {"goal": "oversized reference"},
        "a2flow": {
            "version": "2.0",
            "name": "oversized reference",
            "nodes": [
                {
                    "id": "node_1",
                    "name": "oversized",
                    "code": "oversized",
                    "plugin_type": "component",
                    "inputs": {"host": "public-value"},
                    "next": "end",
                }
            ],
        },
        "bindings": [
            {
                "node_id": "node_1",
                "capability_ref": oversized,
                "schema_hash": "a" * 64,
                "credential_ref": None,
            }
        ],
        "idempotency_key": "oversized-reference-validation",
        "client_context": {},
    }
    validation = _route(
        space,
        "validate",
        payload,
    )

    assert schema_response["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert validation["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert HarnessRun.objects.count() == 0


def _route(space, operation, payload, *, correlation_id="security-trace"):
    """Invoke the actual URL, permission, context, serializer, dispatch and Facade path."""
    path = "/apigw/space/{}/harness/{}/".format(space.id, _PATHS[operation])
    request = APIRequestFactory().post(path, payload, format="json", HTTP_X_REQUEST_ID=correlation_id)
    request.app = SimpleNamespace(bk_app_code=space.app_code, verified=True)
    force_authenticate(request, user=SimpleNamespace(username="security-user", is_authenticated=True))
    response = resolve(path).func(request, space_id=str(space.id))
    assert response.status_code == 200
    return response.data


def _flatten(value):
    """Yield mapping keys and values recursively so hidden sentinel positions are observed."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _flatten(key)
            yield from _flatten(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _flatten(item)
    elif value is not None:
        yield str(value)


def _baseline_rows():
    """Pin rows before an attack so only newly persisted Harness/Template facts are scanned."""
    return {model: set(model.objects.values_list("pk", flat=True)) for model in _PERSISTED_MODELS}


def _new_persisted_values(before):
    """Read every field, including JSON keys and values, from newly durable P0 rows."""
    for model, known_ids in before.items():
        for row in model.objects.exclude(pk__in=known_ids):
            for field in row._meta.fields:
                yield from _flatten(getattr(row, field.attname))


def _log_values(records):
    """Scan both formatted messages and structured Harness audit payloads."""
    for record in records:
        yield record.getMessage()
        yield from _flatten(vars(record))


@dataclass(frozen=True)
class ReleaseDatabaseObservation:
    """Durable interface-side facts relevant to the seven P0 release counters."""

    templates: int
    draft_snapshots: int
    published_snapshots: int
    harness_draft_artifacts: int
    completed_draft_idempotency: int
    debug_contexts: int

    @classmethod
    def capture(cls):
        harness_draft_artifacts = sum(
            1
            for artifacts in HarnessRun.objects.values_list("artifact_references", flat=True)
            for artifact in artifacts
            if isinstance(artifact, dict) and artifact.get("type") == "harness_draft"
        )
        return cls(
            templates=Template.objects.count(),
            draft_snapshots=TemplateSnapshot.objects.filter(draft=True).count(),
            published_snapshots=TemplateSnapshot.objects.filter(draft=False).count(),
            harness_draft_artifacts=harness_draft_artifacts,
            completed_draft_idempotency=HarnessIdempotencyRecord.objects.filter(
                tool_name="create_workflow_draft", status="COMPLETED"
            ).count(),
            debug_contexts=DebugContext.objects.count(),
        )


@dataclass(frozen=True)
class HighPhaseGuards:
    """Observed production entrypoints that a P0 request must never call."""

    release_spies: tuple
    task_spies: tuple
    execution_spies: tuple

    @property
    def all_spies(self):
        return self.release_spies + self.task_spies + self.execution_spies


def _guard_high_phase(monkeypatch):
    """Fail immediately at release, Engine-task and debug execution boundaries while retaining call evidence."""
    release = Mock(side_effect=AssertionError("P0 attempted template release"))
    task = Mock(side_effect=AssertionError("P0 attempted Engine task creation"))
    task_control = Mock(side_effect=AssertionError("P0 attempted Engine task control"))
    node_control = Mock(side_effect=AssertionError("P0 attempted Engine node execution"))
    global_debug = Mock(side_effect=AssertionError("P0 attempted global debug execution"))
    step_debug = Mock(side_effect=AssertionError("P0 attempted step debug execution"))
    monkeypatch.setattr(Template, "release_template", release)
    monkeypatch.setattr(TaskComponentClient, "create_task", task)
    monkeypatch.setattr(TaskComponentClient, "operate_task", task_control)
    monkeypatch.setattr(TaskComponentClient, "node_operate", node_control)
    monkeypatch.setattr(DebugService, "global_run", global_debug)
    monkeypatch.setattr(DebugService, "step_run", step_debug)
    return HighPhaseGuards(
        release_spies=(release,),
        task_spies=(task,),
        execution_spies=(task_control, node_control, global_debug, step_debug),
    )


@dataclass(frozen=True)
class MeasuredSecurityCounters:
    """Boundary counters computed from route responses, logs and newly persisted rows."""

    cross_space_leak: int
    secret_or_token_exposure: int
    silent_schema_drift: int

    @classmethod
    def observe(
        cls,
        *,
        responses=(),
        logs=(),
        persisted_values=(),
        cross_space_markers=(),
        secret_sentinel=None,
        drift_rejected=(),
    ):
        observed = list(_flatten(list(responses))) + list(_flatten(list(logs))) + list(persisted_values)
        text = "\n".join(observed)
        return cls(
            cross_space_leak=sum(text.count(str(marker)) for marker in cross_space_markers),
            secret_or_token_exposure=text.count(secret_sentinel) if secret_sentinel else 0,
            silent_schema_drift=sum(1 for rejected in drift_rejected if rejected is not True),
        )


@dataclass(frozen=True)
class MeasuredReleaseCounters:
    """Combine B1 boundary evidence with B2 durable and guarded side-effect observations."""

    cross_space_leak: int
    secret_or_token_exposure: int
    silent_schema_drift: int
    duplicate_drafts: int
    published_templates: int
    created_tasks: int
    real_executions: int

    @classmethod
    def observe(
        cls,
        *,
        database_before,
        database_after,
        expected_drafts,
        release_spies,
        task_spies,
        execution_spies,
        responses=(),
        logs=(),
        persisted_values=(),
        cross_space_markers=(),
        secret_sentinel=None,
        drift_rejected=(),
    ):
        boundary = MeasuredSecurityCounters.observe(
            responses=responses,
            logs=logs,
            persisted_values=persisted_values,
            cross_space_markers=cross_space_markers,
            secret_sentinel=secret_sentinel,
            drift_rejected=drift_rejected,
        )
        draft_resource_deltas = (
            database_after.templates - database_before.templates,
            database_after.draft_snapshots - database_before.draft_snapshots,
            database_after.harness_draft_artifacts - database_before.harness_draft_artifacts,
            database_after.completed_draft_idempotency - database_before.completed_draft_idempotency,
        )
        return cls(
            cross_space_leak=boundary.cross_space_leak,
            secret_or_token_exposure=boundary.secret_or_token_exposure,
            silent_schema_drift=boundary.silent_schema_drift,
            duplicate_drafts=max(0, max(draft_resource_deltas) - expected_drafts),
            published_templates=max(0, database_after.published_snapshots - database_before.published_snapshots)
            + sum(spy.call_count for spy in release_spies),
            # Task state is stored in the target Engine DB in interface deployments. Guarded Task client calls are
            # therefore the authoritative local observation rather than an unavailable interface-side model.
            created_tasks=sum(spy.call_count for spy in task_spies),
            real_executions=max(0, database_after.debug_contexts - database_before.debug_contexts)
            + sum(spy.call_count for spy in execution_spies),
        )


def _schema_payload(response):
    """Return the exact Schema artifact from a successful public response."""
    assert response["ok"] is True, response
    assert response["artifact_refs"][0]["type"] == "plugin_schema"
    return response["artifact_refs"][0]["payload"]


def _search_card(response):
    """Return the sole selection card from a successful public search response."""
    assert response["ok"] is True, response
    cards = response["artifact_refs"][0]["payload"]
    assert len(cards) == 1, cards
    return cards[0]


def _workflow_payload(card, schema, *, idempotency_key, run_id=None):
    """Build validation input from the opaque card identity and fetched full Schema."""
    reference = decode_capability_ref(card["capability_ref"])
    inputs = {item["key"]: "public-value" for item in schema["inputs"] if item.get("required")}
    payload = {
        "intent_spec": {"goal": "security validation"},
        "a2flow": {
            "version": "2.0",
            "name": "security",
            "nodes": [
                {
                    "id": "node_1",
                    "name": "security-node",
                    "code": reference.code,
                    "plugin_type": reference.plugin_type,
                    "inputs": inputs,
                    "next": "end",
                }
            ],
        },
        "bindings": [
            {
                "node_id": "node_1",
                "capability_ref": card["capability_ref"],
                "schema_hash": card["schema_hash"],
                "credential_ref": None,
            }
        ],
        "idempotency_key": idempotency_key,
        "client_context": {},
    }
    if run_id is not None:
        payload["run_id"] = str(run_id)
    return payload


def _valid_public_revision(space, snapshot, idempotency_key):
    """Create one accepted run/revision through all three public read/validation operations."""
    search = _route(space, "search", {"query": snapshot["code"], "plugin_source": "golden"})
    card = _search_card(search)
    schema = _schema_payload(
        _route(
            space,
            "schema",
            {"capability_ref": card["capability_ref"], "expected_schema_hash": card["schema_hash"]},
        )
    )
    accepted = _route(space, "validate", _workflow_payload(card, schema, idempotency_key=idempotency_key))
    assert accepted["ok"] is True, accepted
    return accepted


def _assert_one_draft(accepted, request, response, before, after):
    """Assert one immutable managed draft, snapshot, artifact and completed idempotency record."""
    assert after.templates - before.templates == 1
    assert after.draft_snapshots - before.draft_snapshots == 1
    assert after.published_snapshots - before.published_snapshots == 0
    assert after.harness_draft_artifacts - before.harness_draft_artifacts == 1
    assert after.completed_draft_idempotency - before.completed_draft_idempotency == 1

    run = HarnessRun.objects.get(run_id=accepted["run_id"])
    artifacts = [
        artifact
        for artifact in run.artifact_references
        if isinstance(artifact, dict) and artifact.get("type") == "harness_draft"
    ]
    assert len(artifacts) == 1
    template_id = response["artifact_refs"][0]["template_id"]
    assert artifacts[0]["template_id"] == template_id
    assert artifacts[0]["revision_id"] == accepted["revision_id"]
    assert artifacts[0]["pipeline_tree_hash"] == response["artifact_refs"][0]["pipeline_tree_hash"]

    template = Template.objects.get(pk=template_id)
    assert template.space_id == run.space_id
    snapshots = list(TemplateSnapshot.objects.filter(template_id=template.id))
    assert len(snapshots) == 1
    assert snapshots[0].pk == template.snapshot_id
    assert snapshots[0].draft is True
    assert snapshots[0].version is None

    records = HarnessIdempotencyRecord.objects.filter(
        run=run,
        tool_name="create_workflow_draft",
        run_scope="run:{}".format(run.run_id),
        idempotency_key=request["idempotency_key"],
    )
    assert records.count() == 1
    record = records.get()
    assert record.status == "COMPLETED"
    assert record.resource_reference == str(template.id)
    assert record.response_snapshot["artifact_refs"][0]["template_id"] == template.id


@pytest.mark.parametrize(
    "serializer,payload",
    [
        (SearchCapabilitiesSerializer, {"query": "host", "platform_app": "forged"}),
        (PluginSchemaSerializer, {"capability_ref": "x", "expected_schema_hash": "a" * 64, "space_id": 2}),
        (
            ValidateWorkflowSerializer,
            {"intent_spec": {}, "a2flow": {}, "bindings": [], "idempotency_key": "key", "actor": "forged"},
        ),
        (
            CreateDraftSerializer,
            {
                "run_id": "00000000-0000-0000-0000-000000000000",
                "revision_id": "00000000-0000-0000-0000-000000000000",
                "plan_hash": "a" * 64,
                "idempotency_key": "key",
                "auto_release": True,
            },
        ),
    ],
)
def test_transport_rejects_forged_authority_fields(serializer, payload):
    """Closed serializers reject caller-controlled authority and release fields."""
    parsed = serializer(data=payload)
    assert parsed.is_valid() is False
    assert "unknown fields" in str(parsed.errors)


@pytest.mark.parametrize(
    "serializer,payload",
    [
        (SearchCapabilitiesSerializer, {"query": "x" * 257}),
        (SearchCapabilitiesSerializer, {"query": "bad\ud800"}),
        (
            ValidateWorkflowSerializer,
            {"intent_spec": {"x": "x" * 4097}, "a2flow": {}, "bindings": [], "idempotency_key": "key"},
        ),
        (
            ValidateWorkflowSerializer,
            {"intent_spec": {"x": [0] * 101}, "a2flow": {}, "bindings": [], "idempotency_key": "key"},
        ),
    ],
)
def test_transport_bounds_hostile_values(serializer, payload):
    """Unicode, byte, item and canonical payload limits are closed at transport."""
    assert serializer(data=payload).is_valid() is False


def test_public_routes_measure_zero_cross_space_exposure(caplog, monkeypatch):
    """Space B cannot discover or access space A capability, run, revision or managed draft."""
    high_phase = _guard_high_phase(monkeypatch)
    space_a = _security_space("security-app-a")
    space_b = _security_space("security-app-b")
    snapshot_a = {
        "plugin_type": "uniform_api",
        "source_key": "b1-source-a-private",
        "code": "alphaprivatecapability",
        "version": "1.0.0",
        "input_key": "b1_input_a_private",
    }
    snapshot_b = {
        "plugin_type": "uniform_api",
        "source_key": "b1-source-b-owned",
        "code": "betaownedcapability",
        "version": "1.0.0",
        "input_key": "b1_input_b_owned",
    }
    caplog.set_level("INFO", logger="bkflow.harness")

    with GoldenCatalog(snapshot_a, space_id=space_a.id, username="security-user") as catalog_a:
        assert isinstance(catalog_a.service, PluginSchemaService)
        search_a = _route(space_a, "search", {"query": snapshot_a["code"], "plugin_source": "golden"})
        card_a = _search_card(search_a)
        schema_a = _schema_payload(
            _route(
                space_a,
                "schema",
                {"capability_ref": card_a["capability_ref"], "expected_schema_hash": card_a["schema_hash"]},
            )
        )
        accepted_a = _route(
            space_a,
            "validate",
            _workflow_payload(card_a, schema_a, idempotency_key="cross-space-a-validation"),
        )
        assert accepted_a["ok"] is True, accepted_a
        draft_a = _route(
            space_a,
            "draft",
            {
                "run_id": accepted_a["run_id"],
                "revision_id": accepted_a["revision_id"],
                "plan_hash": accepted_a["plan_hash"],
                "idempotency_key": "cross-space-a-draft",
            },
        )
        assert draft_a["ok"] is True, draft_a
        template_a = Template.objects.get(pk=draft_a["artifact_refs"][0]["template_id"])
        assert template_a.space_id == space_a.id

        with GoldenCatalog(snapshot_b, space_id=space_b.id, username="security-user") as catalog_b:
            assert isinstance(catalog_b.service, PluginSchemaService)
            search_b = _route(space_b, "search", {"query": snapshot_b["code"], "plugin_source": "golden"})
            card_b = _search_card(search_b)
            schema_b = _schema_payload(
                _route(
                    space_b,
                    "schema",
                    {"capability_ref": card_b["capability_ref"], "expected_schema_hash": card_b["schema_hash"]},
                )
            )
            accepted_b = _route(
                space_b,
                "validate",
                _workflow_payload(card_b, schema_b, idempotency_key="cross-space-b-validation"),
            )
            assert accepted_b["ok"] is True, accepted_b
            run_b = HarnessRun.objects.get(run_id=accepted_b["run_id"])
            run_b.artifact_references = [
                {
                    "type": "harness_draft",
                    "template_id": template_a.id,
                    "revision_id": accepted_b["revision_id"],
                    "pipeline_tree_hash": "0" * 64,
                }
            ]
            run_b.save(update_fields=["artifact_references", "update_at"])
            template_a_snapshot_hash = TemplateSnapshot.objects.get(pk=template_a.snapshot_id).md5sum

            caplog.clear()
            before_attacks = _baseline_rows()
            release_before_attacks = ReleaseDatabaseObservation.capture()
            before_b_revisions = WorkflowPlanRevision.objects.filter(run__space_id=space_b.id).count()
            search_foreign = _route(space_b, "search", {"query": snapshot_a["code"], "plugin_source": "golden"})
            assert search_foreign["artifact_refs"][0]["payload"] == []
            foreign_schema = _route(
                space_b,
                "schema",
                {"capability_ref": card_a["capability_ref"], "expected_schema_hash": card_a["schema_hash"]},
            )
            foreign_capability = _route(
                space_b,
                "validate",
                _workflow_payload(card_a, schema_a, idempotency_key="cross-space-capability"),
            )
            foreign_run = _route(
                space_b,
                "validate",
                _workflow_payload(
                    card_b,
                    schema_b,
                    idempotency_key="cross-space-run",
                    run_id=accepted_a["run_id"],
                ),
            )
            foreign_draft = _route(
                space_b,
                "draft",
                {
                    "run_id": accepted_a["run_id"],
                    "revision_id": accepted_a["revision_id"],
                    "plan_hash": accepted_a["plan_hash"],
                    "idempotency_key": "cross-space-draft",
                },
            )
            foreign_revision = _route(
                space_b,
                "draft",
                {
                    "run_id": accepted_b["run_id"],
                    "revision_id": accepted_a["revision_id"],
                    "plan_hash": accepted_a["plan_hash"],
                    "idempotency_key": "cross-space-revision",
                },
            )
            foreign_managed_draft = _route(
                space_b,
                "draft",
                {
                    "run_id": accepted_b["run_id"],
                    "revision_id": accepted_b["revision_id"],
                    "plan_hash": accepted_b["plan_hash"],
                    "idempotency_key": "cross-space-managed-draft",
                },
            )
            release_after_attacks = ReleaseDatabaseObservation.capture()

    permission_denied = (foreign_schema, foreign_capability, foreign_run, foreign_draft, foreign_revision)
    denied = (*permission_denied, foreign_managed_draft)
    assert all(response["ok"] is False for response in denied)
    assert all(response["errors"][0]["category"] == "PERMISSION" for response in permission_denied)
    assert all("template_id" not in set(_flatten(response["artifact_refs"])) for response in denied)
    assert WorkflowPlanRevision.objects.filter(run__space_id=space_b.id).count() == before_b_revisions
    assert Template.objects.filter(space_id=space_b.id).count() == 0
    assert TemplateSnapshot.objects.filter(template_id__in=Template.objects.filter(space_id=space_b.id)).count() == 0
    assert TemplateSnapshot.objects.get(pk=template_a.snapshot_id).md5sum == template_a_snapshot_hash

    markers = (
        snapshot_a["source_key"],
        snapshot_a["code"],
        snapshot_a["input_key"],
        card_a["capability_ref"],
        accepted_a["run_id"],
        accepted_a["revision_id"],
        accepted_a["plan_hash"],
    )
    counters = MeasuredReleaseCounters.observe(
        responses=[search_foreign, *denied],
        logs=list(_log_values(caplog.records)),
        persisted_values=list(_new_persisted_values(before_attacks)),
        cross_space_markers=markers,
        database_before=release_before_attacks,
        database_after=release_after_attacks,
        expected_drafts=0,
        release_spies=high_phase.release_spies,
        task_spies=high_phase.task_spies,
        execution_spies=high_phase.execution_spies,
    )
    assert counters.cross_space_leak == 0
    assert counters.duplicate_drafts == 0
    assert counters.published_templates == 0
    assert counters.created_tasks == 0
    assert counters.real_executions == 0


def test_public_boundaries_measure_zero_secret_exposure_and_schema_card_split(caplog, monkeypatch):
    """Request, provider, error, artifact and credential sentinels never leave safe boundaries."""
    high_phase = _guard_high_phase(monkeypatch)
    space = _security_space("security-secret-app")
    snapshot = {
        "plugin_type": "uniform_api",
        "source_key": "b1-secret-source",
        "code": "b1_secret_safe_capability",
        "version": "1.0.0",
        "input_key": "public_input_marker",
        "output_key": "public_output_marker",
        "credential_secret": _SENTINEL,
        "provider_extras": {_SENTINEL: _SENTINEL},
    }
    caplog.set_level("INFO", logger="bkflow.harness")

    with GoldenCatalog(snapshot, space_id=space.id, username="security-user") as catalog:
        before = _baseline_rows()
        release_before = ReleaseDatabaseObservation.capture()
        domain_call = Mock()
        with patch.object(HarnessFacade, "search_workflow_capabilities", domain_call):
            rejected_transport = _route(
                space,
                "search",
                {"query": snapshot["code"], _SENTINEL: _SENTINEL},
                correlation_id="transport-sentinel",
            )
        domain_call.assert_not_called()

        unsafe_artifact = {
            "ok": True,
            "run_id": None,
            "revision_id": None,
            "plan_hash": None,
            "status": "COMPLETED",
            "summary": "unsafe",
            "artifact_refs": [{_SENTINEL: _SENTINEL}],
            "errors": [],
            "next_actions": [],
            "correlation_id": "artifact-sentinel",
        }
        with patch.object(HarnessFacade, "search_workflow_capabilities", return_value=unsafe_artifact):
            rejected_artifact = _route(
                space,
                "search",
                {"query": snapshot["code"]},
                correlation_id="artifact-sentinel",
            )

        unsafe_error = {
            "ok": False,
            "run_id": None,
            "revision_id": None,
            "plan_hash": None,
            "status": None,
            "summary": _SENTINEL,
            "artifact_refs": [],
            "errors": [
                {
                    "category": "RETRYABLE_INFRA",
                    "code": "RETRYABLE_INFRA",
                    "path": _SENTINEL,
                    "repairable": True,
                    "retryable": True,
                    "message": _SENTINEL,
                    "suggested_action": _SENTINEL,
                    _SENTINEL: _SENTINEL,
                }
            ],
            "next_actions": [_SENTINEL],
            "correlation_id": "error-sentinel",
        }
        with patch.object(HarnessFacade, "search_workflow_capabilities", return_value=unsafe_error):
            rejected_error = _route(
                space,
                "search",
                {"query": snapshot["code"]},
                correlation_id="error-sentinel",
            )

        search = _route(space, "search", {"query": snapshot["code"], "plugin_source": "golden"})
        card = _search_card(search)
        schema_response = _route(
            space,
            "schema",
            {"capability_ref": card["capability_ref"], "expected_schema_hash": card["schema_hash"]},
        )
        schema = _schema_payload(schema_response)

        forbidden_card_fields = {"inputs", "outputs", "conversion_metadata", "credential", "credential_ref"}
        assert forbidden_card_fields.isdisjoint(card)
        assert snapshot["input_key"] not in repr(card)
        assert snapshot["output_key"] not in repr(card)
        assert schema["inputs"][0]["key"] == snapshot["input_key"]
        assert schema["outputs"][0]["key"] == snapshot["output_key"]

        accepted = _route(
            space,
            "validate",
            _workflow_payload(card, schema, idempotency_key="secret-validation"),
        )
        assert accepted["ok"] is True, accepted
        draft = _route(
            space,
            "draft",
            {
                "run_id": accepted["run_id"],
                "revision_id": accepted["revision_id"],
                "plan_hash": accepted["plan_hash"],
                "idempotency_key": "secret-draft",
            },
        )
        assert draft["ok"] is True, draft
        assert any(
            call.get("app_secret") == _SENTINEL for call in catalog.uniform_header_calls
        ), catalog.uniform_header_calls
        assert any(_SENTINEL in list(_flatten(payload)) for payload in catalog.uniform_provider_payloads)

        cache.clear()
        catalog.uniform_client.side_effect = RuntimeError("provider-error {}".format(_SENTINEL))
        provider_error = _route(
            space,
            "schema",
            {"capability_ref": card["capability_ref"], "expected_schema_hash": card["schema_hash"]},
            correlation_id="provider-error",
        )

        persisted_values = list(_new_persisted_values(before))
        release_after = ReleaseDatabaseObservation.capture()

    responses = [
        rejected_transport,
        rejected_artifact,
        rejected_error,
        search,
        schema_response,
        accepted,
        draft,
        provider_error,
    ]
    assert rejected_transport["ok"] is False
    assert rejected_artifact["ok"] is False
    assert rejected_error["ok"] is False
    assert provider_error["ok"] is False
    assert provider_error["errors"][0]["code"] == "RETRYABLE_INFRA"
    counters = MeasuredReleaseCounters.observe(
        responses=responses,
        logs=list(_log_values(caplog.records)),
        persisted_values=persisted_values,
        secret_sentinel=_SENTINEL,
        database_before=release_before,
        database_after=release_after,
        expected_drafts=1,
        release_spies=high_phase.release_spies,
        task_spies=high_phase.task_spies,
        execution_spies=high_phase.execution_spies,
    )
    assert counters.secret_or_token_exposure == 0
    assert counters.duplicate_drafts == 0
    assert counters.published_templates == 0
    assert counters.created_tasks == 0
    assert counters.real_executions == 0


def test_public_success_replaces_malicious_correlation_before_every_durable_copy(caplog):
    """Successful and failed request correlations are generated once before every durable copy."""
    correlation_sentinel = "Bearer C2-CORRELATION-SENTINEL"
    space = _security_space("security-correlation-app")
    snapshot = {
        "plugin_type": "component",
        "source_key": None,
        "code": "c2_safe_correlation_component",
        "version": "1.0.0",
        "input_key": "host",
    }
    caplog.set_level("INFO", logger="bkflow.harness")
    before = _baseline_rows()

    with GoldenCatalog(snapshot, space_id=space.id, username="security-user"):
        search = _route(space, "search", {"query": snapshot["code"]})
        card = _search_card(search)
        schema = _schema_payload(
            _route(
                space,
                "schema",
                {"capability_ref": card["capability_ref"], "expected_schema_hash": card["schema_hash"]},
            )
        )
        accepted = _route(
            space,
            "validate",
            _workflow_payload(card, schema, idempotency_key="safe-correlation-validation"),
            correlation_id=correlation_sentinel,
        )
        draft = _route(
            space,
            "draft",
            {
                "run_id": accepted["run_id"],
                "revision_id": accepted["revision_id"],
                "plan_hash": accepted["plan_hash"],
                "idempotency_key": "safe-correlation-draft",
            },
        )
        failed_payload = _workflow_payload(card, schema, idempotency_key="failed-correlation-validation")
        failed_payload["a2flow"]["nodes"][0]["inputs"] = {}
        failed = _route(
            space,
            "validate",
            failed_payload,
            correlation_id="x-bkapi-authorization C2-CORRELATION-FAILURE-SENTINEL",
        )

    assert accepted["ok"] is True, accepted
    assert draft["ok"] is True, draft
    safe_correlation = accepted["correlation_id"]
    assert safe_correlation != correlation_sentinel
    assert len(safe_correlation) == 32
    int(safe_correlation, 16)
    run = HarnessRun.objects.get(run_id=accepted["run_id"])
    report = ValidationReport.objects.get(run=run, revision_id=accepted["revision_id"])
    validation_record = HarnessIdempotencyRecord.objects.get(
        run=run,
        tool_name="validate_workflow",
        idempotency_key="safe-correlation-validation",
    )
    assert report.correlation_id == safe_correlation
    assert validation_record.response_snapshot["correlation_id"] == safe_correlation
    assert failed["ok"] is False
    failed_run = HarnessRun.objects.get(run_id=failed["run_id"])
    failed_report = ValidationReport.objects.get(run=failed_run, revision=None)
    failed_record = HarnessIdempotencyRecord.objects.get(
        run=failed_run,
        tool_name="validate_workflow",
        idempotency_key="failed-correlation-validation",
    )
    assert failed_report.correlation_id == failed["correlation_id"]
    assert failed_record.response_snapshot["correlation_id"] == failed["correlation_id"]
    assert failed["correlation_id"] != "x-bkapi-authorization C2-CORRELATION-FAILURE-SENTINEL"

    counters = MeasuredSecurityCounters.observe(
        responses=[accepted, draft, failed],
        logs=list(_log_values(caplog.records)),
        persisted_values=list(_new_persisted_values(before)),
        secret_sentinel="C2-CORRELATION",
    )
    assert counters.secret_or_token_exposure == 0


@pytest.mark.parametrize(
    "target,value",
    [
        ("intent", "Bearer C2-VALUE-SENTINEL"),
        ("a2flow", "x-bkapi-authorization C2-VALUE-SENTINEL"),
        ("client_context", "credential://id/C2-VALUE-SENTINEL"),
    ],
)
def test_public_secret_shaped_values_under_safe_keys_leave_no_failure_evidence(caplog, target, value):
    """Real route and Facade validation rejects secret values before run, report or replay persistence."""
    space = _security_space("security-value-{}".format(target.replace("_", "-")))
    snapshot = {
        "plugin_type": "component",
        "source_key": None,
        "code": "c2_{}_component".format(target),
        "version": "1.0.0",
        "input_key": "host",
    }
    caplog.set_level("INFO", logger="bkflow.harness")

    with GoldenCatalog(snapshot, space_id=space.id, username="security-user"):
        search = _route(space, "search", {"query": snapshot["code"]})
        card = _search_card(search)
        schema = _schema_payload(
            _route(
                space,
                "schema",
                {"capability_ref": card["capability_ref"], "expected_schema_hash": card["schema_hash"]},
            )
        )
        payload = _workflow_payload(card, schema, idempotency_key="c2-value-validation")
        if target == "intent":
            payload["intent_spec"] = {"goal": value}
        elif target == "a2flow":
            payload["a2flow"]["name"] = value
        else:
            payload["client_context"] = {"conversation_ref": value}
        before = _baseline_rows()
        caplog.clear()
        rejected = _route(space, "validate", payload)
        persisted_values = list(_new_persisted_values(before))

    assert rejected["ok"] is False
    assert rejected["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert all(set(model.objects.values_list("pk", flat=True)) == known_ids for model, known_ids in before.items())
    counters = MeasuredSecurityCounters.observe(
        responses=[rejected],
        logs=list(_log_values(caplog.records)),
        persisted_values=persisted_values,
        secret_sentinel="C2-VALUE-SENTINEL",
    )
    assert counters.secret_or_token_exposure == 0


def test_public_secret_shaped_idempotency_keys_are_never_hashed_or_persisted(caplog):
    """Validation and draft reject their raw idempotency namespaces before any owned side effect."""
    sentinel = "C2-IDEMPOTENCY-SENTINEL"
    space = _security_space("security-idempotency-secret-app")
    snapshot = {
        "plugin_type": "component",
        "source_key": None,
        "code": "c2_idempotency_component",
        "version": "1.0.0",
        "input_key": "host",
    }
    caplog.set_level("INFO", logger="bkflow.harness")

    with GoldenCatalog(snapshot, space_id=space.id, username="security-user"):
        search = _route(space, "search", {"query": snapshot["code"]})
        card = _search_card(search)
        schema = _schema_payload(
            _route(
                space,
                "schema",
                {"capability_ref": card["capability_ref"], "expected_schema_hash": card["schema_hash"]},
            )
        )
        before = _baseline_rows()
        rejected_validation = _route(
            space,
            "validate",
            _workflow_payload(
                card,
                schema,
                idempotency_key="authorization={}".format(sentinel),
            ),
        )
        assert all(set(model.objects.values_list("pk", flat=True)) == known for model, known in before.items())

        accepted = _route(
            space,
            "validate",
            _workflow_payload(card, schema, idempotency_key="safe-idempotency-validation"),
        )
        rejected_draft = _route(
            space,
            "draft",
            {
                "run_id": accepted["run_id"],
                "revision_id": accepted["revision_id"],
                "plan_hash": accepted["plan_hash"],
                "idempotency_key": "credential://id/{}".format(sentinel),
            },
        )
        persisted_values = list(_new_persisted_values(before))

    assert rejected_validation["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert rejected_draft["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert rejected_draft["errors"][0]["path"] == "idempotency_key"
    assert Template.objects.count() == 0
    assert TemplateSnapshot.objects.count() == 0
    assert not HarnessIdempotencyRecord.objects.filter(idempotency_key__contains=sentinel).exists()
    counters = MeasuredSecurityCounters.observe(
        responses=[rejected_validation, accepted, rejected_draft],
        logs=list(_log_values(caplog.records)),
        persisted_values=persisted_values,
        secret_sentinel=sentinel,
    )
    assert counters.secret_or_token_exposure == 0


def test_public_safe_security_language_and_closed_binding_credential_ref_remain_compatible(caplog):
    """Ordinary token prose and the authorized binding-only credential reference still draft successfully."""
    credential_body_sentinel = "C2-CREDENTIAL-BODY-SENTINEL"
    space = _security_space("security-safe-language-app")
    credential = Credential.objects.create(
        space_id=space.id,
        name="c2-binding-credential",
        type=CredentialType.BK_APP.value,
        content={"bk_app_code": "safe-app", "bk_app_secret": credential_body_sentinel},
        scope_level=CredentialScopeLevel.ALL.value,
    )
    snapshot = {
        "plugin_type": "component",
        "source_key": None,
        "code": "c2_safe_language_component",
        "version": "1.0.0",
        "input_key": "host",
    }
    caplog.set_level("INFO", logger="bkflow.harness")
    before = _baseline_rows()

    with GoldenCatalog(snapshot, space_id=space.id, username="security-user"):
        search = _route(space, "search", {"query": snapshot["code"]})
        card = _search_card(search)
        schema = _schema_payload(
            _route(
                space,
                "schema",
                {"capability_ref": card["capability_ref"], "expected_schema_hash": card["schema_hash"]},
            )
        )
        payload = _workflow_payload(card, schema, idempotency_key="token-rotation-validation")
        payload["intent_spec"] = {"goal": "Discuss token rotation without embedding credentials"}
        payload["a2flow"]["name"] = "Token rotation runbook"
        payload["client_context"] = {"conversation_ref": "token-rotation-discussion"}
        payload["bindings"][0]["credential_ref"] = "credential://id/{}".format(credential.id)
        accepted = _route(space, "validate", payload)
        draft = _route(
            space,
            "draft",
            {
                "run_id": accepted["run_id"],
                "revision_id": accepted["revision_id"],
                "plan_hash": accepted["plan_hash"],
                "idempotency_key": "token-rotation-draft",
            },
        )
        persisted_values = list(_new_persisted_values(before))

    assert accepted["ok"] is True, accepted
    assert draft["ok"] is True, draft
    binding = CapabilityBinding.objects.get(revision_id=accepted["revision_id"])
    assert binding.credential_ref == "credential://id/{}".format(credential.id)
    counters = MeasuredSecurityCounters.observe(
        responses=[accepted, draft],
        logs=list(_log_values(caplog.records)),
        persisted_values=persisted_values,
        secret_sentinel=credential_body_sentinel,
    )
    assert counters.secret_or_token_exposure == 0


@pytest.mark.parametrize(
    "mode,snapshot,expected_code",
    [
        (
            "version",
            {
                "plugin_type": "component",
                "source_key": None,
                "code": "b1_drift_version",
                "version": "1.0.0",
                "input_key": "host",
            },
            "SCHEMA_DRIFT",
        ),
        (
            "schema_hash",
            {
                "plugin_type": "uniform_api",
                "source_key": "b1-drift-schema-source",
                "code": "b1_drift_schema",
                "version": "1.0.0",
                "input_key": "region",
            },
            "SCHEMA_DRIFT",
        ),
        (
            "source_revoked",
            {
                "plugin_type": "uniform_api",
                "source_key": "b1-drift-revoked-source",
                "code": "b1_drift_revoked",
                "version": "1.0.0",
                "input_key": "cluster",
            },
            "CAPABILITY_FORBIDDEN",
        ),
    ],
)
def test_real_search_schema_validate_drift_has_zero_silent_acceptance(mode, snapshot, expected_code, monkeypatch):
    """Fresh public validation rejects version, same-version hash and authorization drift."""
    high_phase = _guard_high_phase(monkeypatch)
    space = _security_space("security-drift-{}".format(mode.replace("_", "-")))
    with GoldenCatalog(snapshot, space_id=space.id, username="security-user") as catalog:
        assert isinstance(catalog.service, PluginSchemaService)
        search = _route(space, "search", {"query": snapshot["code"]})
        card = _search_card(search)
        schema = _schema_payload(
            _route(
                space,
                "schema",
                {"capability_ref": card["capability_ref"], "expected_schema_hash": card["schema_hash"]},
            )
        )
        before_revisions = set(WorkflowPlanRevision.objects.values_list("pk", flat=True))
        before_templates = set(Template.objects.values_list("pk", flat=True))
        before_snapshots = set(TemplateSnapshot.objects.values_list("pk", flat=True))
        release_before = ReleaseDatabaseObservation.capture()

        catalog.drift(mode)
        response = _route(
            space,
            "validate",
            _workflow_payload(card, schema, idempotency_key="drift-{}".format(mode)),
        )
        release_after = ReleaseDatabaseObservation.capture()

    rejected = (
        response["ok"] is False
        and response["revision_id"] is None
        and response["errors"][0]["code"] == expected_code
        and set(WorkflowPlanRevision.objects.values_list("pk", flat=True)) == before_revisions
        and set(Template.objects.values_list("pk", flat=True)) == before_templates
        and set(TemplateSnapshot.objects.values_list("pk", flat=True)) == before_snapshots
    )
    counters = MeasuredReleaseCounters.observe(
        responses=[response],
        drift_rejected=[rejected],
        database_before=release_before,
        database_after=release_after,
        expected_drafts=0,
        release_spies=high_phase.release_spies,
        task_spies=high_phase.task_spies,
        execution_spies=high_phase.execution_spies,
    )
    assert counters.silent_schema_drift == 0
    assert counters.duplicate_drafts == 0
    assert counters.published_templates == 0
    assert counters.created_tasks == 0
    assert counters.real_executions == 0


def test_p0_public_surface_has_no_direct_execution_or_publish_operation():
    """The fixed public Facade remains draft-only and exposes exactly four operations."""
    assert set(P0_TOOL_OPERATION_MAP) == {
        "search_workflow_capabilities",
        "get_plugin_schema",
        "validate_workflow",
        "create_workflow_draft",
    }
    assert not {"release", "publish", "debug", "execute", "sdk"}.intersection(P0_TOOL_OPERATION_MAP)


@pytest.mark.parametrize(
    "case_id,operation,payload",
    [
        (
            "auto-release",
            "draft",
            {
                "run_id": "00000000-0000-0000-0000-000000000001",
                "revision_id": "00000000-0000-0000-0000-000000000002",
                "plan_hash": "a" * 64,
                "idempotency_key": "forbid-auto-release",
                "auto_release": True,
            },
        ),
        ("publish", "search", {"query": "safe", "publish": True}),
        ("release", "search", {"query": "safe", "release": "1.0.0"}),
        ("debug", "search", {"query": "safe", "debug": {"mode": "global"}}),
        ("execute", "search", {"query": "safe", "execute": True}),
        ("sdk", "search", {"query": "safe", "sdk_xxx": "invoke"}),
        ("token", "search", {"query": "safe", "token": "forbidden-token"}),
        (
            "nested-token",
            "validate",
            {
                "intent_spec": {},
                "a2flow": {},
                "bindings": [],
                "idempotency_key": "forbidden-nested-token",
                "client_context": {"token": "forbidden-token"},
            },
        ),
        ("direct-action", "search", {"query": "safe", "action": "direct_plugin"}),
        (
            "direct-invocation",
            "search",
            {"query": "safe", "direct_plugin_invocation": {"code": "unsafe", "inputs": {}}},
        ),
        ("plugin-action", "search", {"query": "safe", "plugin_action": "invoke"}),
    ],
)
def test_public_routes_reject_high_phase_and_direct_plugin_fields_before_domain(
    case_id, operation, payload, monkeypatch
):
    """Catch any closed-DTO regression that reaches P0, Task 7, provider, release, task or debug code."""
    high_phase = _guard_high_phase(monkeypatch)
    space = _security_space("forbidden-{}".format(case_id))
    before = ReleaseDatabaseObservation.capture()
    guarded = []
    with ExitStack() as stack:
        guarded.extend(
            [
                stack.enter_context(patch.object(HarnessFacade, _PATHS[operation], Mock(side_effect=AssertionError))),
                stack.enter_context(
                    patch("bkflow.harness.services.facade.create_workflow_draft", Mock(side_effect=AssertionError))
                ),
                stack.enter_context(
                    patch("bkflow.harness.services.draft.create_workflow_draft", Mock(side_effect=AssertionError))
                ),
                stack.enter_context(
                    patch(
                        "bkflow.harness.services.draft.create_template_draft_from_pipeline_tree",
                        Mock(side_effect=AssertionError),
                    )
                ),
                stack.enter_context(
                    patch.object(PluginSchemaService, "list_plugins", Mock(side_effect=AssertionError))
                ),
                stack.enter_context(
                    patch.object(PluginSchemaService, "get_plugin_schema", Mock(side_effect=AssertionError))
                ),
            ]
        )
        response = _route(space, operation, payload, correlation_id="forbidden-boundary")
    after = ReleaseDatabaseObservation.capture()

    assert response["ok"] is False
    assert response["run_id"] is None
    assert response["revision_id"] is None
    assert response["artifact_refs"] == []
    assert response["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert all(item.call_count == 0 for item in guarded)
    assert all(item.call_count == 0 for item in high_phase.all_spies)
    counters = MeasuredReleaseCounters.observe(
        database_before=before,
        database_after=after,
        expected_drafts=0,
        release_spies=high_phase.release_spies,
        task_spies=high_phase.task_spies,
        execution_spies=high_phase.execution_spies,
    )
    assert counters.duplicate_drafts == 0
    assert counters.published_templates == 0
    assert counters.created_tasks == 0
    assert counters.real_executions == 0


def test_versioned_route_surface_is_exactly_p0_through_p4_operations():
    """Catch an uncontracted route while retaining the exact cumulative P4 surface."""
    harness_routes = {str(pattern.pattern) for pattern in apigw_urlpatterns if "/harness/" in str(pattern.pattern)}
    assert harness_routes == {
        r"^space/(?P<space_id>\d+)/harness/search_workflow_capabilities/$",
        r"^space/(?P<space_id>\d+)/harness/get_plugin_schema/$",
        r"^space/(?P<space_id>\d+)/harness/validate_workflow/$",
        r"^space/(?P<space_id>\d+)/harness/create_workflow_draft/$",
        r"^space/(?P<space_id>\d+)/harness/search_workflow_knowledge/$",
        r"^space/(?P<space_id>\d+)/harness/start_debug_session/$",
        r"^space/(?P<space_id>\d+)/harness/run_debug/$",
        r"^space/(?P<space_id>\d+)/harness/get_debug_session/$",
        r"^space/(?P<space_id>\d+)/harness/control_debug_session/$",
        r"^space/(?P<space_id>\d+)/harness/prepare_release/$",
        r"^space/(?P<space_id>\d+)/harness/publish_workflow/$",
        r"^space/(?P<space_id>\d+)/harness/start_workflow_execution/$",
        r"^space/(?P<space_id>\d+)/harness/get_workflow_execution/$",
        r"^space/(?P<space_id>\d+)/harness/control_workflow_execution/$",
        r"^space/(?P<space_id>\d+)/harness/submit_generation_feedback/$",
    }
    assert P0_TOOL_OPERATION_MAP == {
        "search_workflow_capabilities": "harness_search_workflow_capabilities",
        "get_plugin_schema": "harness_get_plugin_schema",
        "validate_workflow": "harness_validate_workflow",
        "create_workflow_draft": "harness_create_workflow_draft",
    }


def test_public_draft_same_key_replay_has_one_draft_and_no_high_phase_side_effects(monkeypatch):
    """Catch a public same-key retry creating a duplicate, release, task, debug session or execution."""
    high_phase = _guard_high_phase(monkeypatch)
    space = _security_space("security-idempotent-draft")
    snapshot = {
        "plugin_type": "uniform_api",
        "source_key": "b2-draft-source",
        "code": "b2_idempotent_draft",
        "version": "1.0.0",
        "input_key": "region",
    }
    with GoldenCatalog(snapshot, space_id=space.id, username="security-user"):
        accepted = _valid_public_revision(space, snapshot, "b2-validation")
        request = {
            "run_id": accepted["run_id"],
            "revision_id": accepted["revision_id"],
            "plan_hash": accepted["plan_hash"],
            "idempotency_key": "b2-draft-replay",
        }
        before = ReleaseDatabaseObservation.capture()
        first = _route(space, "draft", request, correlation_id="b2-draft-replay")
        replay = _route(space, "draft", request, correlation_id="b2-draft-replay")
        after = ReleaseDatabaseObservation.capture()

    assert first["ok"] is True, first
    assert replay == first
    _assert_one_draft(accepted, request, first, before, after)
    counters = MeasuredReleaseCounters.observe(
        responses=[first, replay],
        database_before=before,
        database_after=after,
        expected_drafts=1,
        release_spies=high_phase.release_spies,
        task_spies=high_phase.task_spies,
        execution_spies=high_phase.execution_spies,
    )
    assert counters.duplicate_drafts == 0
    assert counters.published_templates == 0
    assert counters.created_tasks == 0
    assert counters.real_executions == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(
    not connection.features.has_select_for_update,
    reason="SQLite cannot prove the two-connection row-lock boundary; serial exact-once remains covered",
)
def test_two_public_draft_connections_lock_then_replay_one_real_resource(monkeypatch):
    """Catch a same-key contender bypassing the locked run and materializing a second draft."""
    high_phase = _guard_high_phase(monkeypatch)
    space = _security_space("security-concurrent-draft")
    snapshot = {
        "plugin_type": "uniform_api",
        "source_key": "b2-concurrent-source",
        "code": "b2_concurrent_draft",
        "version": "1.0.0",
        "input_key": "region",
    }
    with GoldenCatalog(snapshot, space_id=space.id, username="security-user"):
        accepted = _valid_public_revision(space, snapshot, "b2-concurrent-validation")
        request = {
            "run_id": accepted["run_id"],
            "revision_id": accepted["revision_id"],
            "plan_hash": accepted["plan_hash"],
            "idempotency_key": "b2-concurrent-replay",
        }
        before = ReleaseDatabaseObservation.capture()
        owner_after_lock = Event()
        release_owner = Event()
        contender_at_lock_sql = Event()
        materialize_calls = []
        run_table = HarnessRun._meta.db_table.lower()

        from bkflow.harness.services import draft as draft_service

        real_materialize = draft_service.create_template_draft_from_pipeline_tree

        def hold_owner_after_run_lock(**kwargs):
            materialize_calls.append(1)
            owner_after_lock.set()
            if not release_owner.wait(timeout=10):
                raise AssertionError("timed out while holding the owner run lock")
            return real_materialize(**kwargs)

        def invoke(label):
            close_old_connections()

            def observe_lock_sql(execute, sql, params, many, context):
                normalized = sql.lower()
                if label == "contender" and run_table in normalized and "for update" in normalized:
                    contender_at_lock_sql.set()
                return execute(sql, params, many, context)

            try:
                with connection.execute_wrapper(observe_lock_sql):
                    return _route(space, "draft", request, correlation_id="b2-concurrent")
            finally:
                close_old_connections()

        with patch(
            "bkflow.harness.services.draft.create_template_draft_from_pipeline_tree",
            side_effect=hold_owner_after_run_lock,
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                owner = executor.submit(invoke, "owner")
                assert owner_after_lock.wait(timeout=10), "owner never reached the post-run-lock materializer"
                contender = executor.submit(invoke, "contender")
                assert contender_at_lock_sql.wait(timeout=10), "contender never reached SELECT FOR UPDATE"
                time.sleep(0.1)
                assert contender.done() is False, "contender bypassed the held run lock"
                release_owner.set()
                responses = [owner.result(timeout=20), contender.result(timeout=20)]

        for response in list(responses):
            if response["ok"] is False:
                assert response["errors"][0]["code"] == "RETRYABLE_INFRA", response
                responses.append(_route(space, "draft", request, correlation_id="b2-concurrent-retry"))
        after = ReleaseDatabaseObservation.capture()

    successful = [response for response in responses if response["ok"] is True]
    assert successful
    assert len({repr(response["artifact_refs"]) for response in successful}) == 1
    assert materialize_calls == [1]
    _assert_one_draft(accepted, request, successful[-1], before, after)
    counters = MeasuredReleaseCounters.observe(
        responses=responses,
        database_before=before,
        database_after=after,
        expected_drafts=1,
        release_spies=high_phase.release_spies,
        task_spies=high_phase.task_spies,
        execution_spies=high_phase.execution_spies,
    )
    assert counters.duplicate_drafts == 0
    assert counters.published_templates == 0
    assert counters.created_tasks == 0
    assert counters.real_executions == 0
