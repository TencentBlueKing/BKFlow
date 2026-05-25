import json
from unittest import mock

from django.test import TestCase, override_settings

from bkflow.space.models import Space


class TestGetTaskDetail(TestCase):
    def create_space(self):
        return Space.objects.create(app_code="test", platform_url="http://test.com", name="space")

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.get_task_detail.Template")
    @mock.patch("bkflow.apigw.views.get_task_detail.get_webhook_delivery_history_by_delivery_id")
    @mock.patch("bkflow.apigw.views.get_task_detail.TaskComponentClient")
    def test_get_task_detail_success(self, mock_client_class, mock_get_history, mock_template):
        """测试正常获取任务详情并附带 webhook 投递历史"""
        space = self.create_space()
        mock_client = mock_client_class.return_value
        mock_client.get_task_detail.return_value = {
            "result": True,
            "data": {"id": 123, "name": "test_task", "template_id": 1},
        }
        mock_template.objects.filter.return_value.first.return_value.name = "tpl"
        mock_get_history.return_value = [
            {
                "created_at": "2024-01-01 00:00:00",
                "event_code": "task_start",
                "event_code_name": "任务开始",
                "is_success": True,
                "status_code": 200,
                "response": "ok",
            }
        ]

        url = f"/apigw/space/{space.id}/task/123/get_task_detail/"
        resp = self.client.get(url)
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        self.assertEqual(resp_data["data"]["id"], 123)
        self.assertEqual(len(resp_data["data"]["webhook_delivery_history"]), 1)
        self.assertEqual(resp_data["data"]["webhook_delivery_history"][0]["event_code"], "task_start")

        mock_client_class.assert_called_once_with(space_id=str(space.id))
        mock_client.get_task_detail.assert_called_once_with("123")
        mock_get_history.assert_called_once_with("123")

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.get_task_detail.Template")
    @mock.patch("bkflow.apigw.views.get_task_detail.get_webhook_delivery_history_by_delivery_id")
    @mock.patch("bkflow.apigw.views.get_task_detail.TaskComponentClient")
    def test_get_task_detail_with_empty_webhook_history(self, mock_client_class, mock_get_history, mock_template):
        """测试 webhook 投递历史为空列表的情况"""
        space = self.create_space()
        mock_client = mock_client_class.return_value
        mock_client.get_task_detail.return_value = {
            "result": True,
            "data": {"id": 456, "name": "no_webhook_task", "template_id": 1},
        }
        mock_template.objects.filter.return_value.first.return_value.name = "tpl"
        mock_get_history.return_value = []

        url = f"/apigw/space/{space.id}/task/456/get_task_detail/"
        resp = self.client.get(url)
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        self.assertEqual(resp_data["data"]["webhook_delivery_history"], [])

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.get_task_detail.TaskComponentClient")
    def test_get_task_detail_task_component_returns_error(self, mock_client_class):
        """测试 TaskComponentClient 返回 result=False 时因缺少 data 键触发 500"""
        space = self.create_space()
        mock_client = mock_client_class.return_value
        mock_client.get_task_detail.return_value = {
            "result": False,
            "code": "404",
            "message": "task not found",
        }

        url = f"/apigw/space/{space.id}/task/999/get_task_detail/"
        resp = self.client.get(url)
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], False)
        self.assertEqual(resp_data["code"], 500)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.get_task_detail.Template")
    @mock.patch("bkflow.apigw.views.get_task_detail.get_webhook_delivery_history_by_delivery_id")
    @mock.patch("bkflow.apigw.views.get_task_detail.TaskComponentClient")
    def test_get_task_detail_task_id_converted_to_str(self, mock_client_class, mock_get_history, mock_template):
        """测试 task_id 会被转换为字符串后传入 get_webhook_delivery_history_by_delivery_id"""
        space = self.create_space()
        mock_client = mock_client_class.return_value
        mock_client.get_task_detail.return_value = {
            "result": True,
            "data": {"id": 789, "template_id": 1},
        }
        mock_template.objects.filter.return_value.first.return_value.name = "tpl"
        mock_get_history.return_value = []

        url = f"/apigw/space/{space.id}/task/789/get_task_detail/"
        self.client.get(url)

        mock_get_history.assert_called_once_with("789")
