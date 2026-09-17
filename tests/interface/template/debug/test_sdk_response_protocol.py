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

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEBUG_VIEW_SOURCE = PROJECT_ROOT / "bkflow" / "template" / "views" / "debug.py"
TEMPLATE_URL_SOURCE = PROJECT_ROOT / "bkflow" / "template" / "urls.py"
APIGW_RESOURCE_SOURCE = PROJECT_ROOT / "bkflow" / "apigw" / "management" / "commands" / "data" / "api-resources.yml"


def test_debug_viewset_uses_standard_response_wrapper():
    """权限 mixin 调整后，实际响应仍由统一视图包装。"""
    from types import SimpleNamespace
    from unittest.mock import patch

    from django.test import override_settings
    from rest_framework.test import APIRequestFactory, force_authenticate

    from bkflow.template.views.debug import DebugViewSet

    request = APIRequestFactory().get("/debug/context/", {"template_id": 1})
    force_authenticate(request, user=SimpleNamespace(is_superuser=True, is_authenticated=True))
    with override_settings(ENABLE_MULTI_TENANT_MODE=False, BLOCK_ADMIN_PERMISSION=False), patch(
        "bkflow.template.views.debug.DebugService"
    ) as service:
        service.return_value.build_context_view.return_value = {"context": "test"}
        response = DebugViewSet.as_view({"get": "context"})(request)
    assert response.data == {"result": True, "data": {"context": "test"}, "code": "0", "message": ""}


def test_debug_viewset_has_single_internal_route():
    source = TEMPLATE_URL_SOURCE.read_text()

    assert "DebugSdkViewSet" not in source
    assert 'router.register(r"^debug", DebugViewSet, basename="debug")' in source
    assert 'router.register(r"^debug_sdk"' not in source


def test_sdk_debug_apigw_resources_route_to_debug_viewset():
    source = APIGW_RESOURCE_SOURCE.read_text()

    sdk_debug_paths = [
        "context",
        "input_schema",
        "global_run",
        "reset",
        "terminate",
        "history",
        "reset_impact",
        "step_run",
        "node_mock",
        "context_var",
    ]
    for path in sdk_debug_paths:
        assert f"path: /{{env.api_sub_path}}api/template/debug/{path}/" in source
        assert f"path: /{{env.api_sub_path}}api/template/debug_sdk/{path}/" not in source
