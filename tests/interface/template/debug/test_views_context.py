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

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.template.models import DebugContext
from bkflow.template.views.debug import DebugViewSet

User = get_user_model()


@pytest.mark.django_db
class TestDebugContextViews:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.user, _ = User.objects.update_or_create(
            username="admin", defaults={"is_superuser": True, "is_staff": True}
        )

    def test_get_context_creates_and_returns(self, mocker):
        mocker.patch(
            "bkflow.template.debug.service.DebugService.pipeline_tree",
            new_callable=mocker.PropertyMock,
            return_value={"activities": {}, "flows": {}, "gateways": {}, "constants": {}},
        )
        mocker.patch(
            "bkflow.template.debug.service.DebugService.space_id",
            new_callable=mocker.PropertyMock,
            return_value=10,
        )
        view = DebugViewSet.as_view({"get": "context"})
        request = self.factory.get("/debug/context/", {"template_id": 1})
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 200
        assert response.data["status"] == "idle"
        assert DebugContext.objects.filter(template_id=1).exists()

    def test_input_schema_view(self, mocker):
        mocker.patch(
            "bkflow.template.debug.service.DebugService.pipeline_tree",
            new_callable=mocker.PropertyMock,
            return_value={
                "constants": {"${b}": {"name": "b", "show_type": "show", "value": "", "custom_type": "input"}}
            },
        )
        view = DebugViewSet.as_view({"get": "input_schema"})
        request = self.factory.get("/debug/input_schema/", {"template_id": 1})
        force_authenticate(request, user=self.user)
        response = view(request)
        assert response.status_code == 200
        assert response.data["fields"][0]["key"] == "${b}"
