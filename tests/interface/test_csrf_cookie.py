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

from unittest import mock
from unittest.mock import MagicMock

from django.test import RequestFactory

from bkflow.interface.views import (
    home,
    is_admin_or_current_space_superuser,
    is_admin_or_space_superuser,
)
from bkflow.utils.django_error_hanlder import page_not_found


def _request(path, user=None, get_params=None):
    request = RequestFactory().get(path, data=get_params or {})
    request.user = user or MagicMock(username="admin", is_superuser=True)
    return request


class TestSpaEntriesEnsureCsrfCookie:
    """管理端 SPA 首屏 GET 必须下发 CSRF cookie，否则保存配置 / 任务列表 POST 会失败。"""

    @mock.patch("bkflow.interface.views.Space.objects.filter")
    @mock.patch("bkflow.interface.views.SpaceConfig.objects.get_space_ids_of_superuser", return_value=[])
    def test_is_admin_user_marks_csrf_cookie(self, _mock_ids, _mock_filter):
        request = _request("/is_admin_user/")
        is_admin_or_space_superuser(request)
        assert request.META.get("CSRF_COOKIE_USED") is True

    @mock.patch("bkflow.interface.views.SpaceConfig.objects.filter")
    def test_is_current_space_admin_marks_csrf_cookie(self, mock_filter):
        mock_filter.return_value.exists.return_value = False
        request = _request("/is_current_space_admin/", get_params={"space_id": "240"})
        is_admin_or_current_space_superuser(request)
        assert request.META.get("CSRF_COOKIE_USED") is True

    @mock.patch("bkflow.interface.views.render", return_value=MagicMock())
    def test_home_marks_csrf_cookie(self, _mock_render):
        request = _request("/")
        home(request)
        assert request.META.get("CSRF_COOKIE_USED") is True

    @mock.patch("bkflow.utils.django_error_hanlder.render", return_value=MagicMock())
    @mock.patch("bkflow.utils.django_error_hanlder.LoginRequiredMiddleware")
    def test_page_not_found_marks_csrf_cookie(self, mock_middleware_cls, _mock_render):
        mock_middleware_cls.return_value.authenticate.return_value = MagicMock(username="admin")
        request = _request("/bkflow_engine_admin/")
        page_not_found(request, exception=None)
        assert request.META.get("CSRF_COOKIE_USED") is True
