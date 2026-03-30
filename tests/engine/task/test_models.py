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

import pytest
from bamboo_engine import states
from django.utils import timezone
from django_celery_beat.models import CrontabSchedule as DjangoCeleryBeatCrontabSchedule
from django_celery_beat.models import PeriodicTask as DjangoCeleryBeatPeriodicTask
from pipeline.core.constants import PE

from bkflow.constants import TaskTriggerMethod
from bkflow.task import models as task_models
from bkflow.task.models import (
    AutoRetryNodeStrategy,
    EngineSpaceConfig,
    EngineSpaceConfigValueType,
    PeriodicTask,
    TaskExecutionSnapshot,
    TaskFlowRelation,
    TaskInstance,
    TaskLabelRelation,
    TaskMockData,
    TaskOperationRecord,
    TimeoutNodeConfig,
)
from bkflow.utils.pipeline import build_default_pipeline_tree


@pytest.mark.django_db(transaction=True)
class TestTaskInstance:
    """测试 TaskInstance 模型"""

    def test_create_instance(self):
        """测试创建任务实例"""
        space_id = 1
        pipeline_tree = build_default_pipeline_tree()
        task_instance = TaskInstance.objects.create_instance(space_id=space_id, pipeline_tree=pipeline_tree)

        assert task_instance.space_id == space_id
        assert task_instance.instance_id is not None
        assert task_instance.is_started is False
        assert task_instance.is_finished is False
        assert task_instance.is_deleted is False
        assert task_instance.is_expired is False

    def test_delete_instance(self):
        """测试删除任务实例（软删除）"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        task_instance.delete()

        task_instance.refresh_from_db()
        assert task_instance.is_deleted is True

    def test_clone_instance(self):
        """测试克隆任务实例"""
        task_instance = TaskInstance.objects.create_instance(
            space_id=1, pipeline_tree=build_default_pipeline_tree(), creator="test_creator"
        )
        cloned_instance = task_instance.clone(creator="clone_creator", name="cloned_task")

        assert cloned_instance.space_id == task_instance.space_id
        assert cloned_instance.instance_id != task_instance.instance_id
        assert cloned_instance.creator == "clone_creator"
        assert cloned_instance.name == "cloned_task"

    def test_calculate_tree_info(self):
        """测试计算树信息"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        task_instance.calculate_tree_info()

        assert task_instance.tree_info_id is not None
        assert task_instance.node_id_set is not None
        assert len(task_instance.node_id_set) > 0

    def test_has_node(self):
        """测试检查节点是否存在"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        task_instance.calculate_tree_info()

        # 获取一个节点 ID
        node_ids = list(task_instance.node_id_set)
        if node_ids:
            assert task_instance.has_node(node_ids[0]) is True
            assert task_instance.has_node("non_existent_node") is False

    def test_get_notify_info(self):
        """测试获取通知信息"""
        task_instance = TaskInstance.objects.create_instance(
            space_id=1, pipeline_tree=build_default_pipeline_tree(), executor="test_executor"
        )
        notify_info = task_instance.get_notify_info()
        assert "types" in notify_info
        assert "test_executor" in notify_info["receivers"]

    def test_manager_set_finished_and_revoked(self):
        """Test TaskInstanceManager.set_finished/set_revoked"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())

        TaskInstance.objects.set_finished(task_instance.instance_id)
        task_instance.refresh_from_db()
        assert task_instance.is_finished is True
        assert task_instance.finish_time is not None

        TaskInstance.objects.set_revoked(task_instance.instance_id)
        task_instance.refresh_from_db()
        assert task_instance.is_revoked is True
        assert task_instance.finish_time is not None

    def test_delete_instance_real_delete(self):
        """Test TaskInstance.delete(real_delete=True)"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        task_id = task_instance.id

        task_instance.delete(real_delete=True)
        assert not TaskInstance.objects.filter(id=task_id).exists()

    def test_set_execution_data_creates_snapshot_when_missing(self):
        """Cover TaskInstance.set_execution_data DoesNotExist branch"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        TaskInstance.objects.filter(id=task_instance.id).update(execution_snapshot_id=99999999)
        task_instance.refresh_from_db()

        data = build_default_pipeline_tree()
        task_instance.set_execution_data(data)
        task_instance.refresh_from_db()

        assert TaskExecutionSnapshot.objects.filter(id=task_instance.execution_snapshot_id).exists()

    def test_calculate_tree_info_returns_when_execution_data_is_none(self):
        """Cover TaskInstance.calculate_tree_info early return when execution_data is None"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        TaskInstance.objects.filter(id=task_instance.id).update(execution_snapshot_id=None, tree_info_id=None)
        task_instance.refresh_from_db()

        task_instance.calculate_tree_info()
        task_instance.refresh_from_db()
        assert task_instance.tree_info_id is None

    def test_calculate_tree_info_updates_when_tree_info_exists(self):
        """Cover TaskInstance.calculate_tree_info update branch"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        task_instance.calculate_tree_info()
        tree_info_id = task_instance.tree_info_id

        task_instance.calculate_tree_info()
        task_instance.refresh_from_db()
        assert task_instance.tree_info_id == tree_info_id

    def test_create_instance_mock_creates_task_mock_data(self):
        """Cover TaskInstanceManager.create_instance mock_data mapping branch"""
        pipeline_tree = build_default_pipeline_tree()
        node_id = list(pipeline_tree[PE.activities].keys())[0]
        mock_data = {
            "nodes": [node_id],
            "outputs": {node_id: {"k": "v"}},
            "mock_data_ids": {"foo": "bar"},
        }
        task_instance = TaskInstance.objects.create_instance(
            space_id=1,
            pipeline_tree=pipeline_tree,
            create_method="MOCK",
            mock_data=mock_data,
        )

        task_mock_data = TaskMockData.objects.get(taskflow_id=task_instance.id)
        mapped_node_id = task_mock_data.data["nodes"][0]
        assert mapped_node_id in task_instance.execution_data[PE.activities]
        assert list(task_mock_data.data["outputs"].keys()) == [mapped_node_id]
        assert task_mock_data.mock_data_ids == {"foo": "bar"}

    def test_change_parent_task_node_state_to_running_without_relation(self):
        """Cover TaskInstance.change_parent_task_node_state_to_running no relation branch"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        TaskInstance.objects.filter(id=task_instance.id).update(trigger_method=TaskTriggerMethod.subprocess.name)
        task_instance.refresh_from_db()

        assert not TaskFlowRelation.objects.filter(task_id=task_instance.id).exists()
        task_instance.change_parent_task_node_state_to_running()

    def test_node_id_set_triggers_calculate_tree_info(self):
        """Cover TaskInstance.node_id_set branch that triggers calculate_tree_info"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        TaskInstance.objects.filter(id=task_instance.id).update(tree_info_id=None)
        task_instance.refresh_from_db()

        node_ids = task_instance.node_id_set
        assert isinstance(node_ids, set)
        task_instance.refresh_from_db()
        assert task_instance.tree_info_id is not None

    def test_get_notify_info_with_more_receivers(self):
        """Cover TaskInstance.get_notify_info more_receivers branch and executor filtering"""
        task_instance = TaskInstance.objects.create_instance(
            space_id=1,
            pipeline_tree=build_default_pipeline_tree(),
            executor="user_a",
        )
        TaskInstance.objects.filter(id=task_instance.id).update(
            extra_info={
                "notify_config": {
                    "notify_receivers": {"more_receiver": "user_a,user_b,user_c"},
                    "notify_type": {"success": ["weixin"], "fail": ["weixin"]},
                    "notify_format": {"title": "t", "content": "c"},
                }
            }
        )
        task_instance.refresh_from_db()

        notify_info = task_instance.get_notify_info()
        assert notify_info["receivers"].count("user_a") == 1
        assert set(notify_info["receivers"]) == {"user_a", "user_b", "user_c"}


@pytest.mark.django_db(transaction=True)
class TestTaskInstanceMoreCoverage:
    def test_taskinstance_properties(self):
        """
        Cover TaskInstance snapshot/data/pipeline_tree/tree_info/
        execution_snapshot/execution_data/node_id_set/elapsed_time
        """
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())

        assert task_instance.snapshot is not None
        assert isinstance(task_instance.data, dict)

        assert task_instance.execution_snapshot is not None
        assert isinstance(task_instance.execution_data, dict)
        assert task_instance.pipeline_tree == task_instance.execution_data

        task_instance.calculate_tree_info()
        assert task_instance.tree_info is not None
        assert isinstance(task_instance.node_id_set, set)

        TaskInstance.objects.filter(id=task_instance.id).update(
            start_time=timezone.now(),
            finish_time=timezone.now(),
        )
        task_instance.refresh_from_db()
        assert task_instance.elapsed_time is not None

    def test_replace_id_with_subprocess_node(self, monkeypatch):
        """Cover TaskInstance._replace_id subprocess recursion branch"""

        def _noop_replace_all_id(_data):
            return {}

        monkeypatch.setattr(task_models, "replace_all_id", _noop_replace_all_id)

        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        exec_data = {
            PE.start_event: {"id": "s0"},
            PE.end_event: {"id": "e0"},
            PE.gateways: [],
            PE.activities: {
                "sub1": {
                    PE.type: PE.SubProcess,
                    "pipeline": {
                        PE.start_event: {"id": "s1"},
                        PE.end_event: {"id": "e1"},
                        PE.gateways: [],
                        PE.activities: {},
                    },
                },
                "act2": {PE.type: "ServiceActivity"},
            },
        }

        task_instance._replace_id(exec_data)
        assert exec_data[PE.activities]["sub1"]["pipeline"]["id"] == "sub1"

    def test_get_node_id_set_with_subprocess_node(self):
        """Cover TaskInstance._get_node_id_set subprocess recursion branch"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())

        data = {
            PE.start_event: {"id": "s0"},
            PE.end_event: {"id": "e0"},
            PE.gateways: ["g1"],
            PE.activities: {
                "sub1": {
                    PE.type: PE.SubProcess,
                    "pipeline": {
                        PE.start_event: {"id": "s1"},
                        PE.end_event: {"id": "e1"},
                        PE.gateways: [],
                        PE.activities: {"a1": {PE.type: "ServiceActivity"}},
                    },
                }
            },
        }

        node_ids = set()
        task_instance._get_node_id_set(node_ids, data)
        assert {"s0", "e0", "g1", "sub1", "s1", "e1", "a1"}.issubset(node_ids)

    def test_change_parent_task_node_state_to_running_not_subprocess(self):
        """Cover change_parent_task_node_state_to_running early return when not child task"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        task_instance.change_parent_task_node_state_to_running()

    def test_change_parent_task_node_state_to_running_success_path(self, monkeypatch):
        """Cover deeper branches in change_parent_task_node_state_to_running with runtime mocks"""
        parent_task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        child_task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        TaskInstance.objects.filter(id=child_task.id).update(trigger_method=TaskTriggerMethod.subprocess.name)
        child_task.refresh_from_db()

        TaskFlowRelation.objects.create(
            task_id=child_task.id,
            parent_task_id=parent_task.id,
            root_task_id=parent_task.id,
            extra_info={"node_id": "node_1", "node_version": 1},
        )

        class DummySchedule:
            id = 123

        class DummyQS:
            def update(self, **kwargs):
                return 1

        class DummyRuntime:
            def get_state(self, node_id):
                return type("S", (), {"name": states.FAILED, "version": 1})()

            def get_schedule_with_node_and_version(self, node_id, version):
                return DummySchedule()

            def set_state(self, **kwargs):
                return None

            def get_execution_data_outputs(self, node_id):
                return {"ex_data": "x", "k": "v"}

            def set_execution_data_outputs(self, node_id, data_outputs):
                assert "ex_data" not in data_outputs
                return None

        monkeypatch.setattr(task_models, "BambooDjangoRuntime", lambda: DummyRuntime())
        monkeypatch.setattr(task_models.DBSchedule.objects, "filter", lambda **kwargs: DummyQS())

        child_task.change_parent_task_node_state_to_running()

    def test_change_parent_task_node_state_to_running_state_mismatch_returns(self, monkeypatch):
        """Cover change_parent_task_node_state_to_running early return when node state/version mismatch"""
        parent_task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        child_task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        TaskInstance.objects.filter(id=child_task.id).update(trigger_method=TaskTriggerMethod.subprocess.name)
        child_task.refresh_from_db()

        TaskFlowRelation.objects.create(
            task_id=child_task.id,
            parent_task_id=parent_task.id,
            root_task_id=parent_task.id,
            extra_info={"node_id": "node_1", "node_version": 1},
        )

        class DummyRuntime:
            def get_state(self, node_id):
                return type("S", (), {"name": states.RUNNING, "version": 1})()

            def get_schedule_with_node_and_version(self, node_id, version):
                raise AssertionError("should not reach schedule branch")

        monkeypatch.setattr(task_models, "BambooDjangoRuntime", lambda: DummyRuntime())

        child_task.change_parent_task_node_state_to_running()


@pytest.mark.django_db(transaction=True)
class TestTaskMockData:
    """测试 TaskMockData 模型"""

    def test_mock_data_operations(self):
        """测试 Mock 数据操作"""
        taskflow_id = 1
        mock_data = {"outputs": {"node1": {"output1": "value1"}}, "nodes": ["node1"]}
        task_mock_data = TaskMockData.objects.create(taskflow_id=taskflow_id, data=mock_data)
        assert task_mock_data.taskflow_id == taskflow_id
        assert task_mock_data.data == mock_data

        # Test to_json
        json_data = task_mock_data.to_json()
        assert json_data["taskflow_id"] == 1
        assert json_data["data"] == mock_data


@pytest.mark.django_db(transaction=True)
class TestTaskOperationRecord:
    """测试 TaskOperationRecord 模型"""

    def test_create_operation_record(self):
        """测试创建操作记录"""
        record = TaskOperationRecord.objects.create(
            instance_id=1, operator="test_operator", operate_type="start", operate_source="api"
        )
        assert record.instance_id == 1
        assert record.operator == "test_operator"


@pytest.mark.django_db(transaction=True)
class TestAutoRetryNodeStrategy:
    """测试 AutoRetryNodeStrategy 模型"""

    def test_create_retry_strategy(self):
        """测试创建重试策略"""
        strategy = AutoRetryNodeStrategy.objects.create(
            taskflow_id=1,
            root_pipeline_id="root_123",
            node_id="node_123",
            retry_times=0,
            max_retry_times=5,
            interval=10,
        )
        assert strategy.taskflow_id == 1
        assert strategy.max_retry_times == 5


@pytest.mark.django_db(transaction=True)
class TestTimeoutNodeConfig:
    """测试 TimeoutNodeConfig 模型"""

    def test_create_timeout_config(self):
        """测试创建超时配置"""
        config = TimeoutNodeConfig.objects.create(
            task_id=1, root_pipeline_id="root_123", node_id="node_123", action="forced_fail", timeout=300
        )
        assert config.task_id == 1
        assert config.timeout == 300


@pytest.mark.django_db(transaction=True)
class TestTimeoutNodeConfigManager:
    def test_batch_create_node_timeout_config_parse_fail(self, monkeypatch):
        """Cover TimeoutNodeConfigManager.batch_create_node_timeout_config parse fail branch"""

        def _fake_parse(_pipeline_tree):
            return {"result": False, "data": []}

        monkeypatch.setattr(task_models, "parse_node_timeout_configs", _fake_parse)

        TimeoutNodeConfig.objects.batch_create_node_timeout_config(
            taskflow_id=1,
            root_pipeline_id="root_123",
            pipeline_tree={},
        )
        assert TimeoutNodeConfig.objects.count() == 0


@pytest.mark.django_db(transaction=True)
class TestPeriodicTask:
    def test_create_task_and_enabled_property(self):
        """Test PeriodicTaskManager.create_task and PeriodicTask.enabled"""
        cron = {"minute": "0", "hour": "*", "day_of_week": "*", "day_of_month": "*", "month_of_year": "*"}
        periodic_task = PeriodicTask.objects.create_task(
            name="pt",
            template_id=1,
            trigger_id=1,
            cron=cron,
            config={"template_id": 1},
            creator="tester",
            extra_info={"k": "v"},
            is_enabled=False,
        )

        assert periodic_task.celery_task_id is not None
        assert periodic_task.enabled is False

    def test_modify_cron_must_disabled_branch(self):
        """Cover PeriodicTask.modify_cron must_disabled and enabled branch"""
        schedule = DjangoCeleryBeatCrontabSchedule.objects.create(
            minute="0",
            hour="*",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
        )
        celery_task = DjangoCeleryBeatPeriodicTask.objects.create(
            crontab=schedule,
            name="celery_pt_1",
            task="bkflow.task.celery.tasks.bkflow_periodic_task_start",
            enabled=True,
            kwargs=json.dumps({"periodic_task_id": 1}),
        )
        periodic_task = PeriodicTask.objects.create(
            name="pt",
            template_id=1,
            trigger_id=1,
            cron={"minute": "0"},
            celery_task=celery_task,
            config={},
            creator="tester",
        )

        new_cron = {"minute": "5", "hour": "*", "day_of_week": "*", "day_of_month": "*", "month_of_year": "*"}
        periodic_task.modify_cron(new_cron, must_disabled=True)

        periodic_task.celery_task.refresh_from_db()
        assert periodic_task.celery_task.crontab.minute == "5"
        assert periodic_task.celery_task.enabled is True

    def test_modify_cron_else_branch(self):
        """Cover PeriodicTask.modify_cron else branch"""
        schedule = DjangoCeleryBeatCrontabSchedule.objects.create(
            minute="0",
            hour="*",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
        )
        celery_task = DjangoCeleryBeatPeriodicTask.objects.create(
            crontab=schedule,
            name="celery_pt_2",
            task="bkflow.task.celery.tasks.bkflow_periodic_task_start",
            enabled=False,
            kwargs=json.dumps({"periodic_task_id": 1}),
        )
        periodic_task = PeriodicTask.objects.create(
            name="pt",
            template_id=1,
            trigger_id=1,
            cron={"minute": "0"},
            celery_task=celery_task,
            config={},
            creator="tester",
        )

        new_cron = {"minute": "10", "hour": "*", "day_of_week": "*", "day_of_month": "*", "month_of_year": "*"}
        periodic_task.modify_cron(new_cron, must_disabled=True)

        periodic_task.celery_task.refresh_from_db()
        assert periodic_task.celery_task.crontab.minute == "10"

    def test_delete_periodic_task_deletes_celery_task(self):
        """Cover PeriodicTask.delete"""
        cron = {"minute": "0", "hour": "*", "day_of_week": "*", "day_of_month": "*", "month_of_year": "*"}
        periodic_task = PeriodicTask.objects.create_task(
            name="pt_delete",
            template_id=1,
            trigger_id=1,
            cron=cron,
            config={},
            creator="tester",
        )
        celery_task_id = periodic_task.celery_task_id
        periodic_task_id = periodic_task.id

        periodic_task.delete()
        assert not PeriodicTask.objects.filter(id=periodic_task_id).exists()
        assert not DjangoCeleryBeatPeriodicTask.objects.filter(id=celery_task_id).exists()


@pytest.mark.django_db(transaction=True)
class TestPeriodicTaskMoreCoverage:
    def test_default_cron_and_unicode(self):
        """Cover default_cron and PeriodicTask.__unicode__"""
        cron = task_models.default_cron()
        assert cron["minute"] == "0"
        assert cron["hour"] == "*"

        periodic_task = PeriodicTask.objects.create(
            name="pt_unicode",
            template_id=1,
            trigger_id=1,
            cron=cron,
            config={},
            creator="tester",
        )
        assert "pt_unicode" in periodic_task.__unicode__()
        assert str(periodic_task.id) in periodic_task.__unicode__()


@pytest.mark.django_db(transaction=True)
class TestTaskLabelRelationManager:
    def test_set_labels_add_and_remove(self):
        """Cover BaseLabelRelationManager.set_labels add/remove branches"""
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        TaskLabelRelation.objects.create(task_id=task_instance.id, label_id=1)
        TaskLabelRelation.objects.create(task_id=task_instance.id, label_id=2)

        TaskLabelRelation.objects.set_labels(task_instance.id, [2, 3])

        label_ids = list(TaskLabelRelation.objects.filter(task_id=task_instance.id).values_list("label_id", flat=True))
        assert sorted(label_ids) == [2, 3]

    def test_fetch_tasks_labels(self):
        """Cover BaseLabelRelationManager.fetch_tasks_labels branches"""
        task1 = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        task2 = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())

        # empty
        assert TaskLabelRelation.objects.fetch_tasks_labels([task1.id, task2.id]) == {}

        TaskLabelRelation.objects.create(task_id=task1.id, label_id=1)
        TaskLabelRelation.objects.create(task_id=task1.id, label_id=2)
        TaskLabelRelation.objects.create(task_id=task2.id, label_id=3)

        result = TaskLabelRelation.objects.fetch_tasks_labels([task1.id, task2.id])
        assert sorted(result[task1.id]) == [1, 2]
        assert result[task2.id] == [3]


@pytest.mark.django_db(transaction=True)
class TestEngineSpaceConfig:
    """测试 EngineSpaceConfig 模型"""

    def test_create_configs(self):
        """测试创建文本和 JSON 类型配置"""
        # Text config
        config = EngineSpaceConfig.objects.create(
            interface_config_id=1,
            space_id=1,
            name="test_config",
            value_type=EngineSpaceConfigValueType.TEXT.value,
            text_value="test_value",
        )
        assert config.text_value == "test_value"

        # JSON config
        json_value = {"key": "value"}
        config = EngineSpaceConfig.objects.create(
            interface_config_id=2,
            space_id=1,
            name="test_json_config",
            value_type=EngineSpaceConfigValueType.JSON.value,
            json_value=json_value,
        )
        assert config.json_value == json_value

    def test_get_space_var(self):
        """测试获取空间变量"""
        # Existing config
        json_value = {"space": {"space_var": {"var1": "value1"}}, "scope": {}}
        EngineSpaceConfig.objects.create(
            interface_config_id=1,
            space_id=1,
            name="engine_space_config",
            value_type=EngineSpaceConfigValueType.JSON.value,
            json_value=json_value,
        )
        space_var = EngineSpaceConfig.get_space_var(space_id=1)
        assert space_var["space"]["space_var"] == {"var1": "value1"}

        # Not exist
        space_var = EngineSpaceConfig.get_space_var(space_id=999)
        assert space_var == {}


@pytest.mark.django_db(transaction=True)
class TestEngineSpaceConfigMoreCoverage:
    def test_to_json(self):
        """Cover EngineSpaceConfig.to_json"""
        config = EngineSpaceConfig.objects.create(
            interface_config_id=100,
            space_id=1,
            name="cfg",
            value_type=EngineSpaceConfigValueType.TEXT.value,
            text_value="v",
            json_value={"k": "v"},
        )
        data = config.to_json()
        assert data["id"] == config.id
        assert data["name"] == "cfg"
        assert data["value_type"] == EngineSpaceConfigValueType.TEXT.value
        assert data["value"] == "v"
        assert data["json_value"] == {"k": "v"}
        assert data["interface_config_id"] == 100
