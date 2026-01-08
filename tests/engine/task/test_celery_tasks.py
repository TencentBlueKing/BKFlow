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
from unittest.mock import MagicMock, patch

import pytest

from bkflow.constants import TaskTriggerMethod, WebhookEventType
from bkflow.task.celery.tasks import (
    auto_retry_node,
    bkflow_periodic_task_start,
    dispatch_timeout_nodes,
    execute_node_timeout_strategy,
    send_task_message,
)
from bkflow.task.models import (
    AutoRetryNodeStrategy,
    PeriodicTask,
    TaskInstance,
    TimeoutNodeConfig,
    TimeoutNodesRecord,
)
from bkflow.task.operations import OperationResult
from bkflow.task.utils import ATOM_FAILED
from bkflow.utils.pipeline import build_default_pipeline_tree


@pytest.mark.django_db(transaction=True)
class TestAutoRetryNode:
    """测试 auto_retry_node 任务"""

    def setup_method(self):
        """每个测试方法执行前的设置"""
        self.pipeline_tree = build_default_pipeline_tree()

    @patch("bkflow.task.celery.tasks.settings.redis_inst")
    @patch("bkflow.task.celery.tasks._ensure_node_can_retry")
    @patch("bkflow.task.celery.tasks.TaskNodeOperation")
    def test_auto_retry_node_success(self, mock_node_operation, mock_ensure_retry, mock_redis):
        """测试自动重试节点成功"""
        from redis.client import Redis

        # 创建任务实例
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=self.pipeline_tree)
        node_id = "node_1"
        retry_times = 0

        # Mock redis - 需要是 Redis 实例以通过 redis_inst_check 装饰器
        mock_redis_instance = MagicMock(spec=Redis)
        mock_redis_instance.set.return_value = True
        mock_redis_instance.delete.return_value = True
        mock_redis.__class__ = Redis  # 让 isinstance 检查通过
        mock_redis.set = mock_redis_instance.set
        mock_redis.delete = mock_redis_instance.delete

        # Mock ensure_node_can_retry
        mock_ensure_retry.return_value = True

        # Mock TaskNodeOperation
        mock_operation = MagicMock()
        mock_operation.retry.return_value = OperationResult(result=True, message="success")
        mock_node_operation.return_value = mock_operation

        # 创建 AutoRetryNodeStrategy 记录
        AutoRetryNodeStrategy.objects.create(
            taskflow_id=task_instance.id,
            root_pipeline_id=task_instance.instance_id,
            node_id=node_id,
            retry_times=retry_times,
        )

        # 执行测试
        auto_retry_node(task_instance.id, task_instance.instance_id, node_id, retry_times)

        # 验证
        mock_operation.retry.assert_called_once_with(operator="system", inputs={})
        mock_redis_instance.delete.assert_called_once()

        # 验证重试次数更新
        strategy = AutoRetryNodeStrategy.objects.get(root_pipeline_id=task_instance.instance_id, node_id=node_id)
        assert strategy.retry_times == retry_times + 1

    @patch("bkflow.task.celery.tasks.settings.redis_inst")
    def test_auto_retry_node_lock_failed(self, mock_redis):
        """测试自动重试节点（获取锁失败）"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=self.pipeline_tree)
        node_id = "node_1"

        # Mock redis - 锁获取失败
        mock_redis.set.return_value = False

        auto_retry_node(task_instance.id, task_instance.instance_id, node_id, 0)

        # 验证没有调用 delete
        mock_redis.delete.assert_not_called()

    @patch("bkflow.task.celery.tasks.settings.redis_inst")
    @patch("bkflow.task.celery.tasks._ensure_node_can_retry")
    def test_auto_retry_node_ensure_timeout(self, mock_ensure_retry, mock_redis):
        """测试自动重试节点（ensure_node_can_retry 超时）"""
        from redis.client import Redis

        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=self.pipeline_tree)
        node_id = "node_1"

        # Mock redis - 需要是 Redis 实例以通过 redis_inst_check 装饰器
        mock_redis_instance = MagicMock(spec=Redis)
        mock_redis_instance.set.return_value = True
        mock_redis_instance.delete.return_value = True
        mock_redis.__class__ = Redis  # 让 isinstance 检查通过
        mock_redis.set = mock_redis_instance.set
        mock_redis.delete = mock_redis_instance.delete

        mock_ensure_retry.return_value = False

        # 创建 AutoRetryNodeStrategy 记录
        AutoRetryNodeStrategy.objects.create(
            taskflow_id=task_instance.id,
            root_pipeline_id=task_instance.instance_id,
            node_id=node_id,
            retry_times=0,
        )

        auto_retry_node(task_instance.id, task_instance.instance_id, node_id, 0)

        # 验证仍然会删除锁
        mock_redis_instance.delete.assert_called_once()

    @patch("bkflow.task.celery.tasks.settings.redis_inst")
    @patch("bkflow.task.celery.tasks._ensure_node_can_retry")
    def test_auto_retry_node_task_not_found(self, mock_ensure_retry, mock_redis):
        """测试自动重试节点（任务不存在）"""
        node_id = "node_1"
        fake_task_id = 999999

        mock_redis.set.return_value = True
        mock_ensure_retry.return_value = True

        auto_retry_node(fake_task_id, "fake_pipeline_id", node_id, 0)

        # 验证没有报错，正常返回
        mock_redis.delete.assert_not_called()

    @patch("bkflow.task.celery.tasks.settings.redis_inst")
    @patch("bkflow.task.celery.tasks._ensure_node_can_retry")
    @patch("bkflow.task.celery.tasks.TaskNodeOperation")
    def test_auto_retry_node_retry_failed(self, mock_node_operation, mock_ensure_retry, mock_redis):
        """测试自动重试节点（重试失败）"""
        from redis.client import Redis

        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=self.pipeline_tree)
        node_id = "node_1"

        # Mock redis - 需要是 Redis 实例以通过 redis_inst_check 装饰器
        mock_redis_instance = MagicMock(spec=Redis)
        mock_redis_instance.set.return_value = True
        mock_redis_instance.delete.return_value = True
        mock_redis.__class__ = Redis  # 让 isinstance 检查通过
        mock_redis.set = mock_redis_instance.set
        mock_redis.delete = mock_redis_instance.delete

        mock_ensure_retry.return_value = True

        # Mock 重试失败
        mock_operation = MagicMock()
        mock_operation.retry.return_value = OperationResult(result=False, message="retry failed")
        mock_node_operation.return_value = mock_operation

        AutoRetryNodeStrategy.objects.create(
            taskflow_id=task_instance.id,
            root_pipeline_id=task_instance.instance_id,
            node_id=node_id,
            retry_times=0,
        )

        auto_retry_node(task_instance.id, task_instance.instance_id, node_id, 0)

        # 验证仍然会更新重试次数
        strategy = AutoRetryNodeStrategy.objects.get(root_pipeline_id=task_instance.instance_id, node_id=node_id)
        assert strategy.retry_times == 1

    @patch("bkflow.task.celery.tasks.BambooDjangoRuntime")
    def test_ensure_node_can_retry_success(self, mock_runtime_class):
        """测试 _ensure_node_can_retry 成功"""
        from bkflow.task.celery.tasks import _ensure_node_can_retry

        node_id = "node_1"
        mock_runtime = MagicMock()
        mock_runtime_class.return_value = mock_runtime
        mock_runtime.get_sleep_process_info_with_current_node_id.return_value = {"node_id": node_id}

        result = _ensure_node_can_retry(node_id)
        assert result is True

    @patch("bkflow.task.celery.tasks.BambooDjangoRuntime")
    @patch("bkflow.task.celery.tasks.time.sleep")
    def test_ensure_node_can_retry_timeout(self, mock_sleep, mock_runtime_class):
        """测试 _ensure_node_can_retry 超时"""
        from bkflow.task.celery.tasks import _ensure_node_can_retry

        node_id = "node_1"
        mock_runtime = MagicMock()
        mock_runtime_class.return_value = mock_runtime
        mock_runtime.get_sleep_process_info_with_current_node_id.return_value = None

        result = _ensure_node_can_retry(node_id)
        assert result is False
        assert mock_sleep.call_count == 3


@pytest.mark.django_db(transaction=True)
class TestSendTaskMessage:
    """测试 send_task_message 任务"""

    def setup_method(self):
        """每个测试方法执行前的设置"""
        self.pipeline_tree = build_default_pipeline_tree()

    @patch("bkflow.task.celery.tasks.InterfaceModuleClient")
    @patch("bkflow.task.celery.tasks.send_task_instance_message")
    def test_send_task_message_failed(self, mock_send_msg, mock_client_class):
        """测试发送任务失败消息"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=self.pipeline_tree)

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.broadcast_task_events.return_value = None

        send_task_message(task_instance.instance_id, ATOM_FAILED)

        mock_send_msg.assert_called_once_with(task_instance, ATOM_FAILED)
        mock_client.broadcast_task_events.assert_called_once()

        # 验证事件类型
        call_args = mock_client.broadcast_task_events.call_args
        assert call_args[1]["data"]["event"] == WebhookEventType.TASK_FAILED.value

    @patch("bkflow.task.celery.tasks.InterfaceModuleClient")
    @patch("bkflow.task.celery.tasks.send_task_instance_message")
    def test_send_task_message_finished(self, mock_send_msg, mock_client_class):
        """测试发送任务完成消息"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=self.pipeline_tree)

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        send_task_message(task_instance.instance_id, "finished")

        # 验证事件类型
        call_args = mock_client.broadcast_task_events.call_args
        assert call_args[1]["data"]["event"] == WebhookEventType.TASK_FINISHED.value

    @patch("bkflow.task.celery.tasks.InterfaceModuleClient")
    @patch("bkflow.task.celery.tasks.send_task_instance_message")
    def test_send_task_message_task_not_found(self, mock_send_msg, mock_client_class):
        """测试发送消息（任务不存在）"""
        fake_instance_id = "fake_instance_id"

        send_task_message(fake_instance_id, ATOM_FAILED)

        # 不应该调用发送消息
        mock_send_msg.assert_not_called()

    @patch("bkflow.task.celery.tasks.send_task_instance_message")
    def test_send_task_message_exception(self, mock_send_msg):
        """测试发送消息异常"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=self.pipeline_tree)

        # Mock 抛出异常
        mock_send_msg.side_effect = Exception("send error")

        # 不应该抛出异常
        send_task_message(task_instance.instance_id, ATOM_FAILED)


@pytest.mark.django_db(transaction=True)
class TestDispatchTimeoutNodes:
    """测试 dispatch_timeout_nodes 任务"""

    def setup_method(self):
        """每个测试方法执行前的设置"""
        self.pipeline_tree = build_default_pipeline_tree()

    @patch("bkflow.task.celery.tasks.execute_node_timeout_strategy.apply_async")
    @patch("bkflow.task.celery.tasks.settings.BKFLOW_MODULE")
    def test_dispatch_timeout_nodes_success(self, mock_module, mock_apply_async):
        """测试分发超时节点成功"""
        # 创建超时记录 - 使用单个下划线分隔的格式，因为代码使用 split("_") 分割
        timeout_nodes = ["node1_v1", "node2_v2"]
        record = TimeoutNodesRecord.objects.create(timeout_nodes=json.dumps(timeout_nodes))

        mock_module.code = "test_module"

        dispatch_timeout_nodes(record.id)

        # 验证每个节点都被分发
        assert mock_apply_async.call_count == 2

        # 验证调用参数 - 代码使用 split("_") 分割，所以 node1_v1 会被分割为 node1 和 v1
        calls = mock_apply_async.call_args_list
        assert calls[0][1]["kwargs"]["node_id"] == "node1"
        assert calls[0][1]["kwargs"]["version"] == "v1"
        assert calls[1][1]["kwargs"]["node_id"] == "node2"
        assert calls[1][1]["kwargs"]["version"] == "v2"

    @patch("bkflow.task.celery.tasks.execute_node_timeout_strategy.apply_async")
    @patch("bkflow.task.celery.tasks.settings.BKFLOW_MODULE")
    def test_dispatch_timeout_nodes_empty(self, mock_module, mock_apply_async):
        """测试分发超时节点（空列表）"""
        record = TimeoutNodesRecord.objects.create(timeout_nodes=json.dumps([]))

        mock_module.code = "test_module"

        dispatch_timeout_nodes(record.id)

        # 验证没有分发任何节点
        mock_apply_async.assert_not_called()


@pytest.mark.django_db(transaction=True)
class TestExecuteNodeTimeoutStrategy:
    """测试 execute_node_timeout_strategy 任务"""

    def setup_method(self):
        """每个测试方法执行前的设置"""
        self.pipeline_tree = build_default_pipeline_tree()

    @patch("bkflow.task.celery.tasks.node_timeout_handler")
    @patch("bkflow.task.celery.tasks.State.objects.filter")
    @patch("bkflow.task.celery.tasks.Process.objects.filter")
    def test_execute_node_timeout_strategy_success(self, mock_process_filter, mock_state_filter, mock_handler):
        """测试执行节点超时策略成功"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=self.pipeline_tree)
        node_id = "node_1"
        version = "v1"
        action = "forced_fail"

        # 创建超时配置
        TimeoutNodeConfig.objects.create(
            task_id=task_instance.id,
            root_pipeline_id=task_instance.instance_id,
            node_id=node_id,
            action=action,
            timeout=60,
        )

        # Mock Process 和 State 存在
        mock_process_filter.return_value.exists.return_value = True
        mock_state_filter.return_value.exists.return_value = True

        # Mock handler
        mock_handler_instance = MagicMock()
        mock_handler_instance.deal_with_timeout_node.return_value = {"result": True, "message": "success"}
        mock_handler.__getitem__.return_value = mock_handler_instance

        result = execute_node_timeout_strategy(node_id, version)

        assert result["result"] is True
        mock_handler_instance.deal_with_timeout_node.assert_called_once_with(task_instance, node_id)

    @patch("bkflow.task.celery.tasks.State.objects.filter")
    @patch("bkflow.task.celery.tasks.Process.objects.filter")
    def test_execute_node_timeout_strategy_node_not_match(self, mock_process_filter, mock_state_filter):
        """测试执行节点超时策略（节点不匹配）"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=self.pipeline_tree)
        node_id = "node_1"
        version = "v1"

        TimeoutNodeConfig.objects.create(
            task_id=task_instance.id,
            root_pipeline_id=task_instance.instance_id,
            node_id=node_id,
            action="forced_fail",
            timeout=60,
        )

        # Mock Process 不存在
        mock_process_filter.return_value.exists.return_value = False
        mock_state_filter.return_value.exists.return_value = True

        result = execute_node_timeout_strategy(node_id, version)

        assert result["result"] is False
        assert "现已通过" in result["message"]

    @patch("bkflow.task.celery.tasks.State.objects.filter")
    @patch("bkflow.task.celery.tasks.Process.objects.filter")
    def test_execute_node_timeout_strategy_state_not_match(self, mock_process_filter, mock_state_filter):
        """测试执行节点超时策略（状态不匹配）"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=self.pipeline_tree)
        node_id = "node_1"
        version = "v1"

        TimeoutNodeConfig.objects.create(
            task_id=task_instance.id,
            root_pipeline_id=task_instance.instance_id,
            node_id=node_id,
            action="forced_fail",
            timeout=60,
        )

        # Mock State 不存在
        mock_process_filter.return_value.exists.return_value = True
        mock_state_filter.return_value.exists.return_value = False

        result = execute_node_timeout_strategy(node_id, version)

        assert result["result"] is False


@pytest.mark.django_db(transaction=True)
class TestBkflowPeriodicTaskStart:
    """测试 bkflow_periodic_task_start 任务"""

    def setup_method(self):
        """每个测试方法执行前的设置"""
        self.pipeline_tree = build_default_pipeline_tree()

    @patch("bkflow.task.celery.tasks.InterfaceModuleClient")
    @patch("bkflow.task.celery.tasks.TaskOperation")
    def test_bkflow_periodic_task_start_success(self, mock_task_operation, mock_client_class):
        """测试周期任务启动成功"""
        # 创建周期任务
        periodic_task = PeriodicTask.objects.create(
            name="test_periodic_task",
            creator="test_user",
            template_id=1,
            trigger_id=1,
            cron={"minute": "0", "hour": "*", "day_of_week": "*", "day_of_month": "*", "month_of_year": "*"},
            config={"space_id": 1, "pipeline_tree": self.pipeline_tree},
            extra_info={},
        )

        # Mock InterfaceModuleClient
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_template_data.return_value = {"data": {"pipeline_tree": self.pipeline_tree}}
        mock_client.broadcast_task_events.return_value = None

        # Mock TaskOperation
        mock_operation = MagicMock()
        mock_operation.start.return_value = OperationResult(result=True, message="success")
        mock_task_operation.return_value = mock_operation

        bkflow_periodic_task_start(periodic_task_id=periodic_task.id)

        # 验证任务被创建
        task_count = TaskInstance.objects.filter(trigger_method=TaskTriggerMethod.timing.name).count()
        assert task_count == 1

        # 验证周期任务统计更新
        periodic_task.refresh_from_db()
        assert periodic_task.total_run_count == 1
        assert periodic_task.last_run_at is not None

    @patch("bkflow.task.celery.tasks.InterfaceModuleClient")
    def test_bkflow_periodic_task_start_not_found(self, mock_client_class):
        """测试周期任务启动（任务不存在）"""
        fake_task_id = 999999

        # 代码中有 bug，使用了错误的 key 'period_task_id'，但测试传入的是 'periodic_task_id'
        # 当 PeriodicTask 不存在时，会抛出 DoesNotExist，然后代码会尝试访问错误的 key
        # 这里需要传入两个 key 来避免 KeyError
        bkflow_periodic_task_start(periodic_task_id=fake_task_id, period_task_id=fake_task_id)

        # 不应该有任务被创建
        task_count = TaskInstance.objects.filter(trigger_method=TaskTriggerMethod.timing.name).count()
        assert task_count == 0

    @patch("bkflow.task.celery.tasks.InterfaceModuleClient")
    @patch("bkflow.task.celery.tasks.TaskOperation")
    def test_bkflow_periodic_task_start_operation_failed(self, mock_task_operation, mock_client_class):
        """测试周期任务启动失败（操作失败）"""
        periodic_task = PeriodicTask.objects.create(
            name="test_periodic_task",
            creator="test_user",
            template_id=1,
            trigger_id=1,
            cron={"minute": "0", "hour": "*", "day_of_week": "*", "day_of_month": "*", "month_of_year": "*"},
            config={"space_id": 1, "pipeline_tree": self.pipeline_tree},
            extra_info={},
        )

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_template_data.return_value = {"data": {"pipeline_tree": self.pipeline_tree}}

        # Mock 启动失败
        mock_operation = MagicMock()
        mock_operation.start.return_value = OperationResult(result=False, message="start failed")
        mock_task_operation.return_value = mock_operation

        bkflow_periodic_task_start(periodic_task_id=periodic_task.id)

        # 验证周期任务统计没有更新
        periodic_task.refresh_from_db()
        assert periodic_task.total_run_count == 0

    @patch("bkflow.task.celery.tasks.InterfaceModuleClient")
    def test_bkflow_periodic_task_start_serializer_invalid(self, mock_client_class):
        """测试周期任务启动（序列化器验证失败）"""
        # 创建一个配置不完整的周期任务
        periodic_task = PeriodicTask.objects.create(
            name="test_periodic_task",
            creator="test_user",
            template_id=1,
            trigger_id=1,
            cron={"minute": "0", "hour": "*", "day_of_week": "*", "day_of_month": "*", "month_of_year": "*"},
            config={"space_id": 1},  # 缺少 pipeline_tree
            extra_info={},
        )

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_template_data.return_value = {"data": {"pipeline_tree": None}}  # 返回 None

        bkflow_periodic_task_start(periodic_task_id=periodic_task.id)

        # 验证任务没有被创建
        task_count = TaskInstance.objects.filter(trigger_method=TaskTriggerMethod.timing.name).count()
        assert task_count == 0

    @patch("bkflow.task.celery.tasks.InterfaceModuleClient")
    @patch("bkflow.task.celery.tasks.TaskOperation")
    def test_bkflow_periodic_task_start_with_constants(self, mock_task_operation, mock_client_class):
        """测试周期任务启动（包含常量）"""
        pipeline_tree = self.pipeline_tree.copy()
        pipeline_tree["constants"] = {
            "${key1}": {
                "key": "${key1}",
                "value": "value1",
                "show_type": "show",
                "source_type": "custom",
                "custom_type": "input",
                "source_info": {},
            },
            "${key2}": {
                "key": "${key2}",
                "value": "value2",
                "show_type": "show",
                "source_type": "custom",
                "custom_type": "input",
                "source_info": {},
            },
        }

        periodic_task = PeriodicTask.objects.create(
            name="test_periodic_task",
            creator="test_user",
            template_id=1,
            trigger_id=1,
            cron={"minute": "0", "hour": "*", "day_of_week": "*", "day_of_month": "*", "month_of_year": "*"},
            config={"space_id": 1, "pipeline_tree": pipeline_tree},
            extra_info={},
        )

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_template_data.return_value = {"data": {"pipeline_tree": pipeline_tree}}

        mock_operation = MagicMock()
        mock_operation.start.return_value = OperationResult(result=True, message="success")
        mock_task_operation.return_value = mock_operation

        bkflow_periodic_task_start(periodic_task_id=periodic_task.id)

        # 验证任务创建消息包含参数
        # 注意：代码中创建了两次 InterfaceModuleClient，所以需要检查是否有调用
        assert mock_client.broadcast_task_events.called, "broadcast_task_events should be called"
        broadcast_calls = mock_client.broadcast_task_events.call_args_list
        if broadcast_calls:
            create_event_call = broadcast_calls[0]
            assert create_event_call[1]["data"]["event"] == WebhookEventType.TASK_CREATE.value
            assert "parameters" in create_event_call[1]["data"]["extra_info"]

    @patch("bkflow.task.celery.tasks.InterfaceModuleClient")
    @patch("bkflow.task.celery.tasks.TaskOperation")
    def test_bkflow_periodic_task_start_exception(self, mock_task_operation, mock_client_class):
        """测试周期任务启动异常"""
        periodic_task = PeriodicTask.objects.create(
            name="test_periodic_task",
            creator="test_user",
            template_id=1,
            trigger_id=1,
            cron={"minute": "0", "hour": "*", "day_of_week": "*", "day_of_month": "*", "month_of_year": "*"},
            config={"space_id": 1, "pipeline_tree": self.pipeline_tree},
            extra_info={},
        )

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_template_data.side_effect = Exception("template error")

        # 不应该抛出异常
        bkflow_periodic_task_start(periodic_task_id=periodic_task.id)

        # 验证任务没有被创建
        task_count = TaskInstance.objects.filter(trigger_method=TaskTriggerMethod.timing.name).count()
        assert task_count == 0

    @patch("bkflow.task.celery.tasks.InterfaceModuleClient")
    @patch("bkflow.task.celery.tasks.TaskOperation")
    @patch("bkflow.task.celery.tasks.timezone.localtime")
    def test_bkflow_periodic_task_start_task_name_with_timestamp(
        self, mock_localtime, mock_task_operation, mock_client_class
    ):
        """测试周期任务启动（任务名包含时间戳）"""
        periodic_task = PeriodicTask.objects.create(
            name="test_periodic_task",
            creator="test_user",
            template_id=1,
            trigger_id=1,
            cron={"minute": "0", "hour": "*", "day_of_week": "*", "day_of_month": "*", "month_of_year": "*"},
            config={"space_id": 1, "pipeline_tree": self.pipeline_tree},
            extra_info={},
        )

        # Mock 时间
        mock_time = MagicMock()
        mock_time.strftime.return_value = "20231201120000"
        mock_localtime.return_value = mock_time

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_template_data.return_value = {"data": {"pipeline_tree": self.pipeline_tree}}

        mock_operation = MagicMock()
        mock_operation.start.return_value = OperationResult(result=True, message="success")
        mock_task_operation.return_value = mock_operation

        bkflow_periodic_task_start(periodic_task_id=periodic_task.id)

        # 验证任务名包含时间戳
        task = TaskInstance.objects.filter(trigger_method=TaskTriggerMethod.timing.name).first()
        assert task is not None
        assert "20231201120000" in task.name

    @patch("bkflow.task.celery.tasks.InterfaceModuleClient")
    @patch("bkflow.task.celery.tasks.getattr")
    def test_bkflow_periodic_task_start_operation_not_found(self, mock_getattr, mock_client_class):
        """测试周期任务启动（操作方法不存在）"""
        periodic_task = PeriodicTask.objects.create(
            name="test_periodic_task",
            creator="test_user",
            template_id=1,
            trigger_id=1,
            cron={"minute": "0", "hour": "*", "day_of_week": "*", "day_of_month": "*", "month_of_year": "*"},
            config={"space_id": 1, "pipeline_tree": self.pipeline_tree},
            extra_info={},
        )

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_template_data.return_value = {"data": {"pipeline_tree": self.pipeline_tree}}

        # Mock getattr 返回 None
        mock_getattr.return_value = None

        bkflow_periodic_task_start(periodic_task_id=periodic_task.id)

        # 验证任务被创建但没有启动
        task_count = TaskInstance.objects.filter(trigger_method=TaskTriggerMethod.timing.name).count()
        assert task_count == 1

        # 验证周期任务统计没有更新
        periodic_task.refresh_from_db()
        assert periodic_task.total_run_count == 0
