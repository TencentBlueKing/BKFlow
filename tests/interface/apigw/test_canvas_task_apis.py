import json
from pathlib import Path
from unittest import mock

import yaml
from django.test import RequestFactory, SimpleTestCase, override_settings

from bkflow.apigw.views.get_node_outputs import get_node_outputs
from bkflow.apigw.views.get_task_operation_record import get_task_operation_record
from bkflow.apigw.views.get_tasks_pipeline import get_tasks_pipeline
from bkflow.utils import err_code


@override_settings(BK_APIGW_REQUIRE_EXEMPT=True, ENABLE_MULTI_TENANT_MODE=False)
class TestCanvasTaskApis(SimpleTestCase):
    """通过真实视图和响应包装器验证画布接口，不访问数据库或 Engine。"""

    def setUp(self):
        self.factory = RequestFactory()

    @mock.patch("bkflow.apigw.views.get_node_outputs.TaskComponentClient")
    def test_invalid_json_returns_validation_error(self, client_class):
        """空请求体、非法 JSON 和非法编码统一返回参数错误。"""
        for body in (b"", b"{", b"\xff"):
            with self.subTest(body=body):
                request = self.factory.generic("POST", "/", data=body, content_type="application/json")
                response = get_node_outputs(request, space_id="1")
                data = json.loads(response.content)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(data["result"])
                self.assertEqual(data["code"], err_code.VALIDATION_ERROR.code)
                self.assertIsNone(data["data"])
                self.assertEqual(json.loads(data["message"]), {"body": "请求体必须是有效的 JSON"})
                self.assertNotIn("Expecting", data["message"])
                self.assertNotIn("decode", data["message"])
        client_class.assert_not_called()

    @mock.patch("bkflow.apigw.views.get_node_outputs.TaskComponentClient")
    def test_invalid_json_object_returns_validation_error(self, client_class):
        """JSON 类型错误和缺少必填字段仍由序列化器处理。"""
        for body in (b"null", b"[]", b"{}", b'{"task_id": 17}'):
            with self.subTest(body=body):
                request = self.factory.generic("POST", "/", data=body, content_type="application/json")
                response = get_node_outputs(request, space_id="1")
                self.assertEqual(json.loads(response.content)["code"], err_code.VALIDATION_ERROR.code)
        client_class.assert_not_called()

    @mock.patch("bkflow.apigw.views.get_node_outputs.TaskComponentClient")
    def test_node_outputs_preserves_response_and_authorized_space(self, client_class):
        """正常请求透传结果，调用方不能覆盖 URL 中已授权的空间。"""
        result = {"result": True, "data": [{"n1": [{"_result": True}]}], "code": "0", "message": ""}
        client_class.return_value.get_node_outputs.return_value = result
        request = self.factory.post(
            "/", {"task_id": 17, "node_ids": ["n1"], "space_id": 2}, content_type="application/json"
        )
        response = get_node_outputs(request, space_id="1")
        self.assertEqual(json.loads(response.content), result)
        client_class.assert_called_once_with(space_id="1")
        client_class.return_value.get_node_outputs.assert_called_once_with(
            data={"space_id": "1", "task_id": 17, "node_ids": ["n1"]}
        )

    @mock.patch("bkflow.apigw.views.get_tasks_pipeline.TaskComponentClient")
    def test_pipeline_gateway_method_reaches_engine(self, client_class):
        """按网关配置的转发方法调用视图，防止再次出现 GET/POST 不一致。"""
        resources_path = Path(__file__).resolve().parents[3] / "bkflow/apigw/management/commands/data/api-resources.yml"
        resources = yaml.safe_load(resources_path.read_text())
        operation = resources["paths"]["/space/{space_id}/get_tasks_pipeline/"]["get"]
        method = operation["x-bk-apigateway-resource"]["backend"]["method"]
        result = {"result": True, "data": {"17": {}}, "code": "0", "message": ""}
        client_class.return_value.get_tasks_pipeline.return_value = result
        request = self.factory.generic(method.upper(), "/?task_ids=17,18")
        response = get_tasks_pipeline(request, space_id="1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), result)
        client_class.return_value.get_tasks_pipeline.assert_called_once_with({"space_id": "1", "task_ids": "17,18"})

    @mock.patch("bkflow.apigw.views.get_tasks_pipeline.TaskComponentClient")
    def test_invalid_task_ids_do_not_reach_engine(self, client_class):
        """错误的任务 ID 列表在进入 Engine 前返回参数错误。"""
        for task_ids in ("abc", "17,", "17,,18", ",17", "0", "-1", "17,0", "1.5", ""):
            with self.subTest(task_ids=task_ids):
                request = self.factory.get("/", {"task_ids": task_ids})
                response = get_tasks_pipeline(request, space_id="1")
                self.assertEqual(json.loads(response.content)["code"], err_code.VALIDATION_ERROR.code)
        client_class.assert_not_called()

    @mock.patch("bkflow.apigw.views.get_task_operation_record.TaskComponentClient")
    def test_operation_record_passes_optional_node_filter(self, client_class):
        """任务 ID 和可选节点条件按接口契约传递。"""
        result = {"result": True, "data": [], "message": "success"}
        client_class.return_value.get_task_operation_record.return_value = result
        request = self.factory.get("/", {"node_id": "n1"})
        response = get_task_operation_record(request, space_id="1", task_id="17")
        self.assertEqual(json.loads(response.content), result)
        client_class.return_value.get_task_operation_record.assert_called_once_with("17", data={"node_id": "n1"})
