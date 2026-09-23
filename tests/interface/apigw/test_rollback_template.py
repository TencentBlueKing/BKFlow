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

from bkflow.space.configs import FlowVersioning
from bkflow.space.models import Space, SpaceConfig
from bkflow.template.models import Template, TemplateSnapshot


class TestRollbackTemplate(TestCase):
    def setUp(self):
        self.space = self.create_space()
        self.pipeline_tree = self.build_pipeline_tree()

    def build_pipeline_tree(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="example_component")
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)

        pipeline = build_tree(start, data={"test": "test"})

        return pipeline

    def create_space(self):
        return Space.objects.create(app_code="test", platform_url="http://test.com", name="space")

    def enable_flow_versioning(self, space_id):
        SpaceConfig.objects.create(space_id=space_id, name=FlowVersioning.name, text_value="true")

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_rollback_template_success(self):
        """测试回滚模板成功"""
        self.enable_flow_versioning(self.space.id)

        # 创建两个版本的快照
        snapshot1 = TemplateSnapshot.create_snapshot(
            pipeline_tree=self.pipeline_tree, username="test_admin", version="1.0.0"
        )
        snapshot2 = TemplateSnapshot.create_snapshot(
            pipeline_tree=self.pipeline_tree, username="test_admin", version="1.1.0"
        )
        template = Template.objects.create(name="测试流程", space_id=self.space.id, snapshot_id=snapshot2.id)
        snapshot1.template_id = template.id
        snapshot1.save()
        snapshot2.template_id = template.id
        snapshot2.save()

        data = {"version": "1.0.0"}
        url = "/apigw/space/{}/template/{}/rollback_template/".format(self.space.id, template.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_rollback_template_version_not_exists(self):
        """测试回滚模板时版本不存在"""
        self.enable_flow_versioning(self.space.id)

        snapshot = TemplateSnapshot.create_snapshot(
            pipeline_tree=self.pipeline_tree, username="test_admin", version="1.0.0"
        )
        template = Template.objects.create(name="测试流程", space_id=self.space.id, snapshot_id=snapshot.id)
        snapshot.template_id = template.id
        snapshot.save()

        data = {"version": "2.0.0"}  # 不存在的版本
        url = "/apigw/space/{}/template/{}/rollback_template/".format(self.space.id, template.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], False)
        self.assertIn("不存在", resp_data["message"])

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_rollback_template_flow_versioning_disabled(self):
        """测试回滚模板时版本管理未开启"""
        # 不启用版本管理
        snapshot = TemplateSnapshot.create_snapshot(
            pipeline_tree=self.pipeline_tree, username="test_admin", version="1.0.0"
        )
        template = Template.objects.create(name="测试流程", space_id=self.space.id, snapshot_id=snapshot.id)
        snapshot.template_id = template.id
        snapshot.save()

        data = {"version": "1.0.0"}
        url = "/apigw/space/{}/template/{}/rollback_template/".format(self.space.id, template.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], False)
        self.assertIn("版本管理", resp_data["message"])

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_rollback_template_not_found(self):
        """测试回滚模板时模板不存在"""
        self.enable_flow_versioning(self.space.id)

        data = {"version": "1.0.0"}
        url = "/apigw/space/{}/template/{}/rollback_template/".format(self.space.id, 99999)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], False)
        self.assertIn("not found", resp_data["message"])

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_rollback_template_missing_version(self):
        """测试回滚模板时缺少版本参数"""
        self.enable_flow_versioning(self.space.id)

        snapshot = TemplateSnapshot.create_snapshot(
            pipeline_tree=self.pipeline_tree, username="test_admin", version="1.0.0"
        )
        template = Template.objects.create(name="测试流程", space_id=self.space.id, snapshot_id=snapshot.id)
        snapshot.template_id = template.id
        snapshot.save()

        data = {}  # 缺少版本参数
        url = "/apigw/space/{}/template/{}/rollback_template/".format(self.space.id, template.id)
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        # 缺少必填参数，应该返回 result=False 和包含错误信息
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], False)
        self.assertIn("version", resp_data["message"])
