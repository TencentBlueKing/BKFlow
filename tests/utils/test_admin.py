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
from django.test import override_settings

from bkflow.utils.admin import get_admin_username, is_admin_username


class TestAdminUtils:
    """测试管理员工具函数"""

    def test_get_admin_username_default(self):
        """测试默认值"""
        with override_settings():
            from django.conf import settings

            if hasattr(settings, "BK_ADMIN_USERNAME"):
                delattr(settings, "BK_ADMIN_USERNAME")
            assert get_admin_username() == "admin"

    @override_settings(BK_ADMIN_USERNAME="bk_admin_test123")
    def test_get_admin_username_configured(self):
        """测试配置值"""
        assert get_admin_username() == "bk_admin_test123"

    @override_settings(BK_ADMIN_USERNAME="bk_admin_xyz")
    def test_is_admin_username_current(self):
        """测试当前配置的管理员"""
        assert is_admin_username("bk_admin_xyz") is True
        assert is_admin_username("other_user") is False

    def test_is_admin_username_legacy(self):
        """测试历史遗留值"""
        assert is_admin_username("admin") is True
        assert is_admin_username("bk_admin") is True

    def test_is_admin_username_empty(self):
        """测试空值"""
        assert is_admin_username("") is False
        assert is_admin_username(None) is False
