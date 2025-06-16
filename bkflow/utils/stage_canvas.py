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


class StageCanvasHandler:
    @staticmethod
    def sync_stage_canvas_data_node_ids(node_map, pipeline_tree):
        """
        在 recursive_replace_id 执行后调用，同步 stage_canvas_data 中的节点 ID

        Args:
            node_map (dict): 包含旧 ID 到新 ID 映射的字典，结构为 {pipeline_id: {'activities': {old_id: new_id}}}
            pipeline_tree (dict): 包含 stage_canvas_data 和 activities 的流水线树结构

        Returns:
            dict: 更新后的 pipeline_tree
        """
        # 获取 stage_canvas_data
        stage_canvas_data = pipeline_tree.get("stage_canvas_data", [])

        # 直接获取唯一pipeline的activities映射
        activities_node_map = next(iter(node_map.values())).get("activities", {})

        # 收集所有需要处理的节点
        all_nodes = []
        for stage in stage_canvas_data:
            for job in stage.get("jobs", []):
                all_nodes.extend(job.get("nodes", []))

        # 直接更新节点 ID
        for node in all_nodes:
            node_id = node.get("id")
            if node_id in activities_node_map:
                node["id"] = activities_node_map[node_id]

        return pipeline_tree
