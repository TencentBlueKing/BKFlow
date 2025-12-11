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
from unittest.mock import patch

from bamboo_engine.builder import (
    EmptyEndEvent,
    EmptyStartEvent,
    ServiceActivity,
    build_tree,
)
from blueapps.account.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from bkflow.space.models import Space
from bkflow.template.models import Template, TemplateSnapshot
from bkflow.template.views.template import TemplateViewSet


class TestUpdateTemplate(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin_user = User.objects.create_superuser(username="test_admin", password="password")

    def build_pipeline_tree(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="example_component")
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)

        pipeline = build_tree(start, data={"test": "test"})

        return pipeline

    def create_space(self):
        return Space.objects.create(app_code="test", platform_url="http://test.com", name="space")

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_update_template_success(self):
        space = self.create_space()
        pipeline_tree = self.build_pipeline_tree()
        snapshot = TemplateSnapshot.create_snapshot(pipeline_tree=pipeline_tree, username="test_admin", version="1.0.0")
        template = Template.objects.create(name="测试流程", space_id=space.id, snapshot_id=snapshot.id)
        snapshot.template_id = template.id
        snapshot.save()

        data = {
            "name": "测试流程更新",
            "template_id": template.id,
            "pipeline_tree": pipeline_tree,
            "desc": "测试描述",
            "space_id": space.id,
            "username": "test_admin",
        }

        url = "/apigw/space/{}/update_template/{}/".format(space.id, template.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        self.assertEqual(resp_data["data"]["name"], "测试流程更新")
        self.assertEqual(resp_data["data"]["desc"], "测试描述")

    @patch("bkflow.template.models.PeriodicTriggerHandler.create")
    @patch("bkflow.template.models.PeriodicTriggerHandler.update")
    def test_create_trigger_success(self, mock_create, mock_update):
        space = self.create_space()
        pipeline_tree = self.build_pipeline_tree()
        snapshot = TemplateSnapshot.create_snapshot(pipeline_tree=pipeline_tree, username="test_admin", version="1.0.0")
        template = Template.objects.create(name="测试流程", space_id=space.id, snapshot_id=snapshot.id, desc="测试流程描述")
        snapshot.template_id = template.id
        snapshot.save()

        data = template.to_json(with_pipeline_tree=True)
        # 添加单个触发器，验证触发器是否创建成功
        data["triggers"] = [
            {
                "id": None,
                "space_id": space.id,
                "template_id": template.id,
                "config": {
                    "constants": {"${test}": "test"},
                    "cron": {
                        "hour": "*",
                        "minute": "*/1",
                        "day_of_week": "*",
                        "day_of_month": "*",
                        "month_of_year": "*",
                    },
                    "mode": "json",
                },
                "updated_by": "who",
                "creator": "jackvidyu",
                "is_enabled": False,
                "name": "old trigger",
                "type": "periodic",
            }
        ]

        mock_create.return_value = None

        url = "/api/template/{}/".format(template.id)
        request = self.factory.put(url, data=data, format="json")
        request.user = self.admin_user
        view_func = TemplateViewSet.as_view({"put": "update"})
        response = view_func(request=request, pk=template.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], True)
        self.assertEqual(response.data["data"]["triggers"][0]["name"], "old trigger")

        old_trigger_id = response.data["data"]["triggers"][0]["id"]
        # 更新刚才创建的触发器
        data["triggers"] = [
            {
                "id": old_trigger_id,
                "space_id": space.id,
                "template_id": template.id,
                "config": {
                    "constants": {"${test}": "test"},
                    "cron": {
                        "hour": "*",
                        "minute": "*/1",
                        "day_of_week": "*",
                        "day_of_month": "*",
                        "month_of_year": "*",
                    },
                    "mode": "json",
                },
                "updated_by": "who",
                "creator": "jackvidyu",
                "is_enabled": False,
                "name": "old trigger new name",
                "type": "periodic",
            }
        ]

        mock_update.return_value = None

        request = self.factory.put(url, data=data, format="json")
        request.user = self.admin_user
        view_func = TemplateViewSet.as_view({"put": "update"})
        response = view_func(request=request, pk=template.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"], True)
        self.assertEqual(response.data["data"]["triggers"][0]["name"], "old trigger new name")
