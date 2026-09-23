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
from unittest.mock import patch

from bkflow.apigw.serializers.token import TokenResourceValidator


class TestTokenResourceValidator:
    @patch("bkflow.apigw.serializers.token.TaskComponentClient")
    def test_task_exists_uses_task_list_and_accepts_count_one(self, mock_client_cls):
        """按 id 查列表 count=1 即视为存在，不走任务详情。"""
        client = mock_client_cls.return_value
        client.task_list.return_value = {
            "result": True,
            "data": {"count": 1, "results": [{"id": 40, "space_id": 205, "create_method": "DEBUG"}]},
            "code": "0",
            "message": "",
        }

        validator = TokenResourceValidator(space_id=205, resource_type="TASK", resource_id="40")

        assert validator.task_exists("40") is True
        client.task_list.assert_called_once_with(data={"id": "40", "space_id": 205, "limit": 1, "offset": 0})
        client.get_task_detail.assert_not_called()

    @patch("bkflow.apigw.serializers.token.TaskComponentClient")
    def test_task_exists_rejects_when_list_count_is_zero(self, mock_client_cls):
        """列表查不到（含跨空间）时拒绝申请。"""
        mock_client_cls.return_value.task_list.return_value = {
            "result": True,
            "data": {"count": 0, "results": []},
            "code": "0",
            "message": "",
        }

        validator = TokenResourceValidator(space_id=205, resource_type="TASK", resource_id="40")

        assert validator.task_exists("40") is False

    @patch("bkflow.apigw.serializers.token.TaskComponentClient")
    def test_task_exists_rejects_when_list_query_fails(self, mock_client_cls):
        """列表查询失败时拒绝申请。"""
        mock_client_cls.return_value.task_list.return_value = {
            "result": False,
            "data": None,
            "code": "500",
            "message": "error",
        }

        validator = TokenResourceValidator(space_id=205, resource_type="TASK", resource_id="40")

        assert validator.task_exists("40") is False
