"""Real conversion and persistence across variable-bearing release preparation."""

import pytest
from django.utils import timezone
from pipeline.component_framework.models import ComponentModel
from pipeline.variable_framework.models import VariableModel

from bkflow.harness.constants import DebugMode, DebugSessionStatus, HarnessRunStatus
from bkflow.harness.models import (
    DebugSession,
    HarnessRun,
    ReleaseManifest,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import sha256_json
from bkflow.harness.services.capability_ref import encode_capability_ref
from bkflow.harness.services.debug.policy import trusted_context_snapshot
from bkflow.harness.services.draft import create_workflow_draft
from bkflow.harness.services.evidence import record_evidence
from bkflow.harness.services.release.facade import prepare_release_with_context
from bkflow.harness.services.release.policy import ReleasePolicy
from bkflow.harness.services.resolver import CapabilityResolver
from bkflow.harness.services.validator import WorkflowValidator
from bkflow.pipeline_plugins.components.collections.pause.legacy import PauseComponent
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService
from bkflow.space.configs import HarnessPublishEnabledConfig
from bkflow.space.models import Space, SpaceConfig
from bkflow.template.debug.dependency import compute_tree_fingerprint
from bkflow.template.models import Template
from tests.interface.harness.release.test_prepare_release import trusted_context


@pytest.mark.django_db
@pytest.mark.parametrize("variable_type", ["custom", "component_outputs"])
def test_real_variable_conversion_survives_validation_draft_and_release_preparation(monkeypatch, variable_type):
    """Adding is_param during validation must not make a real converted draft stale."""
    space = Space.objects.create(name="variable release", app_code="trusted-app", platform_url="")
    context = trusted_context(space_id=space.id, scope_value=str(space.id))
    SpaceConfig.objects.create(
        space_id=space.id, name=HarnessPublishEnabledConfig.name, value_type="TEXT", text_value="true"
    )
    ComponentModel.objects.create(code=PauseComponent.code, version=PauseComponent.version, name="pause", status=True)
    VariableModel.objects.create(code="input", status=True)
    monkeypatch.setattr(
        "bkflow.plugin.services.plugin_schema_service.ComponentLibrary.get_component_class",
        lambda code, version: PauseComponent,
    )
    service = PluginSchemaService(space_id=space.id, username=context.actor)
    resolver = CapabilityResolver(service)
    reference = encode_capability_ref("component", None, PauseComponent.code, PauseComponent.version)
    capability = resolver.resolve(reference)
    variable = {
        "key": "${payload}",
        "name": "payload",
        "source_type": variable_type,
        "show_type": "show" if variable_type == "custom" else "hide",
        "custom_type": "input" if variable_type == "custom" else "",
        "value": "synthetic" if variable_type == "custom" else "",
        "source_info": {} if variable_type == "custom" else {"A": ["callback_data"]},
    }
    request = {
        "intent_spec": {"goal": "variable release preparation only"},
        "a2flow": {
            "version": "2.0",
            "name": "variable release",
            "nodes": [
                {"id": "A", "type": "Activity", "name": "First", "inputs": {"description": "synthetic"}, "next": "B"},
                {
                    "id": "B",
                    "type": "Activity",
                    "name": "Second",
                    "inputs": {"description": "payload: ${payload}"},
                    "next": "end",
                },
            ],
            "variables": [variable],
        },
        "bindings": [
            {
                "node_id": node,
                "capability_ref": reference,
                "schema_hash": capability.schema_hash,
                "credential_ref": None,
            }
            for node in ("A", "B")
        ],
        "idempotency_key": "validate-variable",
    }
    validator = WorkflowValidator(context, resolver=resolver)
    accepted = validator.validate_workflow(request)
    assert accepted["ok"] is True, accepted
    drafted = create_workflow_draft(
        context,
        {**{key: accepted[key] for key in ("run_id", "revision_id", "plan_hash")}, "idempotency_key": "draft-variable"},
        plugin_schema_service=service,
    )
    assert drafted["ok"] is True, drafted
    run = HarnessRun.objects.get(run_id=accepted["run_id"])
    revision = WorkflowPlanRevision.objects.get(id=accepted["revision_id"])
    template = Template.objects.get(id=drafted["artifact_refs"][0]["template_id"])
    tree = template.snapshot.data
    # Only local debug evidence is seeded here; this test never runs a plugin or claims engine E2E.
    run.status = HarnessRunStatus.RELEASE_READY
    run.save(update_fields=["status"])
    session = DebugSession.objects.create(
        run=run,
        revision=revision,
        template_id=template.id,
        debug_context_id=1,
        mode=DebugMode.GLOBAL,
        status=DebugSessionStatus.COMPLETED,
        plan_hash=revision.plan_hash,
        tree_fingerprint=compute_tree_fingerprint(tree),
        actor=context.actor,
        policy_version=context.policy_version,
        trusted_context_snapshot=trusted_context_snapshot(context),
        expires_at=timezone.now() + timezone.timedelta(minutes=5),
        last_heartbeat_at=timezone.now(),
        terminal_reason="debug_completed",
    )
    record_evidence(
        run=run,
        revision=revision,
        debug_session=session,
        event_type="DEBUG_SESSION_COMPLETED",
        action="get_debug_session",
        payload={"session_id": str(session.id), "status": DebugSessionStatus.COMPLETED, "reason": "debug_completed"},
        actor=context.actor,
        correlation_id=context.correlation_id,
    )
    profile = {
        "version": "harness-postconditions-p3-v1",
        "operator": "all",
        "predicates": [{"type": "OUTPUT_EXISTS", "node_id": "A", "output_key": "callback_data"}],
    }
    prepared = prepare_release_with_context(
        context,
        {
            "run_id": str(run.run_id),
            "revision_id": str(revision.id),
            "expected_plan_hash": revision.plan_hash,
            "idempotency_key": "prepare-variable",
        },
        resolver=resolver,
        release_policy=ReleasePolicy(profiles={context.policy_version: profile}),
    )
    assert prepared["ok"] is True, prepared
    assert ReleaseManifest.objects.count() == 1
    converted = validator._convert(
        revision.canonical_a2flow, [{"node_id": node, "capability": capability} for node in ("A", "B")]
    )
    assert tree == converted.pipeline_tree
    assert accepted["artifact_refs"][0]["pipeline_tree_hash"] == sha256_json(converted.pipeline_tree)
    assert "is_param" not in tree["constants"]["${payload}"]
