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
import copy
import logging
from typing import Optional

from bamboo_engine.utils.boolrule import BoolRule
from bkflow_feel.api import parse_expression
from pipeline.core.constants import PE
from pipeline.parser.utils import replace_all_id
from pipeline.utils.uniqid import node_uniqid

from bkflow.utils.canvas import OperateType, get_canvas_handler
from bkflow.utils.mako import parse_mako_expression

logger = logging.getLogger(__name__)


DEFAULT_HORIZONTAL_PIPELINE_TREE = {
    "activities": {
        "node89f4f55f853d71c6a15e83d0d0ca": {
            "component": {
                "code": "bk_display",
                "data": {"bk_display_message": {"hook": False, "need_render": True, "value": ""}},
                "version": "v1.0",
            },
            "error_ignorable": False,
            "id": "node89f4f55f853d71c6a15e83d0d0ca",
            "incoming": ["line36c9bd1b0fd00d891e1ece06f48c"],
            "loop": None,
            "name": "消息展示",
            "optional": True,
            "outgoing": "linedb35ed07d28c25832e19eacbcc72",
            "stage_name": "",
            "type": "ServiceActivity",
            "retryable": True,
            "skippable": True,
            "auto_retry": {"enable": False, "interval": 0, "times": 1},
            "timeout_config": {"enable": False, "seconds": 10, "action": "forced_fail"},
            "labels": [],
        }
    },
    "constants": {},
    "end_event": {
        "id": "node6fc3d06623e4bfd228b491cd47de",
        "incoming": ["linedb35ed07d28c25832e19eacbcc72"],
        "name": "",
        "outgoing": "",
        "type": "EmptyEndEvent",
        "labels": [],
    },
    "flows": {
        "line36c9bd1b0fd00d891e1ece06f48c": {
            "id": "line36c9bd1b0fd00d891e1ece06f48c",
            "is_default": False,
            "source": "node27a3099dcf3a81c82f71b3d7ef24",
            "target": "node89f4f55f853d71c6a15e83d0d0ca",
        },
        "linedb35ed07d28c25832e19eacbcc72": {
            "id": "linedb35ed07d28c25832e19eacbcc72",
            "is_default": False,
            "source": "node89f4f55f853d71c6a15e83d0d0ca",
            "target": "node6fc3d06623e4bfd228b491cd47de",
        },
    },
    "gateways": {},
    "line": [
        {
            "id": "line36c9bd1b0fd00d891e1ece06f48c",
            "source": {"arrow": "Right", "id": "node27a3099dcf3a81c82f71b3d7ef24"},
            "target": {"arrow": "Left", "id": "node89f4f55f853d71c6a15e83d0d0ca"},
        },
        {
            "id": "linedb35ed07d28c25832e19eacbcc72",
            "source": {"arrow": "Right", "id": "node89f4f55f853d71c6a15e83d0d0ca"},
            "target": {"arrow": "Left", "id": "node6fc3d06623e4bfd228b491cd47de"},
        },
    ],
    "location": [
        {"id": "node27a3099dcf3a81c82f71b3d7ef24", "type": "startpoint", "x": 40, "y": 150},
        {
            "id": "node89f4f55f853d71c6a15e83d0d0ca",
            "type": "tasknode",
            "name": "消息展示",
            "stage_name": "",
            "x": 240,
            "y": 140,
            "group": "蓝鲸服务(BK)",
            "icon": "",
        },
        {"id": "node6fc3d06623e4bfd228b491cd47de", "type": "endpoint", "x": 540, "y": 150},
    ],
    "outputs": [],
    "start_event": {
        "id": "node27a3099dcf3a81c82f71b3d7ef24",
        "incoming": "",
        "name": "",
        "outgoing": "line36c9bd1b0fd00d891e1ece06f48c",
        "type": "EmptyStartEvent",
        "labels": [],
    },
    "canvas_mode": "horizontal",
}


DEFAULT_VERTICAL_PIPELINE_TREE = {
    "activities": {
        "node89f4f55f853d71c6a15e83d0d0ca": {
            "component": {
                "code": "bk_display",
                "data": {"bk_display_message": {"hook": False, "need_render": True, "value": ""}},
                "version": "v1.0",
            },
            "error_ignorable": False,
            "id": "node89f4f55f853d71c6a15e83d0d0ca",
            "incoming": ["line36c9bd1b0fd00d891e1ece06f48c"],
            "loop": None,
            "name": "消息展示",
            "optional": True,
            "outgoing": "linedb35ed07d28c25832e19eacbcc72",
            "stage_name": "",
            "type": "ServiceActivity",
            "retryable": True,
            "skippable": True,
            "auto_retry": {"enable": False, "interval": 0, "times": 1},
            "timeout_config": {"enable": False, "seconds": 10, "action": "forced_fail"},
            "labels": [],
        }
    },
    "constants": {},
    "end_event": {
        "id": "node6fc3d06623e4bfd228b491cd47de",
        "incoming": ["linedb35ed07d28c25832e19eacbcc72"],
        "name": "",
        "outgoing": "",
        "type": "EmptyEndEvent",
        "labels": [],
    },
    "flows": {
        "line36c9bd1b0fd00d891e1ece06f48c": {
            "id": "line36c9bd1b0fd00d891e1ece06f48c",
            "is_default": False,
            "source": "node27a3099dcf3a81c82f71b3d7ef24",
            "target": "node89f4f55f853d71c6a15e83d0d0ca",
        },
        "linedb35ed07d28c25832e19eacbcc72": {
            "id": "linedb35ed07d28c25832e19eacbcc72",
            "is_default": False,
            "source": "node89f4f55f853d71c6a15e83d0d0ca",
            "target": "node6fc3d06623e4bfd228b491cd47de",
        },
    },
    "gateways": {},
    "line": [
        {
            "id": "line36c9bd1b0fd00d891e1ece06f48c",
            "source": {"arrow": "Bottom", "id": "node27a3099dcf3a81c82f71b3d7ef24"},
            "target": {"arrow": "Top", "id": "node89f4f55f853d71c6a15e83d0d0ca"},
        },
        {
            "id": "linedb35ed07d28c25832e19eacbcc72",
            "source": {"arrow": "Bottom", "id": "node89f4f55f853d71c6a15e83d0d0ca"},
            "target": {"arrow": "Top", "id": "node6fc3d06623e4bfd228b491cd47de"},
        },
    ],
    "location": [
        {"id": "node27a3099dcf3a81c82f71b3d7ef24", "type": "startpoint", "x": 40, "y": 150},
        {
            "id": "node89f4f55f853d71c6a15e83d0d0ca",
            "type": "tasknode",
            "name": "消息展示",
            "stage_name": "",
            "x": -20,
            "y": 244,
            "group": "蓝鲸服务(BK)",
            "icon": "",
        },
        {"id": "node6fc3d06623e4bfd228b491cd47de", "type": "endpoint", "x": 40, "y": 358},
    ],
    "outputs": [],
    "start_event": {
        "id": "node27a3099dcf3a81c82f71b3d7ef24",
        "incoming": "",
        "name": "",
        "outgoing": "line36c9bd1b0fd00d891e1ece06f48c",
        "type": "EmptyStartEvent",
        "labels": [],
    },
    "canvas_mode": "vertical",
}


DEFAULT_STAGE_PIPELINE_TREE = {
    "activities": {
        "nodec4b13c772ce97fc184a2612247cc": {
            "component": {
                "code": "bk_display",
                "data": {"bk_display_message": {"hook": False, "need_render": True, "value": ""}},
                "version": "v1.0",
            },
            "error_ignorable": False,
            "id": "nodec4b13c772ce97fc184a2612247cc",
            "incoming": ["line065319f93761c67d5fa7312be4df"],
            "loop": None,
            "name": "消息展示",
            "optional": True,
            "outgoing": "line1c0c2149e22a3e9f27e2b1e09a72",
            "stage_name": "",
            "type": "ServiceActivity",
            "retryable": True,
            "skippable": True,
            "auto_retry": {"enable": False, "interval": 0, "times": 1},
            "timeout_config": {"enable": False, "seconds": 10, "action": "forced_fail"},
            "labels": [],
        }
    },
    "constants": {},
    "end_event": {
        "id": "node90f8323a6030119b7b941c3ca5d9",
        "incoming": ["linebb49db5a0e8a15c9374cf05447d3"],
        "name": "",
        "outgoing": "",
        "type": "EmptyEndEvent",
        "labels": [],
    },
    "flows": {
        "line421d9cb81340871c1482ccfdc32f": {
            "id": "line421d9cb81340871c1482ccfdc32f",
            "source": "noded63f789cab4fa1bcf7bd7e28be33",
            "target": "noded8066692dbdda189bd033e0442ad",
            "is_default": False,
        },
        "linebb49db5a0e8a15c9374cf05447d3": {
            "id": "linebb49db5a0e8a15c9374cf05447d3",
            "source": "node609a8e0d75f184cd4f70f28991b4",
            "target": "node90f8323a6030119b7b941c3ca5d9",
            "is_default": False,
        },
        "line065319f93761c67d5fa7312be4df": {
            "id": "line065319f93761c67d5fa7312be4df",
            "source": "noded8066692dbdda189bd033e0442ad",
            "target": "nodec4b13c772ce97fc184a2612247cc",
            "is_default": False,
        },
        "line1c0c2149e22a3e9f27e2b1e09a72": {
            "id": "line1c0c2149e22a3e9f27e2b1e09a72",
            "is_default": False,
            "source": "nodec4b13c772ce97fc184a2612247cc",
            "target": "node609a8e0d75f184cd4f70f28991b4",
        },
    },
    "gateways": {
        "noded8066692dbdda189bd033e0442ad": {
            "id": "noded8066692dbdda189bd033e0442ad",
            "incoming": ["line421d9cb81340871c1482ccfdc32f"],
            "name": "",
            "outgoing": ["line065319f93761c67d5fa7312be4df"],
            "type": "ParallelGateway",
            "converge_gateway_id": "",
        },
        "node609a8e0d75f184cd4f70f28991b4": {
            "id": "node609a8e0d75f184cd4f70f28991b4",
            "incoming": ["line1c0c2149e22a3e9f27e2b1e09a72"],
            "name": "",
            "outgoing": "linebb49db5a0e8a15c9374cf05447d3",
            "type": "ConvergeGateway",
        },
    },
    "line": [
        {
            "id": "line421d9cb81340871c1482ccfdc32f",
            "source": {"arrow": "Right", "id": "noded63f789cab4fa1bcf7bd7e28be33"},
            "target": {"arrow": "Left", "id": "noded8066692dbdda189bd033e0442ad"},
        },
        {
            "id": "linebb49db5a0e8a15c9374cf05447d3",
            "source": {"arrow": "Right", "id": "node609a8e0d75f184cd4f70f28991b4"},
            "target": {"arrow": "Left", "id": "node90f8323a6030119b7b941c3ca5d9"},
        },
        {
            "id": "line065319f93761c67d5fa7312be4df",
            "source": {"arrow": "Right", "id": "noded8066692dbdda189bd033e0442ad"},
            "target": {"arrow": "Left", "id": "nodec4b13c772ce97fc184a2612247cc"},
        },
        {
            "id": "line1c0c2149e22a3e9f27e2b1e09a72",
            "source": {"arrow": "Right", "id": "nodec4b13c772ce97fc184a2612247cc"},
            "target": {"arrow": "Left", "id": "node609a8e0d75f184cd4f70f28991b4"},
        },
    ],
    "location": [
        {"id": "noded63f789cab4fa1bcf7bd7e28be33", "type": "startpoint", "x": 40, "y": 150},
        {"id": "node90f8323a6030119b7b941c3ca5d9", "type": "endpoint", "x": 840, "y": 150},
        {"id": "noded8066692dbdda189bd033e0442ad", "type": "parallelgateway", "x": 240, "y": 150},
        {"id": "node609a8e0d75f184cd4f70f28991b4", "type": "convergegateway", "x": 640, "y": 150},
        {
            "id": "nodec4b13c772ce97fc184a2612247cc",
            "type": "tasknode",
            "x": 440,
            "y": 140,
            "name": "消息展示",
            "stage_name": "",
            "status": "",
            "skippable": True,
            "retryable": True,
            "optional": True,
            "auto_retry": {"enable": False, "interval": 0, "times": 1},
            "timeout_config": {"enable": False, "seconds": 10, "action": "forced_fail"},
            "isActived": False,
        },
    ],
    "outputs": [],
    "start_event": {
        "id": "noded63f789cab4fa1bcf7bd7e28be33",
        "incoming": "",
        "name": "",
        "outgoing": "line421d9cb81340871c1482ccfdc32f",
        "type": "EmptyStartEvent",
        "labels": [],
    },
    "canvas_mode": "stage",
    "stage_canvas_data": [
        {
            "id": "node9a2bba5dc8b81156537c479f9db0",
            "name": "Stage-1",
            "config": [],
            "jobs": [
                {
                    "id": "nodea995a2776eb4fc455df9ca64777f",
                    "name": "Job-1",
                    "config": [],
                    "nodes": [
                        {
                            "id": "nodec4b13c772ce97fc184a2612247cc",
                            "type": "Node",
                            "option": {
                                "id": "nodec4b13c772ce97fc184a2612247cc",
                                "nodeType": "Node",
                            },
                        }
                    ],
                    "type": "Job",
                }
            ],
            "type": "Stage",
        }
    ],
    "stage_canvas_constants": [],
}


CANVAS_TEMPLATE_MAP = {
    "horizontal": DEFAULT_HORIZONTAL_PIPELINE_TREE,
    "vertical": DEFAULT_VERTICAL_PIPELINE_TREE,
    "stage": DEFAULT_STAGE_PIPELINE_TREE,
}


def build_default_pipeline_tree(canvas_type: str = "horizontal"):
    # 根据 canvas_type 创建不同的 pipeline tree
    try:
        pipeline_tree = copy.deepcopy(CANVAS_TEMPLATE_MAP[canvas_type])
    except KeyError:
        raise ValueError(f"Invalid canvas_type: {canvas_type}，Must be one of: {', '.join(CANVAS_TEMPLATE_MAP.keys())}")

    return replace_pipeline_tree_node_ids(pipeline_tree, OperateType.CREATE_TEMPLATE.value)


def pipeline_gateway_expr_func(expr: str, context: dict, extra_info: dict, *args, **kwargs) -> bool:
    if extra_info.get("parse_lang") == "FEEL":
        return parse_expression(expression=expr)
    if extra_info.get("parse_lang") == "MAKO":
        return parse_mako_expression(expression=expr, context=context)
    return BoolRule(expr).test()


def replace_pipeline_tree_node_ids(
    pipeline_tree: dict, operate_type: str = OperateType.CREATE_TEMPLATE.value, node_map: Optional[dict] = None
) -> dict:
    """替换 pipeline tree 中的节点 ID"""

    handler = get_canvas_handler(pipeline_tree)

    # 复制操作特殊处理
    if operate_type == OperateType.COPY_TEMPLATE.value and not handler.should_process_copy(pipeline_tree):
        return pipeline_tree

    # 生成节点映射
    if handler.should_generate_node_map(pipeline_tree, node_map):
        try:
            node_map_raw = _recursive_replace_id_without_subprocess(pipeline_tree)
            first_pipeline = next(iter(node_map_raw.values()), {})
            node_map = first_pipeline.get("activities", {})
        except Exception as e:
            logger.exception(f"[replace_pipeline_tree_node_ids]Failed to generate node mapping: {e}")
            node_map = {}

    # 处理节点替换
    if node_map:
        handler.handle_node_replacement(pipeline_tree, node_map)

    return pipeline_tree


def _recursive_replace_id_without_subprocess(pipeline_data, subprocess_id=None):
    """
    替换pipeline_id 并返回 对应的 node_map 映射
    备注：这里之所以没有引用bamboo-engine里的_recursive_replace_id_with_node_map
         是因为独立子流程模式下不需要展开子流程
    """
    pipeline_data[PE.id] = node_uniqid()
    node_map = {}
    replace_result_map = replace_all_id(pipeline_data)
    pipeline_id = subprocess_id or pipeline_data[PE.id]
    node_map[pipeline_id] = replace_result_map
    return node_map


def replace_subprocess_version(pipeline_tree: dict) -> dict:
    from bkflow.template.models import TemplateSnapshot

    md5sum_list = []
    for key, value in pipeline_tree["activities"].items():
        if value["type"] == "SubProcess" and len(value["version"]) == 32:
            md5sum_list.append(value["version"])

    snapshot_map = {}
    if md5sum_list:
        snapshots = TemplateSnapshot.objects.filter(md5sum__in=md5sum_list, draft=False).order_by("id")
        snapshot_map = {snapshot.md5sum: snapshot.version for snapshot in snapshots}

    for key, value in pipeline_tree["activities"].items():
        if value["type"] == "SubProcess" and len(value["version"]) == 32:
            # 使用查询结果更新version，如果不存在则保持原样
            value["version"] = snapshot_map.get(value["version"], value["version"])

    return pipeline_tree
