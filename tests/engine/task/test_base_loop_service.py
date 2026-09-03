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
from bamboo_engine.eri import ContextValue, ContextValueType
from django.conf import settings
from pipeline.core.data.base import DataObject

from bkflow.exceptions import ValidationError
from bkflow.pipeline_plugins.components.collections.base import (
    LoopBaseService,
    StepIntervalGenerator,
)


class TestStepIntervalGenerator:
    """StepIntervalGenerator 单元测试"""

    def test_default_init(self):
        gen = StepIntervalGenerator()
        assert gen.max_count == 200
        assert gen.init_interval == 10
        assert gen.max_interval == 600
        assert gen.fix_interval is None

    def test_custom_init(self):
        gen = StepIntervalGenerator(max_count=100, init_interval=5, max_interval=300, fix_interval=15)
        assert gen.max_count == 100
        assert gen.init_interval == 5
        assert gen.max_interval == 300
        assert gen.fix_interval == 15

    def test_next_with_fix_interval(self):
        """fix_interval 优先级最高，无论调用多少次都返回 fix_interval"""
        gen = StepIntervalGenerator(fix_interval=30)
        for _ in range(50):
            assert gen.next() == 30

    def test_next_uses_init_interval_when_count_less_than_30(self):
        """count < 30 时使用初始间隔"""
        gen = StepIntervalGenerator(init_interval=10)
        # 第一次调用 count 会自增到 1
        assert gen.next() == 10
        # 第 29 次调用（count=29）
        for _ in range(28):
            gen.next()
        assert gen.count == 29
        # count < 30 仍然返回 init_interval
        # 实际上此调用会让 count -> 30
        result = gen.next()
        # count == 30 时 走入 else 分支，(30-25)**2 = 25
        assert result == 25

    def test_next_grows_after_threshold(self):
        """count 达到 30 后间隔时间随平方增长"""
        gen = StepIntervalGenerator(init_interval=10, max_interval=600)
        # 快速推进到 count=35
        for _ in range(35):
            gen.next()
        # 此时 count=35，下一次调用后 count=36，返回 min((36-25)**2, 600) = 121
        assert gen.next() == 121

    def test_next_capped_by_max_interval(self):
        """间隔时间上限受 max_interval 限制"""
        gen = StepIntervalGenerator(init_interval=10, max_interval=100)
        # 快速推进到较大 count
        for _ in range(100):
            gen.next()
        # 由于 (count-25)**2 会远大于 max_interval，因此被截断
        assert gen.next() == 100

    def test_reach_limit_false_before_max_count(self):
        gen = StepIntervalGenerator(max_count=5)
        for _ in range(4):
            gen.next()
        assert gen.reach_limit() is False

    def test_reach_limit_true_when_count_reaches_max(self):
        gen = StepIntervalGenerator(max_count=3)
        for _ in range(3):
            gen.next()
        assert gen.reach_limit() is True


class TestLoopBaseServiceOutputsFormat:
    """LoopBaseService.outputs_format 单元测试"""

    def test_outputs_format_contains_expected_keys(self):
        service = LoopBaseService()
        outputs = service.outputs_format()
        # 至少包含两个输出项
        keys = [item.key for item in outputs]
        assert "task_id" in keys
        assert settings.PLUGIN_LOOP_OUTPUTS_KEY in keys

    def test_outputs_format_task_id_type_int(self):
        service = LoopBaseService()
        outputs = service.outputs_format()
        task_id_item = next(item for item in outputs if item.key == "task_id")
        assert task_id_item.type == "int"

    def test_outputs_format_loop_outputs_type_array(self):
        service = LoopBaseService()
        outputs = service.outputs_format()
        loop_item = next(item for item in outputs if item.key == settings.PLUGIN_LOOP_OUTPUTS_KEY)
        assert loop_item.type == "array"


class TestLoopBaseServicePluginExecute:
    """LoopBaseService.plugin_execute 单元测试（基类默认实现为空，返回 None）"""

    def test_plugin_execute_returns_none(self):
        service = LoopBaseService()
        data = DataObject(inputs={})
        parent_data = DataObject(inputs={})
        assert service.plugin_execute(data, parent_data) is None


class TestLoopBaseServicePluginSchedule:
    """LoopBaseService.plugin_schedule 单元测试"""

    def _make_service(self, mocker, node_id="node1", inner_loop=1, loop_enabled=False, loop_outputs_key="outputs"):
        service = LoopBaseService()
        setattr(service, "id", node_id)
        setattr(service, "inner_loop", inner_loop)
        # 替换 logger 避免影响输出
        service.logger = mocker.Mock()

        # mock runtime
        service.runtime = mocker.Mock()
        node = mocker.Mock()
        node.loop_enabled = loop_enabled
        node.loop_outputs_key = loop_outputs_key
        service.runtime.get_node.return_value = node
        # finish_schedule 需要被 mock，因为它在基类里可能会调操作
        mocker.patch.object(service, "finish_schedule")
        return service, node

    def test_plugin_schedule_task_not_exist(self, mocker):
        service, _ = self._make_service(mocker)
        data = DataObject(inputs={})
        data.set_outputs("task_id", 9999)
        parent_data = DataObject(inputs={"task_id": 1})

        mock_task_instance = mocker.patch("bkflow.task.models.TaskInstance.objects.get")
        from bkflow.task.models import TaskInstance

        mock_task_instance.side_effect = TaskInstance.DoesNotExist

        result = service.plugin_schedule(data, parent_data, callback_data={})

        assert result is False
        assert "不存在" in data.get_one_of_outputs("ex_data")

    def test_plugin_schedule_no_loop_task_success(self, mocker):
        """非循环模式，子任务执行成功，输出被写回节点输出"""
        service, _ = self._make_service(mocker, loop_enabled=False)
        data = DataObject(inputs={})
        data.set_outputs("task_id", 100)
        parent_data = DataObject(inputs={"task_id": 1})

        subprocess_task = mocker.Mock(id=100, instance_id="pipeline_100")
        mocker.patch("bkflow.task.models.TaskInstance.objects.get", return_value=subprocess_task)

        service.runtime.get_execution_data_outputs.return_value = {
            "${result}": "success_value",
            "${other}": "ignored_value",
        }
        service.runtime.get_data_outputs.return_value = {"${result}": None}

        result = service.plugin_schedule(data, parent_data, callback_data={"task_success": True})

        assert result is True
        # 只有节点输出中声明的 key 会被回写
        assert data.get_one_of_outputs("${result}") == "success_value"
        service.finish_schedule.assert_called_once()

    def test_plugin_schedule_no_loop_task_fail(self, mocker):
        """非循环模式，子任务执行失败，写入 ex_data 并返回 False"""
        service, _ = self._make_service(mocker, loop_enabled=False)
        data = DataObject(inputs={})
        data.set_outputs("task_id", 101)
        parent_data = DataObject(inputs={"task_id": 1})

        subprocess_task = mocker.Mock(id=101, instance_id="pipeline_101")
        mocker.patch("bkflow.task.models.TaskInstance.objects.get", return_value=subprocess_task)
        service.runtime.get_execution_data_outputs.return_value = {}
        service.runtime.get_data_outputs.return_value = {}

        result = service.plugin_schedule(data, parent_data, callback_data={"task_success": False})

        assert result is False
        assert data.get_one_of_outputs("ex_data") == "子任务执行失败，请检查失败节点"

    def test_plugin_schedule_loop_enabled_success_appends_outputs(self, mocker):
        """循环模式下，成功时输出会被合并到 LOOP_OUTPUTS_INNER_KEY"""
        service, _ = self._make_service(mocker, loop_enabled=True, inner_loop=2, loop_outputs_key="loop_outputs")
        data = DataObject(inputs={})
        data.set_outputs("task_id", 200)
        parent_data = DataObject(inputs={"task_id": 10})

        subprocess_task = mocker.Mock(id=200, instance_id="pipeline_200")
        # TaskInstance.objects.get 会被调用两次：一次取子任务，一次取父任务
        parent_task = mocker.Mock(id=10, instance_id="parent_pipeline_10")

        def get_side_effect(id):
            if id == 200:
                return subprocess_task
            if id == 10:
                return parent_task
            raise Exception("unexpected id")

        mocker.patch("bkflow.task.models.TaskInstance.objects.get", side_effect=get_side_effect)

        # 无历史 loop context values
        service.runtime.get_context_values.return_value = []
        service.runtime.get_execution_data_outputs.return_value = {"${sub_result}": "hello"}
        service.runtime.get_data_outputs.return_value = {"${sub_result}": None}

        result = service.plugin_schedule(data, parent_data, callback_data={"task_success": True})

        assert result is True
        assert data.get_one_of_outputs("${sub_result}") == "hello"

        # 检查 LOOP_OUTPUTS_INNER_KEY 中包含本次循环数据
        inner_outputs = data.get_one_of_outputs(settings.LOOP_OUTPUTS_INNER_KEY)
        assert inner_outputs["task_id"] == 200
        assert inner_outputs["inner_loop"] == 2
        # key 会去掉 ${ 与 } 前后缀
        assert inner_outputs["sub_result"] == "hello"

    def test_plugin_schedule_loop_enabled_fail(self, mocker):
        """循环模式下，子任务失败，仍会写入 LOOP_OUTPUTS_INNER_KEY 且返回 False"""
        service, _ = self._make_service(mocker, loop_enabled=True, inner_loop=3, loop_outputs_key="loop_outputs")
        data = DataObject(inputs={})
        data.set_outputs("task_id", 301)
        parent_data = DataObject(inputs={"task_id": 20})

        subprocess_task = mocker.Mock(id=301, instance_id="pipeline_301")
        parent_task = mocker.Mock(id=20, instance_id="parent_pipeline_20")

        def get_side_effect(id):
            return subprocess_task if id == 301 else parent_task

        mocker.patch("bkflow.task.models.TaskInstance.objects.get", side_effect=get_side_effect)
        service.runtime.get_context_values.return_value = []
        service.runtime.get_execution_data_outputs.return_value = {}
        service.runtime.get_data_outputs.return_value = {}

        result = service.plugin_schedule(data, parent_data, callback_data={"task_success": False})

        assert result is False
        assert data.get_one_of_outputs("ex_data") == "子任务执行失败，请检查失败节点"

        inner_outputs = data.get_one_of_outputs(settings.LOOP_OUTPUTS_INNER_KEY)
        assert inner_outputs["task_id"] == 301
        assert inner_outputs["inner_loop"] == 3
        assert inner_outputs["ex_data"] == "子任务执行失败，请检查失败节点"

    def test_plugin_schedule_loop_enabled_filters_duplicate_inner_loop(self, mocker):
        """循环模式下，若已存在同 inner_loop 的记录，应被过滤后再由 extract_outputs 追加"""
        service, _ = self._make_service(mocker, loop_enabled=True, inner_loop=2, loop_outputs_key="loop_outputs")
        data = DataObject(inputs={})
        data.set_outputs("task_id", 400)
        parent_data = DataObject(inputs={"task_id": 30})

        subprocess_task = mocker.Mock(id=400, instance_id="pipeline_400")
        parent_task = mocker.Mock(id=30, instance_id="parent_pipeline_30")

        def get_side_effect(id):
            return subprocess_task if id == 400 else parent_task

        mocker.patch("bkflow.task.models.TaskInstance.objects.get", side_effect=get_side_effect)

        # 存在旧的相同 inner_loop=2 的记录
        existing_context_value = ContextValue(
            key="loop_outputs",
            type=ContextValueType.PLAIN,
            value=[
                {"inner_loop": 1, "task_id": 100},
                {"inner_loop": 2, "task_id": 200},  # 待过滤
            ],
            code=None,
        )
        service.runtime.get_context_values.return_value = [existing_context_value]
        service.runtime.get_execution_data_outputs.return_value = {}
        service.runtime.get_data_outputs.return_value = {}

        result = service.plugin_schedule(data, parent_data, callback_data={"task_success": True})

        assert result is True
        # 确认 update_context_values 被调用（说明发生了过滤更新）
        service.runtime.update_context_values.assert_called_once()
        args, _ = service.runtime.update_context_values.call_args
        updated_pipeline_id, updated_values = args
        assert updated_pipeline_id == "parent_pipeline_30"
        assert len(updated_values) == 1
        # 过滤后仅剩 inner_loop=1 的记录
        assert updated_values[0].value == [{"inner_loop": 1, "task_id": 100}]

    def test_plugin_schedule_loop_enabled_no_duplicate_no_update(self, mocker):
        """循环模式下，若不存在同 inner_loop 记录，则不需要更新 context"""
        service, _ = self._make_service(mocker, loop_enabled=True, inner_loop=5, loop_outputs_key="loop_outputs")
        data = DataObject(inputs={})
        data.set_outputs("task_id", 500)
        parent_data = DataObject(inputs={"task_id": 40})

        subprocess_task = mocker.Mock(id=500, instance_id="pipeline_500")
        parent_task = mocker.Mock(id=40, instance_id="parent_pipeline_40")

        def get_side_effect(id):
            return subprocess_task if id == 500 else parent_task

        mocker.patch("bkflow.task.models.TaskInstance.objects.get", side_effect=get_side_effect)

        existing_context_value = ContextValue(
            key="loop_outputs",
            type=ContextValueType.PLAIN,
            value=[{"inner_loop": 1, "task_id": 100}],
            code=None,
        )
        service.runtime.get_context_values.return_value = [existing_context_value]
        service.runtime.get_execution_data_outputs.return_value = {}
        service.runtime.get_data_outputs.return_value = {}

        result = service.plugin_schedule(data, parent_data, callback_data={"task_success": True})

        assert result is True
        # 没有重复 inner_loop，不应触发 update_context_values
        service.runtime.update_context_values.assert_not_called()


class TestLoopBaseServiceRenderParentParameters:
    """LoopBaseService._render_parent_parameters 单元测试

    该方法逻辑较为复杂，此处主要覆盖 loop_params 校验相关的关键分支。
    """

    def _make_service(self, mocker, node_id="node1", top_pipeline_id="root_pipeline", inner_loop=1, version="v1"):
        service = LoopBaseService()
        setattr(service, "id", node_id)
        setattr(service, "top_pipeline_id", top_pipeline_id)
        setattr(service, "inner_loop", inner_loop)
        setattr(service, "version", version)
        service.logger = mocker.Mock()
        service.runtime = mocker.Mock()
        return service

    def test_render_parent_parameters_raises_when_loop_param_not_iterable(self, mocker):
        """循环参数渲染后不是可迭代对象时，抛 ValidationError"""
        service = self._make_service(mocker)

        pipeline_tree = {"constants": {}}
        parent_task = mocker.Mock()
        parent_task.pipeline_tree = {
            "activities": {"node1": {"loop_config": {"loop_params": {"${items}": "${some_var}"}}}}
        }

        node = mocker.Mock()
        node.loop_enabled = True
        node.loop_times = None
        service.runtime.get_node.return_value = node
        service.runtime.get_context_key_references.return_value = set()
        service.runtime.get_context_values.side_effect = [
            [],
            [ContextValue(key="${some_var}", type=ContextValueType.PLAIN, value=123, code=None)],
        ]
        service.runtime.get_data_inputs.return_value = {}

        # Mock Template.get_reference / Template.render 和 Context.hydrate，
        # 让 render 直接返回一个非可迭代对象（整数）
        template_mock = mocker.patch("bkflow.pipeline_plugins.components.collections.base.Template")
        # get_reference 用于识别引用；这里让第二次 get_reference 返回 {"${some_var}"}
        template_instance = template_mock.return_value
        template_instance.get_reference.side_effect = [set(), {"${some_var}"}, set()]
        # 渲染 loop_param value 时返回整数
        template_instance.render.return_value = 123

        context_mock = mocker.patch("bkflow.pipeline_plugins.components.collections.base.Context")
        context_mock.return_value.hydrate.return_value = {}

        with pytest.raises(ValidationError) as exc:
            service._render_parent_parameters(pipeline_tree, parent_task)
        assert "必须是可迭代对象" in str(exc.value)

    def test_render_parent_parameters_raises_when_loop_exceeds_max(self, mocker):
        """循环参数长度超过 MAX_LOOP_TIMES 时抛 ValidationError"""
        service = self._make_service(mocker)

        pipeline_tree = {"constants": {}}
        parent_task = mocker.Mock()
        parent_task.pipeline_tree = {
            "activities": {"node1": {"loop_config": {"loop_params": {"${items}": "${big_list}"}}}}
        }
        node = mocker.Mock()
        node.loop_enabled = True
        node.loop_times = None
        service.runtime.get_node.return_value = node
        service.runtime.get_context_key_references.return_value = set()

        big_list = list(range(settings.MAX_LOOP_TIMES + 1))
        service.runtime.get_context_values.side_effect = [
            [],
            [ContextValue(key="${big_list}", type=ContextValueType.PLAIN, value=big_list, code=None)],
        ]
        service.runtime.get_data_inputs.return_value = {}

        template_mock = mocker.patch("bkflow.pipeline_plugins.components.collections.base.Template")
        template_instance = template_mock.return_value
        template_instance.get_reference.side_effect = [set(), {"${big_list}"}, set()]
        template_instance.render.return_value = big_list

        context_mock = mocker.patch("bkflow.pipeline_plugins.components.collections.base.Context")
        context_mock.return_value.hydrate.return_value = {}

        with pytest.raises(ValidationError) as exc:
            service._render_parent_parameters(pipeline_tree, parent_task)
        assert "超过最大循环次数" in str(exc.value)
