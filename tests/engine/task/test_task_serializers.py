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

import pytest
from pipeline.exceptions import PipelineException

from bkflow.task.serializers import CreateTaskInstanceSerializer


@pytest.mark.django_db
class TestCreateTaskInstanceSerializer:
    """测试 CreateTaskInstanceSerializer 中的 validate 方法"""

    @mock.patch("bkflow.task.serializers.validate_web_pipeline_tree")
    @mock.patch("bkflow.task.serializers.standardize_pipeline_node_name")
    def test_validate_pipeline_tree_exception(self, mock_standardize, mock_validate):
        """测试 pipeline_tree 校验抛出 PipelineException 的情况"""
        mock_standardize.return_value = None
        mock_validate.side_effect = PipelineException("流程结构无效")

        pipeline_tree = {
            "activities": {},
            "constants": {},
            "outputs": [],
            "start_event": {},
            "end_event": {},
            "flows": {},
            "gateways": {},
        }
        data = {
            "space_id": 1,
            "name": "test_task",
            "pipeline_tree": pipeline_tree,
            "creator": "admin",
            "create_method": "API",
            "trigger_method": "api",
        }

        serializer = CreateTaskInstanceSerializer(data=data)

        assert not serializer.is_valid()
        assert "pipeline_tree" in serializer.errors
        # 验证异常被正确捕获并转换为 ValidationError

    @mock.patch("bkflow.task.serializers.validate_web_pipeline_tree")
    @mock.patch("bkflow.task.serializers.standardize_pipeline_node_name")
    def test_validate_success(self, mock_standardize, mock_validate):
        """测试正常校验通过的情况"""
        mock_standardize.return_value = None
        mock_validate.return_value = None

        pipeline_tree = {
            "activities": {},
            "constants": {},
            "outputs": [],
            "start_event": {},
            "end_event": {},
            "flows": {},
            "gateways": {},
        }
        data = {
            "space_id": 1,
            "name": "test_task",
            "pipeline_tree": pipeline_tree,
            "creator": "admin",
            "create_method": "API",
            "trigger_method": "api",
        }

        serializer = CreateTaskInstanceSerializer(data=data)

        # 验证序列化器调用了相关的校验函数
        serializer.is_valid()
        mock_standardize.assert_called_once()
        mock_validate.assert_called_once()
