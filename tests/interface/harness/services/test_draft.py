"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file
except in compliance with the License. You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
    10|CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bkflow.harness.constants import (
    HarnessRunStatus,
    ValidationCheckpoint,
    ValidationResult,
)
from bkflow.harness.contracts import ResolvedCapability
from bkflow.harness.models import (
    CapabilityBinding,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import plan_hash, schema_hash
from bkflow.harness.services.capability_ref import encode_capability_ref
from bkflow.pipeline_converter.converters.a2flow_v2.data_models import ConversionResult
from bkflow.space.configs import SpaceConfigValueType
from bkflow.space.models import SpaceConfig
from bkflow.template.models import Template, TemplateSnapshot

SCHEMA = {"inputs": [{"key": "host", "type": "string", "required": True}], "outputs": []}
SCHEMA_HASH = schema_hash(SCHEMA)
CAPABILITY_REF = encode_capability_ref(
    plugin_type="component", source_key=None, code="demo_restart_service", version="1.0.0"
)
A2FLOW = {
    "version": "2.0",
    "name": "restart",
    "nodes": [
        {"id": "node_1", "name": "重启", "code": "demo_restart_service", "data": {"host": "1.2.3.4"}, "next": "end"}
    ],
}
PIPELINE_TREE = {
    "activities": {"n1": {"id": "n1", "type": "ServiceActivity", "name": "重启"}},
    "gateways": {},
    "flows": {},
    "start_event": {"id": "start", "type": "EmptyStartEvent"},
    "end_event": {"id": "end", "type": "EmptyEndEvent"},
    "constants": {},
}
VALID_DEPLOYMENT = {
    "platform_key": "bkaidev",
    "allowed_scope_types": ["biz"],
    "scope_type": None,
    "scope_value": None,
    "target_environment": "stage",
    "risk_policy_version": "p0-v1",
    "mcp_contract_version": "1.0.0",
}
DEFAULT_POLICIES = {
    "execution": {"mode": "draft_only"},
    "risk": {"max_level": "L1"},
    "retry": {"max": 0},
    "timeout": {"seconds": 30},
    "compensation": {"enabled": False},
    "postcondition": {"required": False},
}


def _enable_harness(space):
    SpaceConfig.objects.create(
        space_id=space.id, name="harness_enabled", value_type=SpaceConfigValueType.TEXT.value, text_value="true"
    )
    SpaceConfig.objects.create(
        space_id=space.id,
        name="harness_deployment",
        value_type=SpaceConfigValueType.JSON.value,
        json_value=VALID_DEPLOYMENT,
    )
    SpaceConfig.objects.create(
        space_id=space.id, name="superusers", value_type=SpaceConfigValueType.JSON.value, json_value=["alice"]
    )


def _request():
    return SimpleNamespace(
        app=SimpleNamespace(bk_app_code="bkflow_harness"),
        user=SimpleNamespace(username="alice", is_authenticated=True),
        data={},
        trace_id="corr-draft",
    )


def _plan_hash(space_id):
    return plan_hash(
        {
            "a2flow": A2FLOW,
            "bindings": [
                {
                    "node_id": "node_1",
                    "capability_ref": CAPABILITY_REF,
                    "resolved_version": "1.0.0",
                    "schema_hash": SCHEMA_HASH,
                    "credential_ref": None,
                    "risk_level": "L1",
                }
            ],
            "space_id": space_id,
            "scope_type": None,
            "scope_value": None,
            "target_environment": "stage",
            "authorization_scope": "space:{}".format(space_id),
            "policies": DEFAULT_POLICIES,
        }
    )


def _prepare_revision(harness_run, space, status=HarnessRunStatus.VALIDATING.value):
    digest = _plan_hash(space.id)
    harness_run.status = status
    harness_run.save(update_fields=["status"])
    revision = WorkflowPlanRevision.objects.create(
        run=harness_run,
        sequence=1,
        intent_spec={"goal": "restart"},
        canonical_a2flow=A2FLOW,
        plan_hash=digest,
    )
    CapabilityBinding.objects.create(
        revision=revision,
        node_id="node_1",
        capability_ref=CAPABILITY_REF,
        resolved_version="1.0.0",
        schema_hash=SCHEMA_HASH,
        credential_ref=None,
        risk_level="L1",
    )
    ValidationReport.objects.create(
        run=harness_run,
        revision=revision,
        checkpoint=ValidationCheckpoint.VALIDATE_WORKFLOW.value,
        validator_version="p0-v1",
        result=ValidationResult.PASSED.value,
        risk_manifest={"converter_fingerprint": "a" * 64, "pipeline_tree_hash": schema_hash(PIPELINE_TREE)},
        correlation_id="corr-draft",
    )
    return revision, digest


@pytest.fixture
def draft_space(space):
    _enable_harness(space)
    return space


def _persist_template(space_id, bind_app_code):
    snapshot = TemplateSnapshot.create_draft_snapshot(PIPELINE_TREE, "alice")
    template = Template.objects.create(
        name="restart",
        space_id=space_id,
        creator="alice",
        updated_by="alice",
        snapshot_id=snapshot.id,
        bk_app_code=bind_app_code,
    )
    snapshot.template_id = template.id
    snapshot.save(update_fields=["template_id"])
    return template


@pytest.fixture
def draft_mocks(monkeypatch):
    create = Mock(side_effect=lambda **kwargs: _persist_template(kwargs["space_id"], kwargs["bind_app_code"]))
    update = Mock(
        side_effect=lambda **kwargs: TemplateSnapshot.objects.filter(template_id=kwargs["template"].id).first()
    )
    resolve = Mock(
        return_value=ResolvedCapability(
            capability_ref=CAPABILITY_REF,
            plugin_type="component",
            code="demo_restart_service",
            source_key=None,
            resolved_version="1.0.0",
            schema_hash=SCHEMA_HASH,
            schema=SCHEMA,
            risk_level="L1",
        )
    )
    convert = Mock(
        return_value=ConversionResult(
            pipeline_tree=PIPELINE_TREE,
            converter_fingerprint="a" * 64,
            source_map={"node_1": "n1"},
        )
    )
    monkeypatch.setattr("bkflow.harness.services.draft.resolve_capability", resolve)
    monkeypatch.setattr("bkflow.harness.services.draft.A2FlowV2Converter.convert_with_metadata", convert)
    monkeypatch.setattr("bkflow.harness.services.draft.ValidatorHandler.validate", Mock())
    monkeypatch.setattr("bkflow.harness.services.draft.create_template_from_a2flow", create)
    monkeypatch.setattr("bkflow.harness.services.draft.update_template_draft_from_a2flow", update)
    return SimpleNamespace(create=create, update=update, resolve=resolve, convert=convert)


def _draft(space, payload):
    from bkflow.harness.services.draft import create_workflow_draft

    return create_workflow_draft(_request(), space.id, payload)


@pytest.mark.django_db
def test_create_draft_forces_auto_release_false_and_trusted_app(draft_space, harness_run, draft_mocks):
    """草稿创建忽略模型传入的 auto_release，绑定应用来自可信上下文。"""
    revision, digest = _prepare_revision(harness_run, draft_space)
    envelope = _draft(
        draft_space,
        {
            "run_id": str(harness_run.id),
            "revision_id": str(revision.id),
            "plan_hash": digest,
            "idempotency_key": "draft-1",
            "auto_release": True,
            "bind_app_code": "evil_app",
        },
    )
    assert envelope["ok"] is True
    assert envelope["status"] == HarnessRunStatus.DRAFT_READY.value
    assert envelope["status"] not in {HarnessRunStatus.PUBLISHED.value, HarnessRunStatus.EXECUTING.value}
    kwargs = draft_mocks.create.call_args.kwargs
    assert kwargs["auto_release"] is False
    assert kwargs["bind_app_code"] == "bkflow_harness"
    assert kwargs["a2flow"] == A2FLOW


@pytest.mark.django_db
def test_draft_rejects_stale_hash_repair_state_and_mismatched_caller(draft_space, harness_run, draft_mocks):
    """过期哈希、待修复状态或身份不匹配时拒绝创建草稿。"""
    revision, digest = _prepare_revision(harness_run, draft_space)
    stale = _draft(
        draft_space,
        {
            "run_id": str(harness_run.id),
            "revision_id": str(revision.id),
            "plan_hash": "b" * 64,
            "idempotency_key": "stale",
        },
    )
    assert stale["ok"] is False
    assert stale["errors"][0]["code"] in {"PLAN_HASH_MISMATCH", "USER_INPUT"}

    harness_run.status = HarnessRunStatus.NEEDS_REPAIR.value
    harness_run.save(update_fields=["status"])
    repair = _draft(
        draft_space,
        {
            "run_id": str(harness_run.id),
            "revision_id": str(revision.id),
            "plan_hash": digest,
            "idempotency_key": "repair",
        },
    )
    assert repair["ok"] is False
    draft_mocks.create.assert_not_called()


@pytest.mark.django_db
def test_validation_stale_when_fingerprint_changes(draft_space, harness_run, draft_mocks):
    """校验器或转换指纹变化时返回 VALIDATION_STALE。"""
    revision, digest = _prepare_revision(harness_run, draft_space)
    draft_mocks.convert.return_value = ConversionResult(
        pipeline_tree=PIPELINE_TREE,
        converter_fingerprint="c" * 64,
        source_map={"node_1": "n1"},
    )
    envelope = _draft(
        draft_space,
        {
            "run_id": str(harness_run.id),
            "revision_id": str(revision.id),
            "plan_hash": digest,
            "idempotency_key": "stale-fp",
        },
    )
    assert envelope["ok"] is False
    assert envelope["errors"][0]["code"] == "VALIDATION_STALE"
    draft_mocks.create.assert_not_called()


@pytest.mark.django_db
def test_idempotent_retry_and_later_revision_updates_same_template(draft_space, harness_run, draft_mocks):
    """相同幂等键回放同一模板；后续修订原位更新同一草稿。"""
    revision, digest = _prepare_revision(harness_run, draft_space)
    payload = {
        "run_id": str(harness_run.id),
        "revision_id": str(revision.id),
        "plan_hash": digest,
        "idempotency_key": "draft-same",
    }
    first = _draft(draft_space, payload)
    second = _draft(draft_space, payload)
    assert first["ok"] is True
    assert second["artifact_refs"] == first["artifact_refs"]
    assert draft_mocks.create.call_count == 1

    harness_run.refresh_from_db()
    harness_run.status = HarnessRunStatus.VALIDATING.value
    harness_run.save(update_fields=["status"])
    later = WorkflowPlanRevision.objects.create(
        run=harness_run,
        sequence=2,
        parent_revision=revision,
        intent_spec={"goal": "restart"},
        canonical_a2flow=A2FLOW,
        plan_hash=digest,
    )
    CapabilityBinding.objects.create(
        revision=later,
        node_id="node_1",
        capability_ref=CAPABILITY_REF,
        resolved_version="1.0.0",
        schema_hash=SCHEMA_HASH,
        credential_ref=None,
        risk_level="L1",
    )
    ValidationReport.objects.create(
        run=harness_run,
        revision=later,
        checkpoint=ValidationCheckpoint.VALIDATE_WORKFLOW.value,
        validator_version="p0-v1",
        result=ValidationResult.PASSED.value,
        risk_manifest={"converter_fingerprint": "a" * 64, "pipeline_tree_hash": schema_hash(PIPELINE_TREE)},
        correlation_id="corr-draft",
    )
    updated = _draft(
        draft_space,
        {
            "run_id": str(harness_run.id),
            "revision_id": str(later.id),
            "plan_hash": digest,
            "idempotency_key": "draft-2",
        },
    )
    assert updated["ok"] is True
    assert draft_mocks.update.call_count == 1
    assert draft_mocks.create.call_count == 1
    first_ids = [item["value"] for item in first["artifact_refs"] if item["type"] == "template_id"]
    updated_ids = [item["value"] for item in updated["artifact_refs"] if item["type"] == "template_id"]
    assert first_ids == updated_ids
    assert first_ids
