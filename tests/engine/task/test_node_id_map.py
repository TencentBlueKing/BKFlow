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
from unittest.mock import MagicMock

import pytest
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIRequestFactory

from bkflow.task.models import TaskInstance
from bkflow.task.views import TaskInstanceViewSet
from bkflow.utils.pipeline import build_default_pipeline_tree


@pytest.mark.django_db(transaction=True)
class TestGetNodeIdMap:
    """测试 TaskInstanceViewSet.get_node_id_map：模板节点 id -> 运行时节点 id 映射"""

    def setup_method(self):
        self.factory = APIRequestFactory()

    def _create_request_with_auth(self, method, path, data=None, space_id="1", from_superuser="0", **kwargs):
        """创建带 AppInternalPermission 认证的请求"""
        if method == "get":
            request = self.factory.get(path, data, **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")

        request.user = MagicMock()
        request.user.username = "test_user"
        request.user.is_superuser = False
        request.app_internal_token = settings.APP_INTERNAL_TOKEN

        if space_id:
            request.META[f"HTTP_{settings.APP_INTERNAL_SPACE_ID_HEADER_KEY}"] = space_id
        if from_superuser:
            request.META[f"HTTP_{settings.APP_INTERNAL_FROM_SUPERUSER_HEADER_KEY}"] = from_superuser

        return request

    def test_get_node_id_map_returns_template_to_runtime_mapping(self):
        tree = build_default_pipeline_tree()
        original_flow_id = tree["start_event"]["outgoing"]
        original_act_id = next(iter(tree["activities"]))
        gateway_id = "gateway_template_id"
        gateway_flow_id = "gateway_flow_id"
        tree["flows"][original_flow_id]["target"] = gateway_id
        tree["flows"][gateway_flow_id] = {
            "id": gateway_flow_id,
            "is_default": True,
            "source": gateway_id,
            "target": original_act_id,
        }
        tree["activities"][original_act_id]["incoming"] = [gateway_flow_id]
        tree["gateways"][gateway_id] = {
            "id": gateway_id,
            "type": "ExclusiveGateway",
            "incoming": original_flow_id,
            "outgoing": [gateway_flow_id],
            "conditions": {},
            "default_condition": {"flow_id": gateway_flow_id},
        }
        # create_instance 会就地修改 tree（replace_all_id），故提前捕获原始模板节点 id
        original_act_ids = set(tree["activities"].keys())
        original_gateway_ids = set(tree["gateways"].keys())
        instance = TaskInstance.objects.create_instance(
            pipeline_tree=tree, space_id=1, create_method="DEBUG", creator="admin"
        )

        view = TaskInstanceViewSet.as_view({"get": "get_node_id_map"})
        request = self._create_request_with_auth("get", f"/task/{instance.id}/get_node_id_map/")
        response = view(request, pk=instance.id)

        assert response.status_code == status.HTTP_200_OK
        mapping = response.data["data"]
        # 每个模板节点 id 都应出现在映射的 key 中
        assert set(mapping.keys()) == original_act_ids | original_gateway_ids
        # 运行时 id 应与模板 id 不同，证明确实发生了重映射
        assert all(mapping[k] != k for k in mapping)
        # value 应为任务执行数据中真实的运行时节点 id
        runtime_ids = set(instance.execution_data["activities"].keys()) | set(
            instance.execution_data["gateways"].keys()
        )
        assert set(mapping.values()) == runtime_ids

    def test_get_node_id_map_returns_empty_when_no_activities(self):
        """execution_data 为空/无 activities 时，应返回空映射而非报错"""
        instance = TaskInstance.objects.create_instance(
            pipeline_tree=build_default_pipeline_tree(), space_id=1, create_method="DEBUG", creator="admin"
        )
        # 将执行数据置为无 activities 的形态，验证守卫分支返回空映射
        TaskInstance.objects.filter(id=instance.id).update(execution_snapshot_id=None)
        instance.refresh_from_db()

        view = TaskInstanceViewSet.as_view({"get": "get_node_id_map"})
        request = self._create_request_with_auth("get", f"/task/{instance.id}/get_node_id_map/")
        response = view(request, pk=instance.id)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] == {}
