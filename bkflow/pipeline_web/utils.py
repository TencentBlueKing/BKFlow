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

from bkflow.pipeline_plugins.components.collections.value_assign.v1_0_0 import (
    ValueAssignComponent,
)

logger = logging.getLogger("root")


def topology_sort(relations):
    """
    拓扑排序
    :params relations: 拓扑关系字典，需保证输入关系合法
    :type relations: dict, key为引用者id，value为被引用者id列表
    :return 关系拓扑排序后顺序列表
    :rtype list
    """
    visited = set()
    orders = []

    def dfs(referencer_id):
        if referencer_id in visited:
            return
        for referenced_id in relations.get(referencer_id, []):
            dfs(referenced_id)
        visited.add(referencer_id)
        orders.append(referencer_id)

    for rid in relations:
        dfs(rid)

    return orders


def pre_handle_pipeline_tree(pipeline_tree):
    """
    pipeline_tree 特殊处理 hooks
    变量赋值节点 pipeline 特殊处理 将变量名添加引用符号避免计算被去除
    :params pipeline_tree 流程树
    """
    for pipeline_node in pipeline_tree["activities"].values():
        if pipeline_node["type"] == "SubProcess":
            continue
        if pipeline_node["component"]["code"] == ValueAssignComponent.code:
            data = pipeline_node["component"]["data"]
            for assignment in data["bk_assignment_list"]["value"]:
                original_key = assignment["key"]
                assignment["key"] = f"${{{original_key}}}"


def post_handle_pipeline_tree(pipeline_tree):
    """
    pipeline_tree 特殊处理 hooks
    变量赋值节点 pipeline 特殊处理 将变量名去除引用符号还原
    :params pipeline_tree 流程树
    """
    for pipeline_node in pipeline_tree["activities"].values():
        if pipeline_node["type"] == "SubProcess":
            continue
        if pipeline_node["component"]["code"] == ValueAssignComponent.code:
            data = pipeline_node["component"]["data"]
            for assignment in data["bk_assignment_list"]["value"]:
                key = assignment["key"]
                if key.startswith("${") and key.endswith("}"):
                    original_key = key[2:-1]  # 去掉包裹的 ${}
                    assignment["key"] = original_key
