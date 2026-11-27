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

import datetime
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve
from django.utils import timezone

from bkflow.permission.models import Token
from bkflow.space.models import Space, SpaceConfig


class TestApplyToken(TestCase):
    """测试 apply_token 接口"""

    def setUp(self):
        """设置测试数据"""
        self.space = Space.objects.create(app_code="test", platform_url="http://test.com", name="test_space")
        self.space_id = self.space.id

        # 设置 token 过期时间配置
        SpaceConfig.objects.create(
            space_id=self.space_id,
            name="token_expiration",
            text_value="1h",
            value_type="TEXT",
        )

    def tearDown(self):
        """清理测试数据"""
        Token.objects.all().delete()
        SpaceConfig.objects.filter(space_id=self.space_id).delete()
        Space.objects.filter(id=self.space_id).delete()

    def _apply_token(self, data):
        """调用 apply_token 接口"""
        url = f"/apigw/space/{self.space_id}/apply_token/"
        return self.client.post(path=url, data=json.dumps(data), content_type="application/json")

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.apigw.serializers.token.TokenResourceValidator.validate")
    def test_apply_token_create_new(self, mock_validate):
        """测试申请新 token（token 不存在时创建新的）"""
        mock_validate.return_value = True

        data = {
            "resource_type": "TASK",
            "resource_id": "123",
            "permission_type": "VIEW",
            "user": "ignored",
        }

        resp = self._apply_token(data)
        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp_data["result"])
        self.assertIn("token", resp_data["data"])
        self.assertEqual(resp_data["data"]["user"], "username")
        self.assertEqual(resp_data["data"]["resource_type"], "TASK")
        self.assertEqual(resp_data["data"]["resource_id"], "123")

        # 验证 token 已创建
        token_count = Token.objects.filter(
            space_id=self.space_id, grants__resource_type="TASK", grants__resource_id="123"
        ).count()
        self.assertEqual(token_count, 1)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.apigw.serializers.token.TokenResourceValidator.validate")
    def test_apply_token_return_same_token(self, mock_validate):
        """测试申请同一资源的 token 返回相同的 token"""
        mock_validate.return_value = True

        data = {
            "resource_type": "TASK",
            "resource_id": "456",
            "permission_type": "VIEW",
        }

        # 第一次申请
        resp1 = self._apply_token(data)
        resp_data1 = json.loads(resp1.content)
        token1 = resp_data1["data"]["token"]

        # 第二次申请同一资源
        resp2 = self._apply_token(data)
        resp_data2 = json.loads(resp2.content)
        token2 = resp_data2["data"]["token"]

        # 验证返回相同的 token
        self.assertEqual(token1, token2)

        # 验证只有一个 token 记录
        token_count = Token.objects.filter(
            space_id=self.space_id, grants__resource_type="TASK", grants__resource_id="456"
        ).count()
        self.assertEqual(token_count, 1)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.apigw.serializers.token.TokenResourceValidator.validate")
    def test_apply_token_renewal_enabled(self, mock_validate):
        """测试开启自动续期时刷新过期时间"""
        mock_validate.return_value = True

        # 设置开启自动续期
        SpaceConfig.objects.create(
            space_id=self.space_id,
            name="token_auto_renewal",
            text_value="true",
            value_type="TEXT",
        )

        data = {
            "resource_type": "TASK",
            "resource_id": "789",
            "permission_type": "VIEW",
        }

        # 第一次申请
        resp1 = self._apply_token(data)
        resp_data1 = json.loads(resp1.content)

        # 等待一小段时间，模拟时间流逝
        # 直接修改数据库中的过期时间，使其更早
        token = Token.objects.get(token=resp_data1["data"]["token"])
        # 设置一个较早的过期时间（30分钟后），确保刷新后的时间（1小时后）会更大
        # 记录设置修改时间的时间点
        time_before_modify = timezone.now()
        modified_expired_time = time_before_modify + datetime.timedelta(minutes=30)
        token.expired_time = modified_expired_time
        token.save()

        # 第二次申请同一资源（如果实现了自动续期，应该会刷新过期时间）
        self._apply_token(data)

        # 刷新后的 token
        token.refresh_from_db()
        new_expired_time = token.expired_time

        # 验证过期时间已刷新（新的过期时间应该比修改后的时间晚）
        # 如果自动续期功能正常工作，new_expired_time 应该是当前时间 + 1h
        # 而 modified_expired_time 是 time_before_modify + 30分钟
        # 由于配置的过期时间是1h，所以 new_expired_time 应该明显大于 modified_expired_time
        # 使用时间差来验证，确保至少有接近30分钟的差异（考虑时间精度和调用耗时）
        time_diff = (new_expired_time - modified_expired_time).total_seconds()
        # 考虑到调用耗时，实际差异应该至少接近30分钟（1800秒），允许1秒的误差
        self.assertGreaterEqual(time_diff, 30 * 60 - 1)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.apigw.serializers.token.TokenResourceValidator.validate")
    def test_apply_token_renewal_disabled(self, mock_validate):
        """测试关闭自动续期时不刷新过期时间"""
        mock_validate.return_value = True

        # 设置关闭自动续期
        SpaceConfig.objects.create(
            space_id=self.space_id,
            name="token_auto_renewal",
            text_value="false",
            value_type="TEXT",
        )

        data = {
            "resource_type": "TEMPLATE",
            "resource_id": "101",
            "permission_type": "EDIT",
        }

        # 第一次申请
        resp1 = self._apply_token(data)
        resp_data1 = json.loads(resp1.content)

        # 修改数据库中的过期时间为一个特定值
        token = Token.objects.get(token=resp_data1["data"]["token"])
        fixed_time = timezone.now() + datetime.timedelta(minutes=30)
        token.expired_time = fixed_time
        token.save()

        # 第二次申请同一资源
        self._apply_token(data)

        # 刷新后的 token
        token.refresh_from_db()

        # 验证过期时间未刷新（仍然是设置的固定时间）
        # 由于时间精度问题，使用时间差来比较
        time_diff = abs((token.expired_time - fixed_time).total_seconds())
        self.assertLess(time_diff, 1)  # 误差小于 1 秒

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.apigw.serializers.token.TokenResourceValidator.validate")
    def test_apply_token_different_resources(self, mock_validate):
        """测试不同资源返回不同的 token"""
        mock_validate.return_value = True

        data1 = {
            "resource_type": "TASK",
            "resource_id": "111",
            "permission_type": "VIEW",
        }

        data2 = {
            "resource_type": "TASK",
            "resource_id": "222",
            "permission_type": "VIEW",
        }

        # 申请第一个资源的 token
        resp1 = self._apply_token(data1)
        resp_data1 = json.loads(resp1.content)
        token1 = resp_data1["data"]["token"]

        # 申请第二个资源的 token
        resp2 = self._apply_token(data2)
        resp_data2 = json.loads(resp2.content)
        token2 = resp_data2["data"]["token"]

        # 验证返回不同的 token
        self.assertNotEqual(token1, token2)

        # 验证有两个 token 记录
        token_count = Token.objects.filter(space_id=self.space_id, grants__resource_type="TASK").distinct().count()
        self.assertEqual(token_count, 2)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.apigw.serializers.token.TokenResourceValidator.validate")
    def test_apply_token_different_permission_types(self, mock_validate):
        """测试同一资源不同权限类型返回不同的 token"""
        mock_validate.return_value = True

        data1 = {
            "resource_type": "TEMPLATE",
            "resource_id": "333",
            "permission_type": "VIEW",
        }

        data2 = {
            "resource_type": "TEMPLATE",
            "resource_id": "333",
            "permission_type": "EDIT",
        }

        # 申请 VIEW 权限的 token
        resp1 = self._apply_token(data1)
        resp_data1 = json.loads(resp1.content)
        token1 = resp_data1["data"]["token"]

        # 申请 EDIT 权限的 token
        resp2 = self._apply_token(data2)
        resp_data2 = json.loads(resp2.content)
        token2 = resp_data2["data"]["token"]

        # 验证返回不同的 token（不同权限类型）
        self.assertNotEqual(token1, token2)


@override_settings(BK_APIGW_REQUIRE_EXEMPT=False, ENABLE_MULTI_TENANT_MODE=True, TOKEN_COMPOSITE_ENABLED=True)
class TestApplyTokenByApp(TestCase):
    """测试应用态签发及空间权限约束。"""

    @classmethod
    def setUpTestData(cls):
        cls.space = Space.objects.create(
            app_code="bk_fara", platform_url="http://test.com", name="app_token_space", tenant_id="tenant-a"
        )

    def _apply(self, body, *, app_code="bk_fara", verified=True, tenant="tenant-a", has_jwt=True):
        path = f"/apigw/space/{self.space.pk}/apply_token_by_app/"
        request = RequestFactory().post(path, data=json.dumps(body), content_type="application/json")
        request.META["HTTP_X_BK_TENANT_ID"] = tenant
        if has_jwt:
            request.jwt = SimpleNamespace(payload={})
            request.app = SimpleNamespace(bk_app_code=app_code, verified=verified, tenant_mode="global")
        match = resolve(path)
        return match.func(request, **match.kwargs)

    @patch("bkflow.apigw.serializers.token.TokenResourceValidator.validate")
    def test_issue_for_target_user(self, mock_validate):
        """没有用户会话时，单项及组合申请均为请求体中的用户签发。"""
        grant = {"resource_type": "TASK", "resource_id": "123", "permission_type": "VIEW"}
        single = json.loads(self._apply({"user": "target", **grant}).content)["data"]
        composite = json.loads(self._apply({"user": "target", "grants": [grant]}).content)["data"]
        self.assertEqual(single["user"], "target")
        self.assertEqual(composite["user"], "target")
        self.assertEqual(composite["grants"], [grant])
        self.assertEqual(single["token"], composite["token"])
        self.assertTrue(Token.verify(self.space.pk, "target", "TASK", "123", "VIEW", single["token"]))
        self.assertFalse(Token.verify(self.space.pk, "other", "TASK", "123", "VIEW", single["token"]))
        self.assertEqual(mock_validate.call_count, 2)

    def test_reject_invalid_target_user(self):
        """缺少用户名或格式非法时拒绝申请。"""
        grant = {"resource_type": "TASK", "resource_id": "123", "permission_type": "VIEW"}
        for user_data in ({}, {"user": ""}, {"user": "  "}, {"user": None}, {"user": 123}, {"user": "a" * 33}):
            with self.subTest(user_data=user_data):
                result = json.loads(self._apply({**grant, **user_data}).content)
                self.assertFalse(result["result"])
                self.assertEqual(result["code"], 400)
                self.assertIn("user", result["message"])
        self.assertFalse(Token.objects.filter(space_id=self.space.pk).exists())

    def test_reject_unauthorized_application(self):
        """缺少应用身份、空间绑定或租户匹配时拒绝申请。"""
        grant = {"resource_type": "TASK", "resource_id": "123", "permission_type": "VIEW"}
        for identity in (
            {"has_jwt": False},
            {"verified": False},
            {"app_code": "other-app"},
            {"tenant": "tenant-b"},
        ):
            with self.subTest(identity=identity):
                response = self._apply({"user": "target", **grant}, **identity)
                self.assertEqual(response.status_code, 403)
        self.assertFalse(Token.objects.filter(space_id=self.space.pk).exists())
