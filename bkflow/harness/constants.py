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

from django.db import models
from django.utils.translation import ugettext_lazy as _


class HarnessRunStatus(models.TextChoices):
    """Harness 生成任务状态，不复用 Engine 执行状态。"""

    INTENT_CAPTURED = "INTENT_CAPTURED", _("已捕获意图")
    PLANNING = "PLANNING", _("规划中")
    VALIDATING = "VALIDATING", _("校验中")
    NEEDS_REPAIR = "NEEDS_REPAIR", _("待修复")
    DRAFT_READY = "DRAFT_READY", _("草稿就绪")
    DEBUGGING = "DEBUGGING", _("调试中")
    RELEASE_READY = "RELEASE_READY", _("待发布")
    APPROVAL_PENDING = "APPROVAL_PENDING", _("审批中")
    PUBLISHING = "PUBLISHING", _("发布中")
    PUBLISHED = "PUBLISHED", _("已发布")
    EXECUTING = "EXECUTING", _("执行中")
    SUCCEEDED = "SUCCEEDED", _("执行成功")
    FAILED = "FAILED", _("执行失败")
    CANCELLED = "CANCELLED", _("已取消")
    EVIDENCE_FINALIZED = "EVIDENCE_FINALIZED", _("证据已固化")


class ValidationResult(models.TextChoices):
    """校验报告结果。"""

    PASSED = "PASSED", _("通过")
    FAILED = "FAILED", _("失败")


class ValidationCheckpoint(models.TextChoices):
    """校验发生的阶段。"""

    VALIDATE_WORKFLOW = "validate_workflow", _("流程校验")
    CREATE_WORKFLOW_DRAFT = "create_workflow_draft", _("草稿创建")


class IdempotencyStatus(models.TextChoices):
    """幂等记录生命周期。"""

    IN_FLIGHT = "IN_FLIGHT", _("进行中")
    COMPLETED = "COMPLETED", _("已完成")
    FAILED = "FAILED", _("失败")
