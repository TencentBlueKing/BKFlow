"""Compatibility-preserving task creation domain service."""

from copy import deepcopy
from dataclasses import dataclass

from webhook.signals import event_broadcast_signal

from bkflow.constants import TaskTriggerMethod, WebhookEventType, WebhookScopeType
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.label.models import Label
from bkflow.label.serializers import LabelSerializer
from bkflow.plugin.services.open_plugin_snapshot import OpenPluginSnapshotService
from bkflow.space.models import Space
from bkflow.template.models import Template, TemplateSnapshot
from bkflow.template.tenant import validate_template_references

DEFAULT_NOTIFY_CONFIG = {
    "notify_type": {"fail": [], "success": []},
    "notify_receivers": {"more_receiver": "", "receiver_group": []},
}


class TaskCreationRejected(RuntimeError):
    """Engine explicitly rejected a create request."""


class TaskCreationUncertain(RuntimeError):
    """Engine response could not prove whether task creation succeeded."""


@dataclass(frozen=True)
class TaskCreationReceipt:
    """Secret-free result used by Harness execution orchestration."""

    task_ref: str
    status: str = "CREATED"
    warnings: tuple = ()

    def as_dict(self):
        result = {"task_ref": self.task_ref, "status": self.status}
        if self.warnings:
            result["warnings"] = list(self.warnings)
        return result


class TaskCreator:
    """Build and dispatch one Engine task from an explicitly selected snapshot."""

    def __init__(self, *, client_factory=None, snapshot_preparer=None):
        self._client_factory = client_factory or TaskComponentClient
        self._snapshot_preparer = snapshot_preparer or OpenPluginSnapshotService.prepare_task_extra_info

    def _build_payload(self, *, template, snapshot, request_data, actor):
        payload = deepcopy(dict(request_data))
        pipeline_tree = deepcopy(snapshot.data)
        validate_template_references(template.space_id, pipeline_tree)
        payload["scope_type"] = template.scope_type
        payload["scope_value"] = template.scope_value
        payload["space_id"] = template.space_id
        payload["tenant_id"] = Space.objects.get(id=template.space_id).tenant_id
        payload["pipeline_tree"] = pipeline_tree
        payload["trigger_method"] = TaskTriggerMethod.api.name
        payload.setdefault("extra_info", {}).update(
            {"notify_config": deepcopy(template.notify_config or DEFAULT_NOTIFY_CONFIG)}
        )
        payload["extra_info"] = self._snapshot_preparer(
            space_id=int(template.space_id),
            pipeline_tree=pipeline_tree,
            extra_info=payload.get("extra_info"),
            username=actor,
            scope_type=template.scope_type,
            scope_id=template.scope_value,
        )
        credentials = request_data.get("credentials", {})
        if credentials:
            payload.setdefault("extra_info", {}).setdefault("custom_context", {})["credentials"] = deepcopy(credentials)
        custom_span_attributes = request_data.get("custom_span_attributes", {})
        if custom_span_attributes:
            payload.setdefault("extra_info", {}).setdefault("custom_context", {})["custom_span_attributes"] = deepcopy(
                custom_span_attributes
            )
        return payload

    def _dispatch(self, *, template, snapshot, request_data, actor):
        payload = self._build_payload(
            template=template,
            snapshot=snapshot,
            request_data=request_data,
            actor=actor,
        )
        client = self._client_factory(space_id=template.space_id)
        return client.create_task(payload)

    @staticmethod
    def _enrich_and_notify(*, result, request_data, template):
        if not result.get("result") or not isinstance(result.get("data"), dict):
            return result
        label_ids = list(dict.fromkeys(request_data.get("label_ids") or []))
        if label_ids:
            labels = Label.objects.filter(id__in=label_ids)
            result["data"]["labels"] = LabelSerializer(labels, many=True).data
        else:
            result["data"]["labels"] = []
        task_data = result["data"]
        event_broadcast_signal.send(
            sender=WebhookEventType.TASK_CREATE.value,
            scopes=[(WebhookScopeType.SPACE.value, str(template.space_id))],
            extra_info={
                "task_id": task_data["id"],
                "task_name": task_data["name"],
                "template_id": task_data["template_id"],
                "parameters": task_data["parameters"],
                "trigger_source": TaskTriggerMethod.api.name,
            },
        )
        return result

    def create_from_current_template(self, *, template, request_data, actor):
        """Legacy entry: preserve the current-template APIGW response contract."""
        result = self._dispatch(
            template=template,
            snapshot=template.snapshot,
            request_data=request_data,
            actor=actor,
        )
        return self._enrich_and_notify(result=result, request_data=request_data, template=template)

    def create_from_publication(self, *, publication, request_data, actor):
        """Harness entry: create only from the immutable publication snapshot."""
        template = Template.objects.get(id=publication.published_template_id, is_deleted=False)
        snapshot = TemplateSnapshot.objects.get(id=publication.published_snapshot_id, is_deleted=False)
        if snapshot.template_id != template.id:
            raise ValueError("publication snapshot does not belong to template")
        if snapshot.version != publication.published_version or snapshot.draft:
            raise ValueError("publication snapshot does not match published version")
        trusted_request = deepcopy(dict(request_data))
        trusted_request["template_id"] = template.id
        trusted_request["creator"] = actor
        result = self._dispatch(
            template=template,
            snapshot=snapshot,
            request_data=trusted_request,
            actor=actor,
        )
        if not isinstance(result, dict) or result.get("result") is not True or not isinstance(result.get("data"), dict):
            raise TaskCreationUncertain()
        if not result["data"].get("id"):
            raise TaskCreationUncertain()
        task_ref = str(result["data"]["id"])
        warnings = ()
        try:
            self._enrich_and_notify(result=result, request_data=trusted_request, template=template)
        except Exception:
            warnings = ("TASK_CREATE_NOTIFICATION_FAILED",)
        return TaskCreationReceipt(task_ref=task_ref, warnings=warnings)


__all__ = ["TaskCreationReceipt", "TaskCreationRejected", "TaskCreationUncertain", "TaskCreator"]
