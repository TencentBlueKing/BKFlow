"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.db.models import Max

from bkflow.constants import ValidateType
from bkflow.harness.constants import (
    HarnessRunStatus,
    ValidationCheckpoint,
    ValidationResult,
)
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.exceptions import (
    CapabilityForbidden,
    CapabilityNotFound,
    CapabilityRefError,
    SchemaDrift,
)
from bkflow.harness.models import (
    CapabilityBinding,
    HarnessRun,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import plan_hash, sha256_json
from bkflow.harness.services.idempotency import (
    acquire_idempotency,
    complete_idempotency,
    fail_idempotency,
    run_scope_for,
)
from bkflow.harness.services.input_schema import validate_node_data
from bkflow.harness.services.resolver import resolve_capability
from bkflow.harness.services.state import transition_run
from bkflow.pipeline_converter.constants import NodeType
from bkflow.pipeline_converter.converters.a2flow_v2 import A2FlowV2Converter
from bkflow.pipeline_validate.handler import ValidatorHandler

VALIDATOR_VERSION = "p0-v1"
TOOL_NAME = "validate_workflow"
ENVELOPE_KEYS = (
    "ok",
    "run_id",
    "revision_id",
    "plan_hash",
    "status",
    "summary",
    "artifact_refs",
    "errors",
    "next_actions",
    "correlation_id",
)
DEFAULT_POLICIES = {
    "execution": {"mode": "draft_only"},
    "risk": {"max_level": "L1"},
    "retry": {"max": 0},
    "timeout": {"seconds": 30},
    "compensation": {"enabled": False},
    "postcondition": {"required": False},
}


def _envelope(**kwargs) -> Dict[str, Any]:
    return {key: kwargs.get(key) for key in ENVELOPE_KEYS}


def _error(code: str, message: str, path: str = "", repairable: bool = True, retryable: bool = False) -> Dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "path": path,
        "repairable": repairable,
        "retryable": retryable,
    }


def _activity_node_ids(a2flow: Dict[str, Any]) -> List[str]:
    ids = []
    for node in a2flow.get("nodes") or []:
        node_type = node.get("type") or NodeType.ACTIVITY
        if node_type == NodeType.ACTIVITY:
            ids.append(node["id"])
    return ids


def _node_map(a2flow: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {node["id"]: node for node in (a2flow.get("nodes") or [])}


def _validate_binding_coverage(a2flow: Dict[str, Any], bindings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    required = _activity_node_ids(a2flow)
    provided = [item.get("node_id") for item in bindings]
    if len(provided) != len(set(provided)):
        return [_error("USER_INPUT", "duplicate node bindings", path="bindings")]
    if set(provided) != set(required):
        return [_error("USER_INPUT", "node bindings do not match activity nodes", path="bindings")]
    return []


def _validate_node_inputs(node: Dict[str, Any], schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    data = node.get("data") or {}
    errors = validate_node_data(node["id"], data, schema.get("inputs") or [])
    for field in schema.get("inputs") or []:
        if not isinstance(field, dict):
            continue
        key = field.get("key")
        if field.get("required") and key in data and data.get(key) in (None, ""):
            path = "nodes.{}.inputs.{}".format(node["id"], key)
            if not any(item.get("path") == path for item in errors):
                errors.append(_error("SCHEMA_VALIDATION_ERROR", "missing required input {}".format(key), path=path))
    return errors


def _latest_accepted_revision(run: HarnessRun) -> Optional[WorkflowPlanRevision]:
    return run.revisions.order_by("-sequence").first()


def _enter_validating(run: HarnessRun) -> None:
    if run.status == HarnessRunStatus.INTENT_CAPTURED.value:
        transition_run(run, HarnessRunStatus.PLANNING)
        transition_run(run, HarnessRunStatus.VALIDATING)
    elif run.status == HarnessRunStatus.PLANNING.value:
        transition_run(run, HarnessRunStatus.VALIDATING)
    elif run.status == HarnessRunStatus.NEEDS_REPAIR.value:
        transition_run(run, HarnessRunStatus.VALIDATING)
    elif run.status == HarnessRunStatus.DRAFT_READY.value:
        transition_run(run, HarnessRunStatus.VALIDATING)


def _get_or_create_run(context: TrustedHarnessContext, payload: Dict[str, Any]) -> HarnessRun:
    run_id = payload.get("run_id")
    if run_id:
        return HarnessRun.objects.get(
            pk=run_id,
            space_id=context.space_id,
            actor=context.actor,
            platform_app=context.platform_app,
        )
    return HarnessRun.objects.create(
        platform_key=context.platform_key,
        platform_app=context.platform_app,
        actor=context.actor,
        space_id=context.space_id,
        scope_type=context.scope_type,
        scope_value=context.scope_value,
        target_environment=context.target_environment,
        status=HarnessRunStatus.INTENT_CAPTURED.value,
        policy_version=context.policy_version,
        mcp_contract_version=context.mcp_contract_version,
        client_context=payload.get("client_context") or {},
    )


def _persist_failed_report(
    run: HarnessRun, context: TrustedHarnessContext, errors: List[Dict[str, Any]]
) -> ValidationReport:
    report = ValidationReport.objects.create(
        run=run,
        revision=None,
        checkpoint=ValidationCheckpoint.VALIDATE_WORKFLOW.value,
        validator_version=VALIDATOR_VERSION,
        result=ValidationResult.FAILED.value,
        errors=errors,
        correlation_id=context.correlation_id,
    )
    if run.status == HarnessRunStatus.VALIDATING.value:
        transition_run(run, HarnessRunStatus.NEEDS_REPAIR)
    return report


def _fail_envelope(
    run: Optional[HarnessRun],
    context: TrustedHarnessContext,
    errors: List[Dict[str, Any]],
    *,
    report: Optional[ValidationReport] = None,
) -> Dict[str, Any]:
    artifact_refs = []
    if report is not None:
        artifact_refs.append({"type": "report_id", "value": str(report.id)})
    return _envelope(
        ok=False,
        run_id=str(run.id) if run else None,
        revision_id=None,
        plan_hash=None,
        status=run.status if run else None,
        summary="校验失败，需要修复",
        artifact_refs=artifact_refs,
        errors=errors,
        next_actions=[{"action": "repair", "path": errors[0].get("path")} if errors else {}],
        correlation_id=context.correlation_id,
    )


def validate_workflow(request: Any, space_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    """确定性校验 a2flow，并在成功时创建不可变修订。"""
    context = TrustedHarnessContext.from_request(request, space_id)
    return validate_workflow_with_context(context, payload)


def validate_workflow_with_context(context: TrustedHarnessContext, payload: Dict[str, Any]) -> Dict[str, Any]:
    """在已推导可信上下文后执行校验。"""
    idempotency_key = payload.get("idempotency_key")
    if not idempotency_key:
        return _fail_envelope(None, context, [_error("USER_INPUT", "idempotency_key is required")])

    request_hash = sha256_json(
        {
            "a2flow": payload.get("a2flow"),
            "bindings": payload.get("bindings"),
            "intent": payload.get("intent"),
            "run_id": str(payload.get("run_id") or ""),
            "expected_plan_hash": payload.get("expected_plan_hash"),
        }
    )
    acquired = acquire_idempotency(
        platform_app=context.platform_app,
        actor=context.actor,
        space_id=context.space_id,
        tool_name=TOOL_NAME,
        run_scope=run_scope_for(payload.get("run_id")),
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if acquired.replay:
        return acquired.response_snapshot

    try:
        envelope = _validate_owned(context, payload)
        run = HarnessRun.objects.filter(pk=envelope.get("run_id")).first() if envelope.get("run_id") else None
        complete_idempotency(acquired.record, envelope, run=run)
        return envelope
    except Exception:
        fail_idempotency(acquired.record)
        raise


def _validate_owned(context: TrustedHarnessContext, payload: Dict[str, Any]) -> Dict[str, Any]:
    run = _get_or_create_run(context, payload)
    _enter_validating(run)

    expected = payload.get("expected_plan_hash")
    latest = _latest_accepted_revision(run)
    if expected and latest and latest.plan_hash != expected:
        errors = [_error("PLAN_HASH_MISMATCH", "expected_plan_hash does not match the latest accepted revision")]
        report = _persist_failed_report(run, context, errors)
        return _fail_envelope(run, context, errors, report=report)

    a2flow = payload.get("a2flow") or {}
    bindings = payload.get("bindings") or []
    coverage_errors = _validate_binding_coverage(a2flow, bindings)
    if coverage_errors:
        report = _persist_failed_report(run, context, coverage_errors)
        return _fail_envelope(run, context, coverage_errors, report=report)

    nodes = _node_map(a2flow)
    resolved_bindings = []
    input_errors = []
    for binding in bindings:
        try:
            resolved = resolve_capability(
                context,
                binding["capability_ref"],
                expected_schema_hash=binding.get("schema_hash"),
            )
        except CapabilityNotFound as exc:
            errors = [_error("CAPABILITY_NOT_FOUND", str(exc), path="bindings.{}".format(binding.get("node_id")))]
            report = _persist_failed_report(run, context, errors)
            return _fail_envelope(run, context, errors, report=report)
        except CapabilityForbidden as exc:
            errors = [_error("CAPABILITY_FORBIDDEN", str(exc), path="bindings.{}".format(binding.get("node_id")))]
            report = _persist_failed_report(run, context, errors)
            return _fail_envelope(run, context, errors, report=report)
        except SchemaDrift as exc:
            errors = [_error("SCHEMA_DRIFT", str(exc), path="bindings.{}".format(binding.get("node_id")))]
            report = _persist_failed_report(run, context, errors)
            return _fail_envelope(run, context, errors, report=report)
        except CapabilityRefError as exc:
            errors = [_error("USER_INPUT", str(exc), path="bindings.{}".format(binding.get("node_id")))]
            report = _persist_failed_report(run, context, errors)
            return _fail_envelope(run, context, errors, report=report)

        node = nodes.get(binding["node_id"]) or {}
        input_errors.extend(_validate_node_inputs(node, resolved.schema))
        resolved_bindings.append((binding, resolved))

    if input_errors:
        report = _persist_failed_report(run, context, input_errors)
        return _fail_envelope(run, context, input_errors, report=report)

    try:
        conversion = A2FlowV2Converter(
            a2flow,
            space_id=context.space_id,
            username=context.actor,
            scope_type=context.scope_type,
            scope_value=context.scope_value,
        ).convert_with_metadata()
    except Exception as exc:
        errors = [_error("A2FLOW_CONVERSION_ERROR", str(exc), path="a2flow")]
        report = _persist_failed_report(run, context, errors)
        return _fail_envelope(run, context, errors, report=report)

    try:
        ValidatorHandler.validate(conversion.pipeline_tree, validate_type=ValidateType.TEMPLATE)
    except Exception as exc:
        errors = [_error("PIPELINE_VALIDATION_ERROR", str(exc), path="pipeline_tree")]
        report = _persist_failed_report(run, context, errors)
        return _fail_envelope(run, context, errors, report=report)

    plan_bindings = [
        {
            "node_id": binding["node_id"],
            "capability_ref": resolved.capability_ref,
            "resolved_version": resolved.resolved_version,
            "schema_hash": resolved.schema_hash,
            "credential_ref": binding.get("credential_ref"),
            "risk_level": resolved.risk_level,
        }
        for binding, resolved in resolved_bindings
    ]
    digest = plan_hash(
        {
            "a2flow": a2flow,
            "bindings": plan_bindings,
            "space_id": context.space_id,
            "scope_type": context.scope_type,
            "scope_value": context.scope_value,
            "target_environment": context.target_environment,
            "authorization_scope": "space:{}".format(context.space_id),
            "policies": DEFAULT_POLICIES,
        }
    )
    pipeline_tree_hash = sha256_json(conversion.pipeline_tree)
    revision, report = _persist_success(
        run,
        context,
        payload,
        a2flow,
        plan_bindings,
        digest,
        conversion.converter_fingerprint,
        pipeline_tree_hash,
        latest,
    )
    return _envelope(
        ok=True,
        run_id=str(run.id),
        revision_id=str(revision.id),
        plan_hash=digest,
        status=run.status,
        summary="校验通过，已生成修订",
        artifact_refs=[
            {"type": "validator_version", "value": VALIDATOR_VERSION},
            {"type": "converter_fingerprint", "value": conversion.converter_fingerprint},
            {"type": "pipeline_tree_hash", "value": pipeline_tree_hash},
            {"type": "report_id", "value": str(report.id)},
        ],
        errors=[],
        next_actions=[{"action": "create_workflow_draft"}],
        correlation_id=context.correlation_id,
    )


def _persist_success(
    run: HarnessRun,
    context: TrustedHarnessContext,
    payload: Dict[str, Any],
    a2flow: Dict[str, Any],
    plan_bindings: List[Dict[str, Any]],
    digest: str,
    converter_fingerprint: str,
    pipeline_tree_hash: str,
    parent: Optional[WorkflowPlanRevision],
):
    with transaction.atomic():
        sequence = (run.revisions.aggregate(Max("sequence"))["sequence__max"] or 0) + 1
        revision = WorkflowPlanRevision.objects.create(
            run=run,
            sequence=sequence,
            parent_revision=parent,
            intent_spec=payload.get("intent") or {},
            canonical_a2flow=a2flow,
            plan_hash=digest,
        )
        for item in plan_bindings:
            CapabilityBinding.objects.create(
                revision=revision,
                node_id=item["node_id"],
                capability_ref=item["capability_ref"],
                resolved_version=item["resolved_version"],
                schema_hash=item["schema_hash"],
                credential_ref=item.get("credential_ref"),
                risk_level=item["risk_level"],
            )
        report = ValidationReport.objects.create(
            run=run,
            revision=revision,
            checkpoint=ValidationCheckpoint.VALIDATE_WORKFLOW.value,
            validator_version=VALIDATOR_VERSION,
            result=ValidationResult.PASSED.value,
            risk_manifest={
                "converter_fingerprint": converter_fingerprint,
                "pipeline_tree_hash": pipeline_tree_hash,
            },
            correlation_id=context.correlation_id,
        )
    return revision, report
