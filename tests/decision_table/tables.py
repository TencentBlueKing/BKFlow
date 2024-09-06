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

all_types_table = {
    "inputs": [
        {
            "id": "dc724138",
            "desc": "",
            "from": "inputs",
            "name": "selector",
            "tips": "selector",
            "type": "select",
            "options": {
                "type": "custom",
                "items": [{"id": "option_6044a034", "name": "选项1"}, {"id": "option_65bc3d3d", "name": "选项2"}],
                "value": "",
            },
        },
        {
            "id": "1bb803c6",
            "desc": "",
            "from": "inputs",
            "name": "数值类型",
            "tips": "数值类型",
            "type": "int",
            "options": {"type": "custom", "items": [], "value": ""},
        },
        {
            "id": "cd333b63",
            "desc": "",
            "from": "inputs",
            "name": "文本类型",
            "tips": "文本类型",
            "type": "string",
            "options": {"type": "custom", "items": [], "value": ""},
        },
    ],
    "outputs": [
        {
            "id": "7d587535",
            "desc": "",
            "from": "outputs",
            "name": "文本输出",
            "tips": "文本输出",
            "type": "string",
            "options": {"type": "custom", "items": [], "value": ""},
        },
        {
            "id": "09db5d38",
            "desc": "",
            "from": "outputs",
            "name": "数值输出",
            "tips": "数值输出",
            "type": "int",
            "options": {"type": "custom", "items": [], "value": ""},
        },
        {
            "id": "d1b87697",
            "desc": "",
            "from": "outputs",
            "name": "下拉框输出",
            "tips": "下拉框输出",
            "type": "select",
            "options": {
                "type": "custom",
                "items": [{"id": "output1", "name": "选项1"}, {"id": "output2", "name": "选项2"}],
                "value": "",
            },
        },
    ],
    "records": [
        {
            "inputs": {
                "type": "common",
                "conditions": [
                    {
                        "right": {"obj": {"type": "select", "value": "option_65bc3d3d"}, "type": "value"},
                        "compare": "equals",
                    },
                    {"right": {"obj": {"type": "int", "value": "123"}, "type": "value"}, "compare": "equals"},
                    {"right": {"obj": {"type": "string", "value": "abc"}, "type": "value"}, "compare": "equals"},
                ],
            },
            "outputs": {"09db5d38": "34", "7d587535": "deg", "d1b87697": "output1"},
        },
        {
            "inputs": {
                "type": "common",
                "conditions": [
                    {
                        "right": {"obj": {"type": "select", "value": "option_6044a034"}, "type": "value"},
                        "compare": "not-equals",
                    },
                    {"right": {"obj": {"type": "int", "value": "213"}, "type": "value"}, "compare": "not-equals"},
                    {"right": {"obj": {"type": "string", "value": "abc"}, "type": "value"}, "compare": "not-equals"},
                ],
            },
            "outputs": {"09db5d38": "324", "7d587535": "abc", "d1b87697": "output1"},
        },
        {
            "inputs": {
                "type": "or_and",
                "conditions": {
                    "operator": "and",
                    "randomKey": "4962",
                    "conditions": [
                        {
                            "operator": "or",
                            "conditions": [
                                {
                                    "left": {"obj": {"key": "1bb803c6", "type": "string"}, "type": "field"},
                                    "right": {"obj": {"type": "int", "value": "1"}, "type": "value"},
                                    "compare": "equals",
                                },
                                {
                                    "left": {"obj": {"key": "dc724138", "type": "string"}, "type": "field"},
                                    "right": {"obj": {}, "type": "value"},
                                    "compare": "not-null",
                                },
                            ],
                        },
                        {
                            "operator": "and",
                            "conditions": [
                                {
                                    "left": {"obj": {"key": "cd333b63", "type": "string"}, "type": "field"},
                                    "right": {"obj": {"value": "23"}, "type": "value"},
                                    "compare": "contains",
                                }
                            ],
                        },
                    ],
                },
            },
            "outputs": {"09db5d38": "432", "7d587535": "213", "d1b87697": ""},
        },
    ],
}

simple_table = {
    "inputs": [
        {
            "id": "text_area",
            "desc": "",
            "from": "inputs",
            "name": "text_area",
            "tips": "text_area",
            "type": "string",
            "options": {"type": "custom", "items": [], "value": ""},
        },
        {
            "id": "int_area",
            "desc": "",
            "from": "inputs",
            "name": "int_area",
            "tips": "int_area",
            "type": "int",
            "options": {"type": "custom", "items": [], "value": ""},
        },
        {
            "id": "select_area",
            "desc": "",
            "from": "inputs",
            "name": "select_area",
            "tips": "select_area",
            "type": "select",
            "options": {"type": "custom", "items": [{"id": "value1", "name": "选项1"}], "value": ""},
        },
    ],
    "outputs": [
        {
            "id": "output_area",
            "desc": "",
            "from": "outputs",
            "name": "output_area",
            "tips": "output_area",
            "type": "string",
            "options": {"type": "custom", "items": [], "value": ""},
        }
    ],
    "records": [
        {
            "inputs": {
                "type": "common",
                "conditions": [
                    {"right": {"obj": {"type": "string", "value": "a"}, "type": "value"}, "compare": "equals"},
                    {"right": {"obj": {"type": "int", "value": "0"}, "type": "value"}, "compare": "equals"},
                    {"right": {"obj": {"type": "select", "value": "value1"}, "type": "value"}, "compare": "equals"},
                ],
            },
            "outputs": {"output_area": "1"},
        },
        {
            "inputs": {
                "type": "common",
                "conditions": [
                    {"right": {"obj": {"type": "string", "value": "b"}, "type": "value"}, "compare": "equals"},
                    {"right": {"obj": {"type": "int", "value": "1"}, "type": "value"}, "compare": "equals"},
                    {"right": {"obj": {"type": "select", "value": "value1"}, "type": "value"}, "compare": "equals"},
                ],
            },
            "outputs": {"output_area": "2"},
        },
    ],
}

or_and_condition_table = {
    "inputs": [
        {
            "id": "text_area",
            "desc": "",
            "from": "inputs",
            "name": "text_area",
            "tips": "text_area",
            "type": "string",
            "options": {"type": "custom", "items": [], "value": ""},
        },
        {
            "id": "int_area",
            "desc": "",
            "from": "inputs",
            "name": "int_area",
            "tips": "int_area",
            "type": "int",
            "options": {"type": "custom", "items": [], "value": ""},
        },
        {
            "id": "select_area",
            "desc": "",
            "from": "inputs",
            "name": "select_area",
            "tips": "select_area",
            "type": "select",
            "options": {"type": "custom", "items": [{"id": "option1", "name": "选项1"}], "value": ""},
        },
    ],
    "outputs": [
        {
            "id": "output_area",
            "desc": "",
            "from": "outputs",
            "name": "output_area",
            "tips": "output_area",
            "type": "string",
            "options": {"type": "custom", "items": [], "value": ""},
        }
    ],
    "records": [
        {
            "inputs": {
                "type": "or_and",
                "conditions": {
                    "operator": "and",
                    "randomKey": "b504",
                    "conditions": [
                        {
                            "operator": "and",
                            "conditions": [
                                {
                                    "left": {"obj": {"key": "text_area", "type": "string"}, "type": "field"},
                                    "right": {"obj": {"type": "string", "value": "2"}, "type": "value"},
                                    "compare": "equals",
                                }
                            ],
                        }
                    ],
                },
            },
            "outputs": {"output_area": "1"},
        },
        {
            "inputs": {
                "type": "or_and",
                "conditions": {
                    "operator": "and",
                    "randomKey": "85ec",
                    "conditions": [
                        {
                            "operator": "and",
                            "conditions": [
                                {
                                    "left": {"obj": {"key": "text_area", "type": "string"}, "type": "field"},
                                    "right": {"obj": {"type": "string", "value": "1"}, "type": "value"},
                                    "compare": "equals",
                                }
                            ],
                        },
                        {
                            "operator": "and",
                            "conditions": [
                                {
                                    "left": {"obj": {"key": "int_area", "type": "string"}, "type": "field"},
                                    "right": {"obj": {"type": "int", "value": "1"}, "type": "value"},
                                    "compare": "equals",
                                }
                            ],
                        },
                        {
                            "operator": "and",
                            "conditions": [
                                {
                                    "left": {"obj": {"key": "select_area", "type": "string"}, "type": "field"},
                                    "right": {"obj": {"type": "select", "value": "option1"}, "type": "value"},
                                    "compare": "equals",
                                }
                            ],
                        },
                    ],
                },
            },
            "outputs": {"output_area": "2"},
        },
        {
            "inputs": {
                "type": "or_and",
                "conditions": {
                    "operator": "or",
                    "randomKey": "7e6d",
                    "conditions": [
                        {
                            "operator": "and",
                            "conditions": [
                                {
                                    "left": {"obj": {"key": "text_area", "type": "string"}, "type": "field"},
                                    "right": {"obj": {"type": "string", "value": "123"}, "type": "value"},
                                    "compare": "contains",
                                }
                            ],
                        },
                        {
                            "operator": "and",
                            "conditions": [
                                {
                                    "left": {"obj": {"key": "int_area", "type": "string"}, "type": "field"},
                                    "right": {"obj": {"type": "int", "value": "5"}, "type": "value"},
                                    "compare": "greater-than",
                                }
                            ],
                        },
                    ],
                },
            },
            "outputs": {"output_area": "3"},
        },
        {
            "inputs": {
                "type": "or_and",
                "conditions": {
                    "operator": "or",
                    "randomKey": "3d34",
                    "conditions": [
                        {
                            "operator": "and",
                            "conditions": [
                                {
                                    "left": {"obj": {"key": "text_area", "type": "string"}, "type": "field"},
                                    "right": {"obj": {"type": "string", "value": "4"}, "type": "value"},
                                    "compare": "equals",
                                },
                                {
                                    "left": {"obj": {"key": "int_area", "type": "string"}, "type": "field"},
                                    "right": {"obj": {"type": "int", "value": "4"}, "type": "value"},
                                    "compare": "greater-than",
                                },
                            ],
                        },
                        {
                            "operator": "and",
                            "conditions": [
                                {
                                    "left": {"obj": {"key": "int_area", "type": "string"}, "type": "field"},
                                    "right": {"obj": {"type": "int", "value": "4"}, "type": "value"},
                                    "compare": "greater-than",
                                },
                                {
                                    "left": {"obj": {"key": "select_area", "type": "string"}, "type": "field"},
                                    "right": {"obj": {"type": "select[Range]", "value": ["option1"]}, "type": "value"},
                                    "compare": "in-range",
                                },
                            ],
                        },
                    ],
                },
            },
            "outputs": {"output_area": "4"},
        },
    ],
}

expression_table = {
    "inputs": [
        {
            "id": "int_area",
            "desc": "",
            "from": "inputs",
            "name": "int_area",
            "tips": "int_area",
            "type": "int",
            "options": {"type": "custom", "items": [], "value": ""},
        }
    ],
    "outputs": [
        {
            "id": "output_area",
            "desc": "",
            "from": "outputs",
            "name": "output_area",
            "tips": "output_area",
            "type": "string",
            "options": {"type": "custom", "items": [], "value": ""},
        }
    ],
    "records": [{"inputs": {"type": "expression", "conditions": "int_area=2"}, "outputs": {"output_area": "2"}}],
}
