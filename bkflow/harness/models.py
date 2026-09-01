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

import uuid

from django.db import models
from django.utils.translation import ugettext_lazy as _

from bkflow.harness.constants import (
    HarnessRunStatus,
    IdempotencyStatus,
    ValidationCheckpoint,
    ValidationResult,
)
from bkflow.harness.exceptions import ImmutableRevisionError
from bkflow.utils.models import CommonModel


class WorkflowPlanRevisionQuerySet(models.QuerySet):
    """禁止通过 QuerySet.update 修改不可变修订。"""

    def update(self, **kwargs):
        raise ImmutableRevisionError("WorkflowPlanRevision rows cannot be updated")


class WorkflowPlanRevisionManager(models.Manager):
    """只暴露不可变 QuerySet 的修订管理器。"""

    def get_queryset(self):
        return WorkflowPlanRevisionQuerySet(self.model, using=self._db)


class HarnessRun(CommonModel):
    """一次独立的 AI 流程生成任务。"""

    id = models.UUIDField(_("运行ID"), primary_key=True, default=uuid.uuid4, editable=False)
    platform_key = models.CharField(_("平台标识"), max_length=64)
    platform_app = models.CharField(_("平台应用"), max_length=32)
    actor = models.CharField(_("操作者"), max_length=32)
    space_id = models.IntegerField(_("空间ID"), db_index=True)
    scope_type = models.CharField(_("Scope 类型"), max_length=64, null=True, blank=True)
    scope_value = models.CharField(_("Scope 值"), max_length=128, null=True, blank=True)
    target_environment = models.CharField(_("目标环境"), max_length=32)
    status = models.CharField(_("状态"), max_length=32, choices=HarnessRunStatus.choices)
    policy_version = models.CharField(_("策略版本"), max_length=64)
    mcp_contract_version = models.CharField(_("MCP 契约版本"), max_length=32)
    client_context = models.JSONField(_("客户端上下文"), default=dict)
    artifact_refs = models.JSONField(_("工件引用"), default=dict)

    class Meta:
        verbose_name = _("Harness 运行")
        verbose_name_plural = _("Harness 运行")
        ordering = ["-create_at"]

    def __str__(self):
        return str(self.id)


class WorkflowPlanRevision(CommonModel):
    """不可变的流程计划修订。"""

    id = models.UUIDField(_("修订ID"), primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        HarnessRun,
        on_delete=models.PROTECT,
        related_name="revisions",
        verbose_name=_("所属运行"),
    )
    sequence = models.PositiveIntegerField(_("修订序号"))
    parent_revision = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="child_revisions",
        verbose_name=_("父修订"),
    )
    intent_spec = models.JSONField(_("意图快照"), default=dict)
    canonical_a2flow = models.JSONField(_("规范化 a2flow"), default=dict)
    plan_hash = models.CharField(_("计划哈希"), max_length=64)

    objects = WorkflowPlanRevisionManager()

    class Meta:
        verbose_name = _("流程计划修订")
        verbose_name_plural = _("流程计划修订")
        unique_together = (("run", "sequence"),)
        ordering = ["run", "sequence"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutableRevisionError("WorkflowPlanRevision rows are immutable")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.run_id}:{self.sequence}"


class CapabilityBinding(CommonModel):
    """修订上每个节点的精确能力绑定。"""

    revision = models.ForeignKey(
        WorkflowPlanRevision,
        on_delete=models.PROTECT,
        related_name="bindings",
        verbose_name=_("所属修订"),
    )
    node_id = models.CharField(_("节点ID"), max_length=64)
    capability_ref = models.CharField(_("能力引用"), max_length=255)
    resolved_version = models.CharField(_("精确版本"), max_length=64)
    schema_hash = models.CharField(_("Schema 哈希"), max_length=64)
    credential_ref = models.CharField(_("凭证引用"), max_length=128, null=True, blank=True)
    risk_level = models.CharField(_("风险等级"), max_length=16)

    class Meta:
        verbose_name = _("能力绑定")
        verbose_name_plural = _("能力绑定")
        unique_together = (("revision", "node_id"),)
        ordering = ["id"]

    def __str__(self):
        return f"{self.revision_id}:{self.node_id}"


class ValidationReport(CommonModel):
    """校验报告。首次失败可以只挂在 run 上。"""

    run = models.ForeignKey(
        HarnessRun,
        on_delete=models.PROTECT,
        related_name="validation_reports",
        verbose_name=_("所属运行"),
    )
    revision = models.ForeignKey(
        WorkflowPlanRevision,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="validation_reports",
        verbose_name=_("所属修订"),
    )
    checkpoint = models.CharField(_("校验检查点"), max_length=64, choices=ValidationCheckpoint.choices)
    validator_version = models.CharField(_("校验器版本"), max_length=64)
    result = models.CharField(_("校验结果"), max_length=16, choices=ValidationResult.choices)
    risk_manifest = models.JSONField(_("风险清单"), default=dict)
    errors = models.JSONField(_("错误"), default=list)
    warnings = models.JSONField(_("警告"), default=list)
    correlation_id = models.CharField(_("关联ID"), max_length=64)

    class Meta:
        verbose_name = _("校验报告")
        verbose_name_plural = _("校验报告")
        ordering = ["-create_at"]

    def __str__(self):
        return f"{self.run_id}:{self.checkpoint}:{self.result}"


class HarnessIdempotencyRecord(CommonModel):
    """写操作幂等记录。"""

    platform_app = models.CharField(_("平台应用"), max_length=32)
    actor = models.CharField(_("操作者"), max_length=32)
    space_id = models.IntegerField(_("空间ID"))
    tool_name = models.CharField(_("Tool 名称"), max_length=64)
    run_scope = models.CharField(_("运行作用域"), max_length=80)
    run = models.ForeignKey(
        HarnessRun,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="idempotency_records",
        verbose_name=_("所属运行"),
    )
    idempotency_key = models.CharField(_("幂等键"), max_length=128)
    request_hash = models.CharField(_("请求哈希"), max_length=64)
    response_snapshot = models.JSONField(_("响应快照"), default=dict)
    resource_ref = models.JSONField(_("资源引用"), default=dict)
    status = models.CharField(
        _("幂等状态"),
        max_length=16,
        choices=IdempotencyStatus.choices,
        default=IdempotencyStatus.IN_FLIGHT.value,
    )

    class Meta:
        verbose_name = _("Harness 幂等记录")
        verbose_name_plural = _("Harness 幂等记录")
        unique_together = (("platform_app", "actor", "space_id", "tool_name", "run_scope", "idempotency_key"),)
        ordering = ["-create_at"]

    def __str__(self):
        return f"{self.tool_name}:{self.run_scope}:{self.idempotency_key}"
