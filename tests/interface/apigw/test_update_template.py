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


class TestTemplateSerializerLabelSync(TestCase):
    def test_sync_template_labels_invalid_ids_raises_validation_error(self):
        from rest_framework.exceptions import ValidationError

        from bkflow.template.serializers.template import TemplateSerializer

        serializer = TemplateSerializer()

        with patch("bkflow.template.serializers.template.Label.objects.check_label_ids") as mock_check:
            mock_check.return_value = False

            with self.assertRaises(ValidationError) as cm:
                serializer._sync_template_lables(template_id=1, label_ids=[1, 2])

        self.assertIn("标签不存在", str(cm.exception))

    def test_sync_template_labels_set_labels_exception_raises_validation_error(self):
        from rest_framework.exceptions import ValidationError

        from bkflow.template.serializers.template import TemplateSerializer

        serializer = TemplateSerializer()

        with patch("bkflow.template.serializers.template.Label.objects.check_label_ids") as mock_check:
            mock_check.return_value = True

            with patch("bkflow.template.serializers.template.TemplateLabelRelation.objects.set_labels") as mock_set:
                mock_set.side_effect = Exception("db error")

                with self.assertRaises(ValidationError) as cm:
                    serializer._sync_template_lables(template_id=1, label_ids=[1, 2])

        self.assertIn("标签设置失败", str(cm.exception))


class TestApigwTemplateSerializers(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="test_user", password="password")

    def build_pipeline_tree(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="example_component")
        end = EmptyEndEvent()

        start.extend(act_1).extend(end)
        pipeline = build_tree(start, data={"test": "test"})
        return pipeline

    def create_space(self):
        return Space.objects.create(app_code="test", platform_url="http://test.com", name="space")

    def make_request(self, username="test_user"):
        request = self.factory.post("/apigw/")
        if username:
            request.user = self.user
            request.user.username = username
        else:
            # serializer only relies on request.user.username
            request.user = type("DummyUser", (), {"username": ""})()
        return request

    def test_create_template_serializer_maps_bind_app_code_to_bk_app_code(self):
        from bkflow.apigw.serializers.template import CreateTemplateSerializer

        space = self.create_space()
        request = self.make_request(username="test_user")

        serializer = CreateTemplateSerializer(
            data={"name": "test", "bind_app_code": "app_code"},
            context={"request": request, "space_id": space.id},
        )
        serializer.is_valid(raise_exception=True)
        self.assertEqual(serializer.validated_data["bk_app_code"], "app_code")
        self.assertNotIn("bind_app_code", serializer.validated_data)

    def test_create_template_serializer_scope_type_and_value_must_both_present(self):
        from rest_framework.exceptions import ValidationError

        from bkflow.apigw.serializers.template import CreateTemplateSerializer

        space = self.create_space()
        request = self.make_request(username="test_user")

        serializer = CreateTemplateSerializer(
            data={"name": "test", "scope_type": "biz"},
            context={"request": request, "space_id": space.id},
        )

        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_create_template_serializer_source_template_not_exists_raises(self):
        from rest_framework.exceptions import ValidationError

        from bkflow.apigw.serializers.template import CreateTemplateSerializer

        space = self.create_space()
        request = self.make_request(username="test_user")

        serializer = CreateTemplateSerializer(
            data={"name": "test", "source_template_id": 99999999},
            context={"request": request, "space_id": space.id},
        )

        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_create_template_serializer_only_copy_template_in_same_space(self):
        from rest_framework.exceptions import ValidationError

        from bkflow.apigw.serializers.template import CreateTemplateSerializer
        from bkflow.template.models import TemplateSnapshot

        space_1 = self.create_space()
        space_2 = Space.objects.create(app_code="test2", platform_url="http://test.com", name="space2")
        pipeline_tree = self.build_pipeline_tree()
        snapshot = TemplateSnapshot.create_snapshot(pipeline_tree=pipeline_tree, username="test_user", version="1.0.0")
        template = Template.objects.create(name="src", space_id=space_1.id, snapshot_id=snapshot.id)

        request = self.make_request(username="test_user")
        serializer = CreateTemplateSerializer(
            data={"name": "test", "source_template_id": template.id},
            context={"request": request, "space_id": space_2.id},
        )

        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    @patch("bkflow.apigw.serializers.template.validate_pipeline_tree")
    def test_create_template_serializer_pipeline_validate_error_raises(self, mock_validate):
        from rest_framework.exceptions import ValidationError

        from bkflow.apigw.serializers.template import CreateTemplateSerializer

        mock_validate.side_effect = Exception("invalid pipeline")

        space = self.create_space()
        request = self.make_request(username="test_user")
        serializer = CreateTemplateSerializer(
            data={"name": "test", "pipeline_tree": {"invalid": True}},
            context={"request": request, "space_id": space.id},
        )

        with self.assertRaises(ValidationError) as cm:
            serializer.is_valid(raise_exception=True)
        self.assertIn("pipeline校验不通过", str(cm.exception))

    def test_create_template_serializer_creator_and_apigw_user_both_empty_raises(self):
        from rest_framework.exceptions import ValidationError

        from bkflow.apigw.serializers.template import CreateTemplateSerializer

        space = self.create_space()
        request = self.make_request(username="")

        serializer = CreateTemplateSerializer(
            data={"name": "test"},
            context={"request": request, "space_id": space.id},
        )

        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_delete_template_serializer_validate_space_id_invalid_raises(self):
        from rest_framework.exceptions import ValidationError

        from bkflow.apigw.serializers.template import DeleteTemplateSerializer

        serializer = DeleteTemplateSerializer(data={"template_id": 1, "space_id": 99999999})

        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_delete_template_serializer_validate_space_id_valid(self):
        from bkflow.apigw.serializers.template import DeleteTemplateSerializer

        space = self.create_space()
        serializer = DeleteTemplateSerializer(data={"template_id": 1, "space_id": space.id})
        serializer.is_valid(raise_exception=True)
        self.assertEqual(serializer.validated_data["space_id"], space.id)

    def test_update_template_serializer_scope_type_and_value_must_both_present(self):
        from rest_framework.exceptions import ValidationError

        from bkflow.apigw.serializers.template import UpdateTemplateSerializer

        request = self.make_request(username="test_user")
        serializer = UpdateTemplateSerializer(
            data={"scope_type": "biz"},
            context={"request": request},
        )

        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_update_template_serializer_operator_and_apigw_user_both_empty_raises(self):
        from rest_framework.exceptions import ValidationError

        from bkflow.apigw.serializers.template import UpdateTemplateSerializer

        request = self.make_request(username="")
        serializer = UpdateTemplateSerializer(
            data={"name": "test"},
            context={"request": request},
        )

        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    @patch("bkflow.apigw.serializers.template.validate_pipeline_tree")
    def test_update_template_serializer_pipeline_validate_error_raises(self, mock_validate):
        from rest_framework.exceptions import ValidationError

        from bkflow.apigw.serializers.template import UpdateTemplateSerializer

        mock_validate.side_effect = Exception("invalid pipeline")

        request = self.make_request(username="test_user")
        serializer = UpdateTemplateSerializer(
            data={"pipeline_tree": {"invalid": True}},
            context={"request": request},
        )

        with self.assertRaises(ValidationError) as cm:
            serializer.is_valid(raise_exception=True)
        self.assertIn("pipeline校验不通过", str(cm.exception))
