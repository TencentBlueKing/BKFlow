"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file
except in compliance with the License. You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import uuid

import pytest
from django.db import IntegrityError, transaction

from bkflow.harness.constants import HarnessRunStatus, ValidationResult
from bkflow.harness.models import (
    CapabilityBinding,
    HarnessIdempotencyRecord,
    HarnessRun,
    ImmutableRevisionError,
    ValidationReport,
    WorkflowPlanRevision,
)
from bkflow.space.models import Space


@pytest.fixture
def space(db):
    return Space.objects.create(name="harness-p0-space", app_code="bkflow_harness", platform_url="http://example.com")


@pytest.fixture
def harness_run(space):
    return HarnessRun.objects.create(
        platform_key="bkaidev",
        platform_app="bkflow_harness",
        actor="alice",
        space_id=space.id,
        scope_type=None,
        scope_value=None,
        target_environment="stage",
        status=HarnessRunStatus.INTENT_CAPTURED.value,
        policy_version="p0-v1",
        mcp_contract_version="1.0.0",
    )


def _create_revision(harness_run, sequence=1, plan_hash=None, parent=None):
    return WorkflowPlanRevision.objects.create(
        run=harness_run,
        sequence=sequence,
        parent_revision=parent,
        intent_spec={"goal": "restart service"},
        canonical_a2flow={"version": "2.0"},
        plan_hash=plan_hash or ("a" * 64),
    )


@pytest.mark.django_db
class TestHarnessRun:
    def test_persist_trusted_context_and_json_defaults(self, space):
        """HarnessRun 保存可信上下文，JSON 默认值为可调用空对象。"""
        run = HarnessRun.objects.create(
            platform_key="bkaidev",
            platform_app="bkflow_harness",
            actor="alice",
            space_id=space.id,
            scope_type="biz",
            scope_value="100",
            target_environment="stage",
            status=HarnessRunStatus.INTENT_CAPTURED.value,
            policy_version="p0-v1",
            mcp_contract_version="1.0.0",
        )

        run.refresh_from_db()
        assert isinstance(run.id, uuid.UUID)
        assert run.platform_key == "bkaidev"
        assert run.platform_app == "bkflow_harness"
        assert run.actor == "alice"
        assert run.space_id == space.id
        assert run.scope_type == "biz"
        assert run.scope_value == "100"
        assert run.target_environment == "stage"
        assert run.status == HarnessRunStatus.INTENT_CAPTURED.value
        assert run.policy_version == "p0-v1"
        assert run.mcp_contract_version == "1.0.0"
        assert run.client_context == {}
        assert run.artifact_refs == {}
        assert HarnessRunStatus.INTENT_CAPTURED.value != "CREATED"
        assert HarnessRunStatus.DRAFT_READY.value != "FINISHED"


@pytest.mark.django_db
class TestWorkflowPlanRevision:
    def test_uuid_pk_monotonic_sequence_and_unique_run_sequence(self, harness_run):
        """Revision 使用 UUID 主键，同一 run 下 sequence 唯一。"""
        first = _create_revision(harness_run, sequence=1)
        second = _create_revision(harness_run, sequence=2, plan_hash="b" * 64, parent=first)

        assert isinstance(first.id, uuid.UUID)
        assert first.run_id == harness_run.id
        assert first.sequence == 1
        assert first.parent_revision_id is None
        assert first.intent_spec == {"goal": "restart service"}
        assert first.canonical_a2flow == {"version": "2.0"}
        assert first.plan_hash == "a" * 64
        assert second.parent_revision_id == first.id

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                _create_revision(harness_run, sequence=1, plan_hash="c" * 64)

    def test_workflow_plan_revision_rejects_update(self, harness_run):
        """已落库的 Revision 禁止原地修改。"""
        revision = _create_revision(harness_run)
        revision.plan_hash = "b" * 64
        with pytest.raises(ImmutableRevisionError):
            revision.save()

    def test_workflow_plan_revision_rejects_queryset_update(self, harness_run):
        """Revision 不暴露 QuerySet.update 写路径。"""
        _create_revision(harness_run)
        with pytest.raises(ImmutableRevisionError):
            WorkflowPlanRevision.objects.filter(run=harness_run).update(plan_hash="b" * 64)


@pytest.mark.django_db
class TestCapabilityBinding:
    def test_unique_revision_node_and_exact_binding_fields(self, harness_run):
        """每个节点在同一 Revision 上只能有一条精确能力绑定。"""
        revision = _create_revision(harness_run)
        binding = CapabilityBinding.objects.create(
            revision=revision,
            node_id="node_1",
            capability_ref="cap_v1_demo",
            resolved_version="1.0.0",
            schema_hash="c" * 64,
            credential_ref=None,
            risk_level="L1",
        )

        assert binding.node_id == "node_1"
        assert binding.capability_ref == "cap_v1_demo"
        assert binding.resolved_version == "1.0.0"
        assert binding.schema_hash == "c" * 64
        assert binding.credential_ref is None
        assert binding.risk_level == "L1"

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                CapabilityBinding.objects.create(
                    revision=revision,
                    node_id="node_1",
                    capability_ref="cap_v1_other",
                    resolved_version="1.0.1",
                    schema_hash="d" * 64,
                    risk_level="L1",
                )


@pytest.mark.django_db
class TestValidationReport:
    def test_failed_first_validation_attaches_to_run_without_revision(self, harness_run):
        """首次失败校验只挂在 run 上，revision 为空。"""
        report = ValidationReport.objects.create(
            run=harness_run,
            revision=None,
            checkpoint="validate_workflow",
            validator_version="p0-v1",
            result=ValidationResult.FAILED.value,
            risk_manifest={"level": "L1"},
            errors=[{"code": "SCHEMA_VALIDATION_ERROR"}],
            warnings=[],
            correlation_id="corr-1",
        )

        report.refresh_from_db()
        assert report.run_id == harness_run.id
        assert report.revision_id is None
        assert report.checkpoint == "validate_workflow"
        assert report.validator_version == "p0-v1"
        assert report.result == ValidationResult.FAILED.value
        assert report.risk_manifest == {"level": "L1"}
        assert report.errors == [{"code": "SCHEMA_VALIDATION_ERROR"}]
        assert report.warnings == []
        assert report.correlation_id == "corr-1"

    def test_accepted_report_can_bind_revision(self, harness_run):
        """通过校验的报告可以关联已接受的 Revision。"""
        revision = _create_revision(harness_run)
        report = ValidationReport.objects.create(
            run=harness_run,
            revision=revision,
            checkpoint="validate_workflow",
            validator_version="p0-v1",
            result=ValidationResult.PASSED.value,
            correlation_id="corr-2",
        )
        assert report.revision_id == revision.id
        assert report.errors == []
        assert report.warnings == []
        assert report.risk_manifest == {}


@pytest.mark.django_db
class TestHarnessIdempotencyRecord:
    def test_unique_scope_and_optional_run_reference(self, harness_run):
        """幂等记录以调用方、空间、Tool、run_scope 和 key 唯一，run 可空。"""
        first = HarnessIdempotencyRecord.objects.create(
            platform_app="bkflow_harness",
            actor="alice",
            space_id=harness_run.space_id,
            tool_name="validate_workflow",
            run_scope="pre-run",
            run=None,
            idempotency_key="key-1",
            request_hash="e" * 64,
            response_snapshot={"ok": True},
            resource_ref={"run_id": str(harness_run.id)},
        )
        completed = HarnessIdempotencyRecord.objects.create(
            platform_app="bkflow_harness",
            actor="alice",
            space_id=harness_run.space_id,
            tool_name="create_workflow_draft",
            run_scope=f"run:{harness_run.id}",
            run=harness_run,
            idempotency_key="key-2",
            request_hash="f" * 64,
            response_snapshot={"ok": True},
            resource_ref={"template_id": 1},
        )

        assert first.run_id is None
        assert first.run_scope == "pre-run"
        assert completed.run_id == harness_run.id
        assert completed.resource_ref == {"template_id": 1}

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                HarnessIdempotencyRecord.objects.create(
                    platform_app="bkflow_harness",
                    actor="alice",
                    space_id=harness_run.space_id,
                    tool_name="validate_workflow",
                    run_scope="pre-run",
                    idempotency_key="key-1",
                    request_hash="e" * 64,
                )
