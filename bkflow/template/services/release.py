"""Atomic template publication shared by UI, APIGW, and Harness callers."""

import logging

from django.db import transaction
from webhook.signals import event_broadcast_signal

from bkflow.constants import (
    TemplateOperationSource,
    TemplateOperationType,
    WebhookEventType,
    WebhookScopeType,
)
from bkflow.exceptions import ValidationError
from bkflow.space.configs import FlowVersioning
from bkflow.space.models import SpaceConfig
from bkflow.template.models import Template, TemplateOperationRecord, TemplateSnapshot
from bkflow.utils.version import bump_custom

logger = logging.getLogger("root")


class TemplateReleaseService:
    """Publish one exact template draft and its audit record atomically."""

    @staticmethod
    def _dispatch_webhook(space_id, template_id, version, operator):
        """Dispatch after commit without rewriting an already committed result."""
        try:
            event_broadcast_signal.send(
                sender=WebhookEventType.TEMPLATE_RELEASE.value,
                scopes=[(WebhookScopeType.SPACE.value, str(space_id))],
                extra_info={"template_id": template_id, "version": version, "username": operator},
            )
        except Exception:
            logger.exception(
                "[TemplateReleaseService] post-commit release webhook failed template_id=%s version=%s",
                template_id,
                version,
            )

    @classmethod
    def release(
        cls,
        template,
        release_data,
        operator,
        source,
        *,
        emit_webhook=True,
        expected_draft_snapshot_id=None,
    ):
        """Publish the locked template's exact draft and return its snapshot."""
        data = dict(release_data or {})
        version = data.get("version")
        force = data.get("force", False)
        if not version:
            raise ValidationError("版本号不能为空")
        if not isinstance(force, bool):
            raise ValidationError("force 参数不合法")
        if source not in {TemplateOperationSource.app.name, TemplateOperationSource.api.name}:
            raise ValidationError("发布操作来源不合法")

        with transaction.atomic():
            locked = Template.objects.select_for_update().get(pk=template.pk)
            if SpaceConfig.get_config(space_id=locked.space_id, config_name=FlowVersioning.name) != "true":
                raise ValidationError("当前空间未开启版本管理，无法发布模板")
            if TemplateSnapshot.objects.filter(template_id=locked.id, version=version).exists():
                raise ValidationError("版本已存在")
            try:
                bump_custom(version, locked.version)
            except ValueError as error:
                raise ValidationError("版本号不符合规范: {}".format(error)) from None

            drafts = TemplateSnapshot.objects.select_for_update().filter(template_id=locked.id, draft=True)
            draft = drafts.first()
            if drafts.count() > 1:
                raise ValidationError("模板存在多个草稿版本")
            if expected_draft_snapshot_id is not None and (draft is None or draft.id != expected_draft_snapshot_id):
                raise ValidationError("待发布草稿已变化")
            if draft is None and not force:
                raise ValidationError("该模板{}没有草稿版本".format(locked.id))

            payload = {"username": operator, **data}
            snapshot = locked.release_template(payload)
            locked.snapshot_id = snapshot.id
            locked.save(update_fields=["snapshot_id", "update_at"])
            TemplateOperationRecord.objects.create(
                operate_source=source,
                operate_type=TemplateOperationType.release.name,
                instance_id=locked.id,
                operator=operator,
                extra_info={"version": version},
            )
            if emit_webhook:
                transaction.on_commit(lambda: cls._dispatch_webhook(locked.space_id, locked.id, version, operator))

        template.snapshot_id = snapshot.id
        return snapshot


__all__ = ["TemplateReleaseService"]
