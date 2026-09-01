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

from bkflow.constants import ValidateType
from bkflow.harness.constants import HarnessRunStatus, ValidationResult
from bkflow.harness.contracts import TrustedHarnessContext
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
from bkflow.harness.services.resolver import resolve_capability
from bkflow.harness.services.state import transition_run
from bkflow.harness.services.validator import (
    DEFAULT_POLICIES,
    VALIDATOR_VERSION,
    _envelope,
    _error,
)
from bkflow.pipeline_converter.converters.a2flow_v2 import A2FlowV2Converter
from bkflow.pipeline_validate.handler import ValidatorHandler
from bkflow.template.models import Template
from bkflow.template.services.a2flow_template import (
    create_template_from_a2flow,
    update_template_draft_from_a2flow,
)

TOOL_NAME = "create_workflow_draft"


def _fail(run: Optional[HarnessRun], context: TrustedHarnessContext, errors: List[Dict[str, Any]]) -> Dict[str, Any]:
    return _envelope(
        ok=False,
        run_id=str(run.id) if run else None,
        revision_id=None,
        plan_hash=None,
        status=run.status if run else None,
        summary="草稿创建失败",
        artifact_refs=[],
        errors=errors,
        next_actions=[{"action": "validate_workflow"}],
        correlation_id=context.correlation_id,
    )


def create_workflow_draft(request: Any, space_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    """基于已接受修订创建或原位更新 Harness 管理的模板草稿。"""
    context = TrustedHarnessContext.from_request(request, space_id)
    return create_workflow_draft_with_context(context, payload)


def create_workflow_draft_with_context(context: TrustedHarnessContext, payload: Dict[str, Any]) -> Dict[str, Any]:
    """在已推导可信上下文后创建草稿。"""
    idempotency_key = payload.get("idempotency_key")
    if not idempotency_key:
        return _fail(None, context, [_error("USER_INPUT", "idempotency_key is required")])

    request_hash = sha256_json(
        {
            "run_id": str(payload.get("run_id") or ""),
            "revision_id": str(payload.get("revision_id") or ""),
            "plan_hash": payload.get("plan_hash"),
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
        envelope = _create_owned(context, payload)
        run = HarnessRun.objects.filter(pk=envelope.get("run_id")).first() if envelope.get("run_id") else None
        complete_idempotency(acquired.record, envelope, run=run)
        return envelope
    except Exception:
        fail_idempotency(acquired.record)
        raise


def _create_owned(context: TrustedHarnessContext, payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = payload.get("run_id")
    revision_id = payload.get("revision_id")
    if not run_id or not revision_id:
        return _fail(None, context, [_error("USER_INPUT", "run_id and revision_id are required")])

    try:
        run = HarnessRun.objects.get(pk=run_id, space_id=context.space_id)
    except HarnessRun.DoesNotExist:
        return _fail(None, context, [_error("USER_INPUT", "run is not found in the trusted space")])

    if run.actor != context.actor or run.platform_app != context.platform_app:
        return _fail(run, context, [_error("PERMISSION", "caller does not match the stored run")])
    if run.status == HarnessRunStatus.NEEDS_REPAIR.value:
        return _fail(run, context, [_error("USER_INPUT", "cannot create a draft while the run needs repair")])

    try:
        revision = WorkflowPlanRevision.objects.get(pk=revision_id, run=run)
    except WorkflowPlanRevision.DoesNotExist:
        return _fail(run, context, [_error("USER_INPUT", "revision does not belong to the run")])

    if payload.get("plan_hash") != revision.plan_hash:
        return _fail(run, context, [_error("PLAN_HASH_MISMATCH", "plan_hash does not match the stored revision")])

    stale = _revalidate_revision(context, run, revision)
    if stale:
        return _fail(run, context, stale)

    template_id = (run.artifact_refs or {}).get("template_id")
    if template_id:
        template = Template.objects.get(pk=template_id)
        snapshot = update_template_draft_from_a2flow(
            template=template,
            username=context.actor,
            a2flow=revision.canonical_a2flow,
            expected_space_id=context.space_id,
            expected_bind_app_code=context.platform_app,
        )
    else:
        template = create_template_from_a2flow(
            space_id=context.space_id,
            username=context.actor,
            a2flow=revision.canonical_a2flow,
            scope_type=context.scope_type,
            scope_value=context.scope_value,
            bind_app_code=context.platform_app,
            auto_release=False,
        )
        snapshot = type("Snapshot", (), {"id": template.snapshot_id})()

    refs = {"template_id": template.id, "draft_snapshot_id": getattr(snapshot, "id", template.snapshot_id)}
    run.artifact_refs = {**(run.artifact_refs or {}), **refs}
    run.save(update_fields=["artifact_refs", "update_at"])
    if run.status == HarnessRunStatus.VALIDATING.value:
        transition_run(run, HarnessRunStatus.DRAFT_READY, trigger="create_workflow_draft")

    return _envelope(
        ok=True,
        run_id=str(run.id),
        revision_id=str(revision.id),
        plan_hash=revision.plan_hash,
        status=run.status,
        summary="草稿已就绪",
        artifact_refs=[
            {"type": "template_id", "value": template.id},
            {"type": "draft_snapshot_id", "value": refs["draft_snapshot_id"]},
        ],
        errors=[],
        next_actions=[],
        correlation_id=context.correlation_id,
    )


def _revalidate_revision(context: TrustedHarnessContext, run: HarnessRun, revision: WorkflowPlanRevision):
    report = (
        ValidationReport.objects.filter(run=run, revision=revision, result=ValidationResult.PASSED.value)
        .order_by("-create_at")
        .first()
    )
    if report is None:
        return [_error("USER_INPUT", "revision has no accepted validation report")]

    resolved_bindings = []
    for binding in CapabilityBinding.objects.filter(revision=revision).order_by("id"):
        resolved = resolve_capability(
            context,
            binding.capability_ref,
            expected_schema_hash=binding.schema_hash,
        )
        resolved_bindings.append(
            {
                "node_id": binding.node_id,
                "capability_ref": resolved.capability_ref,
                "resolved_version": resolved.resolved_version,
                "schema_hash": resolved.schema_hash,
                "credential_ref": binding.credential_ref,
                "risk_level": resolved.risk_level,
            }
        )

    digest = plan_hash(
        {
            "a2flow": revision.canonical_a2flow,
            "bindings": resolved_bindings,
            "space_id": context.space_id,
            "scope_type": context.scope_type,
            "scope_value": context.scope_value,
            "target_environment": context.target_environment,
            "authorization_scope": "space:{}".format(context.space_id),
            "policies": DEFAULT_POLICIES,
        }
    )
    if digest != revision.plan_hash:
        return [_error("VALIDATION_STALE", "recomputed plan_hash drifted", path="plan_hash")]

    try:
        conversion = A2FlowV2Converter(
            revision.canonical_a2flow,
            space_id=context.space_id,
            username=context.actor,
            scope_type=context.scope_type,
            scope_value=context.scope_value,
        ).convert_with_metadata()
        ValidatorHandler.validate(conversion.pipeline_tree, validate_type=ValidateType.TEMPLATE)
    except Exception as exc:
        return [_error("VALIDATION_STALE", str(exc), path="pipeline_tree")]

    manifest = report.risk_manifest or {}
    if (
        report.validator_version != VALIDATOR_VERSION
        or manifest.get("converter_fingerprint") != conversion.converter_fingerprint
        or manifest.get("pipeline_tree_hash") != sha256_json(conversion.pipeline_tree)
    ):
        return [_error("VALIDATION_STALE", "validator or converter fingerprint changed")]
    return []
