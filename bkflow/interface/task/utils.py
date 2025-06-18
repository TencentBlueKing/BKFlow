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
import re
from collections import defaultdict
from functools import reduce
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
        """获取任务相关的基础数据

        Args: task_id: 任务ID
        Returns: dict: 包含任务相关数据的字典，如果获取失败则包含默认值
        """
        try:
            task_detail = self.client.get_task_detail(task_id)

            if "data" not in task_detail:
                logger.warning(f"Task {task_id} response data missing: detail={task_detail}")

            pipeline_tree = task_detail.get("data", {}).get("pipeline_tree", {})
            return {
                "task_detail": task_detail,
                "pipeline_tree": pipeline_tree,
                "constants": pipeline_tree.get("constants", {}),
                "stage_struct": pipeline_tree.get("stage_canvas_data", []),
                "stage_constants": pipeline_tree.get("stage_canvas_constants", []),
                "activities": pipeline_tree.get("activities", {}),
            }
        except Exception as e:
            logger.exception(f"Failed to get task data for task {task_id}: {str(e)}")
            raise

    def get_rendered_constants(self, task_id: str, stage_canvas_constants: list, constants: dict):
        """获取渲染后的变量值"""
        try:
            # 1. 收集和分类变量
            constant_details, node_vars, context_vars = self._collect_and_classify_variables(
                stage_canvas_constants, constants
            )

            # 2. 获取数据
            node_data = self._fetch_node_data(task_id, node_vars)
            context_data = self._fetch_context_data(task_id, context_vars)

            # 3. 更新变量值
            self._update_constant_values(constant_details, context_data, node_data)

            return stage_canvas_constants
        except Exception as e:
            logger.error(f"Error in get_rendered_constants: {str(e)}")
            return stage_canvas_constants

    def _collect_and_classify_variables(self, stage_canvas_constants, constants):
        """收集和分类变量"""
        constant_details = defaultdict(list)
        node_output_vars = {}
        context_vars = set()

        # 收集变量信息
        for item in stage_canvas_constants:
            try:
                nested_key_info = self.extract_nested_keys(item["key"])
                if nested_key_info:
                    constant_name = nested_key_info["base"]
                    constant_details[constant_name].append(
                        {"item": item, "nested_info": nested_key_info, "processed": False}
                    )
            except Exception as e:
                logger.error(f"Error processing constant {item['key']}: {str(e)}")
                continue

        # 分类变量
        for constant_name in constant_details:
            constant_key = "${%s}" % constant_name
            if constant_key in constants and constants[constant_key].get("source_info"):
                node_id = self.get_variable_source_nodeid(constant_name, constants)
                if node_id and node_id != "input":
                    node_output_vars.setdefault(node_id, []).append(constant_name)
            else:
                context_vars.add(constant_key)

        return constant_details, node_output_vars, context_vars

    def _fetch_node_data(self, task_id: str, node_vars: dict) -> dict:
        """获取节点输出数据"""
        node_output_data = {}
        for node_id, var_names in node_vars.items():
            node_data = self.client.get_task_node_output(task_id, node_id).get("data", {})
            for var_name in var_names:
                node_output_data[var_name] = node_data.get(var_name, {})
        return node_output_data

    def _fetch_context_data(self, task_id: str, context_vars: set) -> dict:
        """获取上下文数据"""
        if not context_vars:
            return {}
        return self.client.render_filtered_constants(task_id, {"variables": list(context_vars)}).get("data", {})

    def _update_constant_values(self, constant_details, context_data, node_data):
        """更新变量值"""
        for constant_name, details_list in constant_details.items():
            context_key = "${%s}" % constant_name

            for detail in details_list:
                if detail["processed"]:
                    continue

                item = detail["item"]
                nested_info = detail["nested_info"]

                # 优先使用上下文数据
                if context_key in context_data:
                    item["value"] = self.get_nested_value(context_data[context_key], nested_info)
                # 否则使用节点数据
                elif constant_name in node_data:
                    item["value"] = self.get_nested_value(node_data[constant_name], nested_info)
                else:
                    item["value"] = ""

                detail["processed"] = True

    def get_variable_source_nodeid(self, variable_key: str, constants: dict) -> str:
        """
        获取变量的来源节点ID

        Args:
            variable_key: 变量名，如 "_loop"
            constants: 常量字典

        Returns:
            str: 如果source_info不为空，返回节点ID；如果为空返回"input"表示是输入变量
        """
        # 检查变量是否存在于constants中
        if f"${{{variable_key}}}" not in constants:
            raise KeyError(f"Variable {variable_key} not found in constants")

        variable_info = constants[f"${{{variable_key}}}"]
        source_info = variable_info.get("source_info", {})

        # 如果source_info为空，则认为是输入变量
        if not source_info:
            return "input"

        # 如果source_info不为空，返回第一个节点ID
        # source_info是一个字典，其中key为节点ID，value为包含变量名的列表
        return next(iter(source_info.keys()))

    def extract_nested_keys(self, input_str):
        # 匹配基础变量名和所有的键
        # 修改正则以检测中文引号
        pattern = r'\${(\w+)(?:\[([\'"""])((?:(?!\2).)+?)\2\])*}'

        # 检查是否包含中文引号
        if "“" in input_str or "”" in input_str:
            raise ValueError("请使用英文引号 ' 或 \" ，不要使用中文引号 " "")

        # 匹配整个表达式
        match = re.match(pattern, input_str)
        if not match:
            return None

        # 获取基础变量名
        base = match.group(1)

        # 查找所有的键，同时支持单引号和双引号
        keys_pattern = r'\[([\'"])((?:(?!\1).)+?)\1\]'
        keys = [m.group(2) for m in re.finditer(keys_pattern, input_str)]

        result = {"base": base, "keys": keys, "depth": len(keys)}

        return result

    def get_nested_value(self, obj, nested_info):
        """
        递归获取嵌套对象的值
        Args:
            obj: 原始对象
            nested_info: 包含访问路径信息的字典，格式如：
                {
                    "base": "variable_name",  # 基础变量名
                    "depth": 0,               # 嵌套深度
                    "keys": []                # 每层的访问键列表
                }
        Returns:
            找到的值或""
        """
        if obj is None:
            return ""

        # 如果是基本类型且没有需要进一步访问的键，直接返回
        if isinstance(obj, (str, int, float, bool)) and not nested_info["keys"]:
            return obj

        current = obj
        try:
            # 按照 keys 列表逐层访问
            for key in nested_info["keys"]:
                if not isinstance(current, (dict, list)):
                    return current

                if isinstance(current, dict):
                    current = current.get(key)
                elif isinstance(current, list):
                    try:
                        idx = int(key)
                        current = current[idx] if 0 <= idx < len(current) else None
                    except (ValueError, IndexError):
                        return ""

                if current is None:
                    return ""

            return current
        except Exception as e:
            logger.error(f"Error getting nested value: {str(e)}, obj: {obj}, nested_info: {nested_info}")
            return ""

    def get_nested_value_reduce(self, obj, keys):
        try:
            return reduce(lambda d, key: d[key], keys, obj)
        except (KeyError, TypeError, IndexError):
            return None

    def get_node_states(self, task_id: str) -> Dict:
        """获取节点状态信息

        Args: task_id: 任务ID
        Returns: 节点状态信息字典
        """
        data = {"space_id": self.space_id}

        try:
            response = self.client.get_task_states(task_id, data=data)
            if "data" not in response:
                logger.warning(f"Task {task_id} states response data missing: {response}")

            return response.get("data", {}).get("children", {})
        except Exception as e:
            logger.exception(f"Failed to get node states for task {task_id}: {str(e)}")
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

        # 2. 获取渲染变量值
        self.get_rendered_constants(task_id, task_data.get("stage_constants"), task_data.get("constants"))

        # 3. 获取节点状态
        node_states = self.get_node_states(task_id)

        # 4. 构建映射关系
        template_to_task_id = self.build_template_task_mapping(task_data["activities"])
        node_info_map = self.build_node_info_map(template_to_task_id, node_states)

        # 5. 更新状态
        self.update_states(task_data["stage_struct"], node_info_map)

        return task_data["task_detail"].get("data", {})
