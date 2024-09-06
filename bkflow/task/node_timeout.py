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
from abc import ABCMeta, abstractmethod

from bkflow.task.operations import TaskNodeOperation


class NodeTimeoutStrategy(metaclass=ABCMeta):
    TIMEOUT_NODE_OPERATOR = "bkflow_engine"

    @abstractmethod
    def deal_with_timeout_node(self, task, node_id):
        pass


class ForcedFailStrategy(NodeTimeoutStrategy):
    def deal_with_timeout_node(self, task, node_id):
        return dict(TaskNodeOperation(task, node_id).forced_fail(operator=self.TIMEOUT_NODE_OPERATOR))


class ForcedFailAndSkipStrategy(NodeTimeoutStrategy):
    def deal_with_timeout_node(self, task, node_id):
        fail_result = TaskNodeOperation(task, node_id).forced_fail(operator=self.TIMEOUT_NODE_OPERATOR)
        if fail_result.result:
            skip_result = TaskNodeOperation(task, node_id).skip(operator=self.TIMEOUT_NODE_OPERATOR)
            return dict(skip_result)
        return dict(fail_result)


node_timeout_handler = {
    "forced_fail": ForcedFailStrategy(),
    "forced_fail_and_skip": ForcedFailAndSkipStrategy(),
}
