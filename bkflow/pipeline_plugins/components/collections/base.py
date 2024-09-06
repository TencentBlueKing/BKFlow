# -*- coding: utf-8 -*-
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

from django.apps import apps
from pipeline.core.flow import AbstractIntervalGenerator, StaticIntervalGenerator
from pipeline.core.flow.activity import Service


class BKFlowBaseService(Service):
    @staticmethod
    def get_taskflow_mock_data(taskflow_id):
        TaskMockData = apps.get_model("task.TaskMockData")
        mock_data = TaskMockData.objects.filter(taskflow_id=taskflow_id).first()
        return getattr(mock_data, "data", {})

    def is_mock_node(self, taskflow_id, node_id):
        mock_data = self.get_taskflow_mock_data(taskflow_id)
        return node_id in mock_data.get("nodes", [])

    def get_mock_outputs(self, taskflow_id):
        mock_data = self.get_taskflow_mock_data(taskflow_id)
        return mock_data.get("outputs", {})

    def mock_schedule(self, data, parent_data, callback_data=None):
        taskflow_id = parent_data.get_one_of_inputs("task_id")
        taskflow_outputs = self.get_mock_outputs(taskflow_id)
        mock_outputs = taskflow_outputs.get(self.id, {})
        for k, value in mock_outputs.items():
            data.set_outputs(k, value)
        self.finish_schedule()
        return True

    def mock_execute(self, data, parent_data):
        if self.need_schedule():
            # 如果需要 schedule，一律改成 2s 轮询
            self.interval = StaticIntervalGenerator(2)
            return True
        taskflow_id = parent_data.get_one_of_inputs("task_id")
        taskflow_outputs = self.get_mock_outputs(taskflow_id)
        mock_outputs = taskflow_outputs.get(self.id, {})
        for k, value in mock_outputs.items():
            data.set_outputs(k, value)
        return True

    def plugin_execute(self, data, parent_data):
        pass

    def plugin_schedule(self, data, parent_data, callback_data=None):
        pass

    def execute(self, data, parent_data):
        if parent_data.get_one_of_inputs("is_mock") and self.is_mock_node(
            parent_data.get_one_of_inputs("task_id"), self.id
        ):
            return self.mock_execute(data, parent_data)
        return self.plugin_execute(data, parent_data)

    def schedule(self, data, parent_data, callback_data=None):
        if parent_data.get_one_of_inputs("is_mock") and self.is_mock_node(
            parent_data.get_one_of_inputs("task_id"), self.id
        ):
            return self.mock_schedule(data, parent_data)
        return self.plugin_schedule(data, parent_data, callback_data)


class StepIntervalGenerator(AbstractIntervalGenerator):
    def __init__(self, max_count=200, init_interval=10, max_interval=600, fix_interval=None):
        """
        :param max_count: 最大计数次数，用于 reach_limit 判断
        :param init_interval: 初始的间隔时间
        :param max_interval: 最大的间隔时间，到达后不会继续增加
        :param fix_interval: 固定的间隔时间，优先级最高
        """
        super(StepIntervalGenerator, self).__init__()
        self.fix_interval = fix_interval
        self.init_interval = init_interval
        self.max_interval = max_interval
        self.max_count = max_count

    def next(self):
        super(StepIntervalGenerator, self).next()
        # 最小 10s，最大 600s 一次
        return self.fix_interval or (
            self.init_interval if self.count < 30 else min((self.count - 25) ** 2, self.max_interval)
        )

    def reach_limit(self):
        return self.count >= self.max_count
