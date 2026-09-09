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
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from django.conf import settings
from django.urls import resolve
from rest_framework.routers import SimpleRouter
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.task.operations import OperationResult
from bkflow.task.views import TaskInstanceViewSet
from tests.utils.node_detail import NODE_DETAIL_VALUES, node_detail_data


@pytest.mark.parametrize("value, expected", NODE_DETAIL_VALUES)
def test_node_detail_renders_without_mutating_execution_data(value, expected):
    """真实路由和 renderer 必须接受特殊输出，且不能改变后续执行使用的对象。"""
    original = copy.deepcopy(value)
    node_data = node_detail_data(value)
    router = SimpleRouter()
    router.register("task", TaskInstanceViewSet, basename="task")
    path = "/task/123/get_task_node_detail/node_1/"
    match = resolve(path, urlconf=tuple(router.urls))
    request = APIRequestFactory().get(path, {"component_code": "python_code"}, HTTP_BKFLOW_INTERNAL_SPACE_ID="1")
    force_authenticate(request, user=SimpleNamespace(is_superuser=False, username="tester"))
    request.app_internal_token = settings.APP_INTERNAL_TOKEN
    task = Mock(space_id=1)
    task.has_node.return_value = True

    with patch.object(TaskInstanceViewSet, "get_object", return_value=task), patch(
        "bkflow.task.views.TaskNodeOperation"
    ) as operation:
        operation.return_value.get_node_data.return_value = OperationResult(result=True, data=node_data)
        operation.return_value.get_node_detail.return_value = OperationResult(
            result=True, data={"state": "FINISHED", "histories": [], "loop": 1}
        )
        response = match.func(request, **match.kwargs)
        response.render()

    result = json.loads(response.content.decode("utf-8"))
    assert response.status_code == 200
    assert result["result"] is True
    assert result["data"]["state"] == "FINISHED"
    assert result["data"]["outputs"][0]["value"] == expected
    assert result["data"]["inputs"]["bk_input_vars"]["value"] == expected
    assert value == original
    assert node_data["outputs"][0]["value"] is value
