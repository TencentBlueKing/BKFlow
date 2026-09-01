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
import pytest

from bkflow.harness.constants import HarnessRunStatus
from bkflow.harness.exceptions import InvalidStateTransition
from bkflow.harness.models import HarnessRun
from bkflow.harness.services.state import transition_run


def test_p0_happy_path_persists_and_returns_structured_result(harness_run):
    """P0 合法转移原子落库，并返回结构化结果。"""
    planning = transition_run(harness_run, HarnessRunStatus.PLANNING)
    validating = transition_run(harness_run, HarnessRunStatus.VALIDATING)
    draft = transition_run(
        harness_run,
        HarnessRunStatus.DRAFT_READY,
        trigger="create_workflow_draft",
    )

    harness_run.refresh_from_db()
    assert harness_run.status == HarnessRunStatus.DRAFT_READY.value
    assert planning.from_status == HarnessRunStatus.INTENT_CAPTURED.value
    assert planning.to_status == HarnessRunStatus.PLANNING.value
    assert validating.to_status == HarnessRunStatus.VALIDATING.value
    assert draft.trigger == "create_workflow_draft"
    assert draft.run_id == harness_run.id


def test_validate_repair_loop(harness_run):
    """校验失败可回到 NEEDS_REPAIR，修复后再进入 VALIDATING。"""
    transition_run(harness_run, HarnessRunStatus.PLANNING)
    transition_run(harness_run, HarnessRunStatus.VALIDATING)
    repair = transition_run(harness_run, HarnessRunStatus.NEEDS_REPAIR)
    again = transition_run(harness_run, HarnessRunStatus.VALIDATING)

    harness_run.refresh_from_db()
    assert repair.to_status == HarnessRunStatus.NEEDS_REPAIR.value
    assert again.to_status == HarnessRunStatus.VALIDATING.value
    assert harness_run.status == HarnessRunStatus.VALIDATING.value


def test_skip_validation_is_rejected(harness_run):
    """禁止跳过校验直接进入草稿。"""
    with pytest.raises(InvalidStateTransition):
        transition_run(harness_run, HarnessRunStatus.DRAFT_READY, trigger="create_workflow_draft")


def test_draft_ready_requires_create_workflow_draft_trigger(harness_run):
    """只有 create_workflow_draft 才能完成 VALIDATING -> DRAFT_READY。"""
    transition_run(harness_run, HarnessRunStatus.PLANNING)
    transition_run(harness_run, HarnessRunStatus.VALIDATING)
    with pytest.raises(InvalidStateTransition):
        transition_run(harness_run, HarnessRunStatus.DRAFT_READY, trigger="validate_workflow")


@pytest.mark.parametrize(
    "target",
    [
        HarnessRunStatus.DEBUGGING,
        HarnessRunStatus.PUBLISHED,
        HarnessRunStatus.EXECUTING,
        HarnessRunStatus.EVIDENCE_FINALIZED,
    ],
)
def test_p1_to_p4_transitions_are_rejected(harness_run, target):
    """P0 拒绝所有后续阶段转移。"""
    transition_run(harness_run, HarnessRunStatus.PLANNING)
    transition_run(harness_run, HarnessRunStatus.VALIDATING)
    transition_run(harness_run, HarnessRunStatus.DRAFT_READY, trigger="create_workflow_draft")
    with pytest.raises(InvalidStateTransition):
        transition_run(harness_run, target)


def test_mutation_after_draft_ready_is_rejected(harness_run):
    """进入 DRAFT_READY 后不能再改回规划或校验。"""
    transition_run(harness_run, HarnessRunStatus.PLANNING)
    transition_run(harness_run, HarnessRunStatus.VALIDATING)
    transition_run(harness_run, HarnessRunStatus.DRAFT_READY, trigger="create_workflow_draft")
    with pytest.raises(InvalidStateTransition):
        transition_run(harness_run, HarnessRunStatus.PLANNING)
    harness_run.refresh_from_db()
    assert harness_run.status == HarnessRunStatus.DRAFT_READY.value
    assert HarnessRun.objects.get(id=harness_run.id).status == HarnessRunStatus.DRAFT_READY.value
