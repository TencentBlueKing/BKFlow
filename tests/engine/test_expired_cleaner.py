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
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from bkflow.contrib.expired_cleaner.tasks import clean_task
from bkflow.contrib.expired_cleaner.utils import (
    chunk_data,
    delete_expired_data,
    get_expired_data,
)
from bkflow.task.models import TaskInstance, TaskMockData, TaskOperationRecord
from bkflow.utils.pipeline import build_default_pipeline_tree


@pytest.mark.django_db(transaction=True)
class TestExpiredCleaner:
    """测试过期数据清理功能"""

    def test_chunk_data(self):
        """测试数据分块功能"""
        data = list(range(10))
        chunk_size = 3
        result = chunk_data(data, chunk_size, lambda x: x)
        assert len(result) == 4  # 10 / 3 = 4 块
        assert result[0] == [0, 1, 2]
        assert result[1] == [3, 4, 5]
        assert result[2] == [6, 7, 8]
        assert result[3] == [9]

    @patch("django.conf.settings.CLEAN_TASK_BATCH_NUM", 100)
    @patch("django.conf.settings.CLEAN_TASK_NODE_BATCH_NUM", 100)
    def test_get_expired_data(self):
        """测试获取过期数据"""
        # No expired tasks
        expired_time = timezone.now() - timedelta(days=30)
        expired_data, expired_batch_data = get_expired_data(expired_time)
        assert expired_data == {}

        # With expired tasks
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        TaskInstance.objects.filter(id=task_instance.id).update(create_time=expired_time - timedelta(days=1))
        expired_data, expired_batch_data = get_expired_data(expired_time)
        assert "task_instance" in expired_data

    @patch("django.conf.settings.CLEAN_TASK_BATCH_NUM", 100)
    @patch("django.conf.settings.CLEAN_TASK_NODE_BATCH_NUM", 100)
    def test_delete_expired_data(self):
        """测试删除过期数据"""
        # 创建过期任务和相关数据
        expired_time = timezone.now() - timedelta(days=30)
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        # 使用 update 方法更新 create_time，避免直接赋值
        TaskInstance.objects.filter(id=task_instance.id).update(create_time=expired_time - timedelta(days=1))
        task_instance.refresh_from_db()

        task_mock_data = TaskMockData.objects.create(taskflow_id=task_instance.id, data={})
        task_operation_record = TaskOperationRecord.objects.create(
            instance_id=task_instance.id, operator="test", operate_type="start", operate_source="api"
        )

        # 验证数据存在
        assert TaskInstance.objects.filter(id=task_instance.id).exists()
        assert TaskMockData.objects.filter(id=task_mock_data.id).exists()
        assert TaskOperationRecord.objects.filter(id=task_operation_record.id).exists()

        # 删除过期数据
        delete_expired_data(expired_time)

        # 验证数据已被删除
        assert not TaskInstance.objects.filter(id=task_instance.id).exists()
        assert not TaskMockData.objects.filter(id=task_mock_data.id).exists()
        assert not TaskOperationRecord.objects.filter(id=task_operation_record.id).exists()

    @patch("bkflow.contrib.expired_cleaner.tasks.delete_expired_data")
    def test_clean_task(self, mock_delete_expired_data):
        """测试清理任务"""
        # Enabled
        with patch("django.conf.settings.ENABLE_CLEAN_TASK", True):
            clean_task()
            mock_delete_expired_data.assert_called_once()

        # Disabled
        mock_delete_expired_data.reset_mock()
        with patch("django.conf.settings.ENABLE_CLEAN_TASK", False):
            clean_task()
            mock_delete_expired_data.assert_not_called()
