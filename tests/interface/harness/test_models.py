"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
import base64
import json
import uuid

import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from bkflow.harness.models import (
    CapabilityBinding,
    HarnessIdempotencyRecord,
    HarnessRun,
    ImmutableRevisionError,
    ValidationReport,
    WorkflowPlanRevision,
)


@pytest.fixture
def harness_run(db):
    """Create a trusted-context Harness run for model contracts."""
    return HarnessRun.objects.create(
        platform="bkfara",
        platform_app="bkfara_app",
        actor="dannydeng",
        space_id=100,
        scope="project:100",
        environment="stag",
        status="INTENT_CAPTURED",
        policy_version="2026.09",
        mcp_contract_version="p0",
        client_context={"conversation_ref": "opaque-ref"},
        artifact_references=["artifact://intent/1"],
    )


def max_domain_capability_ref():
    """Build a valid opaque reference from the largest catalog field values."""
    canonical_payload = json.dumps(
        {
            "plugin_type": "api_plugin",
            "source_key": "s" * 64,
            "code": "c" * 128,
            "version": "v" * 64,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "cap_v1_" + base64.urlsafe_b64encode(canonical_payload).decode("ascii")


@pytest.mark.django_db
class TestHarnessModels:
    def test_harness_run_persists_trusted_context_and_isolates_json_defaults(self, harness_run):
        """Persist a run's trusted identity context without sharing JSON defaults."""
        second_run = HarnessRun.objects.create(
            platform="bkfara",
            platform_app="bkfara_app",
            actor="other_actor",
            space_id=101,
            scope="project:101",
            environment="stag",
            status="INTENT_CAPTURED",
            policy_version="2026.09",
            mcp_contract_version="p0",
        )

        assert isinstance(harness_run.run_id, uuid.UUID)
        assert harness_run.client_context == {"conversation_ref": "opaque-ref"}
        assert harness_run.artifact_references == ["artifact://intent/1"]
        assert second_run.client_context == {}
        assert second_run.artifact_references == []
        assert second_run.client_context is not harness_run.client_context
        assert second_run.artifact_references is not harness_run.artifact_references

    def test_workflow_plan_revision_has_uuid_and_unique_run_sequence(self, harness_run):
        """Reject a duplicate sequence inside one run while retaining revision ancestry."""
        revision = WorkflowPlanRevision.objects.create(
            run=harness_run,
            sequence=1,
            intent_spec={"goal": "restart service"},
            canonical_a2flow={"version": "2.0"},
            plan_hash="a" * 64,
        )
        child_revision = WorkflowPlanRevision.objects.create(
            run=harness_run,
            sequence=2,
            parent_revision=revision,
            intent_spec={"goal": "restart service safely"},
            canonical_a2flow={"version": "2.0"},
            plan_hash="b" * 64,
        )

        assert isinstance(revision.pk, uuid.UUID)
        assert child_revision.parent_revision_id == revision.pk
        with pytest.raises(IntegrityError), transaction.atomic():
            WorkflowPlanRevision.objects.create(
                run=harness_run,
                sequence=1,
                intent_spec={"goal": "duplicate"},
                canonical_a2flow={"version": "2.0"},
                plan_hash="c" * 64,
            )

    def test_workflow_plan_revision_rejects_update(self, harness_run):
        """Prevent a saved revision from changing its plan hash."""
        revision = WorkflowPlanRevision.objects.create(
            run=harness_run,
            sequence=1,
            intent_spec={"goal": "restart service"},
            canonical_a2flow={"version": "2.0"},
            plan_hash="a" * 64,
        )

        revision.plan_hash = "b" * 64

        with pytest.raises(ImmutableRevisionError):
            revision.save()

    def test_workflow_plan_revision_rejects_queryset_update(self, harness_run):
        """Prevent bulk updates from bypassing immutable revision records."""
        revision = WorkflowPlanRevision.objects.create(
            run=harness_run,
            sequence=1,
            intent_spec={"goal": "restart service"},
            canonical_a2flow={"version": "2.0"},
            plan_hash="a" * 64,
        )

        with pytest.raises(ImmutableRevisionError):
            WorkflowPlanRevision.objects.filter(pk=revision.pk).update(plan_hash="b" * 64)

    def test_capability_binding_is_unique_per_revision_node_and_protects_revision(self, harness_run):
        """Pin one exact capability for each node of an immutable revision."""
        revision = WorkflowPlanRevision.objects.create(
            run=harness_run,
            sequence=1,
            intent_spec={"goal": "restart service"},
            canonical_a2flow={"version": "2.0"},
            plan_hash="a" * 64,
        )
        CapabilityBinding.objects.create(
            revision=revision,
            node_id="node-1",
            capability_ref="plugin:restart",
            resolved_version="1.2.3",
            schema_hash="d" * 64,
            credential_ref="credential://restart",
            risk="L1",
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            CapabilityBinding.objects.create(
                revision=revision,
                node_id="node-1",
                capability_ref="plugin:restart-other",
                resolved_version="1.2.4",
                schema_hash="e" * 64,
                risk="L1",
            )
        with pytest.raises(ProtectedError):
            revision.hard_delete()

    def test_capability_binding_round_trips_maximum_domain_reference(self, harness_run):
        """Store an opaque valid capability reference beyond varchar-sized storage."""
        revision = WorkflowPlanRevision.objects.create(
            run=harness_run,
            sequence=1,
            intent_spec={"goal": "restart service"},
            canonical_a2flow={"version": "2.0"},
            plan_hash="a" * 64,
        )
        capability_ref = max_domain_capability_ref()
        binding = CapabilityBinding(
            revision=revision,
            node_id="node-max-reference",
            capability_ref=capability_ref,
            resolved_version="1.2.3",
            schema_hash="d" * 64,
            risk="L1",
        )

        assert len(capability_ref) > 255
        binding.full_clean()
        binding.save()

        assert CapabilityBinding.objects.get(pk=binding.pk).capability_ref == capability_ref

    def test_workflow_plan_revision_allows_same_sequence_in_another_run(self, harness_run):
        """Scope revision sequence uniqueness to its Harness run."""
        second_run = HarnessRun.objects.create(
            platform="bkfara",
            platform_app="bkfara_app",
            actor="other_actor",
            space_id=101,
            scope="project:101",
            environment="stag",
            status="INTENT_CAPTURED",
            policy_version="2026.09",
            mcp_contract_version="p0",
        )
        WorkflowPlanRevision.objects.create(
            run=harness_run,
            sequence=1,
            intent_spec={"goal": "restart service"},
            canonical_a2flow={"version": "2.0"},
            plan_hash="a" * 64,
        )

        neighbor = WorkflowPlanRevision.objects.create(
            run=second_run,
            sequence=1,
            intent_spec={"goal": "restart another service"},
            canonical_a2flow={"version": "2.0"},
            plan_hash="b" * 64,
        )

        assert neighbor.run_id == second_run.id

    def test_capability_binding_allows_same_node_in_another_revision(self, harness_run):
        """Scope node binding uniqueness to the pinned plan revision."""
        first_revision = WorkflowPlanRevision.objects.create(
            run=harness_run,
            sequence=1,
            intent_spec={"goal": "restart service"},
            canonical_a2flow={"version": "2.0"},
            plan_hash="a" * 64,
        )
        second_revision = WorkflowPlanRevision.objects.create(
            run=harness_run,
            sequence=2,
            intent_spec={"goal": "restart another service"},
            canonical_a2flow={"version": "2.0"},
            plan_hash="b" * 64,
        )
        CapabilityBinding.objects.create(
            revision=first_revision,
            node_id="node-1",
            capability_ref="plugin:restart",
            resolved_version="1.2.3",
            schema_hash="d" * 64,
            risk="L1",
        )

        neighbor = CapabilityBinding.objects.create(
            revision=second_revision,
            node_id="node-1",
            capability_ref="plugin:restart",
            resolved_version="1.2.3",
            schema_hash="d" * 64,
            risk="L1",
        )

        assert neighbor.revision_id == second_revision.id

    def test_failed_validation_report_belongs_to_run_without_revision(self, harness_run):
        """Record a first validation failure before a valid revision exists."""
        report = ValidationReport.objects.create(
            run=harness_run,
            checkpoint="VALIDATE",
            validator_version="2026.09",
            result={"valid": False},
            risk_manifest={"risk": "L1"},
            errors=[{"code": "INVALID_NODE"}],
            warnings=[{"code": "MISSING_DESCRIPTION"}],
            correlation_id="corr-1",
        )

        assert report.revision is None
        assert report.errors == [{"code": "INVALID_NODE"}]
        assert report.warnings == [{"code": "MISSING_DESCRIPTION"}]
        with pytest.raises(ProtectedError):
            harness_run.hard_delete()

    def test_idempotency_scope_is_non_null_and_exactly_unique(self, harness_run):
        """Deduplicate writes only inside the trusted caller and run scope."""
        common_values = {
            "platform_app": "bkfara_app",
            "actor": "dannydeng",
            "space_id": 100,
            "tool_name": "validate_workflow",
            "idempotency_key": "retry-key-1",
            "request_hash": "f" * 64,
            "response_snapshot": {"ok": True},
            "resource_reference": "artifact://validation/1",
            "run": harness_run,
        }
        HarnessIdempotencyRecord.objects.create(run_scope="pre-run:project:100", **common_values)
        HarnessIdempotencyRecord.objects.create(run_scope=str(harness_run.run_id), **common_values)

        with pytest.raises(IntegrityError), transaction.atomic():
            HarnessIdempotencyRecord.objects.create(run_scope="pre-run:project:100", **common_values)
        with pytest.raises(IntegrityError), transaction.atomic():
            HarnessIdempotencyRecord.objects.create(run_scope=None, **common_values)

    def test_idempotency_key_allows_each_scope_dimension_to_vary(self, harness_run):
        """Allow one identical key in every distinct trusted idempotency namespace."""
        common_values = {
            "platform_app": "bkfara_app",
            "actor": "dannydeng",
            "space_id": 100,
            "tool_name": "validate_workflow",
            "run_scope": "pre-run",
            "idempotency_key": "retry-key-1",
            "request_hash": "f" * 64,
            "response_snapshot": {"ok": True},
            "resource_reference": "artifact://validation/1",
            "run": harness_run,
        }
        HarnessIdempotencyRecord.objects.create(**common_values)

        neighbors = (
            {"platform_app": "another_app"},
            {"actor": "another_actor"},
            {"space_id": 101},
            {"tool_name": "create_workflow_draft"},
            {"run_scope": "run:another-run"},
        )
        for override in neighbors:
            HarnessIdempotencyRecord.objects.create(**{**common_values, **override})

        assert HarnessIdempotencyRecord.objects.count() == 6
