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
import pytest

from bkflow.task.models import (
    AutoRetryNodeStrategy,
    EngineSpaceConfig,
    EngineSpaceConfigValueType,
    TaskInstance,
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
        assert "receivers" in notify_info
        assert "format" in notify_info
        assert "test_executor" in notify_info["receivers"]


@pytest.mark.django_db(transaction=True)
class TestTaskMockData:
    """测试 TaskMockData 模型"""

    def test_create_mock_data(self):
        """测试创建 Mock 数据"""
        taskflow_id = 1
        mock_data = {"outputs": {"node1": {"output1": "value1"}}, "nodes": ["node1"]}
        task_mock_data = TaskMockData.objects.create(taskflow_id=taskflow_id, data=mock_data)

        assert task_mock_data.taskflow_id == taskflow_id
        assert task_mock_data.data == mock_data

    def test_to_json(self):
        """测试转换为 JSON"""
        mock_data = {"outputs": {"node1": {"output1": "value1"}}}
        task_mock_data = TaskMockData.objects.create(taskflow_id=1, data=mock_data)
        json_data = task_mock_data.to_json()

        assert json_data["taskflow_id"] == 1
        assert json_data["data"] == mock_data


@pytest.mark.django_db(transaction=True)
class TestTaskOperationRecord:
    """测试 TaskOperationRecord 模型"""

    def test_create_operation_record(self):
        """测试创建操作记录"""
        record = TaskOperationRecord.objects.create(
            instance_id=1,
            operator="test_operator",
            operate_type="start",
            operate_source="api",
        )

        assert record.instance_id == 1
        assert record.operator == "test_operator"
        assert record.operate_type == "start"
        assert record.operate_source == "api"


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
        assert strategy.root_pipeline_id == "root_123"
        assert strategy.node_id == "node_123"
        assert strategy.max_retry_times == 5


@pytest.mark.django_db(transaction=True)
class TestTimeoutNodeConfig:
    """测试 TimeoutNodeConfig 模型"""

    def test_create_timeout_config(self):
        """测试创建超时配置"""
        config = TimeoutNodeConfig.objects.create(
            task_id=1,
            root_pipeline_id="root_123",
            node_id="node_123",
            action="forced_fail",
            timeout=300,
        )

        assert config.task_id == 1
        assert config.node_id == "node_123"
        assert config.action == "forced_fail"
        assert config.timeout == 300


@pytest.mark.django_db(transaction=True)
class TestEngineSpaceConfig:
    """测试 EngineSpaceConfig 模型"""

    def test_create_text_config(self):
        """测试创建文本类型配置"""
        config = EngineSpaceConfig.objects.create(
            interface_config_id=1,
            space_id=1,
            name="test_config",
            value_type=EngineSpaceConfigValueType.TEXT.value,
            text_value="test_value",
        )

        assert config.interface_config_id == 1
        assert config.space_id == 1
        assert config.name == "test_config"
        assert config.text_value == "test_value"

    def test_create_json_config(self):
        """测试创建 JSON 类型配置"""
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
        # 创建空间变量配置，name 必须是 "engine_space_config"
        json_value = {"space": {"space_var": {"var1": "value1"}}, "scope": {}}
        EngineSpaceConfig.objects.create(
            interface_config_id=1,
            space_id=1,
            name="engine_space_config",
            value_type=EngineSpaceConfigValueType.JSON.value,
            json_value=json_value,
        )

        space_var = EngineSpaceConfig.get_space_var(space_id=1)
        assert "space" in space_var
        assert space_var["space"]["space_var"] == {"var1": "value1"}

    def test_get_space_var_not_exist(self):
        """测试获取不存在的空间变量"""
        space_var = EngineSpaceConfig.get_space_var(space_id=999)
        assert space_var == {}
