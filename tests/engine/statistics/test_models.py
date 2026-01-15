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

from django.test import TestCase
from django.utils import timezone

from bkflow.statistics.models import TaskflowExecutedNodeStatistics, TaskflowStatistics


class TestTaskflowStatistics(TestCase):
    """任务统计模型测试"""

    def test_create_taskflow_statistics(self):
        """测试创建任务统计"""
        stat = TaskflowStatistics.objects.create(
            task_id=1,
            instance_id="instance_001",
            template_id=1,
            space_id=1,
            engine_id="engine_a",
            atom_total=5,
            node_total=10,
            creator="admin",
            executor="admin",
            create_time=timezone.now(),
            create_method="API",
            trigger_method="manual",
            is_started=True,
            is_finished=True,
            is_success=True,
            final_state="FINISHED",
        )
        self.assertEqual(stat.task_id, 1)
        self.assertEqual(stat.engine_id, "engine_a")
        self.assertTrue(stat.is_success)

    def test_elapsed_time_calculation(self):
        """测试耗时计算"""
        start_time = timezone.now()
        finish_time = start_time + timedelta(seconds=120)

        stat = TaskflowStatistics.objects.create(
            task_id=2,
            instance_id="instance_002",
            space_id=1,
            create_time=start_time,
            start_time=start_time,
            finish_time=finish_time,
            elapsed_time=120,
        )
        self.assertEqual(stat.elapsed_time, 120)

    def test_unique_task_id(self):
        """测试任务ID唯一性"""
        TaskflowStatistics.objects.create(
            task_id=3,
            instance_id="instance_003",
            space_id=1,
            create_time=timezone.now(),
        )
        with self.assertRaises(Exception):
            TaskflowStatistics.objects.create(
                task_id=3,
                instance_id="instance_003_dup",
                space_id=1,
                create_time=timezone.now(),
            )

    def test_str_representation(self):
        """测试字符串表示"""
        stat = TaskflowStatistics(task_id=1)
        self.assertEqual(str(stat), "Task_1")


class TestTaskflowExecutedNodeStatistics(TestCase):
    """节点执行统计模型测试"""

    def test_create_node_statistics(self):
        """测试创建节点执行统计"""
        stat = TaskflowExecutedNodeStatistics.objects.create(
            component_code="test_component",
            version="v1.0",
            is_remote=False,
            task_id=1,
            instance_id="instance_001",
            template_id=1,
            space_id=1,
            engine_id="engine_a",
            node_id="node_1",
            node_name="测试节点",
            started_time=timezone.now(),
            archived_time=timezone.now(),
            elapsed_time=10,
            status=True,
            state="FINISHED",
            is_skip=False,
            retry_count=0,
            task_create_time=timezone.now(),
        )
        self.assertEqual(stat.component_code, "test_component")
        self.assertTrue(stat.status)
        self.assertEqual(stat.state, "FINISHED")

    def test_node_with_retry(self):
        """测试重试节点"""
        stat = TaskflowExecutedNodeStatistics.objects.create(
            component_code="test_component",
            version="v1.0",
            task_id=1,
            instance_id="instance_001",
            space_id=1,
            node_id="node_1",
            started_time=timezone.now(),
            status=False,
            state="FAILED",
            is_retry=True,
            retry_count=2,
            task_create_time=timezone.now(),
        )
        self.assertTrue(stat.is_retry)
        self.assertEqual(stat.retry_count, 2)

    def test_node_with_skip(self):
        """测试跳过的节点"""
        stat = TaskflowExecutedNodeStatistics.objects.create(
            component_code="test_component",
            version="v1.0",
            task_id=1,
            instance_id="instance_001",
            space_id=1,
            node_id="node_1",
            started_time=timezone.now(),
            status=True,
            state="FINISHED",
            is_skip=True,
            task_create_time=timezone.now(),
        )
        self.assertTrue(stat.is_skip)

    def test_remote_plugin_node(self):
        """测试远程插件节点"""
        stat = TaskflowExecutedNodeStatistics.objects.create(
            component_code="remote_plugin_code",
            version="v2.0",
            is_remote=True,
            task_id=1,
            instance_id="instance_001",
            space_id=1,
            node_id="node_1",
            started_time=timezone.now(),
            status=True,
            state="FINISHED",
            task_create_time=timezone.now(),
        )
        self.assertTrue(stat.is_remote)
        self.assertEqual(stat.version, "v2.0")

    def test_str_representation(self):
        """测试字符串表示"""
        stat = TaskflowExecutedNodeStatistics(
            component_code="test_component",
            task_id=1,
            node_id="node_1",
        )
        self.assertEqual(str(stat), "test_component_1_node_1")
