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
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.urls import resolve
from rest_framework.routers import SimpleRouter
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.interface.task.view import TaskInterfaceViewSet
from tests.utils.node_detail import NODE_DETAIL_VALUES, node_detail_data


@pytest.mark.parametrize("value, expected", NODE_DETAIL_VALUES)
def test_node_detail_proxy_renders_special_values(value, expected):
    """engine JSON 解码后仍可能含代理字符，不能在 interface 再次触发 500。"""
    router = SimpleRouter()
    router.register("task", TaskInterfaceViewSet, basename="task")
    path = "/task/get_task_node_detail/123/node/node_1/"
    match = resolve(path, urlconf=tuple(router.urls))
    request = APIRequestFactory().get(path, {"space_id": "1"})
    force_authenticate(request, user=SimpleNamespace(is_superuser=True, username="admin"))
    # 模拟 engine 已将不支持的对象转换为展示值，并经过真实 JSON 编解码。
    engine_result = json.loads(json.dumps({"result": True, "data": node_detail_data(expected), "message": ""}))

    with patch("bkflow.interface.task.view.TaskComponentClient") as client:
        client.return_value.get_task_node_detail.return_value = engine_result
        response = match.func(request, **match.kwargs)
        response.render()

    result = json.loads(response.content.decode("utf-8"))
    assert response.status_code == 200
    assert result["result"] is True
    assert result["data"]["outputs"][0]["value"] == expected
    assert result["data"]["inputs"]["bk_input_vars"]["value"] == expected
