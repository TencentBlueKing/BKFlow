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

from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.template.models import Template

logger = logging.getLogger("root")


def _task_detail(space_id, task_id):
    """引擎资源不可读取时拒绝匹配，不将边界异常变成放行。"""
    try:
        result = TaskComponentClient(space_id=space_id).get_task_detail(task_id)
    except Exception:
        logger.warning("[resource_matching] Failed to get task detail, space_id=%s, task_id=%s", space_id, task_id)
        return None
    if not isinstance(result, dict) or not result.get("result") or not isinstance(result.get("data"), dict):
        return None
    return result["data"]


def _matches_task_ancestor(grant, space_id, task_id):
    """沿目标任务的父链向上匹配，重复节点或失败时有限终止。"""
    visited = set()
    current = str(task_id)
    while current not in visited:
        visited.add(current)
        task = _task_detail(space_id, current)
        if task is None:
            return False
        parent = task.get("parent_task_info")
        if not isinstance(parent, dict) or parent.get("task_id") is None:
            return False
        current = str(parent["task_id"])
        if current == grant.resource_id:
            return True
    return False


def _matches_scope(grant, space_id, resource_id, target_resource_type, is_composite):
    """按明确目标类型匹配 scope；旧内部调用保留模板优先回退。"""
    if target_resource_type is None:
        if is_composite:
            return False
        if grant.resource_id == str(resource_id):
            return True
    elif target_resource_type not in {"TASK", "TEMPLATE"}:
        return False
    parts = grant.resource_id.split("_", 1)
    if len(parts) != 2:
        return False
    scope_type, scope_value = parts
    if target_resource_type in {None, "TEMPLATE"}:
        try:
            template = Template.objects.get(id=resource_id, space_id=space_id)
        except (Template.DoesNotExist, ValueError, TypeError):
            if target_resource_type == "TEMPLATE":
                return False
        else:
            return template.scope_type == scope_type and template.scope_value == scope_value
    task = _task_detail(space_id, resource_id)
    return task is not None and task.get("scope_type") == scope_type and task.get("scope_value") == scope_value


def matches_resource(grant, space_id, resource_id, target_resource_type=None, is_composite=False) -> bool:
    """匹配一项完整授权的资源范围，不合并不同明细的资源与动作。"""
    if grant.resource_type == "SCOPE":
        return _matches_scope(grant, space_id, resource_id, target_resource_type, is_composite)
    if grant.resource_id == str(resource_id):
        return True
    if grant.resource_type == "TASK":
        return _matches_task_ancestor(grant, space_id, resource_id)
    return False
