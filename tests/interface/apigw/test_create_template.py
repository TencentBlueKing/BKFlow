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
import copy
import json
from unittest import mock

from django.test import TestCase, override_settings

from bkflow.label.models import Label, TemplateLabelRelation
from bkflow.space.models import Space
from bkflow.template.models import Template, TemplateSnapshot
from tests.interface.apigw.test_create_task import build_pipeline_tree


class TestCreateTemplate(TestCase):
    def create_space(self):
        return Space.objects.create(app_code="test", platform_url="http://test.com", name="space")

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_create_template_success(self):
        space = self.create_space()
        data = {"name": "测试流程"}
        url = f"/apigw/space/{space.id}/create_template/"
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        self.assertEqual(resp_data["data"]["name"], "测试流程")

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_create_template_with_labels_syncs_relations(self):
        space = self.create_space()
        label_1 = Label.objects.create(
            name="l1",
            creator="tester",
            updated_by="tester",
            space_id=space.id,
            label_scope=["template"],
        )
        label_2 = Label.objects.create(
            name="l2",
            creator="tester",
            updated_by="tester",
            space_id=space.id,
            label_scope=["template"],
        )

        data = {"name": "测试流程", "label_ids": [label_1.id, label_2.id]}
        url = f"/apigw/space/{space.id}/create_template/"
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        template_id = resp_data["data"]["id"]

        rel_label_ids = set(
            TemplateLabelRelation.objects.filter(template_id=template_id).values_list("label_id", flat=True)
        )
        self.assertEqual(rel_label_ids, {label_1.id, label_2.id})

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.create_template.apply_webhook_configs")
    def test_create_template_with_webhook_configs(self, mock_apply_webhook):
        """测试传入 webhook_configs 时成功调用 apply_webhook_configs"""
        space = self.create_space()
        mock_apply_webhook.return_value = {"result": True, "message": "success"}

        data = {"name": "带Webhook的流程", "webhook_configs": {"method": "POST", "endpoint": "http://test.com/hook"}}
        url = f"/apigw/space/{space.id}/create_template/"
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        mock_apply_webhook.assert_called_once()
        call_args = mock_apply_webhook.call_args
        self.assertEqual(call_args[0][0], {"method": "POST", "endpoint": "http://test.com/hook"})
        self.assertEqual(resp_data["data"]["name"], "带Webhook的流程")

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.views.create_template.apply_webhook_configs")
    def test_create_template_with_webhook_configs_failure(self, mock_apply_webhook):
        """测试 apply_webhook_configs 返回失败时应抛出 CreateTemplateException"""
        space = self.create_space()
        mock_apply_webhook.return_value = {"result": False, "message": "webhook配置错误"}

        data = {"name": "Webhook失败的流程", "webhook_configs": {"method": "GET", "endpoint": "http://bad.com"}}
        url = f"/apigw/space/{space.id}/create_template/"
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], False)
        self.assertEqual(resp_data["code"], 500)
        self.assertIn("webhook配置错误", resp_data["message"])

    def _build_tree_with_gateway(self, parse_lang=None):
        """构造带分支网关的 pipeline_tree，parse_lang 为 None 时不设置（默认 boolrule）"""
        tree = copy.deepcopy(build_pipeline_tree())
        gateway = {
            "id": "gateway_1",
            "type": "ExclusiveGateway",
            "conditions": {},
        }
        if parse_lang is not None:
            gateway["extra_info"] = {"parse_lang": parse_lang}
        tree.setdefault("gateways", {})["gateway_1"] = gateway
        return tree

    def _create_source_template(self, space, pipeline_tree):
        """先建快照再建模板（snapshot_id 为必填字段），并返回模板实例"""
        snapshot = TemplateSnapshot.create_snapshot(pipeline_tree, "tester", "1.0.0")
        template = Template.objects.create(
            name="源模板",
            space_id=space.id,
            creator="tester",
            updated_by="tester",
            snapshot_id=snapshot.id,
        )
        snapshot.template_id = template.id
        snapshot.save(update_fields=["template_id"])
        return template

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.serializers.template.validate_pipeline_tree")
    def test_create_template_rejected_when_gateway_parse_lang_mismatch(self, mock_validate_structure):
        """
        选中逻辑：直接传入的 pipeline_tree 含网关，其 parse_lang 与空间默认配置(boolrule)不符 -> 应拒绝
        注：mock 掉 serializer 中的 pipeline 结构校验，使请求树直达视图层的网关表达式校验分支
        """
        space = self.create_space()
        invalid_tree = self._build_tree_with_gateway(parse_lang="FEEL")

        data = {"name": "网关表达式违规", "pipeline_tree": invalid_tree}
        url = f"/apigw/space/{space.id}/create_template/"
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], False)
        self.assertEqual(resp_data["code"], 500)
        self.assertIn("网关表达式", resp_data["message"])
        self.assertFalse(Template.objects.filter(name="网关表达式违规").exists())

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @mock.patch("bkflow.apigw.serializers.template.validate_pipeline_tree")
    def test_create_template_ok_when_gateway_parse_lang_matches_default(self, mock_validate_structure):
        """
        选中逻辑：传入的 pipeline_tree 含网关但未显式设置 parse_lang（默认按 boolrule 解析），
        与空间默认配置(boolrule)一致 -> 应创建成功
        """
        space = self.create_space()
        valid_tree = self._build_tree_with_gateway(parse_lang=None)

        data = {"name": "网关表达式合法", "pipeline_tree": valid_tree}
        url = f"/apigw/space/{space.id}/create_template/"
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], True)
        template = Template.objects.get(name="网关表达式合法")
        self.assertIn("gateway_1", template.pipeline_tree.get("gateways", {}))

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_create_template_from_source_rejected_when_source_gateway_invalid(self):
        """
        选中逻辑：通过 source_template_id 复制，源模板树含违规网关，请求本身不带 pipeline_tree，
        最终保存的源模板树应在视图层被统一校验并拒绝
        """
        space = self.create_space()
        invalid_source_tree = self._build_tree_with_gateway(parse_lang="FEEL")
        source_template = self._create_source_template(space, invalid_source_tree)

        data = {"name": "复制自违规源模板", "source_template_id": source_template.id}
        url = f"/apigw/space/{space.id}/create_template/"
        resp = self.client.post(path=url, data=json.dumps(data), content_type="application/json")
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp_data["result"], False)
        self.assertEqual(resp_data["code"], 500)
        self.assertIn("网关表达式", resp_data["message"])
        self.assertFalse(Template.objects.filter(name="复制自违规源模板").exists())
