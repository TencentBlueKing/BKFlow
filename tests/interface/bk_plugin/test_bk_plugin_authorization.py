from unittest import TestCase

import pytest
from blueapps.account.models import User
from rest_framework import status
from rest_framework.test import APIRequestFactory

from bkflow.bk_plugin.models import AuthStatus, BKPlugin, BKPluginAuthorization
from bkflow.bk_plugin.views import BKPluginManagerViewSet, BKPluginViewSet
from bkflow.constants import WHITE_LIST
from bkflow.exceptions import PluginUnAuthorization
from bkflow.space.models import Space
from tests.interface.bk_plugin.plugins import remote_plugin_one, remote_plugin_two


@pytest.mark.django_db
class TestBKPlugin(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin_user = User.objects.create_superuser(username="test_admin", password="password")
        self.normal_user = User.objects.create_user(username="normal_user", password="password")
        self.visitor_user = User.objects.create_user(username="visitor_user", password="password")
        self.space = Space.objects.create(name="test_space", platform_url="xxxx", app_code="test", desc="test")
        self.plugin_one = BKPlugin.objects.create(
            name="plugin1",
            code="plugin1",
            tag=1,
            managers=["normal_user", "test_admin"],
        )
        self.plugin_two = BKPlugin.objects.create(
            name="plugin2",
            code="plugin2",
            tag=1,
            managers=["test_admin"],
        )
        self.plugin_one_authorization = BKPluginAuthorization.objects.create(
            code=self.plugin_one.code,
            status=AuthStatus.authorized.value,
            status_update_time="2025-01-01 00:00:00",
            status_updator=self.admin_user.username,
        )
        self.plugin_two_authorization = BKPluginAuthorization.objects.create(
            code=self.plugin_two.code,
            status=AuthStatus.authorized.value,
            status_update_time="2025-01-01 00:00:00",
            config={WHITE_LIST: ["1"]},
            status_updator=self.admin_user.username,
        )

    def test_list(self):
        """测试拉取插件列表以及二次授权使用范围过滤"""

        url = "/api/bk_plugin/"
        request = self.factory.get(url)
        request.user = self.admin_user
        view_func = BKPluginViewSet.as_view({"get": "list"})
        response = view_func(request=request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["data"]["count"] == 2

        # 测试二次授权使用范围过滤
        filtered_request = self.factory.get(url, data={"tag": 1, "space_id": 2})
        filtered_request.user = self.normal_user
        filtered_response = view_func(filtered_request)
        assert filtered_response.status_code == status.HTTP_200_OK
        assert filtered_response.data["data"]["data"]["count"] == 1
        assert filtered_response.data["data"]["data"]["plugins"][0]["code"] == self.plugin_one.code

    def test_is_manager(self):
        """测试空间管理员判断"""

        url = "/api/bk_plugin/is_manager/"
        request = self.factory.get(url)
        request.user = self.visitor_user
        view_func = BKPluginViewSet.as_view({"get": "is_manager"})
        response = view_func(request=request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["data"]["is_manager"] is False

    def test_authorization_list(self):
        """测试拉取包含授权记录的插件列表"""
        url = "/api/bk_plugin/manager/"
        self.plugin_without_authorization_record = BKPlugin.objects.create(
            name="plugin3",
            code="plugin3",
            tag=1,
            managers=["test_admin"],
        )
        request = self.factory.get(url)
        request.user = self.admin_user
        view_func = BKPluginManagerViewSet.as_view({"get": "list"})
        response = view_func(request=request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["count"] == 3

        request.user = self.normal_user
        response = view_func(request=request)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["count"] == 1

    def test_authorization_partial_update(self):
        """测试更新授权记录"""

        url = f"/api/bk_plugin/manager/{self.plugin_one.code}/"
        request = self.factory.patch(
            url, data={"status": AuthStatus.unauthorized.value, "config": {WHITE_LIST: ["1", "2", "3"]}}, format="json"
        )
        request.user = self.admin_user
        view_func = BKPluginManagerViewSet.as_view({"patch": "partial_update"})
        response = view_func(request=request, code=self.plugin_one.code)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["status"] == AuthStatus.unauthorized.value
        assert response.data["data"]["config"][WHITE_LIST] == ["1", "2", "3"]

    def test_fill_plugin_info(self):
        plugin = BKPlugin.objects.fill_plugin_info(remote_plugin_one)
        assert plugin.managers == ["test_user1", "test_user2"]
        assert plugin.code == "plugin1"
        assert plugin.tag == 1

    def test_is_same_plugin(self):
        fields_to_compare = [f.name for f in BKPlugin._meta.fields if not f.primary_key]
        assert BKPlugin.objects.is_same_plugin(self.plugin_one, self.plugin_two, fields_to_compare) is False

    def test_sync_bk_plugins(self):
        plugins_dict = {
            "test-plugin": remote_plugin_one,
            "test-plugin2": remote_plugin_two,
        }
        BKPlugin.objects.sync_bk_plugins(plugins_dict)
        assert BKPlugin.objects.count() == 2
        plugin_one = BKPlugin.objects.get(code="plugin1")
        assert plugin_one.managers == ["test_user1", "test_user2"]

    def test_get_codes_by_space_id(self):
        codes = BKPluginAuthorization.objects.get_codes_by_space_id("1")
        assert codes == ["plugin1", "plugin2"]
        codes = BKPluginAuthorization.objects.get_codes_by_space_id("2")
        assert codes == ["plugin1"]

    def test_batch_check_authorization(self):
        exist_codes = ["plugin1", "plugin2"]
        with self.assertRaises(PluginUnAuthorization) as context:
            BKPluginAuthorization.objects.batch_check_authorization(exist_codes, 2)
        self.assertEqual(str(context.exception), "流程中存在未授权插件：['plugin2']")
