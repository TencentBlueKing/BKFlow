import json
from unittest import mock

from django.test import TestCase, override_settings

from bkflow.decision_table.models import DecisionTable
from bkflow.space.models import Space
from bkflow.template.models import (
    Template,
    TemplateReference,
    TemplateSnapshot,
    Trigger,
)
from bkflow.utils import err_code


class TestDeleteTemplate(TestCase):
    def create_space(self):
        return Space.objects.create(app_code="test", platform_url="http://test.com", name="space")

    def _create_template(self, space_id):
        snapshot = TemplateSnapshot.objects.create(data={"activities": {}}, creator="tester", version="1.0.0")
        template = Template.objects.create(
            space_id=space_id, snapshot_id=snapshot.id, name="test_template", creator="tester", updated_by="tester"
        )
        snapshot.template_id = template.id
        snapshot.save()
        return template

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.delete_template.clear_scope_webhooks")
    @mock.patch("bkflow.template.models.Trigger.objects.batch_delete_by_ids")
    def test_delete_template_success(self, mock_batch_delete, mock_clear_webhooks):
        """测试正常删除模板，无引用时成功删除"""
        # 让 mock 实际执行删除操作
        mock_batch_delete.side_effect = lambda space_id, trigger_ids: Trigger.objects.filter(id__in=trigger_ids).update(
            is_deleted=True
        )

        space = self.create_space()
        template = self._create_template(space.id)
        # 创建一个 trigger 以验证 batch_delete_by_ids 被调用
        trigger = Trigger.objects.create(
            space_id=space.id,
            template_id=template.id,
            name="test_trigger",
            config={},
            type="webhook",
        )

        url = f"/apigw/space/{space.id}/delete_template/{template.id}/"
        resp = self.client.post(url)
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        self.assertEqual(resp_data["code"], err_code.SUCCESS.code)
        self.assertEqual(resp_data["data"], {})

        template.refresh_from_db()
        self.assertTrue(template.is_deleted)

        trigger.refresh_from_db()
        self.assertTrue(trigger.is_deleted)

        mock_batch_delete.assert_called_once_with(space_id=str(space.id), trigger_ids=[trigger.id])
        mock_clear_webhooks.assert_called_once_with([str(template.id)])

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_delete_template_with_decision_table_reference(self):
        """测试存在决策表引用时删除失败"""
        space = self.create_space()
        template = self._create_template(space.id)
        decision_table = DecisionTable.objects.create(
            space_id=space.id,
            template_id=template.id,
            name="test_decision",
            data={},
            creator="tester",
            updated_by="tester",
        )

        url = f"/apigw/space/{space.id}/delete_template/{template.id}/"
        resp = self.client.post(url)
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], False)
        self.assertEqual(resp_data["code"], err_code.VALIDATION_ERROR.code)
        self.assertEqual(resp_data["data"]["decision_templates"], [decision_table.id])

        template.refresh_from_db()
        self.assertFalse(template.is_deleted)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_delete_template_with_template_reference(self):
        """测试存在父模板引用时删除失败"""
        space = self.create_space()
        template = self._create_template(space.id)
        parent_template = self._create_template(space.id)
        TemplateReference.objects.create(
            root_template_id=parent_template.id,
            subprocess_template_id=template.id,
            subprocess_node_id="node_1",
            version="1",
        )

        url = f"/apigw/space/{space.id}/delete_template/{template.id}/"
        resp = self.client.post(url)
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], False)
        self.assertEqual(resp_data["code"], err_code.VALIDATION_ERROR.code)
        self.assertEqual(resp_data["data"]["parent_templates"], [str(parent_template.id)])

        template.refresh_from_db()
        self.assertFalse(template.is_deleted)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_delete_template_with_both_references(self):
        """测试同时存在决策表和父模板引用时删除失败并返回所有引用"""
        space = self.create_space()
        template = self._create_template(space.id)
        decision_table = DecisionTable.objects.create(
            space_id=space.id,
            template_id=template.id,
            name="test_decision",
            data={},
            creator="tester",
            updated_by="tester",
        )
        parent_template = self._create_template(space.id)
        TemplateReference.objects.create(
            root_template_id=parent_template.id,
            subprocess_template_id=template.id,
            subprocess_node_id="node_1",
            version="1",
        )

        url = f"/apigw/space/{space.id}/delete_template/{template.id}/"
        resp = self.client.post(url)
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], False)
        self.assertEqual(resp_data["data"]["decision_templates"], [decision_table.id])
        self.assertEqual(resp_data["data"]["parent_templates"], [str(parent_template.id)])

        template.refresh_from_db()
        self.assertFalse(template.is_deleted)
