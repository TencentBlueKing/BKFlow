from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError

from bkflow.constants import TaskTriggerMethod, WebhookEventType, WebhookScopeType
from bkflow.space.models import Space
from bkflow.task.services.task_creator import TaskCreationUncertain, TaskCreator
from bkflow.template.models import Template, TemplateSnapshot

PIPELINE_TREE = {
    "activities": {},
    "gateways": {},
    "end_event": {"id": "end"},
    "flows": {},
    "start_event": {"id": "start"},
    "constants": {},
}


class TaskCreatorTestCase(TestCase):
    def setUp(self):
        self.space = Space.objects.create(app_code="task-creator", platform_url="http://test", name="task creator")
        snapshot = TemplateSnapshot.create_snapshot(
            pipeline_tree=deepcopy(PIPELINE_TREE), username="owner", version="1.0.0"
        )
        self.template = Template.objects.create(
            name="flow",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="owner",
            scope_type="project",
            scope_value="scope-1",
            notify_config={"notify_type": {"fail": ["weixin"], "success": []}},
        )
        snapshot.template_id = self.template.id
        snapshot.save(update_fields=["template_id"])

    def test_current_template_preserves_legacy_payload_and_defensively_copies_tree(self):
        self.space.tenant_id = "tenant-a"
        self.space.save(update_fields=["tenant_id"])
        engine = mock.Mock()
        engine.create_task.return_value = {
            "result": True,
            "data": {
                "id": 42,
                "name": "task",
                "template_id": self.template.id,
                "parameters": {"visible": "ok"},
            },
        }
        prepared_trees = []

        def prepare_snapshot(**kwargs):
            prepared_trees.append(kwargs["pipeline_tree"])
            kwargs["pipeline_tree"]["mutated_by_preparer"] = True
            result = deepcopy(kwargs["extra_info"])
            result["open_plugin_snapshots"] = {"n1": {"version": "1.0.0"}}
            return result

        creator = TaskCreator(client_factory=lambda **kwargs: engine, snapshot_preparer=prepare_snapshot)
        request_data = {
            "template_id": self.template.id,
            "name": "task",
            "creator": "legacy-user",
            "constants": {"${x}": "value"},
            "credentials": {"cred": {"username": "u", "password": "p"}},
            "custom_span_attributes": {"trace": "safe"},
            "label_ids": [],
            "extra_info": {"custom_context": {"legacy": "kept"}},
        }
        original_request = deepcopy(request_data)

        result = creator.create_from_current_template(
            template=self.template,
            request_data=request_data,
            actor="gateway-user",
        )

        self.assertEqual(result, engine.create_task.return_value)
        engine.create_task.assert_called_once()
        payload = engine.create_task.call_args.args[0]
        self.assertEqual(payload["space_id"], self.space.id)
        self.assertEqual(payload["tenant_id"], "tenant-a")
        self.assertEqual(payload["scope_type"], "project")
        self.assertEqual(payload["scope_value"], "scope-1")
        self.assertEqual(payload["trigger_method"], TaskTriggerMethod.api.name)
        self.assertEqual(payload["creator"], "legacy-user")
        self.assertEqual(payload["extra_info"]["notify_config"], self.template.notify_config)
        self.assertEqual(payload["extra_info"]["custom_context"]["credentials"], request_data["credentials"])
        self.assertEqual(
            payload["extra_info"]["custom_context"]["custom_span_attributes"],
            request_data["custom_span_attributes"],
        )
        self.assertEqual(payload["extra_info"]["custom_context"]["legacy"], "kept")
        self.assertEqual(request_data, original_request)
        self.assertNotIn("mutated_by_preparer", self.template.pipeline_tree)
        self.assertIsNot(prepared_trees[0], self.template.pipeline_tree)

    @mock.patch("bkflow.task.services.task_creator.event_broadcast_signal.send")
    def test_current_template_enriches_labels_and_emits_legacy_task_create(self, send):
        engine = mock.Mock()
        engine.create_task.return_value = {
            "result": True,
            "data": {
                "id": 43,
                "name": "task",
                "template_id": self.template.id,
                "parameters": {"${x}": "value"},
            },
        }
        creator = TaskCreator(
            client_factory=lambda **kwargs: engine, snapshot_preparer=lambda **kwargs: kwargs["extra_info"]
        )

        result = creator.create_from_current_template(
            template=self.template,
            request_data={"template_id": self.template.id, "name": "task", "creator": "legacy-user"},
            actor="gateway-user",
        )

        self.assertEqual(result["data"]["labels"], [])
        send.assert_called_once_with(
            sender=WebhookEventType.TASK_CREATE.value,
            scopes=[(WebhookScopeType.SPACE.value, str(self.space.id))],
            extra_info={
                "task_id": 43,
                "task_name": "task",
                "template_id": self.template.id,
                "parameters": {"${x}": "value"},
                "trigger_source": TaskTriggerMethod.api.name,
            },
        )

    def test_publication_entry_uses_exact_published_snapshot_and_returns_safe_receipt(self):
        self.space.tenant_id = "tenant-a"
        self.space.save(update_fields=["tenant_id"])
        published = self.template.snapshot
        later = TemplateSnapshot.create_snapshot(
            pipeline_tree={**deepcopy(PIPELINE_TREE), "later": True}, username="owner", version="2.0.0"
        )
        later.template_id = self.template.id
        later.save(update_fields=["template_id"])
        self.template.snapshot_id = later.id
        self.template.save(update_fields=["snapshot_id"])
        publication = SimpleNamespace(
            published_template_id=self.template.id,
            published_snapshot_id=published.id,
            published_version="1.0.0",
        )
        engine = mock.Mock()
        engine.create_task.return_value = {
            "result": True,
            "data": {
                "id": 44,
                "name": "task",
                "template_id": self.template.id,
                "parameters": {"secret": "must-not-return"},
            },
        }
        creator = TaskCreator(
            client_factory=lambda **kwargs: engine, snapshot_preparer=lambda **kwargs: kwargs["extra_info"]
        )

        receipt = creator.create_from_publication(
            publication=publication,
            request_data={"name": "task", "creator": "harness-user"},
            actor="harness-user",
        )

        self.assertEqual(receipt.task_ref, "44")
        self.assertEqual(receipt.status, "CREATED")
        self.assertEqual(receipt.as_dict(), {"task_ref": "44", "status": "CREATED"})
        sent = engine.create_task.call_args.args[0]
        self.assertEqual(sent["tenant_id"], "tenant-a")
        self.assertEqual(sent["pipeline_tree"], published.data)
        self.assertNotEqual(sent["pipeline_tree"], later.data)
        self.assertNotIn("parameters", receipt.as_dict())

    @override_settings(ENABLE_MULTI_TENANT_MODE=True)
    def test_cross_space_subprocess_is_rejected_before_engine_dispatch(self):
        other_space = Space.objects.create(app_code="other-app", name="other", tenant_id="tenant-b")
        other = Template.objects.create(name="foreign", space_id=other_space.id, snapshot_id=self.template.snapshot_id)
        snapshot = self.template.snapshot
        snapshot.data["activities"] = {"sub": {"type": "SubProcess", "template_id": other.id}}
        snapshot.save(update_fields=["data"])
        engine = mock.Mock()
        creator = TaskCreator(client_factory=lambda **kwargs: engine, snapshot_preparer=lambda **kw: kw["extra_info"])
        with self.assertRaises(ValidationError):
            creator.create_from_current_template(template=self.template, request_data={}, actor="owner")
        engine.create_task.assert_not_called()

    def test_publication_entry_keeps_untyped_engine_result_false_uncertain(self):
        publication = SimpleNamespace(
            published_template_id=self.template.id,
            published_snapshot_id=self.template.snapshot_id,
            published_version="1.0.0",
        )
        engine = mock.Mock()
        engine.create_task.return_value = {"result": False, "message": "opaque transport failure"}
        creator = TaskCreator(
            client_factory=lambda **kwargs: engine, snapshot_preparer=lambda **kwargs: kwargs["extra_info"]
        )

        with self.assertRaises(TaskCreationUncertain):
            creator.create_from_publication(
                publication=publication,
                request_data={"name": "task", "creator": "harness-user"},
                actor="harness-user",
            )

    def test_publication_entry_rejects_snapshot_owned_by_another_template_before_dispatch(self):
        other = Template.objects.create(
            name="other", space_id=self.space.id, snapshot_id=self.template.snapshot_id, creator="owner"
        )
        other_snapshot = TemplateSnapshot.create_snapshot(
            pipeline_tree=deepcopy(PIPELINE_TREE), username="owner", version="1.0.0"
        )
        other_snapshot.template_id = other.id
        other_snapshot.save(update_fields=["template_id"])
        other.snapshot_id = other_snapshot.id
        other.save(update_fields=["snapshot_id"])
        publication = SimpleNamespace(
            published_template_id=self.template.id,
            published_snapshot_id=other_snapshot.id,
            published_version="1.0.0",
        )
        engine = mock.Mock()
        creator = TaskCreator(
            client_factory=lambda **kwargs: engine, snapshot_preparer=lambda **kwargs: kwargs["extra_info"]
        )

        with self.assertRaisesMessage(ValueError, "publication snapshot does not belong to template"):
            creator.create_from_publication(
                publication=publication,
                request_data={"name": "task", "creator": "harness-user"},
                actor="harness-user",
            )
        engine.create_task.assert_not_called()

    @mock.patch("bkflow.task.services.task_creator.event_broadcast_signal.send")
    def test_publication_entry_keeps_known_task_ref_when_post_create_notification_fails(self, send):
        publication = SimpleNamespace(
            published_template_id=self.template.id,
            published_snapshot_id=self.template.snapshot_id,
            published_version="1.0.0",
        )
        engine = mock.Mock()
        engine.create_task.return_value = {
            "result": True,
            "data": {
                "id": 45,
                "name": "task",
                "template_id": self.template.id,
                "parameters": {},
            },
        }
        send.side_effect = RuntimeError("notification secret")
        creator = TaskCreator(
            client_factory=lambda **kwargs: engine, snapshot_preparer=lambda **kwargs: kwargs["extra_info"]
        )

        receipt = creator.create_from_publication(
            publication=publication,
            request_data={
                "template_id": 999999,
                "name": "task",
                "creator": "untrusted-user",
            },
            actor="trusted-harness-user",
        )

        self.assertEqual(receipt.task_ref, "45")
        self.assertEqual(receipt.warnings, ("TASK_CREATE_NOTIFICATION_FAILED",))
        self.assertEqual(
            receipt.as_dict(),
            {"task_ref": "45", "status": "CREATED", "warnings": ["TASK_CREATE_NOTIFICATION_FAILED"]},
        )
        sent = engine.create_task.call_args.args[0]
        self.assertEqual(sent["template_id"], self.template.id)
        self.assertEqual(sent["creator"], "trusted-harness-user")
