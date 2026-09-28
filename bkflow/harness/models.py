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

import hashlib
import json
import re
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, router, transaction
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from bkflow.harness.constants import (
    MAX_SCOPE_KEY_LENGTH,
    DebugMode,
    DebugSessionStatus,
    FeedbackAttributionCategory,
    GenerationFeedbackType,
    HarnessAction,
    HarnessRunStatus,
    IdempotencyRecordStatus,
    ImprovementCandidateStatus,
    ImprovementCandidateType,
    KnowledgeBindingStatus,
    KnowledgeRetrievalMode,
    KnowledgeTier,
    KnowledgeTrustLevel,
    RiskLevel,
    ValidationCheckpoint,
)
from bkflow.harness.safety import (
    is_bounded_non_secret_json,
    is_safe_idempotency_key,
    safe_opaque_identifier,
)
from bkflow.harness.services.canonical import canonical_json_bytes
from bkflow.harness.services.evidence import (
    EVIDENCE_REDACTION_VERSION,
    is_safe_evidence_ref,
    validate_evidence_artifact_refs,
    validate_redacted_evidence_payload,
)
from bkflow.harness.services.knowledge.security import (
    is_bounded_non_secret_text,
    is_safe_opaque_uri,
)
from bkflow.utils.models import CommonModel


class ImmutableRevisionError(RuntimeError):
    """Raised when a persisted workflow plan revision is modified."""


OPAQUE_REF_PATTERN = re.compile(r"^[a-z][a-z0-9+.-]*://\S+$")
HEX_64_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
CREDENTIAL_REF_PATTERN = re.compile(r"^credential://id/([1-9][0-9]{0,18})$")
KNOWLEDGE_CLASSIFICATION_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")


def _is_bounded_string(value, max_length, allow_none=False):
    """Return whether a value is a non-empty bounded string or an allowed null."""
    if value is None:
        return allow_none
    return isinstance(value, str) and 0 < len(value) <= max_length


def _is_opaque_ref(value, max_length=255):
    """Return whether a value is a bounded opaque URI-style reference."""
    return _is_bounded_string(value, max_length) and bool(OPAQUE_REF_PATTERN.fullmatch(value))


class WorkflowPlanRevisionQuerySet(models.QuerySet):
    """Disallow bulk mutation of immutable revision records."""

    def update(self, **kwargs):
        """Reject direct database updates that bypass ``save`` immutability."""
        raise ImmutableRevisionError("Workflow plan revisions are immutable")


class HarnessRun(CommonModel):
    """A trusted-context AI workflow generation run."""

    run_id = models.UUIDField(_("运行 ID"), default=uuid.uuid4, unique=True, editable=False)
    platform = models.CharField(_("平台标识"), max_length=64)
    platform_app = models.CharField(_("平台应用"), max_length=128)
    actor = models.CharField(_("操作人"), max_length=128)
    space_id = models.IntegerField(_("空间 ID"), db_index=True)
    scope = models.CharField(_("授权范围"), max_length=MAX_SCOPE_KEY_LENGTH)
    environment = models.CharField(_("目标环境"), max_length=64)
    status = models.CharField(_("状态"), max_length=32, choices=HarnessRunStatus.choices)
    policy_version = models.CharField(_("策略版本"), max_length=64)
    mcp_contract_version = models.CharField(_("MCP 契约版本"), max_length=64)
    client_context = models.JSONField(_("客户端上下文"), default=dict)
    artifact_references = models.JSONField(_("工件引用"), default=list)

    class Meta:
        verbose_name = _("Harness 运行")
        verbose_name_plural = verbose_name
        ordering = ["-id"]


class WorkflowPlanRevision(CommonModel):
    """An immutable, versioned workflow plan belonging to a Harness run."""

    id = models.UUIDField(_("修订 ID"), primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(HarnessRun, verbose_name=_("运行"), on_delete=models.PROTECT, related_name="revisions")
    sequence = models.PositiveIntegerField(_("修订序号"))
    parent_revision = models.ForeignKey(
        "self",
        verbose_name=_("父修订"),
        on_delete=models.PROTECT,
        related_name="child_revisions",
        null=True,
        blank=True,
    )
    intent_spec = models.JSONField(_("意图规格"), default=dict)
    canonical_a2flow = models.JSONField(_("规范化 a2flow"), default=dict)
    plan_hash = models.CharField(_("计划哈希"), max_length=64)

    objects = models.Manager.from_queryset(WorkflowPlanRevisionQuerySet)()

    class Meta:
        verbose_name = _("工作流计划修订")
        verbose_name_plural = verbose_name
        ordering = ["run_id", "sequence"]
        constraints = [models.UniqueConstraint(fields=["run", "sequence"], name="uniq_harness_run_revision_sequence")]

    def save(self, *args, **kwargs):
        """Allow only the initial insert so persisted plans remain immutable."""
        if not self._state.adding:
            raise ImmutableRevisionError("Workflow plan revisions are immutable")
        return super().save(*args, **kwargs)


class CapabilityBinding(CommonModel):
    """An exact capability and schema pin for one plan node."""

    revision = models.ForeignKey(
        WorkflowPlanRevision,
        verbose_name=_("计划修订"),
        on_delete=models.PROTECT,
        related_name="capability_bindings",
    )
    node_id = models.CharField(_("节点 ID"), max_length=128)
    capability_ref = models.TextField(_("能力引用"))
    resolved_version = models.CharField(_("解析版本"), max_length=128)
    schema_hash = models.CharField(_("Schema 哈希"), max_length=64)
    conversion_fingerprint = models.CharField(_("转换事实哈希"), max_length=64, null=True, blank=True)
    credential_ref = models.CharField(_("凭证引用"), max_length=255, null=True, blank=True)
    risk = models.CharField(_("风险等级"), max_length=2, choices=RiskLevel.choices)

    class Meta:
        verbose_name = _("能力绑定")
        verbose_name_plural = verbose_name
        constraints = [models.UniqueConstraint(fields=["revision", "node_id"], name="uniq_harness_revision_node")]


class ValidationReport(CommonModel):
    """A validation result attached to a run and optionally a valid revision."""

    run = models.ForeignKey(
        HarnessRun, verbose_name=_("运行"), on_delete=models.PROTECT, related_name="validation_reports"
    )
    revision = models.ForeignKey(
        WorkflowPlanRevision,
        verbose_name=_("计划修订"),
        on_delete=models.PROTECT,
        related_name="validation_reports",
        null=True,
        blank=True,
    )
    checkpoint = models.CharField(_("检查点"), max_length=32, choices=ValidationCheckpoint.choices)
    validator_version = models.CharField(_("校验器版本"), max_length=64)
    result = models.JSONField(_("校验结果"), default=dict)
    risk_manifest = models.JSONField(_("风险清单"), default=dict)
    errors = models.JSONField(_("错误"), default=list)
    warnings = models.JSONField(_("告警"), default=list)
    correlation_id = models.CharField(_("关联 ID"), max_length=128)

    class Meta:
        verbose_name = _("校验报告")
        verbose_name_plural = verbose_name
        ordering = ["-id"]


class HarnessIdempotencyRecord(CommonModel):
    """A scoped snapshot for safely replaying a Harness write request."""

    platform_app = models.CharField(_("平台应用"), max_length=128)
    actor = models.CharField(_("操作人"), max_length=128)
    space_id = models.IntegerField(_("空间 ID"))
    tool_name = models.CharField(_("Tool 名称"), max_length=128)
    run_scope = models.CharField(_("运行作用域"), max_length=255)
    run = models.ForeignKey(
        HarnessRun,
        verbose_name=_("运行"),
        on_delete=models.PROTECT,
        related_name="idempotency_records",
        null=True,
        blank=True,
    )
    idempotency_key = models.CharField(_("幂等键"), max_length=255)
    request_hash = models.CharField(_("请求哈希"), max_length=64)
    status = models.CharField(
        _("幂等状态"), max_length=16, choices=IdempotencyRecordStatus.choices, default=IdempotencyRecordStatus.IN_FLIGHT
    )
    response_snapshot = models.JSONField(_("响应快照"), default=dict)
    resource_reference = models.CharField(_("资源引用"), max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = _("Harness 幂等记录")
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(
                fields=["platform_app", "actor", "space_id", "tool_name", "run_scope", "idempotency_key"],
                name="uniq_harness_idempotency_scope",
            )
        ]


class KnowledgeSourceBindingQuerySet(models.QuerySet):
    """Validate safe inserts and reject unsafe set-based binding mutation."""

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        """Validate and derive every binding before a batch insert."""
        objs = list(objs)
        for obj in objs:
            obj.full_clean(validate_unique=False)
        return super().bulk_create(objs, batch_size=batch_size, ignore_conflicts=ignore_conflicts)

    def bulk_update(self, objs, fields, batch_size=None):
        """Reject batch updates because derived identities depend on each stored row."""
        raise ValidationError("Knowledge source bindings do not support bulk_update")

    def update(self, **kwargs):
        """Reject set-based updates that bypass validation and identity derivation."""
        raise ValidationError("Knowledge source bindings do not support QuerySet.update")

    def delete(self):
        """Retain governed history; only the synchronizer may transition rows to retired."""
        raise ValidationError("Knowledge source bindings must retire instead of delete")


class KnowledgeSourceBinding(CommonModel):
    """A governed, tier-scoped binding to one opaque knowledge source."""

    PROVIDER_CONFIG_SCHEMA = {
        "collection": 128,
        "endpoint_ref": 255,
        "index": 128,
        "namespace": 128,
        "region": 64,
        "retrieval_profile": 128,
    }
    IDENTITY_FIELDS = (
        "provider",
        "source_ref",
        "platform_key",
        "space_id",
        "scope_type",
        "scope_value",
        "environment",
    )

    provider = models.CharField(_("知识提供方"), max_length=64)
    source_ref = models.TextField(_("知识源引用"))
    tier = models.CharField(_("知识层级"), max_length=16, choices=KnowledgeTier.choices)
    platform_key = models.CharField(_("平台标识"), max_length=64, null=True, blank=True)
    space_id = models.IntegerField(_("空间 ID"), null=True, blank=True)
    scope_type = models.CharField(_("范围类型"), max_length=64, null=True, blank=True)
    scope_value = models.CharField(_("范围值"), max_length=MAX_SCOPE_KEY_LENGTH, null=True, blank=True)
    trust_level = models.CharField(_("可信等级"), max_length=16, choices=KnowledgeTrustLevel.choices)
    priority = models.IntegerField(_("优先级"), default=0)
    environment = models.CharField(_("目标环境"), max_length=64)
    allowed_apps = models.JSONField(_("允许应用"), default=list, blank=True)
    allowed_actors = models.JSONField(_("允许操作人"), default=list, blank=True)
    data_classification = models.CharField(_("数据分类"), max_length=64)
    snapshot_version = models.CharField(_("快照版本"), max_length=128)
    expires_at = models.DateTimeField(_("过期时间"), null=True, blank=True)
    last_verified_at = models.DateTimeField(_("最近验证时间"), null=True, blank=True)
    owner = models.CharField(_("负责人"), max_length=128)
    reviewer = models.CharField(_("审核人"), max_length=128, null=True, blank=True)
    status = models.CharField(
        _("生命周期状态"),
        max_length=16,
        choices=KnowledgeBindingStatus.choices,
        default=KnowledgeBindingStatus.DISABLED,
    )
    retrieval_mode = models.CharField(_("检索模式"), max_length=16, choices=KnowledgeRetrievalMode.choices)
    max_top_k = models.PositiveSmallIntegerField(
        _("最大返回数"), default=10, validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    redaction_policy = models.JSONField(_("脱敏策略"), default=dict, blank=True)
    credential_ref = models.CharField(_("凭证引用"), max_length=255, null=True, blank=True)
    provider_config = models.JSONField(_("提供方非秘密配置"), default=dict, blank=True)
    active_identity = models.CharField(_("生效绑定身份"), max_length=64, unique=True, null=True, blank=True, editable=False)

    objects = models.Manager.from_queryset(KnowledgeSourceBindingQuerySet)()

    class Meta:
        verbose_name = _("知识源绑定")
        verbose_name_plural = verbose_name
        ordering = ["-priority", "id"]
        base_manager_name = "objects"
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(
                        tier__in=[KnowledgeTier.GLOBAL, KnowledgeTier.PUBLIC],
                        platform_key__isnull=True,
                        space_id__isnull=True,
                        scope_type__isnull=True,
                        scope_value__isnull=True,
                    )
                    | models.Q(
                        tier=KnowledgeTier.PLATFORM,
                        platform_key__isnull=False,
                        space_id__isnull=True,
                        scope_type__isnull=True,
                        scope_value__isnull=True,
                    )
                    & ~models.Q(platform_key="")
                    | models.Q(
                        tier=KnowledgeTier.SPACE,
                        platform_key__isnull=False,
                        space_id__isnull=False,
                        scope_type__isnull=True,
                        scope_value__isnull=True,
                    )
                    & ~models.Q(platform_key="")
                    | models.Q(
                        tier=KnowledgeTier.SCOPE,
                        platform_key__isnull=False,
                        space_id__isnull=False,
                        scope_type__isnull=False,
                        scope_value__isnull=False,
                    )
                    & ~models.Q(platform_key="")
                    & ~models.Q(scope_type="")
                    & ~models.Q(scope_value="")
                ),
                name="harness_knowledge_binding_tier_dimensions",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(status=KnowledgeBindingStatus.ACTIVE, active_identity__isnull=False)
                    | ~models.Q(status=KnowledgeBindingStatus.ACTIVE) & models.Q(active_identity__isnull=True)
                ),
                name="harness_knowledge_binding_active_identity",
            ),
            models.CheckConstraint(
                check=models.Q(max_top_k__gte=1, max_top_k__lte=20),
                name="harness_knowledge_binding_max_top_k",
            ),
        ]

    def _canonicalize_identity_fields(self):
        """Normalize identity inputs with their Django database field types."""
        for field_name in ("platform_key", "scope_type", "scope_value"):
            if getattr(self, field_name) == "":
                setattr(self, field_name, None)
        for field_name in self.IDENTITY_FIELDS:
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, self._meta.get_field(field_name).to_python(value))

    def _metadata_validation_errors(self):
        """Build errors for binding metadata outside the positive persistence schema."""
        errors = {}
        scalar_limits = {
            "provider": 64,
            "platform_key": 64,
            "scope_type": 64,
            "scope_value": MAX_SCOPE_KEY_LENGTH,
            "environment": 64,
            "data_classification": 64,
        }
        for field_name, max_bytes in scalar_limits.items():
            value = getattr(self, field_name)
            if value is not None and not is_bounded_non_secret_text(value, max_bytes):
                errors[field_name] = _("知识绑定元数据必须是有界非秘密 UTF-8 字符串")
        if (
            isinstance(self.data_classification, str)
            and KNOWLEDGE_CLASSIFICATION_PATTERN.fullmatch(self.data_classification) is None
        ):
            errors["data_classification"] = _("数据分类格式不合法")
        if not isinstance(self.provider_config, dict) or set(self.provider_config) - set(self.PROVIDER_CONFIG_SCHEMA):
            errors["provider_config"] = _("提供方配置包含未授权字段")
        else:
            for key, max_length in self.PROVIDER_CONFIG_SCHEMA.items():
                if key not in self.provider_config:
                    continue
                value = self.provider_config[key]
                if not is_bounded_non_secret_text(value, max_length):
                    errors["provider_config"] = _("提供方配置值必须是有界非空字符串")
                    break
                if key == "endpoint_ref" and not is_safe_opaque_uri(value, "endpoint", max_length):
                    errors["provider_config"] = _("endpoint_ref 必须是 endpoint 命名空间的安全有界引用")
                    break

        for field_name in ("allowed_apps", "allowed_actors"):
            value = getattr(self, field_name)
            if (
                not isinstance(value, list)
                or len(value) > 100
                or not all(is_bounded_non_secret_text(item, 128) for item in value)
            ):
                errors[field_name] = _("允许列表最多包含 100 个有界非秘密 UTF-8 字符串")

        if not isinstance(self.redaction_policy, dict) or set(self.redaction_policy) - {"policy_ref"}:
            errors["redaction_policy"] = _("脱敏策略仅允许 policy_ref")
        elif self.redaction_policy and not is_safe_opaque_uri(
            self.redaction_policy.get("policy_ref"), "redaction", 255
        ):
            errors["redaction_policy"] = _("policy_ref 必须是 redaction 命名空间的安全有界引用")

        if not is_safe_opaque_uri(self.source_ref, "knowledge", 2048):
            errors["source_ref"] = _("知识源引用必须是 knowledge 命名空间的安全有界引用")
        if not is_bounded_non_secret_text(self.snapshot_version, 128):
            errors["snapshot_version"] = _("快照版本必须是有界非秘密 UTF-8 字符串")
        if self.credential_ref is not None and (
            not isinstance(self.credential_ref, str) or CREDENTIAL_REF_PATTERN.fullmatch(self.credential_ref) is None
        ):
            errors["credential_ref"] = _("凭证引用必须使用 canonical credential ID 引用")
        return errors

    def _dimension_validation_errors(self):
        """Validate the exact trusted identity dimensions required by the selected tier."""
        dimensions = {
            "platform_key": self.platform_key,
            "space_id": self.space_id,
            "scope_type": self.scope_type,
            "scope_value": self.scope_value,
        }
        required_by_tier = {
            KnowledgeTier.GLOBAL: set(),
            KnowledgeTier.PUBLIC: set(),
            KnowledgeTier.PLATFORM: {"platform_key"},
            KnowledgeTier.SPACE: {"platform_key", "space_id"},
            KnowledgeTier.SCOPE: {"platform_key", "space_id", "scope_type", "scope_value"},
        }
        required = required_by_tier.get(self.tier)
        errors = {}
        if required is None:
            errors["tier"] = _("未知知识层级")
            return errors
        for field_name, value in dimensions.items():
            if field_name in required and value is None:
                errors[field_name] = _("该知识层级必须提供此维度")
            elif field_name not in required and value is not None:
                errors[field_name] = _("该知识层级不允许提供此维度")
        return errors

    def _governance_validation_errors(self):
        """Enforce local dual-review facts without claiming external governance evidence."""
        errors = {}
        if not is_bounded_non_secret_text(self.owner, 128):
            errors["owner"] = _("负责人必须是有界非秘密字符串")
        if not is_bounded_non_secret_text(self.reviewer, 128):
            errors["reviewer"] = _("审核人必须是有界非秘密字符串")
        elif self.owner == self.reviewer:
            errors["reviewer"] = _("负责人和审核人必须不同")
        if (
            self.trust_level in {KnowledgeTrustLevel.VERIFIED, KnowledgeTrustLevel.TRUSTED}
            and self.last_verified_at is None
        ):
            errors["last_verified_at"] = _("已验证知识必须记录最近验证时间")
        if self.trust_level not in KnowledgeTrustLevel.values:
            errors["trust_level"] = _("未知知识可信等级")
        if self.status not in KnowledgeBindingStatus.values:
            errors["status"] = _("未知知识绑定状态")
        if self.retrieval_mode not in KnowledgeRetrievalMode.values:
            errors["retrieval_mode"] = _("未知知识检索模式")
        return errors

    def _derive_active_identity(self):
        """Hash the complete active identity so MySQL can enforce it with a normal unique index."""
        if self.status != KnowledgeBindingStatus.ACTIVE:
            return None
        identity = [
            self.provider,
            self.source_ref,
            self.platform_key,
            self.space_id,
            self.scope_type,
            self.scope_value,
            self.environment,
        ]
        payload = json.dumps(identity, ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def clean(self):
        """Validate exact tier dimensions and keep provider configuration non-secret."""
        super().clean()
        self._canonicalize_identity_fields()
        errors = self._dimension_validation_errors()
        errors.update(self._metadata_validation_errors())
        errors.update(self._governance_validation_errors())
        if errors:
            raise ValidationError(errors)
        self.active_identity = self._derive_active_identity()

    def save(self, *args, **kwargs):
        """Refresh the derived active identity before every normal database write."""
        self._canonicalize_identity_fields()
        errors = self._dimension_validation_errors()
        errors.update(self._metadata_validation_errors())
        errors.update(self._governance_validation_errors())
        if errors:
            raise ValidationError(errors)
        self.active_identity = self._derive_active_identity()
        update_fields = kwargs.get("update_fields")
        if update_fields is None:
            return super().save(*args, **kwargs)

        if self._state.adding:
            raise ValidationError({"update_fields": _("new binding instances do not support partial saves")})

        selected_fields = set(update_fields)
        if not selected_fields:
            return super().save(*args, **kwargs)

        using = kwargs.get("using") or router.db_for_write(self.__class__, instance=self)
        kwargs["using"] = using
        identity_state_fields = set(self.IDENTITY_FIELDS) | {"status"}
        with transaction.atomic(using=using):
            persisted = (
                self.__class__._base_manager.using(using)
                .select_for_update()
                .values(*identity_state_fields)
                .get(pk=self.pk)
            )
            changed_identity_fields = {
                field_name for field_name in identity_state_fields if getattr(self, field_name) != persisted[field_name]
            }
            omitted_identity_fields = changed_identity_fields - selected_fields
            if omitted_identity_fields:
                raise ValidationError(
                    {
                        "update_fields": _("partial save omitted changed identity fields: %(fields)s")
                        % {"fields": ", ".join(sorted(omitted_identity_fields))}
                    }
                )
            if selected_fields & identity_state_fields or "active_identity" in selected_fields:
                selected_fields.add("active_identity")
            kwargs["update_fields"] = selected_fields
            return super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """Block soft deletion so governed bindings remain auditable as retired rows."""
        raise ValidationError("Knowledge source bindings must retire instead of delete")

    def hard_delete(self):
        """Block physical deletion so governed bindings remain auditable as retired rows."""
        raise ValidationError("Knowledge source bindings must retire instead of delete")


class KnowledgeRetrievalAuditQuerySet(models.QuerySet):
    """Validate safe batch inserts and keep audit evidence append-only in bulk APIs."""

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        """Validate each audit before a batch insert."""
        objs = list(objs)
        for obj in objs:
            obj.full_clean(validate_unique=False)
        return super().bulk_create(objs, batch_size=batch_size, ignore_conflicts=ignore_conflicts)

    def bulk_update(self, objs, fields, batch_size=None):
        """Reject batch updates to append-only retrieval evidence."""
        raise ValidationError("Knowledge retrieval audits do not support bulk_update")

    def update(self, **kwargs):
        """Reject set-based updates to append-only retrieval evidence."""
        raise ValidationError("Knowledge retrieval audits do not support QuerySet.update")

    def delete(self):
        """Reject set-based deletion of append-only retrieval evidence."""
        raise ValidationError("Knowledge retrieval audits are append-only")


class KnowledgeRetrievalAudit(CommonModel):
    """A bounded evidence record for one knowledge retrieval attempt."""

    TRUSTED_CONTEXT_KEYS = {
        "actor",
        "correlation_id",
        "mcp_contract_version",
        "platform_app",
        "platform_key",
        "policy_version",
        "scope_type",
        "scope_value",
        "space_id",
        "target_environment",
    }
    TRUSTED_CONTEXT_STRING_LIMITS = {
        "actor": 128,
        "correlation_id": 128,
        "mcp_contract_version": 64,
        "platform_app": 128,
        "platform_key": 64,
        "policy_version": 64,
        "scope_type": 64,
        "scope_value": MAX_SCOPE_KEY_LENGTH,
        "target_environment": 64,
    }
    PROVIDER_CALL_FIELDS = {
        "call_ref",
        "duration_ms",
        "error_code",
        "hit_count",
        "outcome",
        "provider",
        "snapshot_ref",
    }

    run = models.ForeignKey(
        HarnessRun,
        verbose_name=_("Harness 运行"),
        on_delete=models.PROTECT,
        related_name="knowledge_retrieval_audits",
        null=True,
        blank=True,
    )
    trusted_context_snapshot = models.JSONField(_("可信上下文快照"), default=dict)
    query_fingerprint = models.CharField(_("查询指纹"), max_length=64)
    redacted_query = models.TextField(_("脱敏查询"))
    eligible_binding_ids = models.JSONField(_("候选绑定 ID"), default=list, blank=True)
    provider_call_summaries = models.JSONField(_("提供方调用摘要"), default=list, blank=True)
    hit_refs = models.JSONField(_("命中引用"), default=list, blank=True)
    snapshot_refs = models.JSONField(_("快照引用"), default=list, blank=True)
    correlation_id = models.CharField(_("关联 ID"), max_length=128, db_index=True)
    duration_ms = models.PositiveIntegerField(_("耗时（毫秒）"))
    outcome = models.CharField(_("检索结果"), max_length=32)

    objects = models.Manager.from_queryset(KnowledgeRetrievalAuditQuerySet)()

    class Meta:
        verbose_name = _("知识检索审计")
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        base_manager_name = "objects"

    def clean(self):
        """Reject untrusted context fields, secrets, and unrestricted document payloads."""
        super().clean()
        errors = self._evidence_validation_errors()
        if errors:
            raise ValidationError(errors)

    def _evidence_validation_errors(self):
        """Build field errors for evidence outside the bounded audit schema."""
        errors = {}
        if not isinstance(self.trusted_context_snapshot, dict):
            errors["trusted_context_snapshot"] = _("可信上下文快照必须是对象")
        else:
            unknown_keys = set(self.trusted_context_snapshot) - self.TRUSTED_CONTEXT_KEYS
            invalid_context_value = bool(unknown_keys)
            if not unknown_keys:
                for key, value in self.trusted_context_snapshot.items():
                    if key == "space_id":
                        invalid_context_value = isinstance(value, bool) or not isinstance(value, int)
                    else:
                        invalid_context_value = not _is_bounded_string(
                            value,
                            self.TRUSTED_CONTEXT_STRING_LIMITS[key],
                            allow_none=key in {"scope_type", "scope_value"},
                        )
                    if invalid_context_value:
                        break
            if unknown_keys or invalid_context_value:
                errors["trusted_context_snapshot"] = _("可信上下文快照包含未授权字段")

        if (
            not isinstance(self.eligible_binding_ids, list)
            or len(self.eligible_binding_ids) > 100
            or not all(
                isinstance(item, int) and not isinstance(item, bool) and item > 0 for item in self.eligible_binding_ids
            )
        ):
            errors["eligible_binding_ids"] = _("候选绑定 ID 必须是最多 100 个正整数")

        if not self._valid_provider_call_summaries(self.provider_call_summaries):
            errors["provider_call_summaries"] = _("调用摘要不符合有界字段结构")
        for field_name in ("hit_refs", "snapshot_refs"):
            value = getattr(self, field_name)
            if not isinstance(value, list) or len(value) > 100 or not all(_is_opaque_ref(item) for item in value):
                errors[field_name] = _("审计引用必须是最多 100 个有界引用")
        if not isinstance(self.query_fingerprint, str) or not HEX_64_PATTERN.fullmatch(self.query_fingerprint):
            errors["query_fingerprint"] = _("查询指纹必须是 64 位十六进制字符串")
        if not _is_bounded_string(self.redacted_query, 2000):
            errors["redacted_query"] = _("脱敏查询必须是最多 2000 字符的非空字符串")
        return errors

    def save(self, *args, **kwargs):
        """Allow one validated insert and reject all later instance mutation."""
        if not self._state.adding:
            raise ValidationError("Knowledge retrieval audits are append-only")
        errors = self._evidence_validation_errors()
        if errors:
            raise ValidationError(errors)
        return super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """Reject soft deletion of append-only retrieval evidence."""
        raise ValidationError("Knowledge retrieval audits are append-only")

    def hard_delete(self):
        """Reject physical deletion of append-only retrieval evidence."""
        raise ValidationError("Knowledge retrieval audits are append-only")

    @classmethod
    def _valid_provider_call_summaries(cls, summaries):
        """Validate provider calls against an explicit scalar-only summary schema."""
        if not isinstance(summaries, list) or len(summaries) > 50:
            return False
        for summary in summaries:
            if not isinstance(summary, dict) or set(summary) - cls.PROVIDER_CALL_FIELDS:
                return False
            if not _is_bounded_string(summary.get("provider"), 64):
                return False
            if not _is_bounded_string(summary.get("outcome"), 32):
                return False
            duration_ms = summary.get("duration_ms")
            if isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or not 0 <= duration_ms <= 3_600_000:
                return False
            hit_count = summary.get("hit_count")
            if hit_count is not None and (
                isinstance(hit_count, bool) or not isinstance(hit_count, int) or not 0 <= hit_count <= 10_000
            ):
                return False
            if "error_code" in summary and not _is_bounded_string(summary["error_code"], 64, allow_none=True):
                return False
            for ref_field in ("call_ref", "snapshot_ref"):
                if ref_field in summary and not _is_opaque_ref(summary[ref_field]):
                    return False
        return True


class DebugSessionQuerySet(models.QuerySet):
    """Validate session inserts and close every set-based lifecycle bypass."""

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        """Derive active keys and validate every session before a batch insert."""
        if ignore_conflicts:
            raise ValidationError("Debug sessions do not support ignore_conflicts")
        objs = list(objs)
        for obj in objs:
            obj.full_clean(validate_unique=False)
        return super().bulk_create(objs, batch_size=batch_size, ignore_conflicts=False)

    def bulk_update(self, objs, fields, batch_size=None):
        """Require lifecycle services to lock and save individual sessions."""
        raise ValidationError("Debug sessions do not support bulk_update")

    def update(self, **kwargs):
        """Reject set-based updates that skip identity and derived-key validation."""
        raise ValidationError("Debug sessions do not support QuerySet.update")

    def delete(self):
        """Retain every governed debug session for later evidence correlation."""
        raise ValidationError("Debug sessions cannot be deleted")


class DebugSession(CommonModel):
    """A revision-bound handle over the existing template-scoped debug context."""

    TERMINAL_STATUSES = frozenset(
        {
            DebugSessionStatus.COMPLETED,
            DebugSessionStatus.FAILED,
            DebugSessionStatus.TERMINATED,
            DebugSessionStatus.EXPIRED,
        }
    )
    ACTIVE_STATUSES = frozenset({DebugSessionStatus.ACTIVE, DebugSessionStatus.RUNNING})
    TRUSTED_CONTEXT_KEYS = frozenset(
        {
            "platform_key",
            "platform_app",
            "actor",
            "space_id",
            "scope_type",
            "scope_value",
            "target_environment",
            "policy_version",
            "mcp_contract_version",
            "correlation_id",
        }
    )
    TRUSTED_CONTEXT_STRING_LIMITS = {
        "platform_key": 64,
        "platform_app": 128,
        "actor": 128,
        "scope_type": 64,
        "scope_value": MAX_SCOPE_KEY_LENGTH,
        "target_environment": 64,
        "policy_version": 64,
        "mcp_contract_version": 64,
        "correlation_id": 128,
    }
    IMMUTABLE_FIELDS = frozenset(
        {
            "run_id",
            "revision_id",
            "template_id",
            "debug_context_id",
            "mode",
            "plan_hash",
            "tree_fingerprint",
            "actor",
            "policy_version",
            "trusted_context_snapshot",
        }
    )

    id = models.UUIDField(_("调试会话 ID"), primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        HarnessRun,
        verbose_name=_("Harness 运行"),
        on_delete=models.PROTECT,
        related_name="debug_sessions",
    )
    revision = models.ForeignKey(
        WorkflowPlanRevision,
        verbose_name=_("计划修订"),
        on_delete=models.PROTECT,
        related_name="debug_sessions",
    )
    template_id = models.PositiveBigIntegerField(_("模板 ID"), db_index=True)
    debug_context_id = models.PositiveBigIntegerField(_("调试上下文 ID"))
    mode = models.CharField(_("调试模式"), max_length=16, choices=DebugMode.choices)
    status = models.CharField(_("会话状态"), max_length=16, choices=DebugSessionStatus.choices)
    plan_hash = models.CharField(_("计划哈希"), max_length=64)
    tree_fingerprint = models.JSONField(_("流程树指纹"), default=dict)
    active_template_key = models.CharField(
        _("活跃模板键"), max_length=128, unique=True, null=True, blank=True, editable=False
    )
    current_task_id = models.PositiveBigIntegerField(_("当前任务 ID"), null=True, blank=True)
    actor = models.CharField(_("操作人"), max_length=128)
    policy_version = models.CharField(_("策略版本"), max_length=64)
    trusted_context_snapshot = models.JSONField(_("可信上下文快照"), default=dict)
    expires_at = models.DateTimeField(_("过期时间"), db_index=True)
    last_heartbeat_at = models.DateTimeField(_("最近心跳时间"), null=True, blank=True)
    terminal_reason = models.CharField(_("终态原因"), max_length=512, null=True, blank=True)

    objects = models.Manager.from_queryset(DebugSessionQuerySet)()

    class Meta:
        verbose_name = _("Harness 调试会话")
        verbose_name_plural = verbose_name
        ordering = ["-create_at"]
        base_manager_name = "objects"
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(
                        status__in=[DebugSessionStatus.ACTIVE, DebugSessionStatus.RUNNING],
                        active_template_key__isnull=False,
                    )
                    | models.Q(
                        status__in=[
                            DebugSessionStatus.COMPLETED,
                            DebugSessionStatus.FAILED,
                            DebugSessionStatus.TERMINATED,
                            DebugSessionStatus.EXPIRED,
                        ],
                        active_template_key__isnull=True,
                    )
                ),
                name="harness_debug_session_active_template_key",
            )
        ]

    @property
    def is_terminal(self):
        """Return whether this session has reached a terminal state."""
        return self.status in self.TERMINAL_STATUSES

    @property
    def is_active(self):
        """Return whether this session still owns the template debug lock."""
        return self.status in self.ACTIVE_STATUSES

    def _derive_active_template_key(self):
        """Build the nullable key used by MySQL to enforce one active template session."""
        return "template:{}".format(self.template_id) if self.status in self.ACTIVE_STATUSES else None

    def _trusted_context_errors(self, run):
        """Compare the complete trusted snapshot with the current owning Harness run."""
        value = self.trusted_context_snapshot
        if not isinstance(value, dict) or set(value) != self.TRUSTED_CONTEXT_KEYS:
            return {"trusted_context_snapshot": _("可信上下文快照字段不完整")}

        invalid = False
        for key, limit in self.TRUSTED_CONTEXT_STRING_LIMITS.items():
            item = value.get(key)
            if key in {"scope_type", "scope_value"} and item is None:
                continue
            if not is_bounded_non_secret_text(item, limit):
                invalid = True
                break
        space_id = value.get("space_id")
        if isinstance(space_id, bool) or not isinstance(space_id, int) or space_id <= 0:
            invalid = True
        scope_type = value.get("scope_type")
        scope_value = value.get("scope_value")
        if (scope_type is None) != (scope_value is None):
            invalid = True
        if invalid:
            return {"trusted_context_snapshot": _("可信上下文快照包含无效或秘密字段")}

        snapshot_scope = (
            ""
            if scope_type is None
            else json.dumps([scope_type, scope_value], ensure_ascii=False, separators=(",", ":"))
        )
        expected = {
            "platform_key": run.platform,
            "platform_app": run.platform_app,
            "actor": run.actor,
            "space_id": run.space_id,
            "target_environment": run.environment,
            "policy_version": run.policy_version,
            "mcp_contract_version": run.mcp_contract_version,
        }
        if any(value[key] != expected_value for key, expected_value in expected.items()) or run.scope != snapshot_scope:
            return {"trusted_context_snapshot": _("可信上下文快照与 Harness 运行身份不一致")}
        return {}

    def _validation_errors(self):
        """Build invariant errors shared by full_clean, create, and instance save."""
        errors = {}
        run = self.run if self.run_id else None
        revision = self.revision if self.revision_id else None
        if run is None:
            errors["run"] = _("调试会话必须绑定 Harness 运行")
        else:
            errors.update(self._trusted_context_errors(run))
        if revision is None or run is None or revision.run_id != self.run_id:
            errors["revision"] = _("调试会话的运行与修订不一致")
        if run is not None and self.actor != run.actor:
            errors["actor"] = _("调试会话操作人与运行不一致")
        if run is not None and self.policy_version != run.policy_version:
            errors["policy_version"] = _("调试会话策略与运行不一致")
        if revision is not None and self.plan_hash != revision.plan_hash:
            errors["plan_hash"] = _("调试会话计划哈希与修订不一致")
        if isinstance(self.template_id, bool) or not isinstance(self.template_id, int) or self.template_id <= 0:
            errors["template_id"] = _("模板 ID 必须为正整数")
        if (
            isinstance(self.debug_context_id, bool)
            or not isinstance(self.debug_context_id, int)
            or self.debug_context_id <= 0
        ):
            errors["debug_context_id"] = _("调试上下文 ID 必须为正整数")
        if self.current_task_id is not None and (
            isinstance(self.current_task_id, bool)
            or not isinstance(self.current_task_id, int)
            or self.current_task_id <= 0
        ):
            errors["current_task_id"] = _("当前任务 ID 必须为正整数")
        if not isinstance(self.plan_hash, str) or re.fullmatch(r"[0-9a-f]{64}", self.plan_hash) is None:
            errors["plan_hash"] = _("计划哈希必须是小写 SHA-256")
        if not self._valid_tree_fingerprint(self.tree_fingerprint):
            errors["tree_fingerprint"] = _("流程树指纹必须是 DebugService 的完整有界非秘密结构")
        if self.mode not in DebugMode.values:
            errors["mode"] = _("未知调试模式")
        if self.status not in DebugSessionStatus.values:
            errors["status"] = _("未知调试会话状态")
        if not is_bounded_non_secret_text(self.actor, 128):
            errors["actor"] = _("操作人必须是有界非秘密字符串")
        if not is_bounded_non_secret_text(self.policy_version, 64):
            errors["policy_version"] = _("策略版本必须是有界非秘密字符串")

        now = timezone.now()
        if self.expires_at is None or timezone.is_naive(self.expires_at):
            errors["expires_at"] = _("过期时间必须是带时区时间")
        elif self.status in self.ACTIVE_STATUSES and self.expires_at <= now:
            errors["expires_at"] = _("活跃调试会话尚未过期")
        elif self.status == DebugSessionStatus.EXPIRED and self.expires_at > now:
            errors["expires_at"] = _("EXPIRED 会话必须已经过期")
        if self.last_heartbeat_at is not None:
            if timezone.is_naive(self.last_heartbeat_at):
                errors["last_heartbeat_at"] = _("心跳时间必须是带时区时间")
            elif self.expires_at is not None and self.last_heartbeat_at > self.expires_at:
                errors["last_heartbeat_at"] = _("心跳时间不能晚于会话过期时间")
        if self.terminal_reason == "":
            self.terminal_reason = None
        if self.terminal_reason is not None and not is_bounded_non_secret_text(self.terminal_reason, 512):
            errors["terminal_reason"] = _("终态原因必须是有界非秘密字符串")
        if self.status in self.ACTIVE_STATUSES and self.terminal_reason is not None:
            errors["terminal_reason"] = _("活跃会话不能携带终态原因")
        return errors

    @staticmethod
    def _valid_tree_fingerprint(value):
        """Validate the exact JSON structure returned by ``compute_tree_fingerprint``."""
        if not isinstance(value, dict) or set(value) != {"nodes", "flows", "gateways", "constants"}:
            return False
        nodes = value.get("nodes")
        if not isinstance(nodes, dict) or len(nodes) > 1000:
            return False
        if not all(
            is_bounded_non_secret_text(node_id, 128)
            and isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{32}", digest) is not None
            for node_id, digest in nodes.items()
        ):
            return False
        if not all(
            isinstance(value.get(key), str) and re.fullmatch(r"[0-9a-f]{32}", value[key]) is not None
            for key in ("flows", "gateways", "constants")
        ):
            return False
        try:
            return len(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")) <= 64 * 1024
        except (TypeError, ValueError, UnicodeError):
            return False

    def clean(self):
        """Validate trusted identities, hashes, time semantics, and the derived active key."""
        super().clean()
        if not self._state.adding:
            using = router.db_for_read(self.__class__, instance=self)
            persisted = (
                self.__class__._base_manager.using(using).values(*self.IMMUTABLE_FIELDS, "status").get(pk=self.pk)
            )
            self._reject_identity_mutation(persisted)
            self._validate_transition(persisted, using=using)
        errors = self._validation_errors()
        if errors:
            raise ValidationError(errors)
        self.active_template_key = self._derive_active_template_key()

    def _persisted_state(self, using):
        """Lock and return the fields required for safe lifecycle validation."""
        fields = self.IMMUTABLE_FIELDS | {
            "status",
            "current_task_id",
            "expires_at",
            "last_heartbeat_at",
            "terminal_reason",
        }
        return self.__class__._base_manager.using(using).select_for_update().values(*fields).get(pk=self.pk)

    def _reject_identity_mutation(self, persisted):
        """Keep every authority-bearing session field immutable after insertion."""
        changed = [field for field in self.IMMUTABLE_FIELDS if getattr(self, field) != persisted[field]]
        if changed:
            raise ValidationError({field: _("调试会话身份字段不可修改") for field in changed})

    def _validate_transition(self, persisted, using=None):
        """Allow active operation cycling and one-way transitions into terminal states."""
        old_status = persisted["status"]
        if old_status in self.TERMINAL_STATUSES and self.status != old_status:
            raise ValidationError({"status": _("终态调试会话不可重新激活或改写终态")})
        if old_status in self.ACTIVE_STATUSES and self.status not in self.ACTIVE_STATUSES | self.TERMINAL_STATUSES:
            raise ValidationError({"status": _("调试会话状态迁移不合法")})
        if (
            old_status in self.ACTIVE_STATUSES
            and self.status in self.TERMINAL_STATUSES
            and TokenLease._base_manager.using(using)
            .filter(session_id=self.pk, status=TokenLease.Status.ACTIVE)
            .exists()
        ):
            raise ValidationError({"status": _("调试会话终态化前必须撤销或过期全部活跃 Token 租约")})

    def save(self, *args, **kwargs):
        """Validate every normal write and keep partial status saves consistent with the unique key."""
        using = kwargs.get("using") or router.db_for_write(self.__class__, instance=self)
        if self._state.adding:
            errors = self._validation_errors()
            if errors:
                raise ValidationError(errors)
            self.active_template_key = self._derive_active_template_key()
            if kwargs.get("update_fields") is not None:
                raise ValidationError({"update_fields": _("新调试会话不支持部分保存")})
            return super().save(*args, **kwargs)

        with transaction.atomic(using=using):
            persisted = self._persisted_state(using)
            self._reject_identity_mutation(persisted)
            self._validate_transition(persisted, using=using)
            errors = self._validation_errors()
            if errors:
                raise ValidationError(errors)
            self.active_template_key = self._derive_active_template_key()
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                selected_fields = set(update_fields)
                lifecycle_fields = {
                    "status",
                    "current_task_id",
                    "expires_at",
                    "last_heartbeat_at",
                    "terminal_reason",
                }
                changed = {
                    field_name for field_name in lifecycle_fields if getattr(self, field_name) != persisted[field_name]
                }
                omitted = changed - selected_fields
                if omitted:
                    raise ValidationError(
                        {"update_fields": _("部分保存遗漏已变更的会话字段: %(fields)s") % {"fields": ", ".join(sorted(omitted))}}
                    )
                if "status" in selected_fields or "active_template_key" in selected_fields:
                    selected_fields.add("active_template_key")
                kwargs["update_fields"] = selected_fields
            kwargs["using"] = using
            return super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """Retain debug sessions for audit and recovery."""
        raise ValidationError("Debug sessions cannot be deleted")

    def hard_delete(self):
        """Reject physical deletion of governed debug sessions."""
        raise ValidationError("Debug sessions cannot be deleted")


def _canonical_sha256(value):
    """Hash one normalized JSON value without database-generated identity or time fields."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _is_hex_64(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _safe_ref_list(value, *, allow_uuid=False):
    if not isinstance(value, list) or len(value) > 100:
        return False
    try:
        if len(value) != len(set(value)):
            return False
    except TypeError:
        return False
    for item in value:
        if allow_uuid:
            try:
                if str(uuid.UUID(item)) == item:
                    continue
            except (TypeError, ValueError, AttributeError):
                pass
        if not is_safe_evidence_ref(item):
            return False
    return True


class GovernedAggregateQuerySet(models.QuerySet):
    """Validate append batches and close every set-based mutation bypass."""

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        if ignore_conflicts:
            raise ValidationError("Governed aggregates do not support ignore_conflicts")
        objs = list(objs)
        for obj in objs:
            obj.full_clean(validate_unique=False)
        return super().bulk_create(objs, batch_size=batch_size, ignore_conflicts=False)

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Governed aggregates do not support bulk_update")

    def update(self, **kwargs):
        raise ValidationError("Governed aggregates do not support QuerySet.update")

    def delete(self):
        raise ValidationError("Governed aggregates cannot be deleted")


class AppendOnlyAggregateMixin:
    """Permit one validated insert while retaining audit records permanently."""

    def clean(self):
        super().clean()
        if self.is_deleted:
            raise ValidationError({"is_deleted": _("只追加审计记录不能以删除状态保存")})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Governed aggregate is append-only")
        if kwargs.get("update_fields") is not None:
            raise ValidationError("New governed aggregates do not support partial save")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        raise ValidationError("Governed aggregate is append-only")

    def hard_delete(self):
        raise ValidationError("Governed aggregate is append-only")


class ReleaseManifest(AppendOnlyAggregateMixin, CommonModel):
    """Immutable description of one exact revision prepared for release."""

    id = models.UUIDField(_("发布清单 ID"), primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        HarnessRun, verbose_name=_("运行"), on_delete=models.PROTECT, related_name="release_manifests"
    )
    revision = models.ForeignKey(
        WorkflowPlanRevision,
        verbose_name=_("计划修订"),
        on_delete=models.PROTECT,
        related_name="release_manifests",
    )
    plan_hash = models.CharField(_("计划哈希"), max_length=64)
    draft_template_id = models.PositiveBigIntegerField(_("草稿模板 ID"))
    draft_snapshot_id = models.PositiveBigIntegerField(_("草稿快照 ID"))
    draft_tree_fingerprint = models.JSONField(_("草稿树指纹"), default=dict)
    capability_snapshot = models.JSONField(_("能力快照"), default=list, blank=True)
    validation_evidence_refs = models.JSONField(_("校验证据引用"), default=list)
    debug_evidence_refs = models.JSONField(_("调试证据引用"), default=list)
    postcondition_spec = models.JSONField(_("后置条件"), default=dict)
    risk_manifest = models.JSONField(_("风险清单"), default=dict)
    required_approvals = models.JSONField(_("审批需求"), default=list, blank=True)
    policy_version = models.CharField(_("策略版本"), max_length=64)
    target_environment = models.CharField(_("目标环境"), max_length=64)
    manifest_hash = models.CharField(_("清单哈希"), max_length=64, unique=True, editable=False, blank=True, default="")

    objects = models.Manager.from_queryset(GovernedAggregateQuerySet)()

    class Meta:
        verbose_name = _("Harness 发布清单")
        verbose_name_plural = verbose_name
        ordering = ["-create_at"]
        base_manager_name = "objects"

    def _hash_payload(self):
        return {
            "run_id": str(self.run_id),
            "revision_id": str(self.revision_id),
            "plan_hash": self.plan_hash,
            "draft_template_id": self.draft_template_id,
            "draft_snapshot_id": self.draft_snapshot_id,
            "draft_tree_fingerprint": self.draft_tree_fingerprint,
            "capability_snapshot": self.capability_snapshot,
            "validation_evidence_refs": self.validation_evidence_refs,
            "debug_evidence_refs": self.debug_evidence_refs,
            "postcondition_spec": self.postcondition_spec,
            "risk_manifest": self.risk_manifest,
            "required_approvals": self.required_approvals,
            "policy_version": self.policy_version,
            "target_environment": self.target_environment,
        }

    def clean(self):
        super().clean()
        errors = {}
        run = self.run if self.run_id else None
        revision = self.revision if self.revision_id else None
        if run is None or revision is None or revision.run_id != self.run_id:
            errors["revision"] = _("发布清单运行与修订不一致")
        if self.draft_template_id <= 0 or self.draft_snapshot_id <= 0:
            errors["draft_template_id"] = _("发布清单必须绑定正整数草稿坐标")
        if revision is not None and (self.plan_hash != revision.plan_hash or not _is_hex_64(self.plan_hash)):
            errors["plan_hash"] = _("发布清单计划哈希与修订不一致")
        if run is not None and (
            self.policy_version != run.policy_version or self.target_environment != run.environment
        ):
            errors["policy_version"] = _("发布清单策略或环境与运行不一致")
        for field_name in (
            "draft_tree_fingerprint",
            "capability_snapshot",
            "postcondition_spec",
            "risk_manifest",
        ):
            if not is_bounded_non_secret_json(getattr(self, field_name)):
                errors[field_name] = _("发布清单 JSON 必须有界且不含秘密")
        for field_name in ("validation_evidence_refs", "debug_evidence_refs"):
            if not _safe_ref_list(getattr(self, field_name)):
                errors[field_name] = _("发布清单证据引用不合法")
        if not isinstance(self.required_approvals, list) or len(self.required_approvals) > 32:
            errors["required_approvals"] = _("审批需求必须是有界列表")
        else:
            for requirement in self.required_approvals:
                if (
                    not isinstance(requirement, dict)
                    or set(requirement) != {"action", "risk_level", "policy_ref"}
                    or requirement.get("action") not in HarnessAction.values
                    or requirement.get("risk_level") not in RiskLevel.values
                    or not is_safe_evidence_ref(requirement.get("policy_ref"))
                ):
                    errors["required_approvals"] = _("审批需求必须是无实例 ID 的规范描述")
                    break
        if not _is_bounded_string(self.policy_version, 64) or not _is_bounded_string(self.target_environment, 64):
            errors["target_environment"] = _("发布清单策略与环境必须有界")
        derived_hash = _canonical_sha256(self._hash_payload())
        if self.manifest_hash and self.manifest_hash != derived_hash:
            errors["manifest_hash"] = _("发布清单哈希与规范内容不一致")
        self.manifest_hash = derived_hash
        if errors:
            raise ValidationError(errors)


class ApprovalRequestQuerySet(GovernedAggregateQuerySet):
    """Approval rows use controlled instance transitions rather than set-based writes."""

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        raise ValidationError("Approval requests require a controlled instance save")


class ApprovalRequest(CommonModel):
    """Action-bound approval metadata without receipt plaintext."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"
        EXPIRED = "EXPIRED", "Expired"
        REVOKED = "REVOKED", "Revoked"

    IMMUTABLE_FIELDS = frozenset(
        {
            "manifest_id",
            "run_id",
            "revision_id",
            "plan_hash",
            "action",
            "action_digest",
            "platform",
            "platform_app",
            "actor",
            "space_id",
            "scope",
            "target_environment",
            "policy_version",
            "risk_level",
            "risk_summary",
            "requested_at",
        }
    )

    id = models.UUIDField(_("审批请求 ID"), primary_key=True, default=uuid.uuid4, editable=False)
    manifest = models.ForeignKey(
        ReleaseManifest, verbose_name=_("发布清单"), on_delete=models.PROTECT, related_name="approval_requests"
    )
    run = models.ForeignKey(
        HarnessRun, verbose_name=_("运行"), on_delete=models.PROTECT, related_name="approval_requests"
    )
    revision = models.ForeignKey(
        WorkflowPlanRevision, verbose_name=_("计划修订"), on_delete=models.PROTECT, related_name="approval_requests"
    )
    plan_hash = models.CharField(_("计划哈希"), max_length=64)
    action = models.CharField(_("审批动作"), max_length=64, choices=HarnessAction.choices)
    action_digest = models.CharField(_("动作哈希"), max_length=64)
    platform = models.CharField(_("平台"), max_length=64)
    platform_app = models.CharField(_("平台应用"), max_length=128)
    actor = models.CharField(_("操作人"), max_length=128)
    approver = models.CharField(_("审批人"), max_length=128, null=True, blank=True)
    space_id = models.IntegerField(_("空间 ID"), db_index=True)
    scope = models.CharField(_("授权范围"), max_length=MAX_SCOPE_KEY_LENGTH)
    target_environment = models.CharField(_("目标环境"), max_length=64)
    policy_version = models.CharField(_("策略版本"), max_length=64)
    risk_level = models.CharField(_("风险等级"), max_length=2, choices=RiskLevel.choices)
    risk_summary = models.JSONField(_("风险摘要"), default=dict)
    receipt_provider = models.CharField(_("回执提供方"), max_length=64, null=True, blank=True)
    receipt_ref = models.CharField(_("回执引用"), max_length=255, null=True, blank=True)
    receipt_digest = models.CharField(_("回执哈希"), max_length=64, null=True, blank=True)
    status = models.CharField(_("审批状态"), max_length=16, choices=Status.choices, default=Status.PENDING)
    requested_at = models.DateTimeField(_("申请时间"), default=timezone.now)
    verified_at = models.DateTimeField(_("验证时间"), null=True, blank=True)
    expires_at = models.DateTimeField(_("过期时间"), null=True, blank=True)
    verifier_version = models.CharField(_("验证器版本"), max_length=64, null=True, blank=True)
    active_approval_key = models.CharField(
        _("活跃审批键"), max_length=64, null=True, blank=True, unique=True, editable=False
    )

    objects = models.Manager.from_queryset(ApprovalRequestQuerySet)()

    class Meta:
        verbose_name = _("Harness 审批请求")
        verbose_name_plural = verbose_name
        ordering = ["-requested_at"]
        base_manager_name = "objects"

    def _derive_active_key(self):
        if self.status not in {self.Status.PENDING, self.Status.VERIFIED}:
            return None
        return _canonical_sha256(
            {"manifest_id": str(self.manifest_id), "action": self.action, "action_digest": self.action_digest}
        )

    def _validation_errors(self):
        errors = {}
        manifest = self.manifest if self.manifest_id else None
        if (
            manifest is None
            or self.run_id != manifest.run_id
            or self.revision_id != manifest.revision_id
            or self.plan_hash != manifest.plan_hash
        ):
            errors["manifest"] = _("审批请求与发布清单归属不一致")
        if manifest is not None:
            run = manifest.run
            expected = {
                "platform": run.platform,
                "platform_app": run.platform_app,
                "actor": run.actor,
                "space_id": run.space_id,
                "scope": run.scope,
                "target_environment": manifest.target_environment,
                "policy_version": manifest.policy_version,
            }
            if any(getattr(self, key) != value for key, value in expected.items()):
                errors["run"] = _("审批请求可信上下文与发布清单不一致")
        if self.action not in HarnessAction.values or not _is_hex_64(self.action_digest):
            errors["action_digest"] = _("审批动作或动作哈希不合法")
        if self.risk_level not in RiskLevel.values or not is_bounded_non_secret_json(self.risk_summary):
            errors["risk_summary"] = _("审批风险摘要不合法")
        for name in ("requested_at", "expires_at", "verified_at"):
            value = getattr(self, name)
            if value is not None and timezone.is_naive(value):
                errors[name] = _("审批时间必须带时区")
        if self.expires_at is not None and self.expires_at <= self.requested_at:
            errors["expires_at"] = _("审批必须在申请后过期")
        receipt_values = (self.receipt_provider, self.receipt_ref, self.receipt_digest, self.verified_at, self.approver)
        has_receipt = any(value is not None for value in receipt_values)
        complete_receipt = all(receipt_values)
        if self.status == self.Status.PENDING and has_receipt:
            errors["receipt_ref"] = _("待审批记录不能预填回执结果")
        if self.status == self.Status.PENDING and (self.expires_at is not None or self.verifier_version is not None):
            errors["expires_at"] = _("待审批记录不能预填验证器生命周期")
        if has_receipt:
            if not complete_receipt or not _is_hex_64(self.receipt_digest):
                errors["receipt_ref"] = _("审批回执元数据必须完整且仅保存摘要")
            if not is_safe_opaque_uri(self.receipt_ref, "approval", 255):
                errors["receipt_ref"] = _("审批回执必须是安全 opaque ref")
            if not is_bounded_non_secret_text(self.receipt_provider, 64) or not is_bounded_non_secret_text(
                self.approver, 128
            ):
                errors["receipt_provider"] = _("审批提供方和审批人必须有界且不含秘密")
        if self.status == self.Status.VERIFIED:
            if not complete_receipt:
                errors["receipt_ref"] = _("已验证审批必须记录完整回执元数据")
            if self.verified_at is not None and self.verified_at < self.requested_at:
                errors["verified_at"] = _("审批验证时间不能早于申请时间")
            if self.expires_at is None or (self.verified_at is not None and self.verified_at >= self.expires_at):
                errors["expires_at"] = _("审批验证时必须仍在有效期内")
            if not is_bounded_non_secret_text(self.verifier_version, 64):
                errors["verifier_version"] = _("已验证审批必须记录验证器版本")
        if self.status not in self.Status.values:
            errors["status"] = _("审批状态不合法")
        if self.verifier_version is not None and not is_bounded_non_secret_text(self.verifier_version, 64):
            errors["verifier_version"] = _("审批验证器版本必须有界且不含秘密")
        if self.is_deleted:
            errors["is_deleted"] = _("审批请求不能删除")
        return errors

    def clean(self):
        super().clean()
        errors = self._validation_errors()
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(self.__class__, instance=self)
        self.active_approval_key = self._derive_active_key()
        if self._state.adding:
            if self.status != self.Status.PENDING or kwargs.get("update_fields") is not None:
                raise ValidationError("Approval requests must begin pending")
            self.full_clean()
            return super().save(*args, **kwargs)
        with transaction.atomic(using=using):
            persisted = self.__class__._base_manager.using(using).select_for_update().get(pk=self.pk)
            changed_immutable = [
                name for name in self.IMMUTABLE_FIELDS if getattr(self, name) != getattr(persisted, name)
            ]
            if changed_immutable:
                raise ValidationError({name: _("审批请求授权事实不可修改") for name in changed_immutable})
            allowed = {
                self.Status.PENDING: {
                    self.Status.VERIFIED,
                    self.Status.REJECTED,
                    self.Status.EXPIRED,
                    self.Status.REVOKED,
                },
                self.Status.VERIFIED: {self.Status.EXPIRED, self.Status.REVOKED},
            }
            if self.status != persisted.status and self.status not in allowed.get(persisted.status, set()):
                raise ValidationError({"status": _("审批终态不可复活或改写")})
            receipt_fields = {
                "approver",
                "receipt_provider",
                "receipt_ref",
                "receipt_digest",
                "verified_at",
                "expires_at",
                "verifier_version",
            }
            set_once_fields = {"expires_at", "verifier_version"}
            changed_set_once = [name for name in set_once_fields if getattr(self, name) != getattr(persisted, name)]
            is_verifying = persisted.status == self.Status.PENDING and self.status == self.Status.VERIFIED
            invalid_verifier_pair = is_verifying and (
                any(getattr(persisted, name) is not None for name in set_once_fields)
                or any(getattr(self, name) is None for name in set_once_fields)
            )
            if invalid_verifier_pair or (changed_set_once and not is_verifying):
                invalid_fields = changed_set_once or set_once_fields
                raise ValidationError({name: _("审批验证器生命周期只能在验证成功时写入一次") for name in invalid_fields})
            if persisted.status in {
                self.Status.VERIFIED,
                self.Status.REJECTED,
                self.Status.EXPIRED,
                self.Status.REVOKED,
            }:
                changed_receipt = [name for name in receipt_fields if getattr(self, name) != getattr(persisted, name)]
                if changed_receipt:
                    raise ValidationError({name: _("审批终态回执不可改写") for name in changed_receipt})
            self.full_clean()
            update_fields = kwargs.get("update_fields")
            lifecycle_fields = {
                "status",
                "approver",
                "receipt_provider",
                "receipt_ref",
                "receipt_digest",
                "verified_at",
                "expires_at",
                "verifier_version",
                "active_approval_key",
            }
            changed = {name for name in lifecycle_fields if getattr(self, name) != getattr(persisted, name)}
            if update_fields is not None:
                selected = set(update_fields) | {"active_approval_key"}
                if changed - selected:
                    raise ValidationError({"update_fields": _("部分保存遗漏审批生命周期字段")})
                kwargs["update_fields"] = selected
            kwargs["using"] = using
            return super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        raise ValidationError("Approval requests cannot be deleted")

    def hard_delete(self):
        raise ValidationError("Approval requests cannot be deleted")


class ReleasePublication(AppendOnlyAggregateMixin, CommonModel):
    """Append-only published snapshot anchor used for response-loss recovery."""

    id = models.UUIDField(_("发布结果 ID"), primary_key=True, default=uuid.uuid4, editable=False)
    manifest = models.OneToOneField(
        ReleaseManifest, verbose_name=_("发布清单"), on_delete=models.PROTECT, related_name="publication"
    )
    published_template_id = models.PositiveBigIntegerField(_("已发布模板 ID"))
    published_snapshot_id = models.PositiveBigIntegerField(_("已发布快照 ID"))
    published_version = models.CharField(_("已发布版本"), max_length=32)
    operator = models.CharField(_("发布人"), max_length=128, blank=True)
    publish_idempotency_ref = models.CharField(_("发布幂等引用"), max_length=255)
    publication_hash = models.CharField(_("发布结果哈希"), max_length=64, unique=True, editable=False, blank=True, default="")
    published_at = models.DateTimeField(_("发布时间"), default=timezone.now)

    objects = models.Manager.from_queryset(GovernedAggregateQuerySet)()

    class Meta:
        verbose_name = _("Harness 发布结果")
        verbose_name_plural = verbose_name
        ordering = ["-published_at"]
        base_manager_name = "objects"

    def clean(self):
        super().clean()
        errors = {}
        manifest = self.manifest if self.manifest_id else None
        if manifest is None:
            errors["manifest"] = _("发布结果必须绑定发布清单")
        if not self.operator and manifest is not None:
            self.operator = manifest.run.actor
        if manifest is not None and self.operator != manifest.run.actor:
            errors["operator"] = _("发布人与发布清单操作人不一致")
        if manifest is not None and self.published_template_id != manifest.draft_template_id:
            errors["published_template_id"] = _("发布结果模板必须与发布清单草稿模板一致")
        if self.published_template_id <= 0 or self.published_snapshot_id <= 0:
            errors["published_template_id"] = _("发布结果必须绑定正整数模板与快照坐标")
        if not _is_bounded_string(self.published_version, 32) or safe_opaque_identifier(self.published_version) is None:
            errors["published_version"] = _("发布版本不合法")
        if not is_safe_evidence_ref(self.publish_idempotency_ref):
            errors["publish_idempotency_ref"] = _("发布幂等引用不合法")
        if self.published_at is None or timezone.is_naive(self.published_at):
            errors["published_at"] = _("发布时间必须带时区")
        payload = {
            "manifest_id": str(self.manifest_id),
            "published_template_id": self.published_template_id,
            "published_snapshot_id": self.published_snapshot_id,
            "published_version": self.published_version,
            "operator": self.operator,
            "publish_idempotency_ref": self.publish_idempotency_ref,
        }
        derived_hash = _canonical_sha256(payload)
        if self.publication_hash and self.publication_hash != derived_hash:
            errors["publication_hash"] = _("发布结果哈希不一致")
        self.publication_hash = derived_hash
        if errors:
            raise ValidationError(errors)


class ExecutionRunQuerySet(GovernedAggregateQuerySet):
    """Execution lifecycle changes require locked instance saves."""

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        raise ValidationError("Execution runs require a controlled instance save")


class ExecutionRun(CommonModel):
    """Durable create/start/control saga for one published manifest."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CREATE_DISPATCHING = "CREATE_DISPATCHING", "Create dispatching"
        CREATE_UNCERTAIN = "CREATE_UNCERTAIN", "Create uncertain"
        CREATED = "CREATED", "Created"
        START_DISPATCHING = "START_DISPATCHING", "Start dispatching"
        START_UNCERTAIN = "START_UNCERTAIN", "Start uncertain"
        EXECUTING = "EXECUTING", "Executing"
        PAUSED = "PAUSED", "Paused"
        CONTROL_DISPATCHING = "CONTROL_DISPATCHING", "Control dispatching"
        CONTROL_UNCERTAIN = "CONTROL_UNCERTAIN", "Control uncertain"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    class PostconditionStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        PASSED = "PASSED", "Passed"
        FAILED = "FAILED", "Failed"
        UNAVAILABLE = "UNAVAILABLE", "Unavailable"

    TERMINAL = frozenset((Status.SUCCEEDED, Status.FAILED, Status.CANCELLED))
    TRANSITIONS = {
        Status.PENDING: {Status.CREATE_DISPATCHING, Status.FAILED, Status.CANCELLED},
        Status.CREATE_DISPATCHING: {Status.CREATED, Status.CREATE_UNCERTAIN, Status.FAILED, Status.CANCELLED},
        Status.CREATE_UNCERTAIN: {Status.CREATED, Status.FAILED, Status.CANCELLED},
        Status.CREATED: {Status.START_DISPATCHING, Status.FAILED, Status.CANCELLED},
        Status.START_DISPATCHING: {Status.EXECUTING, Status.START_UNCERTAIN, Status.FAILED, Status.CANCELLED},
        Status.START_UNCERTAIN: {Status.EXECUTING, Status.FAILED, Status.CANCELLED},
        Status.EXECUTING: {
            Status.PAUSED,
            Status.CONTROL_DISPATCHING,
            Status.SUCCEEDED,
            Status.FAILED,
            Status.CANCELLED,
        },
        Status.PAUSED: {
            Status.EXECUTING,
            Status.CONTROL_DISPATCHING,
            Status.SUCCEEDED,
            Status.FAILED,
            Status.CANCELLED,
        },
        Status.CONTROL_DISPATCHING: {
            Status.CONTROL_UNCERTAIN,
            Status.EXECUTING,
            Status.PAUSED,
            Status.SUCCEEDED,
            Status.FAILED,
            Status.CANCELLED,
        },
        Status.CONTROL_UNCERTAIN: {Status.EXECUTING, Status.PAUSED, Status.SUCCEEDED, Status.FAILED, Status.CANCELLED},
    }
    IMMUTABLE_FIELDS = frozenset(
        {
            "manifest_id",
            "run_id",
            "revision_id",
            "published_template_id",
            "published_snapshot_id",
            "published_version",
            "start_idempotency_key",
            "platform",
            "platform_app",
            "actor",
            "space_id",
            "scope",
            "target_environment",
            "policy_version",
        }
    )

    id = models.UUIDField(_("执行 ID"), primary_key=True, default=uuid.uuid4, editable=False)
    manifest = models.ForeignKey(
        ReleaseManifest, verbose_name=_("发布清单"), on_delete=models.PROTECT, related_name="executions"
    )
    run = models.ForeignKey(HarnessRun, verbose_name=_("运行"), on_delete=models.PROTECT, related_name="executions")
    revision = models.ForeignKey(
        WorkflowPlanRevision, verbose_name=_("计划修订"), on_delete=models.PROTECT, related_name="executions"
    )
    published_template_id = models.PositiveBigIntegerField(_("已发布模板 ID"))
    published_snapshot_id = models.PositiveBigIntegerField(_("已发布快照 ID"))
    published_version = models.CharField(_("已发布版本"), max_length=32)
    task_ref = models.CharField(_("任务引用"), max_length=128, null=True, blank=True)
    status = models.CharField(_("执行状态"), max_length=32, choices=Status.choices, default=Status.PENDING)
    start_idempotency_key = models.CharField(_("启动幂等键"), max_length=128)
    create_idempotency_ref = models.CharField(_("创建幂等引用"), max_length=255, null=True, blank=True)
    start_idempotency_ref = models.CharField(_("启动幂等引用"), max_length=255, null=True, blank=True)
    control_idempotency_refs = models.JSONField(_("控制幂等引用"), default=list, blank=True)
    platform = models.CharField(_("平台"), max_length=64)
    platform_app = models.CharField(_("平台应用"), max_length=128)
    actor = models.CharField(_("操作人"), max_length=128)
    space_id = models.IntegerField(_("空间 ID"), db_index=True)
    scope = models.CharField(_("授权范围"), max_length=MAX_SCOPE_KEY_LENGTH)
    target_environment = models.CharField(_("目标环境"), max_length=64)
    policy_version = models.CharField(_("策略版本"), max_length=64)
    postcondition_status = models.CharField(
        _("后置条件状态"), max_length=16, choices=PostconditionStatus.choices, default=PostconditionStatus.PENDING
    )
    postcondition_report = models.JSONField(_("后置条件报告"), default=dict, blank=True)
    last_engine_state = models.CharField(_("最近引擎状态"), max_length=64, null=True, blank=True)
    heartbeat_at = models.DateTimeField(_("最近心跳"), null=True, blank=True)
    terminal_at = models.DateTimeField(_("终态时间"), null=True, blank=True)

    objects = models.Manager.from_queryset(ExecutionRunQuerySet)()

    class Meta:
        verbose_name = _("Harness 执行")
        verbose_name_plural = verbose_name
        ordering = ["-create_at"]
        base_manager_name = "objects"
        constraints = [
            models.UniqueConstraint(
                fields=["manifest", "start_idempotency_key"], name="uniq_harness_manifest_start_key"
            )
        ]

    def _validation_errors(self):
        errors = {}
        manifest = self.manifest if self.manifest_id else None
        if (
            manifest is None
            or self.run_id != manifest.run_id
            or self.revision_id != manifest.revision_id
            or self.target_environment != manifest.target_environment
            or self.policy_version != manifest.policy_version
        ):
            errors["manifest"] = _("执行与发布清单归属不一致")
        publication = None
        if manifest is not None:
            try:
                publication = manifest.publication
            except ReleasePublication.DoesNotExist:
                errors["manifest"] = _("执行必须绑定已发布清单")
            run = manifest.run
            expected = {
                "platform": run.platform,
                "platform_app": run.platform_app,
                "actor": run.actor,
                "space_id": run.space_id,
                "scope": run.scope,
            }
            if any(getattr(self, key) != value for key, value in expected.items()):
                errors["run"] = _("执行可信上下文与发布清单不一致")
        if publication is not None and (
            self.published_template_id != publication.published_template_id
            or self.published_snapshot_id != publication.published_snapshot_id
            or self.published_version != publication.published_version
        ):
            errors["published_snapshot_id"] = _("执行发布坐标与已发布结果不一致")
        if self.published_template_id <= 0 or self.published_snapshot_id <= 0:
            errors["published_template_id"] = _("执行必须绑定正整数发布坐标")
        if not is_safe_idempotency_key(self.start_idempotency_key) or len(self.start_idempotency_key) > 128:
            errors["start_idempotency_key"] = _("启动幂等键不合法")
        if self.task_ref is not None and safe_opaque_identifier(self.task_ref) is None:
            errors["task_ref"] = _("任务引用不合法")
        if (
            self.status
            in {
                self.Status.PENDING,
                self.Status.CREATE_DISPATCHING,
                self.Status.CREATE_UNCERTAIN,
            }
            and self.task_ref is not None
        ):
            errors["task_ref"] = _("任务创建成功前不能提前绑定任务引用")
        if (
            self.status
            in {
                self.Status.CREATED,
                self.Status.START_DISPATCHING,
                self.Status.START_UNCERTAIN,
                self.Status.EXECUTING,
                self.Status.PAUSED,
                self.Status.CONTROL_DISPATCHING,
                self.Status.CONTROL_UNCERTAIN,
                self.Status.SUCCEEDED,
            }
            and not self.task_ref
        ):
            errors["task_ref"] = _("创建后的执行必须保存任务引用")
        if (self.status in self.TERMINAL) != (self.terminal_at is not None):
            errors["terminal_at"] = _("执行终态与终态时间必须一致")
        if self.status in self.TERMINAL:
            if self.postcondition_status in {
                self.PostconditionStatus.PENDING,
                self.PostconditionStatus.RUNNING,
            }:
                errors["postcondition_status"] = _("执行进入终态前必须完成后置条件")
            if (self.status == self.Status.SUCCEEDED) != (self.postcondition_status == self.PostconditionStatus.PASSED):
                errors["postcondition_status"] = _("执行成功态必须且只能对应通过的后置条件")
        for name in ("heartbeat_at", "terminal_at"):
            value = getattr(self, name)
            if value is not None and timezone.is_naive(value):
                errors[name] = _("执行时间必须带时区")
        for name in ("create_idempotency_ref", "start_idempotency_ref"):
            value = getattr(self, name)
            if value is not None and not is_safe_evidence_ref(value):
                errors[name] = _("执行幂等引用不合法")
        if not _safe_ref_list(self.control_idempotency_refs):
            errors["control_idempotency_refs"] = _("控制幂等引用不合法")
        if not is_bounded_non_secret_json(self.postcondition_report):
            errors["postcondition_report"] = _("后置条件报告必须有界且不含秘密")
        if self.is_deleted:
            errors["is_deleted"] = _("执行记录不能删除")
        return errors

    def clean(self):
        super().clean()
        errors = self._validation_errors()
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(self.__class__, instance=self)
        if self._state.adding:
            if self.status != self.Status.PENDING or kwargs.get("update_fields") is not None:
                raise ValidationError("Execution runs must begin pending")
            self.full_clean()
            return super().save(*args, **kwargs)
        with transaction.atomic(using=using):
            persisted = self.__class__._base_manager.using(using).select_for_update().get(pk=self.pk)
            changed_immutable = [
                name for name in self.IMMUTABLE_FIELDS if getattr(self, name) != getattr(persisted, name)
            ]
            if changed_immutable:
                raise ValidationError({name: _("执行授权事实不可修改") for name in changed_immutable})
            if persisted.task_ref and self.task_ref != persisted.task_ref:
                raise ValidationError({"task_ref": _("任务引用只能写入一次")})
            if self.status != persisted.status and self.status not in self.TRANSITIONS.get(persisted.status, set()):
                raise ValidationError({"status": _("执行状态转换不合法")})
            mutable = {
                "status",
                "task_ref",
                "create_idempotency_ref",
                "start_idempotency_ref",
                "control_idempotency_refs",
                "postcondition_status",
                "postcondition_report",
                "last_engine_state",
                "heartbeat_at",
                "terminal_at",
            }
            if persisted.status in self.TERMINAL:
                changed_terminal = [name for name in mutable if getattr(self, name) != getattr(persisted, name)]
                if changed_terminal:
                    raise ValidationError({name: _("执行终态事实不可改写") for name in changed_terminal})
            if self.status in self.TERMINAL and persisted.status not in self.TERMINAL:
                has_active_lease = (
                    TokenLease._base_manager.using(using)
                    .filter(execution_id=self.pk, status=TokenLease.Status.ACTIVE)
                    .exists()
                )
                if has_active_lease:
                    raise ValidationError({"status": _("执行终态化前必须撤销或过期全部活跃 Token 租约")})
            self.full_clean()
            update_fields = kwargs.get("update_fields")
            changed = {name for name in mutable if getattr(self, name) != getattr(persisted, name)}
            if update_fields is not None and changed - set(update_fields):
                raise ValidationError({"update_fields": _("部分保存遗漏执行生命周期字段")})
            kwargs["using"] = using
            return super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        raise ValidationError("Execution runs cannot be deleted")

    def hard_delete(self):
        raise ValidationError("Execution runs cannot be deleted")


class EvidenceBundle(AppendOnlyAggregateMixin, CommonModel):
    """Append-only finalized collection of ordered execution evidence."""

    class Outcome(models.TextChoices):
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    class RetentionClass(models.TextChoices):
        STANDARD = "STANDARD", "Standard"

    id = models.UUIDField(_("证据包 ID"), primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(HarnessRun, verbose_name=_("运行"), on_delete=models.PROTECT, related_name="evidence_bundles")
    revision = models.ForeignKey(
        WorkflowPlanRevision, verbose_name=_("计划修订"), on_delete=models.PROTECT, related_name="evidence_bundles"
    )
    execution = models.OneToOneField(
        ExecutionRun,
        verbose_name=_("执行"),
        on_delete=models.PROTECT,
        related_name="evidence_bundle",
        null=True,
        blank=True,
    )
    evidence_event_refs = models.JSONField(_("证据事件引用"), default=list)
    artifact_refs = models.JSONField(_("工件引用"), default=list, blank=True)
    redaction_version = models.CharField(_("脱敏版本"), max_length=64)
    bundle_hash = models.CharField(_("证据包哈希"), max_length=64, unique=True, editable=False, blank=True, default="")
    outcome = models.CharField(_("结果"), max_length=16, choices=Outcome.choices)
    finalized_at = models.DateTimeField(_("完成时间"))
    retention_class = models.CharField(
        _("保留级别"), max_length=16, choices=RetentionClass.choices, default=RetentionClass.STANDARD
    )

    objects = models.Manager.from_queryset(GovernedAggregateQuerySet)()

    class Meta:
        verbose_name = _("Harness 证据包")
        verbose_name_plural = verbose_name
        ordering = ["-finalized_at"]
        base_manager_name = "objects"

    def clean(self):
        super().clean()
        errors = {}
        run = self.run if self.run_id else None
        revision = self.revision if self.revision_id else None
        execution = self.execution if self.execution_id else None
        if run is None or revision is None or revision.run_id != self.run_id:
            errors["revision"] = _("证据包运行与修订不一致")
        if execution is not None and (execution.run_id != self.run_id or execution.revision_id != self.revision_id):
            errors["execution"] = _("证据包执行归属不一致")
        if execution is not None:
            expected_outcome = {
                ExecutionRun.Status.SUCCEEDED: self.Outcome.SUCCEEDED,
                ExecutionRun.Status.FAILED: self.Outcome.FAILED,
                ExecutionRun.Status.CANCELLED: self.Outcome.CANCELLED,
            }.get(execution.status)
            if expected_outcome is None:
                errors["execution"] = _("证据包只能绑定已终态执行")
            elif self.outcome != expected_outcome:
                errors["outcome"] = _("证据包结果必须与执行终态一致")
            if execution.postcondition_status in {
                ExecutionRun.PostconditionStatus.PENDING,
                ExecutionRun.PostconditionStatus.RUNNING,
            }:
                errors["execution"] = _("证据包只能在后置条件完成后固化")
            if (
                execution.terminal_at is not None
                and self.finalized_at is not None
                and not timezone.is_naive(self.finalized_at)
                and self.finalized_at < execution.terminal_at
            ):
                errors["finalized_at"] = _("证据包完成时间不能早于执行终态")
        elif run is not None:
            expected_outcome = {
                HarnessRunStatus.SUCCEEDED: self.Outcome.SUCCEEDED,
                HarnessRunStatus.FAILED: self.Outcome.FAILED,
                HarnessRunStatus.CANCELLED: self.Outcome.CANCELLED,
            }.get(run.status)
            if expected_outcome is None:
                errors["run"] = _("无流程执行的证据包只能绑定已终态 Harness 运行")
            elif self.outcome != expected_outcome:
                errors["outcome"] = _("证据包结果必须与 Harness 运行终态一致")
        if not _safe_ref_list(self.evidence_event_refs, allow_uuid=True) or not self.evidence_event_refs:
            errors["evidence_event_refs"] = _("证据包必须包含有序且不重复的事件引用")
        else:
            event_ids = []
            for item in self.evidence_event_refs:
                try:
                    event_ids.append(uuid.UUID(item))
                except (TypeError, ValueError, AttributeError):
                    errors["evidence_event_refs"] = _("证据事件引用必须是 UUID")
                    break
            if not errors.get("evidence_event_refs"):
                events = {
                    event_id: (run_id, revision_id, execution_id)
                    for event_id, run_id, revision_id, execution_id in EvidenceEvent._base_manager.filter(
                        id__in=event_ids
                    ).values_list("id", "run_id", "revision_id", "execution_id")
                }
                if len(events) != len(event_ids) or any(
                    events[event_id][0] != self.run_id
                    or events[event_id][1] != self.revision_id
                    or events[event_id][2] != self.execution_id
                    for event_id in event_ids
                    if event_id in events
                ):
                    errors["evidence_event_refs"] = _("证据事件不属于目标运行或执行")
        if not _safe_ref_list(self.artifact_refs):
            errors["artifact_refs"] = _("证据包工件引用不合法")
        if self.redaction_version != EVIDENCE_REDACTION_VERSION:
            errors["redaction_version"] = _("证据包脱敏版本不合法")
        if self.outcome not in self.Outcome.values or self.retention_class != self.RetentionClass.STANDARD:
            errors["outcome"] = _("证据包结果或保留级别不合法")
        if self.finalized_at is None or timezone.is_naive(self.finalized_at):
            errors["finalized_at"] = _("证据包完成时间必须带时区")
        payload = {
            "run_id": str(self.run_id),
            "revision_id": str(self.revision_id),
            "execution_id": str(self.execution_id) if self.execution_id else None,
            "evidence_event_refs": self.evidence_event_refs,
            "artifact_refs": self.artifact_refs,
            "redaction_version": self.redaction_version,
            "outcome": self.outcome,
            "retention_class": self.retention_class,
        }
        derived_hash = _canonical_sha256(payload)
        if self.bundle_hash and self.bundle_hash != derived_hash:
            errors["bundle_hash"] = _("证据包哈希不一致")
        self.bundle_hash = derived_hash
        if errors:
            raise ValidationError(errors)


class TokenLeaseQuerySet(models.QuerySet):
    """Validate lease inserts and require controlled instance lifecycle writes."""

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        """Validate each metadata-only lease before insertion."""
        if ignore_conflicts:
            raise ValidationError("Token leases do not support ignore_conflicts")
        objs = list(objs)
        if any(obj.status == obj.Status.ACTIVE for obj in objs):
            raise ValidationError("Active Token leases require a locked instance save")
        for obj in objs:
            obj.full_clean(validate_unique=False)
        return super().bulk_create(objs, batch_size=batch_size, ignore_conflicts=False)

    def bulk_update(self, objs, fields, batch_size=None):
        """Require the broker to lock and save one lease at a time."""
        raise ValidationError("Token leases do not support bulk_update")

    def update(self, **kwargs):
        """Reject unvalidated set-based lease state changes."""
        raise ValidationError("Token leases do not support QuerySet.update")

    def delete(self):
        """Retain lease metadata as evidence even after expiry or revocation."""
        raise ValidationError("Token leases cannot be deleted")


class TokenLease(CommonModel):
    """Metadata for one short-lived server-side token without plaintext material."""

    class Resource(models.TextChoices):
        """Resources supported by the P2/P3 broker boundary."""

        TEMPLATE = "TEMPLATE", "Template"
        SCOPE = "SCOPE", "Scope"
        TASK = "TASK", "Task"

    class Permission(models.TextChoices):
        """Least-privilege grants admitted by debug and execution leases."""

        MOCK = "MOCK", "Mock"
        VIEW = "VIEW", "View"
        EDIT = "EDIT", "Edit"
        OPERATE = "OPERATE", "Operate"

    class Status(models.TextChoices):
        """Durable lifecycle for one short-lived lease."""

        ACTIVE = "ACTIVE", "Active"
        REVOKED = "REVOKED", "Revoked"
        EXPIRED = "EXPIRED", "Expired"

    IMMUTABLE_FIELDS = frozenset(
        {
            "session_id",
            "execution_id",
            "platform_app",
            "actor",
            "space_id",
            "resource_type",
            "resource_id",
            "permission",
            "issuer_ref",
            "token_fingerprint",
            "issued_at",
            "action",
            "action_digest",
        }
    )

    id = models.UUIDField(_("Token 租约 ID"), primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        DebugSession,
        verbose_name=_("调试会话"),
        on_delete=models.PROTECT,
        related_name="token_leases",
        null=True,
        blank=True,
    )
    execution = models.ForeignKey(
        ExecutionRun,
        verbose_name=_("流程执行"),
        on_delete=models.PROTECT,
        related_name="token_leases",
        null=True,
        blank=True,
    )
    platform_app = models.CharField(_("平台应用"), max_length=128)
    actor = models.CharField(_("操作人"), max_length=128)
    space_id = models.IntegerField(_("空间 ID"), db_index=True)
    resource_type = models.CharField(_("资源类型"), max_length=32, choices=Resource.choices)
    resource_id = models.CharField(_("资源 ID"), max_length=128)
    permission = models.CharField(_("权限"), max_length=32, choices=Permission.choices)
    action = models.CharField(_("授权动作"), max_length=64, choices=HarnessAction.choices, null=True, blank=True)
    action_digest = models.CharField(_("动作哈希"), max_length=64, null=True, blank=True)
    issuer_ref = models.CharField(_("颁发方引用"), max_length=255)
    token_fingerprint = models.CharField(_("Token 指纹"), max_length=64)
    issued_at = models.DateTimeField(_("颁发时间"))
    expires_at = models.DateTimeField(_("过期时间"), db_index=True)
    revoked_at = models.DateTimeField(_("撤销时间"), null=True, blank=True)
    status = models.CharField(_("租约状态"), max_length=16, choices=Status.choices)

    objects = models.Manager.from_queryset(TokenLeaseQuerySet)()

    class Meta:
        verbose_name = _("Harness Token 租约")
        verbose_name_plural = verbose_name
        ordering = ["-issued_at"]
        base_manager_name = "objects"
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(status="ACTIVE", revoked_at__isnull=True)
                    | models.Q(status="REVOKED", revoked_at__isnull=False)
                    | models.Q(status="EXPIRED", revoked_at__isnull=True)
                ),
                name="harness_token_lease_status_timestamps",
            ),
            models.CheckConstraint(
                check=models.Q(expires_at__gt=models.F("issued_at")),
                name="harness_token_lease_expiry_after_issue",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(
                        session__isnull=False, execution__isnull=True, action__isnull=True, action_digest__isnull=True
                    )
                    | models.Q(
                        session__isnull=True,
                        execution__isnull=False,
                        action__isnull=False,
                        action_digest__isnull=False,
                    )
                ),
                name="harness_token_lease_exact_owner_action",
            ),
        ]

    def _validation_errors(self):
        """Build fail-closed identity, reference, fingerprint, and lifecycle errors."""
        errors = {}
        session = self.session if self.session_id else None
        execution = self.execution if self.execution_id else None
        if (session is None) == (execution is None):
            errors["session"] = _("Token 租约必须且只能绑定一个调试会话或流程执行")
        run = session.run if session is not None else execution.run if execution is not None else None
        if session is not None and self.status == self.Status.ACTIVE and not session.is_active:
            errors["session"] = _("活跃 Token 租约必须绑定活跃调试会话")
        if execution is not None and self.status == self.Status.ACTIVE and execution.status in execution.TERMINAL:
            errors["execution"] = _("活跃 Token 租约不能绑定终态流程执行")
        if run is not None and self.platform_app != run.platform_app:
            errors["platform_app"] = _("租约平台应用与所有者不一致")
        if run is not None and self.actor != run.actor:
            errors["actor"] = _("租约操作人与所有者不一致")
        if session is not None and self.actor != session.actor:
            errors["actor"] = _("租约操作人与调试会话不一致")
        if isinstance(self.space_id, bool) or not isinstance(self.space_id, int) or self.space_id <= 0:
            errors["space_id"] = _("空间 ID 必须为正整数")
        elif run is not None and self.space_id != run.space_id:
            errors["space_id"] = _("租约空间与所有者不一致")
        if self.resource_type not in self.Resource.values:
            errors["resource_type"] = _("未知 Token 资源类型")
        if not is_bounded_non_secret_text(self.resource_id, 128):
            errors["resource_id"] = _("资源 ID 必须是有界非秘密字符串")
        elif self.resource_type in {self.Resource.TEMPLATE, self.Resource.TASK}:
            if re.fullmatch(r"[1-9][0-9]{0,18}", self.resource_id) is None:
                errors["resource_id"] = _("模板或任务资源 ID 必须是正整数标识")
            elif (
                self.resource_type == self.Resource.TEMPLATE
                and session is not None
                and int(self.resource_id) != session.template_id
            ):
                errors["resource_id"] = _("模板租约资源与调试会话不一致")
            elif (
                self.resource_type == self.Resource.TEMPLATE
                and execution is not None
                and int(self.resource_id) != execution.published_template_id
            ):
                errors["resource_id"] = _("模板租约资源与流程执行不一致")
            elif (
                self.resource_type == self.Resource.TASK
                and execution is not None
                and (execution.task_ref is None or self.resource_id != execution.task_ref)
            ):
                errors["resource_id"] = _("任务租约资源与流程执行不一致")
            elif self.resource_type == self.Resource.TASK and session is not None:
                errors["resource_type"] = _("调试租约不支持任务资源")
        elif self.resource_type == self.Resource.SCOPE and session is not None:
            snapshot = session.trusted_context_snapshot
            scope_type = snapshot.get("scope_type") if isinstance(snapshot, dict) else None
            scope_value = snapshot.get("scope_value") if isinstance(snapshot, dict) else None
            expected_scope = (
                "{}_{}".format(scope_type, scope_value)
                if isinstance(scope_type, str) and isinstance(scope_value, str)
                else None
            )
            if expected_scope is None or self.resource_id != expected_scope:
                errors["resource_id"] = _("空间级租约资源必须严格匹配调试会话可信作用域")
        elif self.resource_type == self.Resource.SCOPE and execution is not None:
            errors["resource_type"] = _("流程执行租约不支持空间资源")
        if session is not None:
            if self.permission != self.Permission.MOCK or self.action is not None or self.action_digest is not None:
                errors["permission"] = _("调试租约仅允许无动作的 MOCK 权限")
        elif execution is not None:
            allowed_permissions = {
                self.Resource.TEMPLATE: {self.Permission.VIEW, self.Permission.EDIT},
                self.Resource.TASK: {self.Permission.VIEW, self.Permission.OPERATE},
            }
            if self.permission not in allowed_permissions.get(self.resource_type, set()):
                errors["permission"] = _("流程执行租约权限不满足最小授权")
            if self.action not in HarnessAction.values or not _is_hex_64(self.action_digest):
                errors["action_digest"] = _("流程执行租约必须绑定规范动作和动作哈希")
        if not is_safe_evidence_ref(self.issuer_ref) or not self.issuer_ref.startswith("issuer://"):
            errors["issuer_ref"] = _("颁发方引用必须是安全 issuer 引用")
        if not isinstance(self.token_fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", self.token_fingerprint) is None:
            errors["token_fingerprint"] = _("Token 指纹必须是小写 SHA-256")
        if self.status not in self.Status.values:
            errors["status"] = _("未知 Token 租约状态")

        now = timezone.now()
        if self.issued_at is None or timezone.is_naive(self.issued_at):
            errors["issued_at"] = _("颁发时间必须是带时区时间")
        elif self.issued_at > now + timezone.timedelta(minutes=5):
            errors["issued_at"] = _("颁发时间不能位于未来")
        if self.expires_at is None or timezone.is_naive(self.expires_at):
            errors["expires_at"] = _("过期时间必须是带时区时间")
        elif self.issued_at is not None and self.expires_at <= self.issued_at:
            errors["expires_at"] = _("租约必须在颁发后过期")
        if self.revoked_at is not None:
            if timezone.is_naive(self.revoked_at):
                errors["revoked_at"] = _("撤销时间必须是带时区时间")
            elif self.issued_at is not None and self.revoked_at < self.issued_at:
                errors["revoked_at"] = _("撤销时间不能早于颁发时间")
        if self.status == self.Status.ACTIVE:
            if self.revoked_at is not None:
                errors["revoked_at"] = _("活跃租约不能已撤销")
            if self.expires_at is not None and self.expires_at <= now:
                errors["expires_at"] = _("活跃租约必须尚未过期")
        elif self.status == self.Status.REVOKED and self.revoked_at is None:
            errors["revoked_at"] = _("已撤销租约必须记录撤销时间")
        elif self.status == self.Status.EXPIRED:
            if self.revoked_at is not None:
                errors["revoked_at"] = _("过期租约不能同时标记撤销")
            if self.expires_at is not None and self.expires_at > now:
                errors["expires_at"] = _("EXPIRED 租约必须已经过期")
        return errors

    def clean(self):
        """Validate a metadata-only lease before persistence."""
        super().clean()
        if not self._state.adding:
            using = router.db_for_read(self.__class__, instance=self)
            persisted = (
                self.__class__._base_manager.using(using).values(*self.IMMUTABLE_FIELDS, "status").get(pk=self.pk)
            )
            self._reject_identity_mutation(persisted)
            self._validate_transition(persisted)
        errors = self._validation_errors()
        if errors:
            raise ValidationError(errors)

    def _persisted_state(self, using):
        """Lock and return immutable and lifecycle fields for one broker transition."""
        fields = self.IMMUTABLE_FIELDS | {"status", "expires_at", "revoked_at"}
        return self.__class__._base_manager.using(using).select_for_update().values(*fields).get(pk=self.pk)

    def _reject_identity_mutation(self, persisted):
        """Prevent token material references or trusted identities from being rebound."""
        changed = [field for field in self.IMMUTABLE_FIELDS if getattr(self, field) != persisted[field]]
        if changed:
            raise ValidationError({field: _("Token 租约身份字段不可修改") for field in changed})

    def _validate_transition(self, persisted):
        """Keep revoked and expired lease authority permanently terminal."""
        old_status = persisted["status"]
        if old_status in {self.Status.REVOKED, self.Status.EXPIRED} and self.status != old_status:
            raise ValidationError({"status": _("终态 Token 租约不可重新激活或改写终态")})

    def save(self, *args, **kwargs):
        """Validate every insert and controlled instance lifecycle transition."""
        using = kwargs.get("using") or router.db_for_write(self.__class__, instance=self)
        if self._state.adding:
            if kwargs.get("update_fields") is not None:
                raise ValidationError({"update_fields": _("新 Token 租约不支持部分保存")})
            if bool(self.session_id) == bool(self.execution_id):
                raise ValidationError({"session": _("Token 租约必须且只能绑定一个所有者")})
            with transaction.atomic(using=using):
                if self.session_id:
                    try:
                        self.session = (
                            DebugSession._base_manager.using(using).select_for_update().get(pk=self.session_id)
                        )
                    except DebugSession.DoesNotExist:
                        raise ValidationError({"session": _("Token 租约绑定的调试会话不存在")})
                else:
                    try:
                        self.execution = (
                            ExecutionRun._base_manager.using(using).select_for_update().get(pk=self.execution_id)
                        )
                    except ExecutionRun.DoesNotExist:
                        raise ValidationError({"execution": _("Token 租约绑定的流程执行不存在")})
                errors = self._validation_errors()
                if errors:
                    raise ValidationError(errors)
                kwargs["using"] = using
                return super().save(*args, **kwargs)

        with transaction.atomic(using=using):
            persisted = self._persisted_state(using)
            self._reject_identity_mutation(persisted)
            self._validate_transition(persisted)
            errors = self._validation_errors()
            if errors:
                raise ValidationError(errors)
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                selected_fields = set(update_fields)
                changed = {
                    field_name
                    for field_name in ("status", "expires_at", "revoked_at")
                    if getattr(self, field_name) != persisted[field_name]
                }
                omitted = changed - selected_fields
                if omitted:
                    raise ValidationError(
                        {"update_fields": _("部分保存遗漏已变更的租约字段: %(fields)s") % {"fields": ", ".join(sorted(omitted))}}
                    )
                kwargs["update_fields"] = selected_fields
            kwargs["using"] = using
            return super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """Retain lease metadata after revocation or expiry."""
        raise ValidationError("Token leases cannot be deleted")

    def hard_delete(self):
        """Reject physical deletion of lease evidence."""
        raise ValidationError("Token leases cannot be deleted")


class EvidenceEventQuerySet(models.QuerySet):
    """Allow validated append batches and reject every set-based mutation."""

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        """Validate each append-only event before batch insertion."""
        if ignore_conflicts:
            raise ValidationError("Evidence events do not support ignore_conflicts")
        objs = list(objs)
        if any(obj.execution_id is not None for obj in objs):
            raise ValidationError("Execution Evidence requires individually locked insertion")
        for obj in objs:
            obj.full_clean(validate_unique=False)
        return super().bulk_create(objs, batch_size=batch_size, ignore_conflicts=False)

    def bulk_update(self, objs, fields, batch_size=None):
        """Reject batch mutation of append-only evidence."""
        raise ValidationError("Evidence events do not support bulk_update")

    def update(self, **kwargs):
        """Reject set-based mutation of append-only evidence."""
        raise ValidationError("Evidence events do not support QuerySet.update")

    def delete(self):
        """Reject set-based deletion of append-only evidence."""
        raise ValidationError("Evidence events are append-only")


class EvidenceEvent(CommonModel):
    """One bounded, redacted, append-only Harness lifecycle event."""

    EVENT_ACTION_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,63}$")

    id = models.UUIDField(_("证据事件 ID"), primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        HarnessRun,
        verbose_name=_("Harness 运行"),
        on_delete=models.PROTECT,
        related_name="evidence_events",
    )
    revision = models.ForeignKey(
        WorkflowPlanRevision,
        verbose_name=_("计划修订"),
        on_delete=models.PROTECT,
        related_name="evidence_events",
    )
    debug_session = models.ForeignKey(
        DebugSession,
        verbose_name=_("调试会话"),
        on_delete=models.PROTECT,
        related_name="evidence_events",
        null=True,
        blank=True,
    )
    execution = models.ForeignKey(
        ExecutionRun,
        verbose_name=_("流程执行"),
        on_delete=models.PROTECT,
        related_name="evidence_events",
        null=True,
        blank=True,
    )
    event_type = models.CharField(_("事件类型"), max_length=64)
    action = models.CharField(_("动作"), max_length=64)
    redacted_payload = models.JSONField(_("脱敏载荷"), default=dict)
    artifact_refs = models.JSONField(_("工件引用"), default=list, blank=True)
    actor = models.CharField(_("操作人"), max_length=128)
    correlation_id = models.CharField(_("关联 ID"), max_length=128, db_index=True)
    redaction_version = models.CharField(_("脱敏版本"), max_length=64, default=EVIDENCE_REDACTION_VERSION)
    occurred_at = models.DateTimeField(_("发生时间"), default=timezone.now, db_index=True)

    objects = models.Manager.from_queryset(EvidenceEventQuerySet)()

    class Meta:
        verbose_name = _("Harness 证据事件")
        verbose_name_plural = verbose_name
        ordering = ["occurred_at", "id"]
        base_manager_name = "objects"
        constraints = [
            models.CheckConstraint(
                check=models.Q(debug_session__isnull=True) | models.Q(execution__isnull=True),
                name="harness_evidence_at_most_one_owner",
            )
        ]

    def _validation_errors(self):
        """Build bounded, relation-consistent, non-secret event validation errors."""
        errors = {}
        run = self.run if self.run_id else None
        revision = self.revision if self.revision_id else None
        debug_session = None
        execution = None
        if self.debug_session_id is not None:
            try:
                debug_session = self.debug_session
            except DebugSession.DoesNotExist:
                errors["debug_session"] = _("证据调试会话不存在")
        if self.execution_id is not None:
            try:
                execution = self.execution
            except ExecutionRun.DoesNotExist:
                errors["execution"] = _("证据流程执行不存在")
        if run is None:
            errors["run"] = _("证据事件必须绑定 Harness 运行")
        if revision is None or run is None or revision.run_id != self.run_id:
            errors["revision"] = _("证据运行与修订不一致")
        if debug_session is not None and (
            debug_session.run_id != self.run_id or debug_session.revision_id != self.revision_id
        ):
            errors["debug_session"] = _("证据调试会话与运行修订不一致")
        if self.debug_session_id is not None and self.execution_id is not None:
            errors["execution"] = _("证据事件最多绑定一个调试或执行所有者")
        if execution is not None and (execution.run_id != self.run_id or execution.revision_id != self.revision_id):
            errors["execution"] = _("证据流程执行与运行修订不一致")
        if debug_session is not None and (
            self.correlation_id != debug_session.trusted_context_snapshot.get("correlation_id")
        ):
            errors["correlation_id"] = _("证据关联 ID 与调试会话可信上下文不一致")
        if (
            (run is not None and self.actor != run.actor)
            or (debug_session is not None and self.actor != debug_session.actor)
            or (execution is not None and self.actor != execution.actor)
        ):
            errors["actor"] = _("证据操作人与可信运行不一致")
        for field_name in ("event_type", "action"):
            value = getattr(self, field_name)
            if not is_bounded_non_secret_text(value, 64) or self.EVENT_ACTION_PATTERN.fullmatch(value) is None:
                errors[field_name] = _("证据事件字段格式不合法")
        if not is_bounded_non_secret_text(self.actor, 128):
            errors["actor"] = _("证据操作人必须是有界非秘密字符串")
        if not is_bounded_non_secret_text(self.correlation_id, 128):
            errors["correlation_id"] = _("关联 ID 必须是有界非秘密字符串")
        if self.redaction_version != EVIDENCE_REDACTION_VERSION:
            errors["redaction_version"] = _("证据必须使用内置脱敏版本")
        if not validate_redacted_evidence_payload(self.redacted_payload):
            errors["redacted_payload"] = _("证据载荷必须已脱敏且满足内联预算")
        if not validate_evidence_artifact_refs(self.artifact_refs):
            errors["artifact_refs"] = _("工件引用必须是安全、有界且不重复的 opaque ref")
        if self.redacted_payload == {"externalized": True} and len(self.artifact_refs) != 1:
            errors["artifact_refs"] = _("外置证据必须绑定唯一且真实的工件引用")
        if self.occurred_at is None or timezone.is_naive(self.occurred_at):
            errors["occurred_at"] = _("证据时间必须是带时区时间")
        elif self.occurred_at > timezone.now() + timezone.timedelta(minutes=5):
            errors["occurred_at"] = _("证据时间不能位于未来")
        if self.is_deleted:
            errors["is_deleted"] = _("证据事件不能以删除状态插入")
        return errors

    def clean(self):
        """Validate the one allowed append operation."""
        super().clean()
        errors = self._validation_errors()
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Allow exactly one validated insert and reject later instance mutation."""
        if not self._state.adding:
            raise ValidationError("Evidence events are append-only")
        if kwargs.get("update_fields") is not None:
            raise ValidationError("New Evidence events do not support partial save")
        using = kwargs.get("using") or router.db_for_write(self.__class__, instance=self)
        if self.execution_id is not None:
            with transaction.atomic(using=using):
                try:
                    self.execution = (
                        ExecutionRun._base_manager.using(using).select_for_update().get(pk=self.execution_id)
                    )
                except ExecutionRun.DoesNotExist:
                    raise ValidationError({"execution": _("证据流程执行不存在")}) from None
                if EvidenceBundle._base_manager.using(using).filter(execution_id=self.execution_id).exists():
                    raise ValidationError({"execution": _("流程执行证据已经固化")})
                errors = self._validation_errors()
                if errors:
                    raise ValidationError(errors)
                kwargs["using"] = using
                return super().save(*args, **kwargs)
        errors = self._validation_errors()
        if errors:
            raise ValidationError(errors)
        kwargs["using"] = using
        return super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """Reject soft deletion of append-only evidence."""
        raise ValidationError("Evidence events are append-only")

    def hard_delete(self):
        """Reject physical deletion of append-only evidence."""
        raise ValidationError("Evidence events are append-only")


def _safe_optional_ref(value):
    """Accept an absent reference or one bounded non-credential opaque URI."""
    return value is None or is_safe_evidence_ref(value)


def _safe_optional_text(value, max_bytes):
    """Accept an absent governance coordinate or bounded non-secret text."""
    return value is None or is_bounded_non_secret_text(value, max_bytes)


def _safe_text_list(value, max_items=100, max_bytes=128):
    """Validate an ordered, duplicate-free list of bounded non-secret labels."""
    return (
        isinstance(value, list)
        and len(value) <= max_items
        and len(value) == len(set(value))
        and all(is_bounded_non_secret_text(item, max_bytes) for item in value)
    )


def _target_dimension_errors(instance):
    """Validate the exact authority coordinates implied by an optional knowledge tier."""
    dimensions = {
        "target_platform_key": instance.target_platform_key,
        "target_space_id": instance.target_space_id,
        "target_scope_type": instance.target_scope_type,
        "target_scope_value": instance.target_scope_value,
    }
    required_by_tier = {
        None: set(),
        KnowledgeTier.GLOBAL: set(),
        KnowledgeTier.PUBLIC: set(),
        KnowledgeTier.PLATFORM: {"target_platform_key"},
        KnowledgeTier.SPACE: {"target_platform_key", "target_space_id"},
        KnowledgeTier.SCOPE: {
            "target_platform_key",
            "target_space_id",
            "target_scope_type",
            "target_scope_value",
        },
    }
    required = required_by_tier.get(instance.target_tier)
    if required is None:
        return {"target_tier": _("未知候选目标知识层级")}
    errors = {}
    for field_name, value in dimensions.items():
        if field_name in required and value is None:
            errors[field_name] = _("目标知识层级必须提供此维度")
        elif field_name not in required and value is not None:
            errors[field_name] = _("目标知识层级不允许提供此维度")
    return errors


class GenerationFeedback(AppendOnlyAggregateMixin, CommonModel):
    """One immutable, consent-bound observation about an exact Harness revision."""

    id = models.UUIDField(_("生成反馈 ID"), primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(HarnessRun, verbose_name=_("运行"), on_delete=models.PROTECT, related_name="feedback")
    revision = models.ForeignKey(
        WorkflowPlanRevision,
        verbose_name=_("计划修订"),
        on_delete=models.PROTECT,
        related_name="feedback",
    )
    plan_hash = models.CharField(_("计划哈希"), max_length=64)
    execution = models.ForeignKey(
        ExecutionRun,
        verbose_name=_("流程执行"),
        on_delete=models.PROTECT,
        related_name="generation_feedback",
        null=True,
        blank=True,
    )
    evidence_bundle = models.ForeignKey(
        EvidenceBundle,
        verbose_name=_("证据包"),
        on_delete=models.PROTECT,
        related_name="generation_feedback",
        null=True,
        blank=True,
    )
    platform = models.CharField(_("平台"), max_length=64)
    platform_app = models.CharField(_("平台应用"), max_length=128)
    actor = models.CharField(_("反馈人"), max_length=128)
    space_id = models.IntegerField(_("空间 ID"), db_index=True)
    scope = models.CharField(_("授权范围"), max_length=MAX_SCOPE_KEY_LENGTH)
    target_environment = models.CharField(_("目标环境"), max_length=64)
    policy_version = models.CharField(_("策略版本"), max_length=64)
    feedback_type = models.CharField(_("反馈类型"), max_length=32, choices=GenerationFeedbackType.choices)
    rating = models.PositiveSmallIntegerField(
        _("评分"), null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    redacted_summary = models.TextField(_("脱敏摘要"))
    correction_artifact_ref = models.CharField(_("纠正工件引用"), max_length=255, null=True, blank=True)
    observed_outcome = models.JSONField(_("观测结果"), default=dict, blank=True)
    consent_scope = models.CharField(_("授权用途"), max_length=64)
    idempotency_digest = models.CharField(_("幂等摘要"), max_length=64)
    redaction_version = models.CharField(_("脱敏版本"), max_length=64, default=EVIDENCE_REDACTION_VERSION)

    objects = models.Manager.from_queryset(GovernedAggregateQuerySet)()

    class Meta:
        verbose_name = _("Harness 生成反馈")
        verbose_name_plural = verbose_name
        ordering = ["-create_at"]
        base_manager_name = "objects"
        constraints = [
            models.UniqueConstraint(
                fields=["platform_app", "actor", "space_id", "run", "idempotency_digest"],
                name="uniq_harness_feedback_identity_digest",
            )
        ]

    def clean(self):
        super().clean()
        errors = {}
        run = self.run if self.run_id else None
        revision = self.revision if self.revision_id else None
        if run is None or revision is None or revision.run_id != self.run_id:
            errors["revision"] = _("反馈必须绑定同一 Harness 运行的修订")
        elif self.plan_hash != revision.plan_hash:
            errors["plan_hash"] = _("反馈计划哈希与不可变修订不一致")
        if run is not None:
            trusted = {
                "platform": run.platform,
                "platform_app": run.platform_app,
                "actor": run.actor,
                "space_id": run.space_id,
                "scope": run.scope,
                "target_environment": run.environment,
                "policy_version": run.policy_version,
            }
            for field_name, expected in trusted.items():
                if getattr(self, field_name) != expected:
                    errors[field_name] = _("反馈可信上下文与 Harness 运行不一致")
        if self.execution_id is not None:
            execution = self.execution
            if execution.run_id != self.run_id or execution.revision_id != self.revision_id:
                errors["execution"] = _("反馈执行不属于目标运行和修订")
        if self.evidence_bundle_id is not None:
            bundle = self.evidence_bundle
            if bundle.run_id != self.run_id or bundle.revision_id != self.revision_id:
                errors["evidence_bundle"] = _("反馈证据包不属于目标运行和修订")
            if self.execution_id is not None and bundle.execution_id != self.execution_id:
                errors["evidence_bundle"] = _("反馈证据包与执行不一致")
        if self.feedback_type not in GenerationFeedbackType.values:
            errors["feedback_type"] = _("未知反馈类型")
        if self.rating is not None and (isinstance(self.rating, bool) or not 1 <= self.rating <= 5):
            errors["rating"] = _("评分必须位于 1 到 5")
        if not is_bounded_non_secret_text(self.redacted_summary, 8 * 1024):
            errors["redacted_summary"] = _("反馈摘要必须已脱敏且满足内联预算")
        if not _safe_optional_ref(self.correction_artifact_ref):
            errors["correction_artifact_ref"] = _("纠正工件引用不合法")
        if not validate_redacted_evidence_payload(self.observed_outcome):
            errors["observed_outcome"] = _("观测结果必须有界且不含秘密")
        if not is_bounded_non_secret_text(self.consent_scope, 64):
            errors["consent_scope"] = _("反馈授权用途不合法")
        if not _is_hex_64(self.idempotency_digest):
            errors["idempotency_digest"] = _("反馈幂等摘要不合法")
        if self.redaction_version != EVIDENCE_REDACTION_VERSION:
            errors["redaction_version"] = _("反馈必须使用内建脱敏版本")
        if errors:
            raise ValidationError(errors)


class ImprovementCandidateQuerySet(GovernedAggregateQuerySet):
    """Require candidate lifecycle changes to use locked instance services."""

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        raise ValidationError("Improvement candidates require controlled instance saves")


IMPROVEMENT_CANDIDATE_GOVERNANCE_TOKEN = object()


class ImprovementCandidate(CommonModel):
    """A versioned Owner-controlled proposal derived from immutable feedback and Evidence."""

    id = models.UUIDField(_("改进候选 ID"), primary_key=True, default=uuid.uuid4, editable=False)
    source_feedback = models.ForeignKey(
        GenerationFeedback,
        verbose_name=_("来源反馈"),
        on_delete=models.PROTECT,
        related_name="improvement_candidates",
    )
    source_evidence_bundle = models.ForeignKey(
        EvidenceBundle,
        verbose_name=_("来源证据包"),
        on_delete=models.PROTECT,
        related_name="improvement_candidates",
        null=True,
        blank=True,
    )
    candidate_type = models.CharField(_("候选类型"), max_length=32, choices=ImprovementCandidateType.choices)
    attribution = models.CharField(_("归因类型"), max_length=32, choices=FeedbackAttributionCategory.choices)
    proposal_artifact_ref = models.CharField(_("脱敏提案工件"), max_length=255)
    owner_ref = models.CharField(_("负责人引用"), max_length=128, null=True, blank=True)
    reviewer_ref = models.CharField(_("审核人引用"), max_length=128, null=True, blank=True)
    target_system = models.CharField(_("目标系统"), max_length=128)
    target_tier = models.CharField(_("目标知识层级"), max_length=16, choices=KnowledgeTier.choices, null=True, blank=True)
    target_platform_key = models.CharField(_("目标平台"), max_length=64, null=True, blank=True)
    target_space_id = models.IntegerField(_("目标空间 ID"), null=True, blank=True, db_index=True)
    target_scope_type = models.CharField(_("目标范围类型"), max_length=64, null=True, blank=True)
    target_scope_value = models.CharField(_("目标范围值"), max_length=MAX_SCOPE_KEY_LENGTH, null=True, blank=True)
    status = models.CharField(
        _("候选状态"),
        max_length=16,
        choices=ImprovementCandidateStatus.choices,
        default=ImprovementCandidateStatus.DRAFT,
    )
    risk = models.CharField(_("风险等级"), max_length=2, choices=RiskLevel.choices)
    confidence = models.FloatField(_("归因置信度"), validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    regression_case_refs = models.JSONField(_("回归用例引用"), default=list, blank=True)
    impact_artifact_ref = models.CharField(_("影响分析工件"), max_length=255, null=True, blank=True)
    rollback_artifact_ref = models.CharField(_("回滚工件"), max_length=255, null=True, blank=True)
    source_version = models.CharField(_("来源版本"), max_length=128)
    current_version = models.CharField(_("当前版本"), max_length=128)
    target_version = models.CharField(_("目标版本"), max_length=128)
    promotion_receipt_digest = models.CharField(_("晋级回执摘要"), max_length=64, null=True, blank=True)
    parent_candidate = models.ForeignKey(
        "self",
        verbose_name=_("父候选"),
        on_delete=models.PROTECT,
        related_name="revisions",
        null=True,
        blank=True,
    )
    revision_number = models.PositiveIntegerField(_("候选修订序号"), default=1)

    objects = models.Manager.from_queryset(ImprovementCandidateQuerySet)()

    IMMUTABLE_FIELDS = frozenset(
        {
            "source_feedback_id",
            "source_evidence_bundle_id",
            "candidate_type",
            "attribution",
            "proposal_artifact_ref",
            "owner_ref",
            "reviewer_ref",
            "target_system",
            "target_tier",
            "target_platform_key",
            "target_space_id",
            "target_scope_type",
            "target_scope_value",
            "risk",
            "confidence",
            "regression_case_refs",
            "impact_artifact_ref",
            "rollback_artifact_ref",
            "source_version",
            "current_version",
            "target_version",
            "parent_candidate_id",
            "revision_number",
        }
    )

    class Meta:
        verbose_name = _("Harness 改进候选")
        verbose_name_plural = verbose_name
        ordering = ["-create_at"]
        base_manager_name = "objects"

    def clean(self):
        super().clean()
        errors = _target_dimension_errors(self)
        feedback = self.source_feedback if self.source_feedback_id else None
        if feedback is None:
            errors["source_feedback"] = _("候选必须绑定来源反馈")
        if self.source_evidence_bundle_id is not None and feedback is not None:
            evidence = self.source_evidence_bundle
            if evidence.run_id != feedback.run_id or evidence.revision_id != feedback.revision_id:
                errors["source_evidence_bundle"] = _("候选证据与来源反馈不一致")
        if self.candidate_type not in ImprovementCandidateType.values:
            errors["candidate_type"] = _("未知候选类型")
        if self.attribution not in FeedbackAttributionCategory.values:
            errors["attribution"] = _("未知候选归因")
        if not is_safe_evidence_ref(self.proposal_artifact_ref):
            errors["proposal_artifact_ref"] = _("候选提案工件引用不合法")
        for field_name in ("owner_ref", "reviewer_ref"):
            if not _safe_optional_text(getattr(self, field_name), 128):
                errors[field_name] = _("候选治理引用必须是有界非秘密文本")
        if (self.owner_ref is None) != (self.reviewer_ref is None):
            errors["reviewer_ref"] = _("候选负责人和审核人必须同时解析")
        elif self.owner_ref is not None and self.owner_ref == self.reviewer_ref:
            errors["reviewer_ref"] = _("候选负责人和审核人必须不同")
        if self.status != ImprovementCandidateStatus.DRAFT and self.owner_ref is None:
            errors["owner_ref"] = _("未解析 Owner 的候选只能停留在 DRAFT")
        if not is_bounded_non_secret_text(self.target_system, 128):
            errors["target_system"] = _("候选目标系统不合法")
        for field_name, max_bytes in (
            ("target_platform_key", 64),
            ("target_scope_type", 64),
            ("target_scope_value", MAX_SCOPE_KEY_LENGTH),
        ):
            if not _safe_optional_text(getattr(self, field_name), max_bytes):
                errors[field_name] = _("候选目标维度不合法")
        if self.status not in ImprovementCandidateStatus.values:
            errors["status"] = _("未知候选状态")
        if self.risk not in RiskLevel.values:
            errors["risk"] = _("未知候选风险")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not 0 <= self.confidence <= 1
        ):
            errors["confidence"] = _("候选归因置信度必须位于 0 到 1")
        if not _safe_ref_list(self.regression_case_refs):
            errors["regression_case_refs"] = _("候选回归用例引用不合法")
        for field_name in ("impact_artifact_ref", "rollback_artifact_ref"):
            if not _safe_optional_ref(getattr(self, field_name)):
                errors[field_name] = _("候选工件引用不合法")
        for field_name in ("source_version", "current_version", "target_version"):
            if not is_bounded_non_secret_text(getattr(self, field_name), 128):
                errors[field_name] = _("候选版本必须是有界非秘密文本")
        if self.promotion_receipt_digest is not None and not _is_hex_64(self.promotion_receipt_digest):
            errors["promotion_receipt_digest"] = _("晋级回执摘要不合法")
        if self.revision_number < 1:
            errors["revision_number"] = _("候选修订序号必须为正整数")
        if self.parent_candidate_id is None and self.revision_number != 1:
            errors["revision_number"] = _("首个候选修订序号必须为 1")
        if self.parent_candidate_id is not None:
            parent = self.parent_candidate
            if (
                parent.source_feedback_id != self.source_feedback_id
                or parent.candidate_type != self.candidate_type
                or self.revision_number != parent.revision_number + 1
            ):
                errors["parent_candidate"] = _("候选修订谱系不一致")
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Keep proposal revisions immutable and lifecycle writes inside the locked service."""
        governance_token = kwargs.pop("_governance_token", None)
        if self._state.adding:
            if kwargs.get("update_fields") is not None:
                raise ValidationError("New improvement candidates do not support partial save")
            if self.status != ImprovementCandidateStatus.DRAFT or self.promotion_receipt_digest is not None:
                raise ValidationError("New improvement candidates must begin as DRAFT")
            self.full_clean()
            return super().save(*args, **kwargs)

        using = kwargs.get("using") or router.db_for_write(self.__class__, instance=self)
        with transaction.atomic(using=using):
            persisted = self.__class__._base_manager.using(using).select_for_update().get(pk=self.pk)
            immutable_changes = [
                field_name
                for field_name in self.IMMUTABLE_FIELDS
                if getattr(self, field_name) != getattr(persisted, field_name)
            ]
            if immutable_changes:
                raise ValidationError(
                    {field_name: _("已持久化提案变更必须创建 new candidate revision") for field_name in immutable_changes}
                )
            status_changed = self.status != persisted.status
            receipt_changed = self.promotion_receipt_digest != persisted.promotion_receipt_digest
            if (status_changed or receipt_changed) and governance_token is not IMPROVEMENT_CANDIDATE_GOVERNANCE_TOKEN:
                raise ValidationError("Improvement candidate lifecycle requires governance service")
            allowed = {
                ImprovementCandidateStatus.DRAFT: {ImprovementCandidateStatus.IN_REVIEW},
                ImprovementCandidateStatus.IN_REVIEW: {
                    ImprovementCandidateStatus.APPROVED,
                    ImprovementCandidateStatus.REJECTED,
                },
                ImprovementCandidateStatus.APPROVED: {ImprovementCandidateStatus.PUBLISHED},
                ImprovementCandidateStatus.PUBLISHED: {ImprovementCandidateStatus.RETIRED},
            }
            if status_changed and self.status not in allowed.get(persisted.status, set()):
                raise ValidationError({"status": _("非法改进候选生命周期迁移")})
            publishing = (
                persisted.status == ImprovementCandidateStatus.APPROVED
                and self.status == ImprovementCandidateStatus.PUBLISHED
            )
            if receipt_changed and (
                not publishing
                or persisted.promotion_receipt_digest is not None
                or self.promotion_receipt_digest is None
            ):
                raise ValidationError({"promotion_receipt_digest": _("晋级回执摘要只能在发布确认时写入一次")})
            if publishing and not receipt_changed:
                raise ValidationError({"promotion_receipt_digest": _("发布确认必须写入晋级回执摘要")})
            self.full_clean()
            update_fields = kwargs.get("update_fields")
            changed = set()
            if status_changed:
                changed.add("status")
            if receipt_changed:
                changed.add("promotion_receipt_digest")
            if update_fields is not None and changed - set(update_fields):
                raise ValidationError({"update_fields": _("部分保存遗漏候选生命周期字段")})
            kwargs["using"] = using
            return super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        raise ValidationError("Improvement candidates cannot be deleted")

    def hard_delete(self):
        raise ValidationError("Improvement candidates cannot be deleted")


class KnowledgeCandidate(AppendOnlyAggregateMixin, CommonModel):
    """Metadata-only knowledge proposal bound to an external governed source."""

    candidate = models.OneToOneField(
        ImprovementCandidate,
        verbose_name=_("改进候选"),
        on_delete=models.PROTECT,
        related_name="knowledge_candidate",
        primary_key=True,
    )
    target_binding = models.ForeignKey(
        KnowledgeSourceBinding,
        verbose_name=_("目标知识绑定"),
        on_delete=models.PROTECT,
        related_name="knowledge_candidates",
    )
    target_source_ref = models.TextField(_("目标知识源引用"))
    proposed_snapshot_lineage = models.JSONField(_("建议快照谱系"), default=dict)
    citation_refs = models.JSONField(_("引用来源"), default=list, blank=True)
    conflict_set = models.JSONField(_("冲突引用"), default=list, blank=True)

    objects = models.Manager.from_queryset(GovernedAggregateQuerySet)()

    class Meta:
        verbose_name = _("Harness 知识改进候选")
        verbose_name_plural = verbose_name
        base_manager_name = "objects"

    def clean(self):
        super().clean()
        errors = {}
        candidate = self.candidate if self.candidate_id else None
        binding = self.target_binding if self.target_binding_id else None
        if candidate is None or candidate.candidate_type != ImprovementCandidateType.KNOWLEDGE:
            errors["candidate"] = _("知识候选必须绑定 KNOWLEDGE 类型改进候选")
        if binding is None:
            errors["target_binding"] = _("知识候选必须绑定目标知识源")
        elif candidate is not None:
            expected = {
                "target_tier": binding.tier,
                "target_platform_key": binding.platform_key,
                "target_space_id": binding.space_id,
                "target_scope_type": binding.scope_type,
                "target_scope_value": binding.scope_value,
            }
            if any(getattr(candidate, name) != value for name, value in expected.items()):
                errors["target_binding"] = _("目标知识绑定与候选层级或范围不一致")
            if self.target_source_ref != binding.source_ref:
                errors["target_source_ref"] = _("目标知识源引用与治理绑定不一致")
            if candidate.source_feedback.space_id != binding.space_id and binding.space_id is not None:
                errors["target_binding"] = _("知识候选不得跨空间绑定")
        allowed_lineage_keys = {"parent", "proposed", "provider_revision"}
        if (
            not is_bounded_non_secret_json(self.proposed_snapshot_lineage)
            or set(self.proposed_snapshot_lineage) - allowed_lineage_keys
            or not {"parent", "proposed"}.issubset(self.proposed_snapshot_lineage)
        ):
            errors["proposed_snapshot_lineage"] = _("知识候选快照谱系不合法")
        elif binding is not None and self.proposed_snapshot_lineage["parent"] != binding.snapshot_version:
            errors["proposed_snapshot_lineage"] = _("知识候选父快照与当前绑定不一致")
        if not _safe_ref_list(self.citation_refs):
            errors["citation_refs"] = _("知识候选引用不合法")
        if not _safe_ref_list(self.conflict_set):
            errors["conflict_set"] = _("知识候选冲突集不合法")
        if errors:
            raise ValidationError(errors)


class HarnessEvalCase(AppendOnlyAggregateMixin, CommonModel):
    """One immutable, sanitized, hash-addressed evaluation fixture."""

    id = models.UUIDField(_("评测用例 ID"), primary_key=True, default=uuid.uuid4, editable=False)
    case_id = models.CharField(_("用例标识"), max_length=128)
    case_version = models.CharField(_("用例版本"), max_length=64)
    source_candidate = models.ForeignKey(
        ImprovementCandidate,
        verbose_name=_("来源候选"),
        on_delete=models.PROTECT,
        related_name="eval_cases",
    )
    tier = models.CharField(_("适用知识层级"), max_length=16, choices=KnowledgeTier.choices, null=True, blank=True)
    scope = models.CharField(_("适用范围"), max_length=MAX_SCOPE_KEY_LENGTH)
    sanitized_input_artifact_ref = models.CharField(_("脱敏输入工件"), max_length=255)
    expected_invariants = models.JSONField(_("预期不变量"), default=dict)
    scoring_schema = models.JSONField(_("评分 Schema"), default=dict)
    safety_tags = models.JSONField(_("安全标签"), default=list, blank=True)
    fixture_hash = models.CharField(_("Fixture 哈希"), max_length=64, unique=True, editable=False, blank=True, default="")

    objects = models.Manager.from_queryset(GovernedAggregateQuerySet)()

    class Meta:
        verbose_name = _("Harness 评测用例")
        verbose_name_plural = verbose_name
        ordering = ["case_id", "case_version"]
        base_manager_name = "objects"
        constraints = [
            models.UniqueConstraint(fields=["case_id", "case_version"], name="uniq_harness_eval_case_version")
        ]

    def clean(self):
        super().clean()
        errors = {}
        if safe_opaque_identifier(self.case_id) is None:
            errors["case_id"] = _("评测用例标识不合法")
        if safe_opaque_identifier(self.case_version) is None:
            errors["case_version"] = _("评测用例版本不合法")
        if self.tier is not None and self.tier not in KnowledgeTier.values:
            errors["tier"] = _("评测知识层级不合法")
        if not is_bounded_non_secret_text(self.scope, MAX_SCOPE_KEY_LENGTH):
            errors["scope"] = _("评测适用范围不合法")
        if not is_safe_evidence_ref(self.sanitized_input_artifact_ref):
            errors["sanitized_input_artifact_ref"] = _("评测输入工件引用不合法")
        if not is_bounded_non_secret_json(self.expected_invariants):
            errors["expected_invariants"] = _("评测不变量必须有界且不含秘密")
        if not is_bounded_non_secret_json(self.scoring_schema):
            errors["scoring_schema"] = _("评测评分 Schema 必须有界且不含秘密")
        if not _safe_text_list(self.safety_tags, max_items=32, max_bytes=64):
            errors["safety_tags"] = _("评测安全标签不合法")
        payload = {
            "case_id": self.case_id,
            "case_version": self.case_version,
            "source_candidate_id": str(self.source_candidate_id),
            "tier": self.tier,
            "scope": self.scope,
            "sanitized_input_artifact_ref": self.sanitized_input_artifact_ref,
            "expected_invariants": self.expected_invariants,
            "scoring_schema": self.scoring_schema,
            "safety_tags": self.safety_tags,
        }
        derived_hash = _canonical_sha256(payload)
        if self.fixture_hash and self.fixture_hash != derived_hash:
            errors["fixture_hash"] = _("评测 Fixture 哈希不一致")
        self.fixture_hash = derived_hash
        if errors:
            raise ValidationError(errors)


class HarnessEvalRunQuerySet(GovernedAggregateQuerySet):
    """Require evaluation state changes to use controlled instance services."""

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        raise ValidationError("Evaluation runs require controlled instance saves")


class HarnessEvalRun(CommonModel):
    """Version-bound local or signed BKAIDev evaluation result."""

    class RunnerMode(models.TextChoices):
        LOCAL_DETERMINISTIC = "LOCAL_DETERMINISTIC", "Local deterministic"
        SIGNED_BKAIDEV = "SIGNED_BKAIDEV", "Signed BKAIDev"

    class SafetyResult(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PASSED = "PASSED", "Passed"
        FAILED = "FAILED", "Failed"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        PASSED = "PASSED", "Passed"
        FAILED = "FAILED", "Failed"
        BLOCKED = "BLOCKED", "Blocked"

    id = models.UUIDField(_("评测运行 ID"), primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(
        ImprovementCandidate,
        verbose_name=_("改进候选"),
        on_delete=models.PROTECT,
        related_name="eval_runs",
    )
    base_release_version = models.CharField(_("基线发布版本"), max_length=128)
    candidate_release_version = models.CharField(_("候选发布版本"), max_length=128)
    runner_mode = models.CharField(_("Runner 模式"), max_length=32, choices=RunnerMode.choices)
    package_hash = models.CharField(_("评测包哈希"), max_length=64)
    result_hash = models.CharField(_("评测结果哈希"), max_length=64, null=True, blank=True)
    signed_result_ref = models.CharField(_("签名结果引用"), max_length=255, null=True, blank=True)
    signed_result_digest = models.CharField(_("签名结果摘要"), max_length=64, null=True, blank=True)
    aggregate_metrics = models.JSONField(_("聚合指标"), default=dict, blank=True)
    safety_result = models.CharField(
        _("安全结果"), max_length=16, choices=SafetyResult.choices, default=SafetyResult.PENDING
    )
    threshold_snapshot = models.JSONField(_("门禁阈值快照"), default=dict)
    status = models.CharField(_("评测状态"), max_length=16, choices=Status.choices, default=Status.PENDING)
    started_at = models.DateTimeField(_("开始时间"), null=True, blank=True)
    finalized_at = models.DateTimeField(_("完成时间"), null=True, blank=True)

    objects = models.Manager.from_queryset(HarnessEvalRunQuerySet)()

    class Meta:
        verbose_name = _("Harness 评测运行")
        verbose_name_plural = verbose_name
        ordering = ["-create_at"]
        base_manager_name = "objects"
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "runner_mode", "package_hash"],
                name="uniq_harness_eval_candidate_package",
            )
        ]

    def clean(self):
        super().clean()
        errors = {}
        for field_name in ("base_release_version", "candidate_release_version"):
            if not is_bounded_non_secret_text(getattr(self, field_name), 128):
                errors[field_name] = _("评测发布版本不合法")
        if self.runner_mode not in self.RunnerMode.values:
            errors["runner_mode"] = _("未知评测 Runner 模式")
        if not _is_hex_64(self.package_hash):
            errors["package_hash"] = _("评测包哈希不合法")
        if self.result_hash is not None and not _is_hex_64(self.result_hash):
            errors["result_hash"] = _("评测结果哈希不合法")
        if not _safe_optional_ref(self.signed_result_ref):
            errors["signed_result_ref"] = _("签名评测结果引用不合法")
        if self.signed_result_digest is not None and not _is_hex_64(self.signed_result_digest):
            errors["signed_result_digest"] = _("签名评测结果摘要不合法")
        if not is_bounded_non_secret_json(self.aggregate_metrics):
            errors["aggregate_metrics"] = _("评测聚合指标必须有界且不含秘密")
        if not is_bounded_non_secret_json(self.threshold_snapshot):
            errors["threshold_snapshot"] = _("评测门禁阈值必须有界且不含秘密")
        if self.safety_result not in self.SafetyResult.values:
            errors["safety_result"] = _("未知评测安全结果")
        if self.status not in self.Status.values:
            errors["status"] = _("未知评测状态")
        terminal = self.status in {self.Status.PASSED, self.Status.FAILED, self.Status.BLOCKED}
        if terminal != (self.finalized_at is not None):
            errors["finalized_at"] = _("评测终态与完成时间必须一致")
        for field_name in ("started_at", "finalized_at"):
            value = getattr(self, field_name)
            if value is not None and timezone.is_naive(value):
                errors[field_name] = _("评测时间必须带时区")
        if self.started_at is not None and self.finalized_at is not None and self.finalized_at < self.started_at:
            errors["finalized_at"] = _("评测完成时间不能早于开始时间")
        if terminal and self.result_hash is None:
            errors["result_hash"] = _("评测终态必须绑定结果哈希")
        if self.status == self.Status.PASSED and self.safety_result != self.SafetyResult.PASSED:
            errors["safety_result"] = _("评测通过必须同时通过安全门禁")
        if self.runner_mode == self.RunnerMode.SIGNED_BKAIDEV and self.status == self.Status.PASSED:
            if self.signed_result_ref is None or self.signed_result_digest is None:
                errors["signed_result_ref"] = _("BKAIDev 评测通过必须绑定签名结果")
        if self.runner_mode == self.RunnerMode.LOCAL_DETERMINISTIC and (
            self.signed_result_ref is not None or self.signed_result_digest is not None
        ):
            errors["signed_result_ref"] = _("本地确定性评测不能伪造外部签名")
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Validate every Eval write; Task 8 adds the runner transition service."""
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        raise ValidationError("Evaluation runs cannot be deleted")

    def hard_delete(self):
        raise ValidationError("Evaluation runs cannot be deleted")
