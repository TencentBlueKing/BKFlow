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
import re

from bkflow.constants import TEMPLATE_NODE_NAME_MAX_LENGTH

try:
    from pypinyin import lazy_pinyin
except ImportError:  # pragma: no cover
    lazy_pinyin = None


def standardize_name(name, max_length):
    """名称处理"""
    # 替换特殊字符
    name_str = re.compile(r"[<>$&\'\"]+").sub("", name)
    # 长度截取
    return name_str[:max_length]


def pinyin_sort_key(text):
    """中文按拼音排序的排序键（用于 `sorted(key=...)`）。

    直接按字符串排，中文走的是 Unicode 码位序，结果反直觉——「部署」会排在「版本」
    前面（'部'=0x90E8 > '版'=0x7248）。设计稿要求的是「中文名称 A-Z」，即拼音序。

    这里把汉字转成全拼、非汉字原样保留，再统一小写：
        「常用能力」   -> ("changyongnengli", "常用能力")
        「HTTP 请求」  -> ("httpqingqiu", "http 请求")
        「zebra 测试」 -> ("zebraceshi", "zebra 测试")

    第二个元素是原文，作为拼音相同时的次级排序键（保证稳定且可预期）。
    `pypinyin` 不可用时退化为原文小写（行为与改动前一致，只是中文序不理想）。
    """
    if not text:
        return ("", "")
    raw = str(text)
    if lazy_pinyin is None:
        return ("", raw.lower())
    return ("".join(lazy_pinyin(raw)).lower(), raw.lower())


def standardize_pipeline_node_name(pipeline_tree):
    for value in list(pipeline_tree.values()):
        if isinstance(value, dict):
            for info in list(value.values()):
                if isinstance(info, dict) and "name" in info:
                    info["name"] = standardize_name(info["name"], TEMPLATE_NODE_NAME_MAX_LENGTH)
            if "name" in value:
                value["name"] = standardize_name(value["name"], TEMPLATE_NODE_NAME_MAX_LENGTH)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and "name" in item:
                    item["name"] = standardize_name(item["name"], TEMPLATE_NODE_NAME_MAX_LENGTH)
