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
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings

from module_settings import check_engine_admin_permission


@pytest.mark.django_db
class TestEngineAdminPermission:
    """测试 engine admin 权限检查"""

    def test_check_engine_admin_permission_with_superuser(self):
        """测试超级用户权限"""
        request = MagicMock()
        request.user.is_superuser = True
        request.app_internal_token = None

        result = check_engine_admin_permission(request)
        assert result is True

    def test_check_engine_admin_permission_with_internal_token(self):
        """测试内部 token 权限"""
        request = MagicMock()
        request.user.is_superuser = False
        request.app_internal_token = settings.APP_INTERNAL_TOKEN

        result = check_engine_admin_permission(request)
        assert result is True

    def test_check_engine_admin_permission_with_validation_skip(self):
        """测试跳过验证权限"""
        with patch("django.conf.settings.APP_INTERNAL_VALIDATION_SKIP", True):
            request = MagicMock()
            request.user.is_superuser = False
            request.app_internal_token = None

            result = check_engine_admin_permission(request)
            assert result is True

    def test_check_engine_admin_permission_without_permission(self):
        """测试无权限情况"""
        with patch("django.conf.settings.APP_INTERNAL_VALIDATION_SKIP", False):
            request = MagicMock()
            request.user.is_superuser = False
            request.app_internal_token = "wrong_token"

            result = check_engine_admin_permission(request)
            assert result is False

    def test_engine_admin_permission_setting(self):
        """测试 engine admin 权限配置"""
        assert hasattr(settings, "PIPELINE_ENGINE_ADMIN_API_PERMISSION")
        assert settings.PIPELINE_ENGINE_ADMIN_API_PERMISSION == "module_settings.check_engine_admin_permission"


@pytest.mark.django_db
class TestEngineAdminURLs:
    """测试 engine admin URLs 配置"""

    def test_engine_admin_urls_registered(self):
        """验证 engine admin URLs 已注册"""
        # 检查 engine admin 相关的 URL patterns
        engine_admin_actions = [
            "task_pause",
            "task_resume",
            "task_revoke",
            "node_retry",
            "node_skip",
            "node_callback",
            "node_skip_exg",
            "node_skip_cpg",
            "node_forced_fail",
        ]

        # 验证 engine admin 视图可以导入
        from pipeline.contrib.engine_admin import views as engine_admin_views

        for action in engine_admin_actions:
            assert hasattr(engine_admin_views, action), f"engine_admin_views 应该有 {action} 方法"
