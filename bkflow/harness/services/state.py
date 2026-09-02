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
from dataclasses import dataclass
from typing import Optional, Union
from uuid import UUID

from django.db import transaction
from django.utils.translation import ugettext_lazy as _

from bkflow.harness.constants import HarnessRunStatus
from bkflow.harness.exceptions import InvalidStateTransition
from bkflow.harness.models import HarnessRun

StatusLike = Union[str, HarnessRunStatus]

P0_TRANSITIONS = {
    (HarnessRunStatus.INTENT_CAPTURED.value, HarnessRunStatus.PLANNING.value): None,
    (HarnessRunStatus.PLANNING.value, HarnessRunStatus.VALIDATING.value): None,
    (HarnessRunStatus.VALIDATING.value, HarnessRunStatus.NEEDS_REPAIR.value): None,
    (HarnessRunStatus.NEEDS_REPAIR.value, HarnessRunStatus.VALIDATING.value): None,
    (HarnessRunStatus.VALIDATING.value, HarnessRunStatus.DRAFT_READY.value): "create_workflow_draft",
    (HarnessRunStatus.DRAFT_READY.value, HarnessRunStatus.VALIDATING.value): None,
}


@dataclass(frozen=True)
class StateTransitionResult:
    """一次原子状态转移的结果。"""

    run_id: UUID
    from_status: str
    to_status: str
    trigger: Optional[str]


def _status_value(status: StatusLike) -> str:
    return status.value if isinstance(status, HarnessRunStatus) else status


def transition_run(
    run: HarnessRun,
    target_status: StatusLike,
    *,
    trigger: Optional[str] = None,
) -> StateTransitionResult:
    """
    按 P0 状态机转移 HarnessRun。

    :param run: 当前运行
    :param target_status: 目标状态
    :param trigger: 触发动作，VALIDATING -> DRAFT_READY 必须是 create_workflow_draft
    :return: 结构化转移结果
    :raises InvalidStateTransition: 非法或越阶段转移
    """
    target = _status_value(target_status)
    with transaction.atomic():
        locked = HarnessRun.objects.select_for_update().get(pk=run.pk)
        required_trigger = P0_TRANSITIONS.get((locked.status, target), _MISSING)
        if required_trigger is _MISSING:
            raise InvalidStateTransition(
                _("非法状态转移: {from_status} -> {to_status}").format(
                    from_status=locked.status,
                    to_status=target,
                )
            )
        if required_trigger is not None and trigger != required_trigger:
            raise InvalidStateTransition(
                _("状态转移 {from_status} -> {to_status} 需要 trigger={required}").format(
                    from_status=locked.status,
                    to_status=target,
                    required=required_trigger,
                )
            )
        from_status = locked.status
        locked.status = target
        locked.save(update_fields=["status", "update_at"])
        run.status = target
        return StateTransitionResult(
            run_id=locked.id,
            from_status=from_status,
            to_status=target,
            trigger=trigger,
        )


class _MissingType:
    """哨兵，用于区分“未配置转移”和“转移不要求 trigger”。"""


_MISSING = _MissingType()
