# -*- coding: utf-8 -*-
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

from bamboo_engine.builder import (
    EmptyEndEvent,
    EmptyStartEvent,
    ServiceActivity,
    build_tree,
)
from django.test import TestCase, override_settings

from bkflow.space.models import Space
from bkflow.template.models import Template, TemplateSnapshot


class TestUpdateTemplate(TestCase):
    def build_pipeline_tree(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="example_component")
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)

        pipeline = build_tree(start)

        return pipeline

    def create_space(self):
        return Space.objects.create(app_code="test", platform_url="http://test.com", name="space")

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_update_template_success(self):
        space = self.create_space()
        pipeline_tree = self.build_pipeline_tree()
        snapshot = TemplateSnapshot.create_snapshot(pipeline_tree)
        template = Template.objects.create(name="测试流程", space_id=space.id, snapshot_id=snapshot.id)
        snapshot.template_id = template.id
        snapshot.save()

        data = {
            "name": "测试流程更新",
            "template_id": template.id,
            "pipeline_tree": pipeline_tree,
            "desc": "测试描述",
        }

        url = "/apigw/space/{}/update_template/{}/".format(space.id, template.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")

        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        self.assertEqual(resp_data["data"]["name"], "测试流程更新")
        self.assertEqual(resp_data["data"]["desc"], "测试描述")
