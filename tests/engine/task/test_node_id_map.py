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
        # create_instance 会就地修改 tree（replace_all_id），故提前捕获原始模板节点 id
        original_act_ids = set(tree["activities"].keys())
        instance = TaskInstance.objects.create_instance(
            pipeline_tree=tree, space_id=1, create_method="DEBUG", creator="admin"
        )

        view = TaskInstanceViewSet.as_view({"get": "get_node_id_map"})
        request = self._create_request_with_auth("get", f"/task/{instance.id}/get_node_id_map/")
        response = view(request, pk=instance.id)

        assert response.status_code == status.HTTP_200_OK
        mapping = response.data["data"]
        # 每个模板节点 id 都应出现在映射的 key 中
        assert set(mapping.keys()) == original_act_ids
        # 运行时 id 应与模板 id 不同，证明确实发生了重映射
        assert all(mapping[k] != k for k in mapping)
