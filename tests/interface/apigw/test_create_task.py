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
import json
from unittest import mock

from bamboo_engine.builder import (
    EmptyEndEvent,
    EmptyStartEvent,
    ServiceActivity,
    build_tree,
)
from django.test import TestCase, override_settings

from bkflow.space.models import Space
from bkflow.template.models import Template, TemplateSnapshot


def build_pipeline_tree():
    """构建测试用的 pipeline tree"""
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="example_component")
    end = EmptyEndEvent()
    start.extend(act_1).extend(end)
    return build_tree(start, data={"test": "test"})


class TestCreateTask(TestCase):
    """Test create_task apigw views"""

    def setUp(self):
        self.space = Space.objects.create(app_code="test", platform_url="http://test.com", name="test_space")

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.create_task.TaskComponentClient")
    def test_create_task_with_custom_span_attributes(self, mock_client_class):
        """Test create_task with custom_span_attributes parameter"""
        pipeline_tree = build_pipeline_tree()
        snapshot = TemplateSnapshot.create_snapshot(pipeline_tree=pipeline_tree, username="test_user", version="1.0.0")
        template = Template.objects.create(
            name="测试流程", space_id=self.space.id, snapshot_id=snapshot.id, creator="test_user"
        )
        snapshot.template_id = template.id
        snapshot.save()

        mock_client = mock.Mock()
        mock_client.create_task.return_value = {
            "result": True,
            "data": {"id": 1, "name": "测试任务", "template_id": template.id, "parameters": {}},
        }
        mock_client_class.return_value = mock_client

        custom_span_attributes = {"business_id": "12345", "request_id": "req-abc-123"}
        data = {
            "template_id": template.id,
            "name": "测试任务",
            "creator": "test_user",
            "custom_span_attributes": custom_span_attributes,
        }

        url = "/apigw/space/{}/create_task/".format(self.space.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)

        # 验证 custom_span_attributes 被传递到 create_task_data 中
        call_args = mock_client.create_task.call_args[0][0]
        self.assertIn("extra_info", call_args)
        self.assertIn("custom_context", call_args["extra_info"])
        self.assertEqual(call_args["extra_info"]["custom_context"]["custom_span_attributes"], custom_span_attributes)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.create_task_by_app.TaskComponentClient")
    def test_create_task_by_app_with_custom_span_attributes(self, mock_client_class):
        """Test create_task_by_app with custom_span_attributes parameter"""
        pipeline_tree = build_pipeline_tree()
        snapshot = TemplateSnapshot.create_snapshot(pipeline_tree=pipeline_tree, username="test_user", version="1.0.0")
        template = Template.objects.create(
            name="测试流程",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            bk_app_code="test",
        )
        snapshot.template_id = template.id
        snapshot.save()

        mock_client = mock.Mock()
        mock_client.create_task.return_value = {
            "result": True,
            "data": {"id": 1, "name": "测试任务", "template_id": template.id, "parameters": {}},
        }
        mock_client_class.return_value = mock_client

        custom_span_attributes = {"user_type": "vip", "source": "api"}
        data = {
            "template_id": template.id,
            "name": "测试任务",
            "custom_span_attributes": custom_span_attributes,
        }

        url = "/apigw/template/{}/create_task_by_app/".format(template.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)

        # 验证 custom_span_attributes 被传递到 create_task_data 中
        call_args = mock_client.create_task.call_args[0][0]
        self.assertIn("extra_info", call_args)
        self.assertIn("custom_context", call_args["extra_info"])
        self.assertEqual(call_args["extra_info"]["custom_context"]["custom_span_attributes"], custom_span_attributes)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.create_task_without_template.TaskComponentClient")
    def test_create_task_without_template_with_custom_span_attributes(self, mock_client_class):
        """Test create_task_without_template with custom_span_attributes parameter"""
        pipeline_tree = build_pipeline_tree()

        mock_client = mock.Mock()
        mock_client.create_task.return_value = {
            "result": True,
            "data": {"id": 1, "name": "测试任务", "parameters": {}},
        }
        mock_client_class.return_value = mock_client

        custom_span_attributes = {"env": "prod", "region": "us-east-1"}
        data = {
            "name": "测试任务",
            "creator": "test_user",
            "pipeline_tree": pipeline_tree,
            "custom_span_attributes": custom_span_attributes,
        }

        url = "/apigw/space/{}/create_task_without_template/".format(self.space.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)

        # 验证 custom_span_attributes 被传递到 create_task_data 中
        call_args = mock_client.create_task.call_args[0][0]
        self.assertIn("extra_info", call_args)
        self.assertIn("custom_context", call_args["extra_info"])
        self.assertEqual(call_args["extra_info"]["custom_context"]["custom_span_attributes"], custom_span_attributes)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.create_mock_task.TaskComponentClient")
    def test_create_mock_task_with_custom_span_attributes(self, mock_client_class):
        """Test create_mock_task with custom_span_attributes parameter"""
        pipeline_tree = build_pipeline_tree()
        snapshot = TemplateSnapshot.create_snapshot(pipeline_tree=pipeline_tree, username="test_user", version="1.0.0")
        template = Template.objects.create(
            name="测试流程", space_id=self.space.id, snapshot_id=snapshot.id, creator="test_user"
        )
        snapshot.template_id = template.id
        snapshot.save()

        mock_client = mock.Mock()
        mock_client.create_task.return_value = {
            "result": True,
            "data": {"id": 1, "name": "Mock任务", "template_id": template.id, "parameters": {}},
        }
        mock_client_class.return_value = mock_client

        custom_span_attributes = {"test_mode": "mock", "debug": "true"}
        data = {
            "template_id": template.id,
            "name": "Mock任务",
            "creator": "test_user",
            "mock_data": {"nodes": [], "outputs": {}, "mock_data_ids": {}},
            "custom_span_attributes": custom_span_attributes,
        }

        url = "/apigw/space/{}/create_mock_task/".format(self.space.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)

        # 验证 custom_span_attributes 被传递到 create_task_data 中
        call_args = mock_client.create_task.call_args[0][0]
        self.assertIn("extra_info", call_args)
        self.assertIn("custom_context", call_args["extra_info"])
        self.assertEqual(call_args["extra_info"]["custom_context"]["custom_span_attributes"], custom_span_attributes)
