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
from pipeline.core.constants import PE


class AutoRetryNodeStrategyCreator:
    TASKFLOW_NODE_AUTO_RETRY_MAX_TIMES = 10
    TASKFLOW_NODE_AUTO_RETRY_MAX_INTERVAL = 10
    TASKFLOW_NODE_AUTO_RETRY_BATCH_CREATE_COUNT = 1000

    def __init__(self, taskflow_id: int, root_pipeline_id: str):
        """

        Args:
            taskflow_id (int): TaskflowInstance 实例 ID
            root_pipeline_id (str): Pipeline ID
        """
        self.taskflow_id = taskflow_id
        self.root_pipeline_id = root_pipeline_id

    def batch_create_strategy(self, pipeline_tree: dict):
        """批量创建自动重试策略

        Args:
            pipeline_tree (dict): 经过子流程展开后的 pipeline 描述结构
        """

        def _initiate_strategy(pipeline_tree: dict):
            strategies = []
            for act_id, act in pipeline_tree[PE.activities].items():
                if act["type"] == PE.SubProcess:
                    strategies.extend(_initiate_strategy(act[PE.pipeline]))
                else:
                    auto_retry = act.get("auto_retry", {})
                    enable = auto_retry.get("enable")
                    if not enable:
                        continue

                    try:
                        max_retry_times = min(
                            abs(int(auto_retry.get("times", self.TASKFLOW_NODE_AUTO_RETRY_MAX_TIMES))),
                            self.TASKFLOW_NODE_AUTO_RETRY_MAX_TIMES,
                        )
                    except Exception:
                        max_retry_times = self.TASKFLOW_NODE_AUTO_RETRY_MAX_TIMES

                    try:
                        interval = min(
                            abs(int(auto_retry.get("interval", 0))),
                            self.TASKFLOW_NODE_AUTO_RETRY_MAX_INTERVAL,
                        )
                    except Exception:
                        interval = self.TASKFLOW_NODE_AUTO_RETRY_MAX_INTERVAL

                    strategies.append(
                        strategy_model(
                            taskflow_id=self.taskflow_id,
                            root_pipeline_id=self.root_pipeline_id,
                            node_id=act_id,
                            max_retry_times=max_retry_times,
                            interval=interval,
                        )
                    )
            return strategies

        strategy_model = apps.get_model("task", "AutoRetryNodeStrategy")
        strategies = _initiate_strategy(pipeline_tree)
        strategy_model.objects.bulk_create(strategies, batch_size=self.TASKFLOW_NODE_AUTO_RETRY_BATCH_CREATE_COUNT)
