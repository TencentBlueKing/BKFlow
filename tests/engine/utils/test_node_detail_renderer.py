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

import datetime
import json
from decimal import Decimal

import pytest
from rest_framework.renderers import JSONRenderer

from bkflow.utils.renderers import NodeDetailJSONRenderer


@pytest.mark.parametrize(
    "data",
    [
        None,
        {},
        {"中文😀": "正常中文😀", "lines": "\u2028\u2029", "values": [None, True, 1, 2.5]},
        {"date": datetime.date(2026, 9, 9), "amount": Decimal("1.50"), "bytes": b"hello", "tuple": (1, 2)},
    ],
)
def test_normal_responses_keep_existing_encoding(data):
    """普通响应的字节编码、中文及 DRF 日期类型规则均不因兜底逻辑变化。"""
    assert NodeDetailJSONRenderer().render(data) == JSONRenderer().render(data)


@pytest.mark.parametrize("value", ["\ud800", "\udfff", "A\ud800B😀", "literal \\ud800"])
def test_surrogates_survive_engine_and_interface_rendering(value):
    """两次真实 JSON 渲染/解析不替换代理字符，也不把字面量反斜线误当转义。"""
    renderer = NodeDetailJSONRenderer()
    data = {"output": value}
    engine_result = json.loads(renderer.render(data).decode("utf-8"))
    interface_result = json.loads(renderer.render(engine_result).decode("utf-8"))
    assert interface_result == {"output": value}
    assert data == {"output": value}


def test_unsupported_dict_keys_in_nested_sequences_remain_distinguishable():
    """嵌套容器中不支持的键以整个字典文本展示，不合并不同类型的同名键。"""
    value = [{"nested": ({(1, 2): "tuple", "(1, 2)": "text"},)}]
    result = json.loads(NodeDetailJSONRenderer().render(value))
    assert result == [{"nested": ["{(1, 2): 'tuple', '(1, 2)': 'text'}"]}]
    assert isinstance(value[0]["nested"], tuple)
    assert len(value[0]["nested"][0]) == 2


@pytest.mark.parametrize(
    "value, expected",
    [(float("nan"), "nan"), (float("inf"), "inf"), (float("-inf"), "-inf"), (Decimal("NaN"), "nan")],
)
def test_nonfinite_values_are_displayed_as_text(value, expected):
    """JSON 不接受的非有限数值仅转换展示副本，包含 DRF 对 Decimal 的转换结果。"""
    data = {"value": value, "surrogate": "\ud800"}
    result = json.loads(NodeDetailJSONRenderer().render(data))
    assert result == {"value": expected, "surrogate": "\ud800"}
    assert data["value"] is value


def test_nonfinite_dict_keys_do_not_break_strict_json():
    """非有限字典键不能直接送入 strict JSON，也不能与同名字符串键合并。"""
    data = {float("inf"): "number", "inf": "text"}
    assert json.loads(NodeDetailJSONRenderer().render({"value": data})) == {"value": "{inf: 'number', 'inf': 'text'}"}
    assert len(data) == 2
