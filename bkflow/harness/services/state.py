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
from dataclasses import dataclass

from django.db import transaction

from bkflow.harness.exceptions import InvalidStateTransition
from bkflow.harness.models import HarnessRun, ValidationReport, WorkflowPlanRevision

_HARNESS_TRANSITIONS = {
    "INTENT_CAPTURED": {"PLANNING"},
    "PLANNING": {"VALIDATING"},
    "VALIDATING": {"NEEDS_REPAIR"},
    "NEEDS_REPAIR": {"VALIDATING"},
    "DRAFT_READY": {"VALIDATING", "DEBUGGING"},
    "DEBUGGING": {"DRAFT_READY", "RELEASE_READY"},
    "RELEASE_READY": {"APPROVAL_PENDING", "PUBLISHING", "DRAFT_READY"},
    "APPROVAL_PENDING": {"PUBLISHING", "DRAFT_READY"},
    "PUBLISHING": {"PUBLISHED"},
    "PUBLISHED": {"EXECUTING"},
    "EXECUTING": {"SUCCEEDED", "FAILED", "CANCELLED"},
    "SUCCEEDED": {"EVIDENCE_FINALIZED"},
    "FAILED": {"EVIDENCE_FINALIZED"},
    "CANCELLED": {"EVIDENCE_FINALIZED"},
}


@dataclass(frozen=True)
class TransitionResult:
    """Describe one persisted Harness state operation."""

    run_id: str
    previous_status: str
    status: str
    changed: bool

    def as_dict(self):
        """Return a JSON-ready representation for service callers."""
        return {
            "run_id": self.run_id,
            "previous_status": self.previous_status,
            "status": self.status,
            "changed": self.changed,
        }


def _locked_run(run):
    """Lock and reload a run before inspecting or persisting lifecycle state."""
    return HarnessRun.objects.select_for_update().get(pk=run.pk)


def _result(run, previous_status, changed):
    """Build one structured transition result from a locked run."""
    return TransitionResult(run_id=str(run.run_id), previous_status=previous_status, status=run.status, changed=changed)


def transition_run(run, target_status):
    """Persist a non-draft P0 state transition under a row lock.

    ``DRAFT_READY`` is intentionally only available via
    :func:`complete_draft_creation` after its domain write succeeds.
    """
    with transaction.atomic():
        locked_run = _locked_run(run)
        previous_status = locked_run.status
        if target_status not in _HARNESS_TRANSITIONS.get(previous_status, set()):
            raise InvalidStateTransition(
                "{} -> {} is not an approved Harness lifecycle transition".format(previous_status, target_status)
            )
        locked_run.status = target_status
        locked_run.save(update_fields=["status", "update_at"])
        return _result(locked_run, previous_status=previous_status, changed=True)


def record_validation_outcome(run, valid):
    """Record a validation decision without turning validation into draft success."""
    with transaction.atomic():
        locked_run = _locked_run(run)
        previous_status = locked_run.status
        if previous_status != "VALIDATING":
            raise InvalidStateTransition("validation outcome requires VALIDATING, got {}".format(previous_status))
        if not valid:
            locked_run.status = "NEEDS_REPAIR"
            locked_run.save(update_fields=["status", "update_at"])
            return _result(locked_run, previous_status, changed=True)
        return _result(locked_run, previous_status, changed=False)


def _locked_accepted_validation(run, revision, validation_report):
    """Lock and validate the exact current accepted checkpoint for a draft.

    :raises InvalidStateTransition: when the supplied report cannot authorize
        the exact revision of the locked run.
    """
    if revision is None or validation_report is None:
        raise InvalidStateTransition("draft completion requires an accepted validation report and revision")
    if not revision.pk or not validation_report.pk:
        raise InvalidStateTransition("draft completion requires persisted revision and validation report")
    try:
        locked_revision = WorkflowPlanRevision.objects.select_for_update().get(pk=revision.pk)
        locked_report = ValidationReport.objects.select_for_update().get(pk=validation_report.pk)
    except (WorkflowPlanRevision.DoesNotExist, ValidationReport.DoesNotExist):
        raise InvalidStateTransition("draft completion requires persisted revision and validation report")
    if locked_revision.run_id != run.id:
        raise InvalidStateTransition("draft revision does not belong to the run")
    if locked_report.run_id != run.id or locked_report.revision_id != locked_revision.id:
        raise InvalidStateTransition("validation report does not belong to the run revision")
    if locked_report.checkpoint != "VALIDATE":
        raise InvalidStateTransition("draft completion requires a VALIDATE checkpoint")
    if locked_report.result.get("valid") is not True or locked_report.errors:
        raise InvalidStateTransition("draft completion requires a successful validation report")
    latest_run_report = (
        ValidationReport.objects.select_for_update()
        .filter(run_id=run.id, checkpoint="VALIDATE")
        .order_by("-id")
        .first()
    )
    latest_revision_report = (
        ValidationReport.objects.select_for_update()
        .filter(run_id=run.id, revision_id=locked_revision.id, checkpoint="VALIDATE")
        .order_by("-id")
        .first()
    )
    if latest_run_report is None or latest_run_report.id != locked_report.id:
        raise InvalidStateTransition("validation report is not the current run checkpoint")
    if latest_revision_report is None or latest_revision_report.id != locked_report.id:
        raise InvalidStateTransition("validation report is not the current revision checkpoint")
    return locked_revision, locked_report


def complete_draft_creation(run, revision, validation_report):
    """Mark a run draft-ready only with its exact accepted validation checkpoint."""
    with transaction.atomic():
        locked_run = _locked_run(run)
        previous_status = locked_run.status
        if previous_status != "VALIDATING":
            raise InvalidStateTransition("draft completion requires VALIDATING, got {}".format(previous_status))
        _locked_accepted_validation(locked_run, revision, validation_report)
        locked_run.status = "DRAFT_READY"
        locked_run.save(update_fields=["status", "update_at"])
        return _result(locked_run, previous_status, changed=True)
