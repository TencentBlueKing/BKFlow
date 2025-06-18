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
import logging
import time
from typing import Dict

from bkflow.contrib.api.collections.task import TaskComponentClient

logger = logging.getLogger(__name__)


class StageJobStateHandler:
    """处理Stage和Job状态的业务逻辑处理器"""

    def __init__(self, space_id: int, is_superuser: bool = False):
        self.space_id = space_id
        self.is_superuser = is_superuser
        self.client = TaskComponentClient(space_id=space_id, from_superuser=is_superuser)

    def get_task_data(self, task_id: str) -> dict:
        """获取任务相关的基础数据"""
        current_constants = self.client.render_current_constants(task_id)["data"]
        task_detail = self.client.get_task_detail(task_id)
        pipeline_tree = task_detail["data"]["pipeline_tree"]
        pipeline_tree["current_constants"] = current_constants

        return {
            "task_detail": task_detail,
            "pipeline_tree": pipeline_tree,
            "stage_struct": pipeline_tree["stage_canvas_data"],
            "activities": pipeline_tree["activities"],
        }

    def get_node_states(self, task_id: str, max_retries: int = 3, retry_interval: float = 0.5) -> Dict:
        """获取节点状态信息

        Args:
            task_id: 任务ID
            max_retries: 最大重试次数，默认3次
            retry_interval: 重试间隔（秒），默认0.5秒

        Returns:
            节点状态信息字典

        Raises:
            ValueError: 响应数据格式错误
        """
        data = {"space_id": self.space_id}

        for attempt in range(max_retries):
            try:
                response = self.client.get_task_states(task_id, data=data)

                if not isinstance(response, dict):
                    raise ValueError(f"Invalid response type: {type(response)}")

                if "data" not in response:
                    raise KeyError("Missing 'data' field in response")

                if "children" not in response["data"]:
                    raise KeyError("Missing 'children' field in response data")

                return response["data"]["children"]

            except (KeyError, ValueError) as e:
                logger.warning(
                    f"Failed to get node states for task {task_id} (attempt {attempt + 1}/{max_retries}): {str(e)}"
                )

                if attempt < max_retries - 1:
                    time.sleep(retry_interval)
                else:
                    logger.error(f"Failed to get node states for task {task_id} after {max_retries} attempts")

            except Exception as e:
                logger.error(f"Unexpected error while getting node states: {str(e)}")
                raise

        return {}

    def build_template_task_mapping(self, activities: dict) -> dict:
        """构建模板节点ID到任务节点ID的映射"""
        return {
            activity.get("template_node_id"): task_node_id
            for task_node_id, activity in activities.items()
            if activity.get("template_node_id")
        }

    def build_node_info_map(self, template_to_task_id: dict, node_states: dict) -> dict:
        """构建节点信息映射"""
        return {
            template_id: {
                "state": node_states[task_id].get("state", "READY"),
                "start_time": node_states[task_id].get("start_time", ""),
                "finish_time": node_states[task_id].get("finish_time", ""),
                "loop": node_states[task_id].get("loop", 1),
                "retry": node_states[task_id].get("retry", 0),
                "skip": node_states[task_id].get("skip", False),
                "error_ignorable": node_states[task_id].get("error_ignorable", False),
                "error_ignored": node_states[task_id].get("error_ignored", False),
            }
            for template_id, task_id in template_to_task_id.items()
            if task_id in node_states
        }

    @staticmethod
    def calculate_job_state(node_states: list) -> str:
        """计算Job状态"""
        if not node_states:
            return "READY"

        if "FAILED" in node_states:
            return "FAILED"

        if "RUNNING" in node_states:
            return "RUNNING"

        if all(state == "READY" for state in node_states):
            return "READY"

        if all(state == "FINISHED" for state in node_states):
            return "FINISHED"

        return "RUNNING"

    @staticmethod
    def calculate_stage_state(job_states: list) -> str:
        """计算Stage状态"""
        if not job_states:
            return "READY"

        if "FAILED" in job_states:
            return "FAILED"

        if "RUNNING" in job_states:
            return "RUNNING"

        if all(state == "READY" for state in job_states):
            return "READY"

        if all(state == "FINISHED" for state in job_states):
            return "FINISHED"

        return "RUNNING"

    def update_states(self, stage_struct: list, node_info_map: dict) -> None:
        """更新状态信息"""
        # 构建job到nodes的映射，避免深层嵌套
        job_nodes_map = {}
        stage_jobs_map = {}

        # 第一次遍历：构建映射关系
        for stage in stage_struct:
            stage_jobs = []
            for job in stage["jobs"]:
                job_id = job["id"]
                job_nodes_map[job_id] = job["nodes"]
                stage_jobs.append(job_id)
            stage_jobs_map[stage["id"]] = stage_jobs

        # 第二次遍历：更新节点状态
        job_states_map = {}
        for job_id, nodes in job_nodes_map.items():
            node_states = []
            for node in nodes:
                template_node_id = node["id"]
                info = node_info_map.get(
                    template_node_id,
                    {
                        "state": "READY",
                        "start_time": "",
                        "finish_time": "",
                        "loop": 1,
                        "retry": 0,
                        "skip": False,
                        "error_ignorable": False,
                        "error_ignored": False,
                    },
                )
                node.update(info)
                node_states.append(info["state"])

            # 计算job状态
            job_state = self.calculate_job_state(node_states)
            job_states_map[job_id] = job_state

        # 第三次遍历：更新stage和job状态
        for stage in stage_struct:
            stage_jobs = stage_jobs_map[stage["id"]]
            job_states = [job_states_map[job_id] for job_id in stage_jobs]

            # 更新job状态
            for job in stage["jobs"]:
                job["state"] = job_states_map[job["id"]]

            # 更新stage状态
            stage["state"] = self.calculate_stage_state(job_states)

    def process(self, task_id: str) -> dict:
        """处理完整的状态更新流程"""
        # 1. 获取基础数据
        task_data = self.get_task_data(task_id)

        # 2. 获取节点状态
        node_states = self.get_node_states(task_id)

        # 3. 构建映射关系
        template_to_task_id = self.build_template_task_mapping(task_data["activities"])
        node_info_map = self.build_node_info_map(template_to_task_id, node_states)

        # 4. 更新状态
        self.update_states(task_data["stage_struct"], node_info_map)

        return task_data["task_detail"]["data"]
