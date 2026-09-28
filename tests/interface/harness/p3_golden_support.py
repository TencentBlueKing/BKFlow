"""Shared executable contract support for the P3 Golden fixture."""

import copy
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import yaml

from bkflow.harness.models import (
    ApprovalRequest,
    EvidenceBundle,
    EvidenceEvent,
    ExecutionRun,
    HarnessIdempotencyRecord,
    HarnessRun,
    ReleaseManifest,
    ReleasePublication,
    TokenLease,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import sha256_json
from bkflow.template.debug.dependency import compute_tree_fingerprint
from bkflow.template.models import TemplateOperationRecord, TemplateSnapshot

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_FILE = ROOT / "tests/fixtures/harness/release_execution_cases.yaml"
REQUEST_PLACEHOLDERS = frozenset(
    {
        "$run_id",
        "$revision_id",
        "$plan_hash",
        "$manifest_id",
        "$manifest_hash",
        "$publication_id",
        "$execution_id",
        "$approval_request_id",
        "$approval_receipt_ref",
    }
)
EXPECTED_COUNTS = {
    "prepare_and_manifest": 8,
    "approval_binding_and_expiry": 6,
    "publish_idempotency_and_drift": 6,
    "create_start_recovery": 8,
    "execution_readback": 5,
    "postcondition_false_success": 5,
    "task_controls": 4,
    "node_controls": 4,
    "secret_and_cross_space_denial": 2,
}
CATEGORY_DRIVERS = {
    "prepare_and_manifest": frozenset({"prepare"}),
    "approval_binding_and_expiry": frozenset({"publish", "start"}),
    "publish_idempotency_and_drift": frozenset({"publish"}),
    "create_start_recovery": frozenset({"start"}),
    "execution_readback": frozenset({"read"}),
    "postcondition_false_success": frozenset({"read", "postcondition"}),
    "task_controls": frozenset({"control"}),
    "node_controls": frozenset({"control"}),
    "secret_and_cross_space_denial": frozenset({"start"}),
}
VALID_ENGINE_SEQUENCES = {
    "prepare_release": {()},
    "publish_workflow": {
        (),
        ("database_anchor_error", "retry"),
        ("release_committed_response_lost", "exact_readback"),
    },
    "start_workflow_execution": {
        (),
        ("create:8101", "start:ack"),
        ("barrier_committed", "crash_before_create"),
        ("create:uncertain",),
        ("create:8102", "persist_task_ref_crash"),
        ("create:uncertain", "late_receipt:8103", "start:ack"),
        ("create:8104", "task_ref_persisted", "crash_before_start"),
        ("create:8105", "start:uncertain", "read:RUNNING"),
        ("create:8106", "start:uncertain", "read:unavailable"),
    },
    "get_workflow_execution": {
        (),
        ("read:RUNNING",),
        ("read:SUSPENDED",),
        ("read:404",),
        ("read:FINISHED", "output:A.result=ok"),
        ("read:FINISHED", "output:A.result=missing"),
        ("read:FINISHED", "output:A.result=unexpected"),
        ("read:FINISHED", "webhook:unavailable"),
    },
    "control_workflow_execution": {
        ("preflight:RUNNING", "control:ack", "read:SUSPENDED"),
        ("preflight:SUSPENDED", "control:ack", "read:RUNNING"),
        ("preflight:RUNNING", "control:ack", "read:REVOKED"),
        ("preflight:RUNNING", "control:ack", "crash_after_dispatch", "read:SUSPENDED"),
        ("preflight:FAILED/v7", "control:ack", "read:RUNNING/v8"),
        ("preflight:FAILED/v7", "control:ack", "read:FINISHED/v8"),
        ("preflight:RUNNING/v7", "control:ack", "read:FAILED/v8"),
        ("preflight:FAILED/v7", "barrier_committed", "crash_before_control"),
    },
}
ENGINE_SETUP_FIELDS = frozenset(
    {
        "root_state",
        "recover_state",
        "node_state",
        "node_version",
        "recover_node_state",
        "recover_node_version",
        "engine_state",
        "engine_error",
        "output_mode",
        "predicate",
        "evidence",
        "deadline",
        "crash_after_barrier",
        "crash_after_dispatch",
    }
)
REQUIRED_FIELDS = frozenset(
    {
        "id",
        "category",
        "setup",
        "trusted_context",
        "predecessor_revision",
        "draft_fingerprint",
        "policy",
        "approval",
        "engine_sequence",
        "request",
        "expected",
        "forbidden_markers",
    }
)


def load_cases():
    """Load independent case values so one test cannot mutate YAML aliases."""
    document = yaml.safe_load(FIXTURE_FILE.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    return [copy.deepcopy(case) for case in document["cases"]]


CASES = load_cases()
RELEASE_CASES = [
    case
    for case in CASES
    if case["category"]
    in {
        "prepare_and_manifest",
        "approval_binding_and_expiry",
        "publish_idempotency_and_drift",
    }
]
EXECUTION_CASES = [
    case
    for case in CASES
    if case["category"]
    in {
        "create_start_recovery",
        "execution_readback",
        "postcondition_false_success",
        "task_controls",
        "node_controls",
    }
]
SECRET_CASES = [case for case in CASES if case["category"] == "secret_and_cross_space_denial"]


def validate_fixture_structure():
    assert len(CASES) == 48
    assert len(RELEASE_CASES) == 20
    assert len(EXECUTION_CASES) == 26
    assert len(SECRET_CASES) == 2
    assert Counter(case["category"] for case in CASES) == Counter(EXPECTED_COUNTS)
    assert len({case["id"] for case in CASES}) == 48
    assert {case["id"] for case in RELEASE_CASES}.isdisjoint(case["id"] for case in EXECUTION_CASES)
    assert {case["id"] for case in RELEASE_CASES}.isdisjoint(case["id"] for case in SECRET_CASES)
    assert {case["id"] for case in EXECUTION_CASES}.isdisjoint(case["id"] for case in SECRET_CASES)
    assert {case["id"] for case in RELEASE_CASES + EXECUTION_CASES + SECRET_CASES} == {case["id"] for case in CASES}
    assert REQUIRED_FIELDS <= set.intersection(*(set(case) for case in CASES))
    for case in CASES:
        assert set(case["request"]) == {"tool", "payload"}
        assert isinstance(case["request"]["payload"], dict)
        assert case["setup"]["driver"] in CATEGORY_DRIVERS[case["category"]]
        assert ENGINE_SETUP_FIELDS.isdisjoint(case["setup"])
        assert case["trusted_context"]["mcp_contract_version"] == "1.3.0"
        assert case["predecessor_revision"]["validation"] == "passed"
        assert case["draft_fingerprint"]["algorithm"] == "sha256"
        assert case["policy"]["global_real_enabled"] is False
        assert case["forbidden_markers"]
        assert_case_declarations(case)


def assert_case_declarations(case):
    """Reject decorative policy, approval, or Engine declarations."""
    setup = case["setup"]
    tool = case["request"]["tool"]
    policy = case["policy"]
    expected_policy = {
        "profile": case["trusted_context"]["policy_version"],
        "publish_enabled": True,
        "execution_enabled": True,
        "global_real_enabled": False,
    }
    if tool == "get_workflow_execution":
        assert isinstance(policy.get("execution_enabled"), bool)
        expected_policy["execution_enabled"] = policy["execution_enabled"]
    assert policy == expected_policy
    approval = case["approval"]
    expected_action = {
        "prepare_release": "none",
        "publish_workflow": "publish_workflow",
        "start_workflow_execution": "start_workflow_execution",
        "get_workflow_execution": "none",
        "control_workflow_execution": setup.get("action", "none"),
    }[tool]
    if setup.get("phase") == "wrong_action":
        expected_action = "publish_workflow"
    assert approval["action"] == expected_action
    assert approval["mode"] in {
        "none",
        "missing",
        "valid_test_double",
        "wrong_action",
        "forged_test_double",
        "expired_test_double",
    }
    if approval["mode"] in {"valid_test_double", "wrong_action", "forged_test_double", "expired_test_double"}:
        assert set(approval) == {"mode", "action", "receipt_ref"}
    else:
        assert set(approval) == {"mode", "action"}
    assert tuple(case["engine_sequence"]) in VALID_ENGINE_SEQUENCES[tool]


def apply_declared_policy(space_id, case):
    """Apply the server-side feature switches declared by the fixture row."""
    from bkflow.space.configs import (
        HarnessExecutionEnabledConfig,
        HarnessGlobalRealDebugEnabledConfig,
        HarnessPublishEnabledConfig,
        SpaceConfigValueType,
    )
    from bkflow.space.models import SpaceConfig

    values = (
        (HarnessPublishEnabledConfig.name, case["policy"]["publish_enabled"]),
        (HarnessExecutionEnabledConfig.name, case["policy"]["execution_enabled"]),
        (HarnessGlobalRealDebugEnabledConfig.name, case["policy"]["global_real_enabled"]),
    )
    for name, enabled in values:
        SpaceConfig.objects.update_or_create(
            space_id=space_id,
            name=name,
            defaults={"value_type": SpaceConfigValueType.TEXT.value, "text_value": str(enabled).lower()},
        )


def invoke_service(trace, tool, *args, **kwargs):
    """Dispatch only to a real public P3 service and record the observed call."""
    from bkflow.harness.services.execution.control import (
        control_workflow_execution_with_context,
    )
    from bkflow.harness.services.execution.read import (
        get_workflow_execution_with_context,
    )
    from bkflow.harness.services.execution.saga import (
        start_workflow_execution_with_context,
    )
    from bkflow.harness.services.release.facade import prepare_release_with_context
    from bkflow.harness.services.release.publish import publish_workflow_with_context

    registry = {
        "prepare_release": prepare_release_with_context,
        "publish_workflow": publish_workflow_with_context,
        "start_workflow_execution": start_workflow_execution_with_context,
        "get_workflow_execution": get_workflow_execution_with_context,
        "control_workflow_execution": control_workflow_execution_with_context,
    }
    tool_name = getattr(tool, "value", tool)
    function = registry[tool_name]
    trace.append(tool_name)
    return function(*args, **kwargs)


def expected_service_trace(case):
    tool = case["request"]["tool"]
    setup = case["setup"]
    if tool == "prepare_release" and setup.get("replay"):
        return (tool, tool)
    if tool == "publish_workflow":
        if setup.get("phase") == "approval_only":
            return (tool,)
        calls = (
            3
            if (
                setup.get("replay")
                or setup.get("phase") == "conflict_after_success"
                or "database_anchor_error" in case["engine_sequence"]
            )
            else 2
        )
        return tuple(tool for _index in range(calls))
    if (
        tool == "start_workflow_execution"
        and not case["engine_sequence"]
        and setup.get("phase")
        not in {
            "approval_only",
            "wrong_action",
            "cross_space",
            "secret_input",
        }
    ):
        raise AssertionError("an executable start case must declare an Engine sequence")
    if tool == "start_workflow_execution" and case["engine_sequence"]:
        sequence = case["engine_sequence"]
        calls = (
            3
            if any(
                marker in sequence
                for marker in (
                    "crash_before_create",
                    "create:uncertain",
                    "persist_task_ref_crash",
                    "crash_before_start",
                    "read:unavailable",
                )
            )
            else 2
        )
        return tuple(tool for _index in range(calls))
    if tool == "get_workflow_execution":
        calls = 3 if "history" in case["expected"] else (2 if "webhook:unavailable" in case["engine_sequence"] else 1)
        return ("start_workflow_execution", "start_workflow_execution") + tuple(tool for _index in range(calls))
    if tool == "control_workflow_execution":
        tail = "get_workflow_execution" if any(item.startswith("read:") for item in case["engine_sequence"]) else tool
        return (
            "start_workflow_execution",
            "start_workflow_execution",
            tool,
            tool,
            tail,
        )
    return (tool,)


def _materialize(value, runtime):
    if isinstance(value, dict):
        return {key: _materialize(item, runtime) for key, item in value.items()}
    if isinstance(value, list):
        return [_materialize(item, runtime) for item in value]
    if isinstance(value, str) and value in REQUEST_PLACEHOLDERS:
        assert value in runtime and runtime[value] is not None
        return runtime[value]
    return copy.deepcopy(value)


def materialize_request(case, **runtime):
    values = {"${}".format(key): value for key, value in runtime.items()}
    return case["request"]["tool"], _materialize(case["request"]["payload"], values)


def assert_materialized(template, actual):
    if isinstance(template, dict):
        assert isinstance(actual, dict)
        assert set(actual) == set(template)
        for key, expected in template.items():
            assert_materialized(expected, actual[key])
        return
    if isinstance(template, list):
        assert isinstance(actual, list)
        assert len(actual) == len(template)
        for expected, value in zip(template, actual):
            assert_materialized(expected, value)
        return
    if isinstance(template, str) and template in REQUEST_PLACEHOLDERS:
        assert actual != template
        assert actual is not None
        return
    assert actual == template


def trusted_context_facts(context):
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


def immutable_input_facts(run, revision, template, snapshot):
    latest = run.revisions.order_by("-sequence").first()
    validation = ValidationReport.objects.filter(run=run, revision=revision, result__valid=True).exists()
    artifact = next(
        value
        for value in run.artifact_references
        if value.get("type") == "harness_draft" and value.get("revision_id") == str(revision.id)
    )
    exact = (
        artifact.get("template_id") == template.id
        and artifact.get("pipeline_tree_hash") == sha256_json(snapshot.data)
        and compute_tree_fingerprint(snapshot.data) is not None
    )
    return {
        "predecessor_revision": {
            "relation": "latest" if latest.id == revision.id else "superseded",
            "sequence": revision.sequence,
            "validation": "passed" if validation else "failed",
        },
        "draft_fingerprint": {"relation": "exact" if exact else "drifted", "algorithm": "sha256"},
    }


def response_code(response):
    return "OK" if response.get("ok") is True else response["errors"][0]["code"]


def snapshot_counts():
    return {
        "manifest": ReleaseManifest.objects.count(),
        "publication": ReleasePublication.objects.count(),
        "execution": ExecutionRun.objects.count(),
        "idempotency": HarnessIdempotencyRecord.objects.count(),
        "evidence": EvidenceEvent._base_manager.count(),
        "bundle": EvidenceBundle._base_manager.count(),
        "lease": TokenLease._base_manager.count(),
        "publish": TemplateOperationRecord.objects.filter(operate_type="release").count(),
    }


def new_event_types(before_ids, *, run=None, execution=None):
    query = EvidenceEvent._base_manager.exclude(id__in=before_ids).order_by("occurred_at", "id")
    if run is not None:
        query = query.filter(run=run)
    if execution is not None:
        query = query.filter(execution=execution)
    return list(query.values_list("event_type", flat=True))


def assert_no_forbidden_markers(case, response):
    """Scan the Harness aggregate and wire response, excluding legacy Token.token."""
    persisted = {
        model.__name__: list(model._base_manager.values())
        for model in (
            HarnessRun,
            WorkflowPlanRevision,
            ValidationReport,
            ReleaseManifest,
            ApprovalRequest,
            ReleasePublication,
            ExecutionRun,
            HarnessIdempotencyRecord,
            EvidenceEvent,
            EvidenceBundle,
            TokenLease,
            TemplateSnapshot,
        )
    }
    rendered = json.dumps({"response": response, "persisted": persisted}, default=str, sort_keys=True)
    for marker in case["forbidden_markers"]:
        assert marker not in rendered


@dataclass
class ScenarioResult:
    response: dict
    context: object
    run: object
    revision: object
    template: object
    snapshot: object
    tool: str
    payload: dict
    event_types: list
    mutation_counts: dict
    execution: object = None
    token_lease_result: str = "none"
    service_trace: tuple = ()


def assert_common_contract(case, result):
    result.run.refresh_from_db()
    if result.execution is not None:
        result.execution.refresh_from_db()
    facts = immutable_input_facts(result.run, result.revision, result.template, result.snapshot)
    assert trusted_context_facts(result.context) == case["trusted_context"]
    assert facts["predecessor_revision"] == case["predecessor_revision"]
    assert facts["draft_fingerprint"] == case["draft_fingerprint"]
    assert result.tool == case["request"]["tool"]
    assert_materialized(case["request"]["payload"], result.payload)
    assert response_code(result.response) == case["expected"]["envelope_code"], result.response
    assert result.service_trace == expected_service_trace(case), result.service_trace
    expected_run = case["expected"]["run_status"]
    if expected_run != "unchanged":
        assert result.run.status == expected_run, (result.run.status, expected_run)
    expected_execution = case["expected"]["execution_status"]
    if expected_execution == "none":
        assert result.execution is None
    else:
        assert result.execution is not None
        assert result.execution.status == expected_execution
        expected_task_ref = case["expected"].get("task_ref")
        if expected_task_ref is not None:
            assert (result.execution.task_ref or "") == expected_task_ref
        expected_idempotency_status = case["expected"].get("idempotency_status")
        if expected_idempotency_status is not None:
            record = HarnessIdempotencyRecord.objects.get(
                run=result.run,
                tool_name=result.tool,
                resource_reference=str(result.execution.id),
            )
            assert record.status == expected_idempotency_status
            if case["expected"].get("resource_binding") == "execution":
                assert record.resource_reference == str(result.execution.id)
        if case["expected"].get("evidence_bundle") == "finalized":
            bundle = EvidenceBundle._base_manager.get(execution=result.execution)
            assert bundle.finalized_at is not None
            assert bundle.bundle_hash
    assert result.event_types == case["expected"]["evidence_events"], result.event_types
    assert result.token_lease_result == case["expected"]["token_lease_result"]
    assert result.mutation_counts == case["expected"]["mutations"], result.mutation_counts
    assert_no_forbidden_markers(case, result.response)
