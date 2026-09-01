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

from bkflow.harness.constants import HarnessRunStatus, ValidationResult
from bkflow.harness.contracts import ResolvedCapability
from bkflow.harness.exceptions import CapabilityNotFound, SchemaDrift
from bkflow.harness.models import (
    CapabilityBinding,
    HarnessRun,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.harness.services.canonical import schema_hash
from bkflow.harness.services.capability_ref import encode_capability_ref
from bkflow.pipeline_converter.converters.a2flow_v2.data_models import ConversionResult
from bkflow.space.configs import SpaceConfigValueType
from bkflow.space.models import SpaceConfig

ENVELOPE_KEYS = {
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
}
SCHEMA = {"inputs": [{"key": "host", "type": "string", "required": True}], "outputs": []}
SCHEMA_HASH = schema_hash(SCHEMA)
CAPABILITY_REF = encode_capability_ref(
    plugin_type="component",
    source_key=None,
    code="demo_restart_service",
    version="1.0.0",
)
VALID_DEPLOYMENT = {
    "platform_key": "bkaidev",
    "allowed_scope_types": ["biz"],
    "scope_type": None,
    "scope_value": None,
    "target_environment": "stage",
    "risk_policy_version": "p0-v1",
    "mcp_contract_version": "1.0.0",
}
A2FLOW = {
    "version": "2.0",
    "name": "restart",
    "nodes": [
        {
            "id": "node_1",
            "name": "重启服务",
            "code": "demo_restart_service",
            "data": {"host": "1.2.3.4"},
            "next": "end",
        }
    ],
}
PIPELINE_TREE = {
    "activities": {"nact": {"id": "nact", "type": "ServiceActivity"}},
    "gateways": {},
    "flows": {},
    "start_event": {"id": "nstart", "type": "EmptyStartEvent"},
    "end_event": {"id": "nend", "type": "EmptyEndEvent"},
    "constants": {},
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
        trace_id="corr-validate",
    )


def _binding(**overrides):
    item = {
        "node_id": "node_1",
        "capability_ref": CAPABILITY_REF,
        "schema_hash": SCHEMA_HASH,
        "credential_ref": None,
    }
    item.update(overrides)
    return item


def _payload(**overrides):
    item = {
        "intent": {"goal": "restart service"},
        "a2flow": A2FLOW,
        "bindings": [_binding()],
        "idempotency_key": "validate-1",
    }
    item.update(overrides)
    return item


def _resolved(**overrides):
    values = dict(
        capability_ref=CAPABILITY_REF,
        plugin_type="component",
        code="demo_restart_service",
        source_key=None,
        resolved_version="1.0.0",
        schema_hash=SCHEMA_HASH,
        schema=SCHEMA,
        risk_level="L1",
    )
    values.update(overrides)
    return ResolvedCapability(**values)


def _conversion():
    return ConversionResult(
        pipeline_tree=PIPELINE_TREE,
        converter_fingerprint="a" * 64,
        source_map={"node_1": "nact", "start": "nstart", "end": "nend"},
    )


@pytest.fixture
def harness_space(space):
    _enable_harness(space)
    return space


@pytest.fixture
def validator_mocks(monkeypatch):
    resolve = Mock(return_value=_resolved())
    convert = Mock(return_value=_conversion())
    pipeline = Mock()
    monkeypatch.setattr("bkflow.harness.services.validator.resolve_capability", resolve)
    monkeypatch.setattr(
        "bkflow.harness.services.validator.A2FlowV2Converter.convert_with_metadata",
        convert,
    )
    monkeypatch.setattr("bkflow.harness.services.validator.ValidatorHandler.validate", pipeline)
    return SimpleNamespace(resolve=resolve, convert=convert, pipeline=pipeline)


def _validate(space, payload):
    from bkflow.harness.services.validator import validate_workflow

    return validate_workflow(_request(), space.id, payload)


@pytest.mark.django_db
def test_first_validate_creates_run_revision_bindings_and_report(harness_space, validator_mocks):
    """首次校验隐式创建 run，并落不可变修订、绑定和报告。"""
    envelope = _validate(harness_space, _payload())

    assert set(envelope) == ENVELOPE_KEYS
    assert envelope["ok"] is True
    assert envelope["status"] == HarnessRunStatus.VALIDATING.value
    assert envelope["correlation_id"] == "corr-validate"
    assert envelope["revision_id"]
    assert envelope["plan_hash"]
    assert envelope["errors"] == []

    run = HarnessRun.objects.get(id=envelope["run_id"])
    revision = WorkflowPlanRevision.objects.get(id=envelope["revision_id"])
    report = ValidationReport.objects.get(run=run)
    binding = CapabilityBinding.objects.get(revision=revision)

    assert run.status == HarnessRunStatus.VALIDATING.value
    assert revision.run_id == run.id
    assert revision.sequence == 1
    assert revision.parent_revision_id is None
    assert revision.plan_hash == envelope["plan_hash"]
    assert binding.node_id == "node_1"
    assert binding.capability_ref == CAPABILITY_REF
    assert binding.resolved_version == "1.0.0"
    assert binding.schema_hash == SCHEMA_HASH
    assert report.revision_id == revision.id
    assert report.result == ValidationResult.PASSED.value
    assert report.validator_version
    refs = {item["type"]: item for item in envelope["artifact_refs"]}
    assert "validator_version" in refs
    assert "converter_fingerprint" in refs
    assert "pipeline_tree_hash" in refs
    assert "report_id" in refs


@pytest.mark.django_db
def test_failed_validation_creates_run_report_without_revision(harness_space, validator_mocks):
    """失败校验可以建 run 和报告，但不能产生有效修订。"""
    validator_mocks.resolve.side_effect = CapabilityNotFound("missing")

    envelope = _validate(harness_space, _payload())

    assert envelope["ok"] is False
    assert envelope["revision_id"] is None
    assert envelope["status"] == HarnessRunStatus.NEEDS_REPAIR.value
    assert envelope["errors"][0]["code"] == "CAPABILITY_NOT_FOUND"
    assert WorkflowPlanRevision.objects.count() == 0
    report = ValidationReport.objects.get()
    assert report.revision_id is None
    assert report.result == ValidationResult.FAILED.value


@pytest.mark.django_db
def test_binding_coverage_and_schema_input_errors(harness_space, validator_mocks):
    """绑定缺失/多余以及必填输入错误必须给出可定位路径。"""
    extra = _validate(
        harness_space, _payload(bindings=[_binding(), _binding(node_id="ghost")], idempotency_key="extra")
    )
    assert extra["ok"] is False
    assert extra["errors"][0]["code"] == "USER_INPUT"

    missing = _validate(harness_space, _payload(bindings=[], idempotency_key="missing"))
    assert missing["ok"] is False
    assert missing["errors"][0]["code"] == "USER_INPUT"

    a2flow = {
        "version": "2.0",
        "name": "restart",
        "nodes": [{"id": "node_1", "name": "重启服务", "code": "demo_restart_service", "data": {}, "next": "end"}],
    }
    schema_err = _validate(harness_space, _payload(a2flow=a2flow, idempotency_key="schema"))
    assert schema_err["ok"] is False
    assert schema_err["errors"][0]["code"] == "SCHEMA_VALIDATION_ERROR"
    assert schema_err["errors"][0]["path"] == "nodes.node_1.inputs.host"


@pytest.mark.django_db
def test_repair_after_failure_has_no_parent_and_does_not_mutate(harness_space, validator_mocks):
    """首次失败没有 accepted parent；修复成功产生新修订且不回写旧报告。"""
    validator_mocks.resolve.side_effect = SchemaDrift("drift")
    failed = _validate(harness_space, _payload(idempotency_key="fail"))
    failed_report_id = ValidationReport.objects.get().id
    validator_mocks.resolve.side_effect = None
    validator_mocks.resolve.return_value = _resolved()

    repaired = _validate(
        harness_space,
        _payload(run_id=failed["run_id"], idempotency_key="repair"),
    )

    assert repaired["ok"] is True
    revision = WorkflowPlanRevision.objects.get(id=repaired["revision_id"])
    assert revision.parent_revision_id is None
    assert WorkflowPlanRevision.objects.count() == 1
    failed_report = ValidationReport.objects.get(id=failed_report_id)
    assert failed_report.revision_id is None
    assert ValidationReport.objects.filter(result=ValidationResult.PASSED.value).count() == 1


@pytest.mark.django_db
def test_second_accepted_revision_keeps_parent_and_is_immutable(harness_space, validator_mocks):
    """后续有效修订指向前一个 accepted revision，且旧修订不可变。"""
    first = _validate(harness_space, _payload(idempotency_key="r1"))
    second = _validate(
        harness_space,
        _payload(
            run_id=first["run_id"],
            a2flow={**A2FLOW, "desc": "retry"},
            expected_plan_hash=first["plan_hash"],
            idempotency_key="r2",
        ),
    )

    first_revision = WorkflowPlanRevision.objects.get(id=first["revision_id"])
    second_revision = WorkflowPlanRevision.objects.get(id=second["revision_id"])
    assert second["ok"] is True
    assert second_revision.parent_revision_id == first_revision.id
    assert first_revision.canonical_a2flow == first_revision.canonical_a2flow
    first_revision.canonical_a2flow = {"changed": True}
    from bkflow.harness.exceptions import ImmutableRevisionError

    with pytest.raises(ImmutableRevisionError):
        first_revision.save()


@pytest.mark.django_db
def test_expected_plan_hash_mismatch_and_typed_conversion_errors(harness_space, validator_mocks):
    """客户端哈希只做乐观并发；转换和树校验错误要类型化。"""
    first = _validate(harness_space, _payload(idempotency_key="base"))
    mismatch = _validate(
        harness_space,
        _payload(run_id=first["run_id"], expected_plan_hash="b" * 64, idempotency_key="hash"),
    )
    assert mismatch["ok"] is False
    assert mismatch["errors"][0]["code"] == "PLAN_HASH_MISMATCH"
    assert WorkflowPlanRevision.objects.count() == 1

    validator_mocks.convert.side_effect = RuntimeError("bad a2flow")
    convert_err = _validate(harness_space, _payload(run_id=first["run_id"], idempotency_key="convert"))
    assert convert_err["errors"][0]["code"] == "A2FLOW_CONVERSION_ERROR"

    validator_mocks.convert.side_effect = None
    validator_mocks.convert.return_value = _conversion()
    validator_mocks.pipeline.side_effect = RuntimeError("bad tree")
    tree_err = _validate(harness_space, _payload(run_id=first["run_id"], idempotency_key="tree"))
    assert tree_err["errors"][0]["code"] == "PIPELINE_VALIDATION_ERROR"


@pytest.mark.django_db
def test_idempotent_retry_replays_same_revision(harness_space, validator_mocks):
    """相同幂等键和请求哈希回放同一修订。"""
    first = _validate(harness_space, _payload())
    second = _validate(harness_space, _payload())
    assert first["revision_id"] == second["revision_id"]
    assert WorkflowPlanRevision.objects.count() == 1
    assert validator_mocks.convert.call_count == 1
