"""Twenty table-driven P3 release Golden Cases backed by real domain services."""

import copy
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.db import DatabaseError
from django.utils import timezone

from bkflow.harness.constants import (
    HarnessAction,
    HarnessRunStatus,
    IdempotencyRecordStatus,
)
from bkflow.harness.models import (
    ApprovalRequest,
    EvidenceEvent,
    HarnessIdempotencyRecord,
    ReleaseManifest,
    ReleasePublication,
    WorkflowPlanRevision,
)
from bkflow.harness.services.approval import (
    ApprovalVerifier,
    InMemoryApprovalReplayGuard,
)
from bkflow.harness.services.contract_versions import tools_for_contract
from bkflow.harness.services.release.policy import ReleasePolicy
from bkflow.template.models import TemplateSnapshot
from bkflow.template.services.release import TemplateReleaseService
from tests.interface.harness import p3_golden_support as golden
from tests.interface.harness.execution import test_start_execution as start_cases
from tests.interface.harness.release import test_prepare_release as prepare_cases
from tests.interface.harness.release import test_publish_workflow as publish_cases

PREPARE_CASES = [case for case in golden.RELEASE_CASES if case["setup"]["driver"] == "prepare"]
PUBLISH_CASES = [case for case in golden.RELEASE_CASES if case["setup"]["driver"] == "publish"]
START_APPROVAL_CASES = [case for case in golden.RELEASE_CASES if case["setup"]["driver"] == "start"]
ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def golden_release_builder(db):
    return prepare_cases.release_case.__wrapped__(db)


@pytest.fixture
def golden_publish_case(db):
    builder = prepare_cases.release_case.__wrapped__(db)
    return publish_cases.publish_case.__wrapped__(builder)


@pytest.fixture
def golden_execution_case(db):
    return start_cases.execution_case.__wrapped__(db)


def _runtime(case, *, approval_id=None):
    values = {
        "run_id": str(case.run.run_id),
        "revision_id": str(case.revision.id),
        "plan_hash": case.revision.plan_hash,
    }
    if hasattr(case, "manifest"):
        values.update(manifest_id=str(case.manifest.id), manifest_hash=case.manifest.manifest_hash)
    if hasattr(case, "publication"):
        values["publication_id"] = str(case.publication.id)
    if approval_id is not None:
        values.update(approval_request_id=str(approval_id), approval_receipt_ref=case._golden_receipt_ref)
    return values


def _base_publish_request(case, fixture_case):
    tool, payload = golden.materialize_request(
        fixture_case,
        **{
            **_runtime(case),
            "approval_request_id": "00000000-0000-0000-0000-000000000000",
            "approval_receipt_ref": fixture_case["approval"].get("receipt_ref", "approval://golden/pending"),
        },
    )
    payload.pop("approval_request_id", None)
    payload.pop("approval_receipt_ref", None)
    return tool, payload


def _approval_payload(case, fixture_case, approval):
    case._golden_receipt_ref = fixture_case["approval"]["receipt_ref"]
    return golden.materialize_request(fixture_case, **_runtime(case, approval_id=approval.id))


def _release_result(case, response, tool, payload, before_ids, before_counts, trace, *, adapter=None):
    after = golden.snapshot_counts()
    action_names = [call[0] for call in adapter.calls] if adapter is not None else []
    return golden.ScenarioResult(
        response=response,
        context=case.context,
        run=case.run,
        revision=case.revision,
        template=case.template,
        snapshot=case.snapshot,
        tool=tool,
        payload=payload,
        event_types=golden.new_event_types(before_ids, run=case.run),
        mutation_counts={
            "publish": after["publish"] - before_counts["publish"],
            "create": action_names.count("create"),
            "start": action_names.count("start"),
            "control": 0,
            "read": 0,
        },
        service_trace=tuple(trace),
    )


def _execute_prepare(fixture_case, builder):
    golden.assert_case_declarations(fixture_case)
    setup = fixture_case["setup"]
    case = builder(with_terminal_evidence=not setup.get("remove_debug_evidence", False))
    golden.apply_declared_policy(case.context.space_id, fixture_case)
    if setup.get("resolver_schema_hash"):
        case.resolver = prepare_cases.ReleaseResolver(schema_hash=setup["resolver_schema_hash"])
    converter_class = (
        prepare_cases.TreeDriftConverter if setup.get("converter") == "tree_drift" else case.converter_class
    )
    if setup.get("supersede_revision"):
        WorkflowPlanRevision.objects.create(
            run=case.run,
            sequence=2,
            parent_revision=case.revision,
            intent_spec={"goal": "golden successor"},
            canonical_a2flow={"version": "2.0", "nodes": []},
            plan_hash="f" * 64,
        )
    tool, payload = golden.materialize_request(fixture_case, **_runtime(case))
    runtime_case = SimpleNamespace(**{**vars(case), "request": payload})
    before_ids = set(EvidenceEvent._base_manager.values_list("id", flat=True))
    before_counts = golden.snapshot_counts()
    trace = []
    release_policy = ReleasePolicy(profiles={case.context.policy_version: prepare_cases.POSTCONDITION_SPEC})
    kwargs = {"converter_class": converter_class}
    if setup.get("release_policy") == "unavailable":
        release_policy = ReleasePolicy(profiles={})
    response = golden.invoke_service(
        trace,
        tool,
        runtime_case.context,
        runtime_case.request,
        resolver=runtime_case.resolver,
        release_policy=release_policy,
        converter_class=kwargs["converter_class"],
    )
    if setup.get("replay"):
        assert (
            golden.invoke_service(
                trace,
                tool,
                runtime_case.context,
                runtime_case.request,
                resolver=runtime_case.resolver,
                release_policy=release_policy,
                converter_class=kwargs["converter_class"],
            )
            == response
        )
    return _release_result(case, response, tool, payload, before_ids, before_counts, trace)


def _verifier(case, approval, *, expired=False, digest_mismatch=False):
    claims = publish_cases.expected_claims(case, approval)
    if digest_mismatch:
        claims["action_digest"] = "f" * 64
    backend = publish_cases.ReceiptBackend(claims)
    if expired:
        backend.verify = lambda receipt_ref: {
            "allowed": True,
            "provider": "bkaidev",
            "receipt_ref": receipt_ref,
            "claims": copy.deepcopy(claims),
            "expires_at": timezone.now() - timezone.timedelta(seconds=1),
            "revoked": False,
            "reason": "approved",
            "verifier_version": "golden-v1",
        }
    return ApprovalVerifier(backend=backend, replay_guard=InMemoryApprovalReplayGuard())


def _execute_publish(fixture_case, case, monkeypatch):
    golden.assert_case_declarations(fixture_case)
    setup = fixture_case["setup"]
    engine_sequence = fixture_case["engine_sequence"]
    approval_mode = fixture_case["approval"]["mode"]
    golden.apply_declared_policy(case.context.space_id, fixture_case)
    assert fixture_case["approval"]["action"] == HarnessAction.PUBLISH_WORKFLOW
    tool, first_payload = _base_publish_request(case, fixture_case)
    before_ids = set(EvidenceEvent._base_manager.values_list("id", flat=True))
    before_counts = golden.snapshot_counts()
    trace = []
    release_policy = ReleasePolicy(profiles={case.context.policy_version: prepare_cases.POSTCONDITION_SPEC})

    def invoke(payload, verifier=None):
        return golden.invoke_service(
            trace,
            tool,
            case.context,
            payload,
            resolver=case.resolver,
            release_policy=release_policy,
            approval_verifier=verifier,
            converter_class=prepare_cases.ReleaseConverter,
        )

    first = invoke(first_payload)
    if setup.get("phase") == "approval_only":
        return _release_result(case, first, tool, first_payload, before_ids, before_counts, trace)

    approval = ApprovalRequest.objects.get(pk=first["approval_request_id"])
    tool, payload = _approval_payload(case, fixture_case, approval)
    verifier = _verifier(
        case,
        approval,
        expired=approval_mode == "expired_test_double",
        digest_mismatch=approval_mode == "forged_test_double",
    )
    if setup.get("phase") == "version_collision":
        TemplateSnapshot.objects.create(
            template_id=case.template.id,
            draft=False,
            version=payload["version"],
            data={"id": "golden-version-collision"},
            md5sum="d" * 32,
        )
    if "database_anchor_error" in engine_sequence:
        original = ReleasePublication.objects.create
        calls = {"count": 0}

        def fail_once(**kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise DatabaseError("golden publication anchor crash")
            return original(**kwargs)

        monkeypatch.setattr(ReleasePublication.objects, "create", fail_once)
        failed = invoke(payload, verifier)
        assert golden.response_code(failed) == "RETRYABLE_INFRA"
        case.run.refresh_from_db()
        case.snapshot.refresh_from_db()
        approval.refresh_from_db()
        observed_fault = {
            "run_status": case.run.status,
            "approval_status": approval.status,
            "draft": case.snapshot.draft,
            "publications": ReleasePublication.objects.filter(manifest=case.manifest).count(),
            "publish_mutations": golden.snapshot_counts()["publish"] - before_counts["publish"],
            "evidence": EvidenceEvent.objects.filter(run=case.run, event_type="WORKFLOW_PUBLISHED").count(),
            "idempotency": case.run.idempotency_records.filter(tool_name=HarnessAction.PUBLISH_WORKFLOW).count(),
        }
        assert observed_fault == fixture_case["after_fault"]
        response = invoke(payload, verifier)
        case.run.refresh_from_db()
        case.snapshot.refresh_from_db()
        observed_retry = {
            "run_status": case.run.status,
            "draft": case.snapshot.draft,
            "publications": ReleasePublication.objects.filter(manifest=case.manifest).count(),
            "publish_mutations": golden.snapshot_counts()["publish"] - before_counts["publish"],
            "evidence": EvidenceEvent.objects.filter(run=case.run, event_type="WORKFLOW_PUBLISHED").count(),
            "idempotency": case.run.idempotency_records.filter(tool_name=HarnessAction.PUBLISH_WORKFLOW).count(),
        }
        assert observed_retry == fixture_case["after_retry"]
    elif "release_committed_response_lost" in engine_sequence:
        TemplateReleaseService.release(
            case.template,
            {"version": payload["version"], "desc": payload["description"], "force": False},
            case.context.actor,
            "api",
            emit_webhook=False,
            expected_draft_snapshot_id=case.snapshot.id,
        )
        case.run.status = HarnessRunStatus.PUBLISHING
        case.run.save(update_fields=["status"])
        case.snapshot.refresh_from_db()
        observed_preexisting = {
            "draft": case.snapshot.draft,
            "publications": ReleasePublication.objects.filter(manifest=case.manifest).count(),
            "publish_mutations": golden.snapshot_counts()["publish"] - before_counts["publish"],
            "evidence": EvidenceEvent.objects.filter(run=case.run, event_type="WORKFLOW_PUBLISHED").count(),
            "idempotency": case.run.idempotency_records.filter(tool_name=HarnessAction.PUBLISH_WORKFLOW).count(),
        }
        assert observed_preexisting == fixture_case["preexisting"]
        before_counts = golden.snapshot_counts()
        response = invoke(payload, verifier)
    else:
        response = invoke(payload, verifier)
        if setup.get("replay"):
            assert invoke(payload, verifier) == response
        if setup.get("phase") == "conflict_after_success":
            response = invoke(
                {**payload, "description": "Different golden action"},
                _verifier(case, approval),
            )
    if setup.get("assertion_focus") == "approval_binding":
        approval.refresh_from_db()
        assert approval.status == ApprovalRequest.Status.VERIFIED
        assert approval.action == HarnessAction.PUBLISH_WORKFLOW
        assert approval.receipt_ref == fixture_case["approval"]["receipt_ref"]
        assert approval.receipt_digest
        assert approval.manifest_id == case.manifest.id
    if setup.get("assertion_focus") == "publication_atomicity":
        publication = ReleasePublication.objects.get(manifest=case.manifest)
        assert publication.published_snapshot_id == case.snapshot.id
        assert publication.published_version == payload["version"]
        assert publication.publication_hash
        assert (
            case.run.idempotency_records.filter(tool_name=HarnessAction.PUBLISH_WORKFLOW, status="COMPLETED").count()
            == 1
        )
    return _release_result(case, response, tool, payload, before_ids, before_counts, trace)


def _execute_start_approval(fixture_case, case):
    golden.assert_case_declarations(fixture_case)
    golden.apply_declared_policy(case.context.space_id, fixture_case)
    tool, payload = golden.materialize_request(
        fixture_case,
        **{
            **_runtime(case),
            "approval_request_id": "00000000-0000-0000-0000-000000000000",
            "approval_receipt_ref": fixture_case["approval"].get("receipt_ref", "approval://golden/start"),
        },
    )
    before_ids = set(EvidenceEvent._base_manager.values_list("id", flat=True))
    before_counts = golden.snapshot_counts()
    trace = []
    adapter = start_cases.RecordingAdapter()
    if fixture_case["setup"]["phase"] == "approval_only":
        payload.pop("approval_request_id", None)
        payload.pop("approval_receipt_ref", None)
        response = golden.invoke_service(
            trace,
            tool,
            case.context,
            payload,
            resolver=case.resolver,
            release_policy=case.release_policy,
            converter_class=prepare_cases.ReleaseConverter,
            credential_resolver=start_cases.RecordingCredentialResolver(),
            adapter=adapter,
        )
    else:
        publish_approval = ApprovalRequest.objects.filter(
            manifest=case.manifest, action=HarnessAction.PUBLISH_WORKFLOW
        ).first()
        payload["approval_request_id"] = str(publish_approval.id)
        response = golden.invoke_service(
            trace,
            tool,
            case.context,
            payload,
            resolver=case.resolver,
            release_policy=case.release_policy,
            converter_class=prepare_cases.ReleaseConverter,
            credential_resolver=start_cases.RecordingCredentialResolver(),
            adapter=adapter,
        )
    return _release_result(case, response, tool, payload, before_ids, before_counts, trace, adapter=adapter)


def test_fixture_has_exactly_forty_eight_complete_cases_in_the_frozen_distribution():
    golden.validate_fixture_structure()


def test_yaml_alias_values_are_independent_between_loaded_cases():
    cases = golden.load_cases()
    for field in (
        "trusted_context",
        "predecessor_revision",
        "draft_fingerprint",
        "policy",
        "approval",
        "engine_sequence",
        "forbidden_markers",
    ):
        assert cases[0][field] is not cases[1][field]


def test_contract_1_3_0_is_exactly_fourteen_cumulative_tools():
    assert tuple(tools_for_contract("1.3.0")) == (
        "search_workflow_capabilities",
        "get_plugin_schema",
        "validate_workflow",
        "create_workflow_draft",
        "search_workflow_knowledge",
        "start_debug_session",
        "run_debug",
        "get_debug_session",
        "control_debug_session",
        "prepare_release",
        "publish_workflow",
        "start_workflow_execution",
        "get_workflow_execution",
        "control_workflow_execution",
    )


def test_release_runners_do_not_branch_on_case_id():
    sources = (
        inspect.getsource(_execute_prepare)
        + inspect.getsource(_execute_publish)
        + inspect.getsource(_execute_start_approval)
    )
    assert '["id"]' not in sources
    assert "['id']" not in sources


def test_makefile_and_verification_expose_the_reproducible_p3_gate():
    verification = ROOT / "docs/reviews/2026-09-02-bkaidev-harness-p3-verification.md"
    assert verification.exists()
    content = (ROOT / "Makefile").read_text(encoding="utf-8")
    for marker in (
        "harness-p3-gate:",
        "HARNESS_P3_GATE_PATHS",
        "tests/interface/harness",
        "tests/interface/apigw/test_harness_p3.py",
        "tests/interface/template/services/test_release.py",
        "tests/interface/task/services/test_task_creator.py",
        "tests/interface/apigw/test_release_template.py",
        "tests/interface/apigw/test_create_task.py",
        "tests/interface/apigw/test_update_template.py",
        "tests/interface/template/test_template_views.py",
        "manage.py check",
        "makemigrations harness --check --dry-run",
        "unzip -t bkflow/apigw/docs/apigw-docs.zip",
        "git diff --check",
        "--strict-markers",
    ):
        assert marker in content
    assert "/Users/" not in content


@pytest.mark.django_db
@pytest.mark.parametrize("fixture_case", PREPARE_CASES, ids=lambda case: case["id"])
def test_prepare_golden_case_drives_domain_and_durable_state(fixture_case, golden_release_builder):
    result = _execute_prepare(fixture_case, golden_release_builder)
    golden.assert_common_contract(fixture_case, result)
    assert ReleaseManifest.objects.filter(run=result.run).count() == (1 if result.response["ok"] else 0)
    if result.response["ok"]:
        manifest = ReleaseManifest.objects.get(run=result.run)
        assert manifest.plan_hash == result.revision.plan_hash
        assert manifest.draft_snapshot_id == result.snapshot.id
        assert {item["action"] for item in manifest.required_approvals} == {
            HarnessAction.PUBLISH_WORKFLOW,
            HarnessAction.START_WORKFLOW_EXECUTION,
        }
        assert result.response["artifact_refs"][0]["manifest_hash"] == manifest.manifest_hash
        assert (
            HarnessIdempotencyRecord.objects.filter(
                run=result.run,
                tool_name=HarnessAction.PREPARE_RELEASE,
                status=IdempotencyRecordStatus.COMPLETED,
            ).count()
            == 1
        )
        assert ApprovalRequest.objects.filter(manifest=manifest).count() == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("fixture_case", PUBLISH_CASES, ids=lambda case: case["id"])
def test_publish_golden_case_drives_domain_and_durable_state(fixture_case, golden_publish_case, monkeypatch):
    result = _execute_publish(fixture_case, golden_publish_case, monkeypatch)
    golden.assert_common_contract(fixture_case, result)
    expected_publications = (
        1
        if (
            fixture_case["expected"]["mutations"]["publish"]
            or "release_committed_response_lost" in fixture_case["engine_sequence"]
        )
        else 0
    )
    assert (
        ReleasePublication.objects.filter(manifest=result.run.release_manifests.get()).count() == expected_publications
    )
    if fixture_case["setup"].get("phase") == "approval_only":
        approval = ApprovalRequest.objects.get(manifest=result.run.release_manifests.get())
        assert approval.action == HarnessAction.PUBLISH_WORKFLOW
        assert approval.status == ApprovalRequest.Status.PENDING
    if expected_publications:
        publication = ReleasePublication.objects.get(manifest=result.run.release_manifests.get())
        assert publication.published_template_id == result.template.id
        assert publication.published_snapshot_id == result.snapshot.id
        assert publication.publication_hash


@pytest.mark.django_db
@pytest.mark.parametrize("fixture_case", START_APPROVAL_CASES, ids=lambda case: case["id"])
def test_start_approval_golden_case_drives_domain_and_durable_state(fixture_case, golden_execution_case):
    result = _execute_start_approval(fixture_case, golden_execution_case)
    golden.assert_common_contract(fixture_case, result)
    assert result.run.executions.count() == 0
    expected = fixture_case["expected"].get("approval")
    if expected is not None:
        approval = ApprovalRequest.objects.get(
            manifest=result.run.release_manifests.get(),
            action=expected["action"],
            status=expected["status"],
        )
        assert len(approval.action_digest) == 64
        distinct = ApprovalRequest.objects.get(
            manifest=approval.manifest,
            action=expected["distinct_from"],
        )
        assert distinct.id != approval.id


@pytest.mark.parametrize("field", ("policy", "approval", "engine_sequence"))
def test_mutating_behavior_declaration_is_rejected(field):
    source = copy.deepcopy(PUBLISH_CASES[0])
    if field == "policy":
        source[field]["execution_enabled"] = False
    elif field == "approval":
        source[field]["action"] = HarnessAction.START_WORKFLOW_EXECUTION
    else:
        source[field].append("decorative:unused")
    with pytest.raises(AssertionError):
        golden.assert_case_declarations(source)


def test_start_pending_approval_fixture_requires_distinct_durable_approval_contract():
    case = next(item for item in START_APPROVAL_CASES if item["setup"]["phase"] == "approval_only")
    assert case["expected"]["approval"] == {
        "action": HarnessAction.START_WORKFLOW_EXECUTION,
        "status": ApprovalRequest.Status.PENDING,
        "distinct_from": HarnessAction.PUBLISH_WORKFLOW,
        "digest": "present",
    }


@pytest.mark.django_db
@pytest.mark.parametrize("field", ("trusted_context", "predecessor_revision", "draft_fingerprint", "request"))
def test_mutating_audited_release_declaration_breaks_contract(field, golden_release_builder):
    source = copy.deepcopy(PREPARE_CASES[0])
    result = _execute_prepare(source, golden_release_builder)
    if field == "trusted_context":
        source[field]["actor"] = "not-runtime"
    elif field == "predecessor_revision":
        source[field]["sequence"] = 999
    elif field == "draft_fingerprint":
        source[field]["relation"] = "drifted"
    else:
        source[field]["payload"]["idempotency_key"] = "changed-after-materialization"
    with pytest.raises(AssertionError):
        golden.assert_common_contract(source, result)
