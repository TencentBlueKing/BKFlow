"""Forty table-driven P2 Golden Cases backed by actual Harness services."""

import copy
import datetime
import hashlib
from collections import Counter
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import pytest
import yaml
from django.utils import timezone

from bkflow.harness.constants import DebugMode, DebugSessionStatus
from bkflow.harness.models import (
    CapabilityBinding,
    DebugSession,
    EvidenceEvent,
    HarnessIdempotencyRecord,
    HarnessRun,
    TokenLease,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import canonical_scope, sha256_json
from bkflow.harness.services.contract_versions import tools_for_contract
from bkflow.harness.services.debug.approval import DebugApprovalDecision
from bkflow.harness.services.debug.facade import (
    control_debug_session_with_context,
    get_debug_session_with_context,
    run_debug_with_context,
    start_debug_session_with_context,
)
from bkflow.harness.services.token_broker import TokenBroker
from bkflow.harness.services.validator import WorkflowValidator
from bkflow.permission.models import Token
from bkflow.space.configs import HarnessDebugEnabledConfig, SpaceConfigValueType
from bkflow.space.models import Space, SpaceConfig
from bkflow.template.debug.dependency import compute_tree_fingerprint
from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugContext, DebugNodeState, TemplateSnapshot
from tests.interface.template.debug.test_step_run import TREE_GATEWAY

pytest_plugins = ("tests.interface.harness.debug.test_start_session",)

REQUEST_PLACEHOLDERS = frozenset({"$session_id", "$plan_hash", "$run_id", "$revision_id"})

FIXTURE_FILE = Path(__file__).resolve().parents[3] / "fixtures/harness/debug_cases.yaml"
MAKEFILE = Path(__file__).resolve().parents[4] / "Makefile"
FIXTURE = yaml.safe_load(FIXTURE_FILE.read_text(encoding="utf-8"))
CASES = FIXTURE["cases"]
EXPECTED_COUNTS = {
    "step_mock_success_failure": 8,
    "step_dependency_blocked": 5,
    "global_mock_lifecycle": 5,
    "session_lock_conflict": 5,
    "reset_and_control": 4,
    "terminate_and_recovery": 4,
    "plan_or_fingerprint_drift": 3,
    "token_lifecycle": 3,
    "forged_or_expired_approval": 3,
}
REQUIRED_CASE_FIELDS = {
    "id",
    "category",
    "trusted_context",
    "predecessor_revision",
    "draft_fingerprint",
    "request",
    "expected_envelope_code",
    "state_transition",
    "evidence_events",
    "token_lease_result",
    "external_mutations",
    "forbidden_markers",
}


@dataclass
class ScenarioResult:
    response: dict
    before_run: str
    before_session: str
    after_run: str
    after_session: str
    evidence_events: list
    external_mutations: int = 0
    trusted_context: dict = None
    predecessor_revision: dict = None
    draft_fingerprint: dict = None
    materialized_tool: str = None
    materialized_request: dict = None


def _response_code(response):
    return "OK" if response["ok"] else response["errors"][0]["code"]


def _trusted_context_facts(context):
    return {
        "platform_key": context.platform_key,
        "platform_app": context.platform_app,
        "actor": context.actor,
        "space_id": context.space_id,
        "scope_type": context.scope_type,
        "scope_value": context.scope_value,
        "target_environment": context.target_environment,
        "policy_version": context.policy_version,
        "mcp_contract_version": context.mcp_contract_version,
    }


def _materialize_value(value, runtime):
    if isinstance(value, dict):
        return {key: _materialize_value(item, runtime) for key, item in value.items()}
    if isinstance(value, list):
        return [_materialize_value(item, runtime) for item in value]
    if isinstance(value, str) and value in REQUEST_PLACEHOLDERS:
        return runtime[value]
    return copy.deepcopy(value)


def _materialize_case_request(case, *, session=None, run=None, revision=None, extra=None):
    run = run or (session.run if session is not None else None)
    revision = revision or (session.revision if session is not None else None)
    runtime = {
        "$session_id": str(session.id) if session is not None else None,
        "$plan_hash": revision.plan_hash if revision is not None else None,
        "$run_id": str(run.run_id) if run is not None else None,
        "$revision_id": str(revision.id) if revision is not None else None,
    }
    runtime.update(extra or {})
    tool = case["request"]["tool"]
    payload = _materialize_value(case["request"]["payload"], runtime)
    assert all(value is not None for key, value in runtime.items() if key in str(case["request"]["payload"]))
    return tool, payload


def _assert_materialized_template(template, actual):
    if isinstance(template, dict):
        assert isinstance(actual, dict)
        assert set(actual) == set(template)
        for key, value in template.items():
            _assert_materialized_template(value, actual[key])
        return
    if isinstance(template, list):
        assert isinstance(actual, list)
        assert len(actual) == len(template)
        for expected_item, actual_item in zip(template, actual):
            _assert_materialized_template(expected_item, actual_item)
        return
    if isinstance(template, str) and template in REQUEST_PLACEHOLDERS:
        assert actual is not None
        assert actual != template
        return
    assert actual == template


def _audit_facts(context, run, revision, *, session=None):
    latest = run.revisions.order_by("-sequence").first()
    report = run.validation_reports.filter(revision=revision, checkpoint="VALIDATE").order_by("-create_at").first()
    artifact = next(
        value
        for value in run.artifact_references
        if value.get("type") == "harness_draft" and value.get("revision_id") == str(revision.id)
    )
    snapshot = TemplateSnapshot.objects.get(
        template_id=artifact["template_id"],
        draft=True,
        is_deleted=False,
    )
    exact = artifact.get("pipeline_tree_hash") == sha256_json(snapshot.data)
    if session is not None:
        exact = exact and session.tree_fingerprint == compute_tree_fingerprint(snapshot.data)
    return (
        _trusted_context_facts(context),
        {
            "relation": "latest" if latest.id == revision.id else "superseded",
            "sequence": revision.sequence,
            "validation": "passed" if report is not None and report.result.get("valid") is True else "failed",
        },
        {"relation": "exact" if exact else "drifted", "algorithm": "sha256"},
    )


def _ensure_space(context):
    Space.objects.get_or_create(
        id=context.space_id,
        defaults={
            "app_code": context.platform_app,
            "platform_url": "http://example.test",
            "name": "golden-debug-space",
        },
    )


def _enable_debug(context):
    SpaceConfig.objects.get_or_create(
        space_id=context.space_id,
        name=HarnessDebugEnabledConfig.name,
        defaults={"value_type": SpaceConfigValueType.TEXT.value, "text_value": "true"},
    )


def _started(start_case, *, mode=DebugMode.STEP):
    context, _run, _revision, _template, request, resolver = start_case
    response = start_debug_session_with_context(context, {**request, "mode": mode}, resolver=resolver)
    assert response["ok"] is True
    return context, DebugSession.objects.get(), resolver


def _issue_lease(context, session, mocker):
    _ensure_space(context)
    mocker.patch("bkflow.permission.services.token_issuer.TokenResourceValidator.validate", return_value=None)
    return TokenBroker().acquire_debug_lease(context, session)


def _event_ids():
    return set(EvidenceEvent._base_manager.values_list("id", flat=True))


def _new_events(before):
    return list(
        EvidenceEvent._base_manager.exclude(id__in=before)
        .order_by("occurred_at", "id")
        .values_list("event_type", flat=True)
    )


def _result(
    response,
    context,
    session,
    before_run,
    before_session,
    evidence_before,
    *,
    tool,
    payload,
    external_mutations=0,
):
    session.refresh_from_db()
    session.run.refresh_from_db()
    trusted, predecessor, fingerprint = _audit_facts(context, session.run, session.revision, session=session)
    return ScenarioResult(
        response=response,
        before_run=before_run,
        before_session=before_session,
        after_run=session.run.status,
        after_session=session.status,
        evidence_events=_new_events(evidence_before),
        external_mutations=external_mutations,
        trusted_context=trusted,
        predecessor_revision=predecessor,
        draft_fingerprint=fingerprint,
        materialized_tool=tool,
        materialized_request=payload,
    )


def _prepare_gateway(start_case):
    return _replace_tree(start_case, TREE_GATEWAY)


def _replace_tree(start_case, pipeline_tree):
    context, run, revision, template, request, resolver = start_case
    snapshot = TemplateSnapshot.objects.get(pk=template.snapshot_id)
    snapshot.data = copy.deepcopy(pipeline_tree)
    snapshot.save(update_fields=["data"])
    artifacts = copy.deepcopy(run.artifact_references)
    artifacts[0]["pipeline_tree_hash"] = sha256_json(pipeline_tree)
    run.artifact_references = artifacts
    run.save(update_fields=["artifact_references"])
    report = run.validation_reports.get(checkpoint="VALIDATE")
    report.result["pipeline_tree_hash"] = artifacts[0]["pipeline_tree_hash"]
    report.save(update_fields=["result"])
    return context, run, revision, template, request, resolver


def _transitive_tree(start_case):
    _context, _run, _revision, template, _request, _resolver = start_case
    tree = copy.deepcopy(TemplateSnapshot.objects.get(pk=template.snapshot_id).data)
    tree["activities"]["C"] = {
        "id": "C",
        "type": "ServiceActivity",
        "component": {"code": "test", "data": {"value": {"hook": True, "value": "${result_b}"}}},
    }
    tree["flows"]["f2"] = {"id": "f2", "source": "B", "target": "C"}
    tree["constants"]["${result_b}"] = {
        "key": "${result_b}",
        "name": "Result B",
        "show_type": "hide",
        "value": "",
        "source_type": "component_outputs",
        "custom_type": "",
        "source_info": {"B": ["result"]},
    }
    return tree


def _missing_input_tree(start_case):
    _context, _run, _revision, template, _request, _resolver = start_case
    tree = copy.deepcopy(TemplateSnapshot.objects.get(pk=template.snapshot_id).data)
    tree["activities"]["A"]["component"]["data"] = {"required": {"hook": True, "value": "${runtime_missing}"}}
    tree["constants"]["${runtime_missing}"] = {
        "key": "${runtime_missing}",
        "name": "Runtime missing",
        "show_type": "hide",
        "value": "",
        "source_type": "component_outputs",
        "custom_type": "",
        "source_info": {"Z": ["result"]},
    }
    return tree


def _run_step(case, start_case, mocker, *, variant):
    context, session, resolver = _started(start_case)
    if variant == "failure":
        _issue_lease(context, session, mocker)
    elif variant == "safe_projection":
        debug_context = DebugContext.objects.get(pk=session.debug_context_id)
        debug_context.global_vars = {"password": "FORBIDDEN_PROVIDER_SENTINEL"}
        debug_context.save(update_fields=["global_vars"])
    tool, request = _materialize_case_request(case, session=session)
    assert tool == "run_debug"
    evidence_before = _event_ids()
    before_run, before_session = session.run.status, session.status
    response = run_debug_with_context(context, request, resolver=resolver)
    if variant == "replay":
        assert run_debug_with_context(context, request, resolver=resolver) == response
    if variant == "safe_projection":
        assert response["artifact_refs"][0]["updated_global_vars"]["password"] == "[REDACTED]"
    if variant == "updates_globals":
        assert response["artifact_refs"][0]["updated_global_vars"]["${result}"] == "persisted-global"
    if variant == "empty_outputs":
        assert response["artifact_refs"][0]["outputs"] == {}
    if variant == "multiple_outputs":
        assert response["artifact_refs"][0]["outputs"] == {"detail": "secondary", "result": "primary"}
    return _result(
        response,
        context,
        session,
        before_run,
        before_session,
        evidence_before,
        tool=tool,
        payload=request,
    )


def _run_dependency(case, start_case, mocker, *, variant):
    if variant == "transitive_missing":
        _replace_tree(start_case, _transitive_tree(start_case))
    elif variant == "global_var_missing":
        _replace_tree(start_case, _missing_input_tree(start_case))
    elif variant == "gateway_input_missing":
        _prepare_gateway(start_case)
    context, session, resolver = _started(start_case)
    if variant == "no_result_evidence":
        completed = DebugNodeState.objects.get(debug_context_id=session.debug_context_id, node_id="A")
        completed.status = "finished"
        completed.outputs = {}
        completed.save(update_fields=["status", "outputs"])
    tool, request = _materialize_case_request(case, session=session)
    assert tool == "run_debug"
    node_id = request["node_id"]
    kwargs = {"resolver": resolver}
    if variant == "gateway_input_missing":
        _issue_lease(context, session, mocker)
        verifier = mocker.MagicMock()
        verifier.verify.return_value = DebugApprovalDecision(
            True,
            "golden-verifier",
            hashlib.sha256(request["approval_receipt_ref"].encode("utf-8")).hexdigest(),
            "d" * 64,
            "approved",
        )
        mocker.patch("bkflow.harness.services.debug.run.is_harness_real_step_enabled", return_value=True)
        kwargs.update(approval_verifier=verifier, token_broker=TokenBroker(), allow_real=True)
    evidence_before = _event_ids()
    before_run, before_session = session.run.status, session.status
    response = run_debug_with_context(context, request, **kwargs)
    assert not EvidenceEvent.objects.exclude(id__in=evidence_before).exists()
    assert DebugNodeState.objects.get(debug_context_id=session.debug_context_id, node_id=node_id).status == "not_run"
    if variant == "transitive_missing":
        assert DebugNodeState.objects.filter(debug_context_id=session.debug_context_id, node_id="C").exists()
    elif variant == "global_var_missing":
        assert "${runtime_missing}" not in DebugContext.objects.get(pk=session.debug_context_id).global_vars
    elif variant == "gateway_input_missing":
        assert (
            DebugNodeState.objects.get(debug_context_id=session.debug_context_id, node_id="G").node_type
            == "ExclusiveGateway"
        )
    elif variant == "no_result_evidence":
        completed.refresh_from_db()
        assert completed.status == "finished"
        assert completed.outputs == {}
        assert not EvidenceEvent.objects.filter(action="run_debug").exists()
    else:
        assert variant == "direct_missing"
    return _result(
        response,
        context,
        session,
        before_run,
        before_session,
        evidence_before,
        tool=tool,
        payload=request,
    )


def _running_context(session, *, run_type, task_id=7701):
    session.status = DebugSessionStatus.RUNNING
    session.current_task_id = task_id
    session.save(update_fields=["status", "current_task_id"])
    DebugContext.objects.filter(pk=session.debug_context_id).update(
        status="running",
        active_task_id=task_id,
        active_run_type=run_type,
        last_task_id=task_id,
        last_run_type=run_type,
        last_run_status="running",
    )


def _clone_validated_run_for_same_template(start_case):
    context, source_run, source_revision, template, _request, resolver = start_case
    run = HarnessRun.objects.create(
        platform=context.platform_key,
        platform_app=context.platform_app,
        actor=context.actor,
        space_id=context.space_id,
        scope=canonical_scope(context.scope_type, context.scope_value),
        environment=context.target_environment,
        status="DRAFT_READY",
        policy_version=context.policy_version,
        mcp_contract_version=context.mcp_contract_version,
    )
    revision = WorkflowPlanRevision.objects.create(
        run=run,
        sequence=1,
        intent_spec=copy.deepcopy(source_revision.intent_spec),
        canonical_a2flow=copy.deepcopy(source_revision.canonical_a2flow),
        plan_hash=source_revision.plan_hash,
    )
    for binding in source_revision.capability_bindings.all():
        CapabilityBinding.objects.create(
            revision=revision,
            node_id=binding.node_id,
            capability_ref=binding.capability_ref,
            resolved_version=binding.resolved_version,
            schema_hash=binding.schema_hash,
            conversion_fingerprint=binding.conversion_fingerprint,
            credential_ref=binding.credential_ref,
            risk=binding.risk,
        )
    artifact = copy.deepcopy(source_run.artifact_references[0])
    artifact["revision_id"] = str(revision.id)
    run.artifact_references = [artifact]
    run.save(update_fields=["artifact_references"])
    source_report = source_run.validation_reports.get(checkpoint="VALIDATE")
    ValidationReport.objects.create(
        run=run,
        revision=revision,
        checkpoint="VALIDATE",
        validator_version=WorkflowValidator.VERSION,
        result=copy.deepcopy(source_report.result),
        risk_manifest=copy.deepcopy(source_report.risk_manifest),
        errors=[],
        warnings=[],
        correlation_id=context.correlation_id,
    )
    return context, run, revision, template, resolver


def _run_global(case, start_case, mocker, *, variant):
    context, session, resolver = _started(start_case, mode=DebugMode.GLOBAL)
    if variant in {"completion_poll", "failure_poll"}:
        _enable_debug(context)
        _running_context(session, run_type="global")
        if variant == "failure_poll":
            _issue_lease(context, session, mocker)
        calls = {"count": 0}

        def settle(_service, context_row):
            calls["count"] += 1
            context_row.status = "idle"
            context_row.active_task_id = None
            context_row.last_task_id = session.current_task_id
            context_row.last_run_type = "global"
            context_row.last_run_status = "finished" if variant == "completion_poll" else "failed"
            context_row.save(
                update_fields=["status", "active_task_id", "last_task_id", "last_run_type", "last_run_status"]
            )

        mocker.patch.object(DebugService, "sync_from_debug_task", settle)
        tool, request = _materialize_case_request(case, session=session)
        assert tool == "get_debug_session"
        evidence_before = _event_ids()
        before_run, before_session = session.run.status, session.status
        response = get_debug_session_with_context(
            context,
            request,
            resolver=resolver,
        )
        return _result(
            response,
            context,
            session,
            before_run,
            before_session,
            evidence_before,
            tool=tool,
            payload=request,
            external_mutations=calls["count"],
        )

    client = mocker.MagicMock()
    client.create_task.return_value = {
        "result": True,
        "data": {"id": 7701},
        "message": "FORBIDDEN_PROVIDER_SENTINEL",
    }
    client.operate_task.return_value = {"result": True, "message": "FORBIDDEN_PROVIDER_SENTINEL"}
    mocker.patch("bkflow.template.debug.service.DebugService._task_client", return_value=client)
    if variant == "force_all_mock":
        DebugNodeState.objects.filter(debug_context_id=session.debug_context_id).update(execution_mode="real")
    tool, request = _materialize_case_request(case, session=session)
    assert tool == "run_debug"
    evidence_before = _event_ids()
    before_run, before_session = session.run.status, session.status
    response = run_debug_with_context(context, request, resolver=resolver)
    if variant == "replay":
        assert run_debug_with_context(context, request, resolver=resolver) == response
    if variant == "force_all_mock":
        assert set(
            DebugNodeState.objects.filter(debug_context_id=session.debug_context_id).values_list(
                "execution_mode", flat=True
            )
        ) == {"mock"}
    return _result(
        response,
        context,
        session,
        before_run,
        before_session,
        evidence_before,
        tool=tool,
        payload=request,
        external_mutations=client.create_task.call_count + client.operate_task.call_count,
    )


def _run_lock(case, start_case, mocker, *, variant):
    if variant == "template_context_busy":
        context, run, revision, template, _request, resolver = start_case
        DebugContext.objects.create(
            template_id=template.id,
            space_id=context.space_id,
            status="running",
            active_task_id=7799,
        )
        evidence_before = _event_ids()
        before_run, before_session = run.status, "NONE"
        tool, request = _materialize_case_request(case, run=run, revision=revision)
        assert tool == "start_debug_session"
        response = start_debug_session_with_context(context, request, resolver=resolver)
        run.refresh_from_db()
        assert not DebugSession._base_manager.exists()
        trusted, predecessor, fingerprint = _audit_facts(context, run, revision)
        return ScenarioResult(
            response,
            before_run,
            before_session,
            run.status,
            "NONE",
            _new_events(evidence_before),
            trusted_context=trusted,
            predecessor_revision=predecessor,
            draft_fingerprint=fingerprint,
            materialized_tool=tool,
            materialized_request=request,
        )

    context, session, resolver = _started(
        start_case, mode=DebugMode.GLOBAL if variant == "run_while_running" else DebugMode.STEP
    )
    evidence_before = _event_ids()
    before_run, before_session = session.run.status, session.status
    second_run = None
    materialize_run = session.run
    materialize_revision = session.revision
    if variant == "active_template_unique":
        _context, second_run, second_revision, _template, _resolver = _clone_validated_run_for_same_template(start_case)
        materialize_run = second_run
        materialize_revision = second_revision
    tool, request = _materialize_case_request(
        case,
        session=session,
        run=materialize_run,
        revision=materialize_revision,
    )
    if variant == "run_while_running":
        assert tool == "run_debug"
        _running_context(session, run_type="global")
        before_session = session.status
        response = run_debug_with_context(context, request, resolver=resolver)
    elif variant == "cross_tool_inflight":
        assert tool == "control_debug_session"
        _enable_debug(context)
        HarnessIdempotencyRecord.objects.create(
            platform_app=context.platform_app,
            actor=context.actor,
            space_id=context.space_id,
            tool_name="run_debug",
            run_scope="run:{}".format(session.run_id),
            idempotency_key="uncertain-run",
            request_hash="a" * 64,
            status="IN_FLIGHT",
            run=session.run,
            resource_reference=str(session.id),
        )
        response = control_debug_session_with_context(
            context,
            request,
            resolver=resolver,
        )
    elif variant == "second_start":
        assert tool == "start_debug_session"
        response = start_debug_session_with_context(context, request, resolver=resolver)
    else:
        assert variant == "active_template_unique"
        assert tool == "start_debug_session"
        response = start_debug_session_with_context(context, request, resolver=resolver)
        second_run.refresh_from_db()
        assert second_run.status == "DRAFT_READY"
        assert DebugSession._base_manager.filter(template_id=session.template_id).count() == 1
    return _result(
        response,
        context,
        session,
        before_run,
        before_session,
        evidence_before,
        tool=tool,
        payload=request,
    )


def _run_control(case, start_case, mocker, *, variant):
    context, session, resolver = _started(start_case)
    _enable_debug(context)
    if variant == "reset_selected":
        node = DebugNodeState.objects.get(debug_context_id=session.debug_context_id, node_id="A")
        node.status = "finished"
        node.outputs = {"result": "old"}
        node.save(update_fields=["status", "outputs"])
    tool, request = _materialize_case_request(case, session=session)
    assert tool == "control_debug_session"
    evidence_before = _event_ids()
    before_run, before_session = session.run.status, session.status
    response = control_debug_session_with_context(context, request, resolver=resolver)
    if variant == "replay":
        assert control_debug_session_with_context(context, request, resolver=resolver) == response
    if variant == "set_node_mock":
        assert DebugNodeState.objects.get(debug_context_id=session.debug_context_id, node_id="A").mock_outputs == {
            "result": "preset"
        }
    if variant in {"set_context_var", "replay"}:
        assert DebugContext.objects.get(pk=session.debug_context_id).global_vars["${safe}"] == {"nested": "value"}
    return _result(
        response,
        context,
        session,
        before_run,
        before_session,
        evidence_before,
        tool=tool,
        payload=request,
    )


def _run_terminate(case, start_case, mocker, *, variant):
    context, session, resolver = _started(start_case)
    _enable_debug(context)
    if variant != "active_node_rejected":
        _issue_lease(context, session, mocker)
    client = mocker.MagicMock()
    external = 0
    if variant in {"running_global", "running_node"}:
        _running_context(session, run_type="global" if variant == "running_global" else "step")
        if variant == "running_node":
            DebugContext.objects.filter(pk=session.debug_context_id).update(active_node_id="A")
            client.get_node_id_map.return_value = {"result": True, "data": {"A": "runtime-A"}}
            client.node_operate.return_value = {"result": True}
        else:
            client.operate_task.return_value = {"result": True}
        mocker.patch("bkflow.template.debug.service.DebugService._task_client", return_value=client)
    tool, request = _materialize_case_request(case, session=session)
    assert tool == "control_debug_session"
    evidence_before = _event_ids()
    before_run, before_session = session.run.status, session.status
    response = control_debug_session_with_context(context, request, resolver=resolver)
    if variant == "running_global":
        external = client.operate_task.call_count
    elif variant == "running_node":
        external = client.get_node_id_map.call_count + client.node_operate.call_count
    return _result(
        response,
        context,
        session,
        before_run,
        before_session,
        evidence_before,
        tool=tool,
        payload=request,
        external_mutations=external,
    )


def _run_drift(case, start_case, mocker, *, variant):
    context, session, resolver = _started(start_case)
    if variant == "tree_fingerprint":
        snapshot = TemplateSnapshot.objects.get(template_id=session.template_id, draft=True, is_deleted=False)
        changed = copy.deepcopy(snapshot.data)
        changed["activities"]["A"]["component"]["data"] = {"changed": {"value": True}}
        snapshot.data = changed
        snapshot.save(update_fields=["data"])
    elif variant == "superseded_revision":
        WorkflowPlanRevision.objects.create(
            run=session.run,
            sequence=session.revision.sequence + 1,
            parent_revision=session.revision,
            intent_spec={"goal": "superseded"},
            canonical_a2flow={"version": "2.0", "nodes": []},
            plan_hash="e" * 64,
        )
    else:
        assert variant == "plan_hash"
    tool, request = _materialize_case_request(case, session=session)
    assert tool == "run_debug"
    evidence_before = _event_ids()
    before_run, before_session = session.run.status, session.status
    response = run_debug_with_context(context, request, resolver=resolver)
    return _result(
        response,
        context,
        session,
        before_run,
        before_session,
        evidence_before,
        tool=tool,
        payload=request,
    )


def _run_token(case, start_case, mocker, *, variant):
    context, session, resolver = _started(start_case)
    _ensure_space(context)
    _enable_debug(context)
    mocker.patch("bkflow.permission.services.token_issuer.TokenResourceValidator.validate", return_value=None)
    broker = TokenBroker()
    tool, request = _materialize_case_request(case, session=session)
    evidence_before = _event_ids()
    before_run, before_session = session.run.status, session.status
    first = broker.acquire_debug_lease(context, session)
    if variant == "renew":
        Token.objects.filter(token=first.secret).update(expired_time=timezone.now() - datetime.timedelta(seconds=1))
        broker.acquire_debug_lease(context, session)
    elif variant == "revoke":
        assert tool == "control_debug_session"
        response = control_debug_session_with_context(
            context,
            request,
            resolver=resolver,
            token_broker=broker,
        )
        return _result(
            response,
            context,
            session,
            before_run,
            before_session,
            evidence_before,
            tool=tool,
            payload=request,
        )
    assert tool == "get_debug_session"
    response = get_debug_session_with_context(
        context,
        request,
        resolver=resolver,
        token_broker=broker,
    )
    return _result(
        response,
        context,
        session,
        before_run,
        before_session,
        evidence_before,
        tool=tool,
        payload=request,
    )


def _run_approval(case, start_case, mocker, *, variant):
    context, session, resolver = _started(start_case)
    tool, request = _materialize_case_request(case, session=session)
    assert tool == "run_debug"
    mocker.patch("bkflow.harness.services.debug.run.is_harness_real_step_enabled", return_value=True)
    verifier = mocker.MagicMock()
    broker = mocker.MagicMock()
    adapter_class = mocker.MagicMock()
    if variant != "missing":
        reason = "claims_mismatch" if variant == "forged" else "expired"
        receipt = request["approval_receipt_ref"]
        verifier.verify.return_value = DebugApprovalDecision(
            False,
            "golden-verifier-test-double",
            hashlib.sha256(receipt.encode("utf-8")).hexdigest(),
            "c" * 64,
            reason,
        )
    evidence_before = _event_ids()
    before_run, before_session = session.run.status, session.status
    response = run_debug_with_context(
        context,
        request,
        resolver=resolver,
        approval_verifier=verifier,
        token_broker=broker,
        allow_real=True,
        adapter_class=adapter_class,
    )
    if variant == "missing":
        assert response["errors"][0]["path"] == "approval_receipt_ref"
        verifier.verify.assert_not_called()
    else:
        assert verifier.verify.call_count == 1
        assert verifier.verify.return_value.reason == reason
    broker.acquire_debug_lease.assert_not_called()
    adapter_class.assert_not_called()
    return _result(
        response,
        context,
        session,
        before_run,
        before_session,
        evidence_before,
        tool=tool,
        payload=request,
    )


HANDLERS = {
    "step-mock-success": partial(_run_step, variant="success"),
    "step-mock-failure": partial(_run_step, variant="failure"),
    "step-mock-empty-outputs": partial(_run_step, variant="empty_outputs"),
    "step-mock-multiple-outputs": partial(_run_step, variant="multiple_outputs"),
    "step-input-override": partial(_run_step, variant="input_override"),
    "step-updates-globals": partial(_run_step, variant="updates_globals"),
    "step-same-key-replay": partial(_run_step, variant="replay"),
    "step-safe-output-projection": partial(_run_step, variant="safe_projection"),
    "dependency-direct-missing": partial(_run_dependency, variant="direct_missing"),
    "dependency-transitive-missing": partial(_run_dependency, variant="transitive_missing"),
    "dependency-global-var-missing": partial(_run_dependency, variant="global_var_missing"),
    "dependency-gateway-input-missing": partial(_run_dependency, variant="gateway_input_missing"),
    "dependency-no-result-evidence": partial(_run_dependency, variant="no_result_evidence"),
    "global-fast-ack": partial(_run_global, variant="fast_ack"),
    "global-same-key-replay": partial(_run_global, variant="replay"),
    "global-force-all-mock": partial(_run_global, variant="force_all_mock"),
    "global-completion-poll": partial(_run_global, variant="completion_poll"),
    "global-failure-poll": partial(_run_global, variant="failure_poll"),
    "lock-second-start": partial(_run_lock, variant="second_start"),
    "lock-run-while-running": partial(_run_lock, variant="run_while_running"),
    "lock-cross-tool-inflight": partial(_run_lock, variant="cross_tool_inflight"),
    "lock-template-context-busy": partial(_run_lock, variant="template_context_busy"),
    "lock-active-template-unique": partial(_run_lock, variant="active_template_unique"),
    "control-reset-selected": partial(_run_control, variant="reset_selected"),
    "control-set-node-mock": partial(_run_control, variant="set_node_mock"),
    "control-set-context-var": partial(_run_control, variant="set_context_var"),
    "control-same-key-replay": partial(_run_control, variant="replay"),
    "terminate-active-session": partial(_run_terminate, variant="active"),
    "terminate-active-node-rejected": partial(_run_terminate, variant="active_node_rejected"),
    "terminate-running-global": partial(_run_terminate, variant="running_global"),
    "terminate-running-node": partial(_run_terminate, variant="running_node"),
    "drift-plan-hash": partial(_run_drift, variant="plan_hash"),
    "drift-tree-fingerprint": partial(_run_drift, variant="tree_fingerprint"),
    "drift-superseded-revision": partial(_run_drift, variant="superseded_revision"),
    "token-issue-template-lease": partial(_run_token, variant="issue"),
    "token-expire-and-renew": partial(_run_token, variant="renew"),
    "token-revoke-before-terminal": partial(_run_token, variant="revoke"),
    "approval-missing-receipt": partial(_run_approval, variant="missing"),
    "approval-forged-claims": partial(_run_approval, variant="forged"),
    "approval-expired-receipt": partial(_run_approval, variant="expired"),
}


def test_fixture_has_exactly_forty_complete_cases_and_handlers_in_the_frozen_distribution():
    assert len(CASES) == 40
    assert Counter(case["category"] for case in CASES) == Counter(EXPECTED_COUNTS)
    assert len({case["id"] for case in CASES}) == 40
    assert {case["id"] for case in CASES} == set(HANDLERS)
    for case in CASES:
        assert REQUIRED_CASE_FIELDS <= set(case)
        assert case["trusted_context"] == {
            "platform_key": "bkaidev",
            "platform_app": "trusted-app",
            "actor": "dannydeng",
            "space_id": 902,
            "scope_type": "project",
            "scope_value": "902",
            "target_environment": "stag",
            "policy_version": "risk-2026.09",
            "mcp_contract_version": "1.2.0",
        }
        assert case["predecessor_revision"]["validation"] == "passed"
        assert case["draft_fingerprint"]["algorithm"] == "sha256"
        assert set(case["request"]) == {"tool", "payload"}
        assert isinstance(case["request"]["payload"], dict)
        handler = HANDLERS[case["id"]]
        assert callable(handler)
        assert handler.func.__name__ == "_run_{}".format(case["setup"]["handler"])
        assert handler.keywords["variant"] == case["setup"]["variant"]
        assert case["setup"]["precondition"]


def test_contract_1_2_0_is_exactly_nine_cumulative_tools():
    assert tuple(tools_for_contract("1.2.0")) == (
        "search_workflow_capabilities",
        "get_plugin_schema",
        "validate_workflow",
        "create_workflow_draft",
        "search_workflow_knowledge",
        "start_debug_session",
        "run_debug",
        "get_debug_session",
        "control_debug_session",
    )


def test_makefile_exposes_the_reproducible_complete_p2_gate():
    content = MAKEFILE.read_text(encoding="utf-8")
    assert "PYTHON ?=" in content
    assert "PYTEST ?=" in content
    assert "harness-p2-gate:" in content
    for required_path in (
        "tests/interface/harness",
        "tests/interface/permission/test_token_issuer.py",
        "tests/interface/template/debug",
        "tests/interface/apigw/test_harness_p0.py",
        "tests/interface/apigw/test_harness_p1.py",
        "tests/interface/apigw/test_harness_p2.py",
        "tests/interface/apigw/test_harness_resource_contract.py",
        "tests/interface/apigw/test_apply_token.py",
        "tests/interface/apigw/test_token_resource_validator.py",
        "manage.py check",
        "makemigrations harness --check --dry-run",
        "unzip -t bkflow/apigw/docs/apigw-docs.zip",
        "--strict-markers",
    ):
        assert required_path in content
    assert content.index("manage.py check") < content.index("$(PYTEST) $(HARNESS_P2_GATE_PATHS)")
    assert content.index("makemigrations harness --check --dry-run") < content.index(
        "$(PYTEST) $(HARNESS_P2_GATE_PATHS)"
    )
    assert "/Users/" not in content


@pytest.mark.django_db
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_every_golden_case_executes_its_registered_service_and_asserts_postconditions(case, start_case, mocker, caplog):
    outcome = HANDLERS[case["id"]](case, start_case, mocker)
    _assert_declared_audit_facts(case, outcome)

    statuses = list(TokenLease._base_manager.values_list("status", flat=True))
    expected_lease = case["token_lease_result"]
    if expected_lease == "none":
        assert statuses == []
    elif expected_lease == "active":
        assert statuses.count(TokenLease.Status.ACTIVE) == 1
    elif expected_lease == "renewed":
        assert statuses.count(TokenLease.Status.EXPIRED) == 1
        assert statuses.count(TokenLease.Status.ACTIVE) == 1
    else:
        assert expected_lease == "revoked"
        assert TokenLease.Status.ACTIVE not in statuses
        assert TokenLease.Status.REVOKED in statuses

    serialized = str(outcome.response) + str(list(EvidenceEvent._base_manager.values())) + caplog.text
    for marker in case["forbidden_markers"]:
        assert marker not in serialized


def _assert_declared_audit_facts(case, outcome):
    assert _response_code(outcome.response) == case["expected_envelope_code"]
    assert "{}->{}".format(outcome.before_run, outcome.after_run) == case["state_transition"]["run"]
    assert "{}->{}".format(outcome.before_session, outcome.after_session) == case["state_transition"]["session"]
    assert outcome.evidence_events == case["evidence_events"]
    assert outcome.external_mutations == case["external_mutations"]
    assert outcome.trusted_context == case["trusted_context"]
    assert outcome.predecessor_revision == case["predecessor_revision"]
    assert outcome.draft_fingerprint == case["draft_fingerprint"]
    assert outcome.materialized_tool == case["request"]["tool"]
    _assert_materialized_template(case["request"]["payload"], outcome.materialized_request)


@pytest.mark.django_db
@pytest.mark.parametrize("declaration", ("trusted_context", "predecessor_revision", "draft_fingerprint", "request"))
def test_mutating_any_audited_declaration_breaks_the_golden_contract(declaration, start_case, mocker):
    """Context, revision, fingerprint and request declarations all drive executable proof."""
    source = next(case for case in CASES if case["id"] == "step-mock-success")
    mutated = copy.deepcopy(source)
    if declaration == "trusted_context":
        mutated["trusted_context"]["actor"] = "not-the-runtime-actor"
    elif declaration == "predecessor_revision":
        mutated["predecessor_revision"]["sequence"] = 999
    elif declaration == "draft_fingerprint":
        mutated["draft_fingerprint"]["relation"] = "drifted"
    else:
        mutated["request"]["payload"]["unexpected"] = True

    outcome = HANDLERS[mutated["id"]](mutated, start_case, mocker)

    with pytest.raises(AssertionError):
        _assert_declared_audit_facts(mutated, outcome)
