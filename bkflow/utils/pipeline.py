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
import copy

from bamboo_engine.utils.boolrule import BoolRule
from bkflow_feel.api import parse_expression
from pipeline.parser.utils import recursive_replace_id

from bkflow.utils.mako import parse_mako_expression

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


def build_default_pipeline_tree(horizontal_canvas=True):
    pipeline_tree = copy.deepcopy(
        DEFAULT_HORIZONTAL_PIPELINE_TREE if horizontal_canvas else DEFAULT_VERTICAL_PIPELINE_TREE
    )
    recursive_replace_id(pipeline_tree)
    return pipeline_tree


def pipeline_gateway_expr_func(expr: str, context: dict, extra_info: dict, *args, **kwargs) -> bool:
    if extra_info.get("parse_lang") == "FEEL":
        return parse_expression(expression=expr)
    if extra_info.get("parse_lang") == "MAKO":
        return parse_mako_expression(expression=expr, context=context)
    return BoolRule(expr).test()
