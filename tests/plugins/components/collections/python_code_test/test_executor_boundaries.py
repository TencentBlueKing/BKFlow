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

import collections
import datetime
import threading
from decimal import Decimal
from fractions import Fraction
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
import pytz
from pipeline.eri.imp.serializer import SerializerMixin

from bkflow.pipeline_plugins.components.collections.python_code import (
    executor as executor_module,
)
from bkflow.pipeline_plugins.components.collections.python_code.executor import (
    PythonCodeExecutor,
)


@pytest.mark.parametrize("phase", ["json", "wire"])
def test_result_decoding_keeps_the_concurrency_slot(monkeypatch, phase):
    """JSON 和协议解析期间不能让后续请求取得当前名额。"""
    semaphore = threading.BoundedSemaphore(1)
    executor = PythonCodeExecutor(Mock(), process_semaphore=semaphore)
    owner = executor_module.json if phase == "json" else executor_module
    name = "loads" if phase == "json" else "_decode_wire_value"
    decode = getattr(owner, name)
    slot_held = []

    def inspect_slot(value):
        acquired = semaphore.acquire(blocking=False)
        slot_held.append(not acquired)
        if acquired:
            semaphore.release()
        return decode(value)

    monkeypatch.setattr(owner, name, inspect_slot)
    result = executor.execute_code('def main():\n    return "ok"')

    assert result.success is True, result.message
    assert slot_held == [True]
    assert semaphore.acquire(blocking=False) is True
    semaphore.release()


@pytest.mark.parametrize("phase", ["json", "wire"])
def test_decode_memory_error_returns_failure_and_releases_slot(monkeypatch, phase):
    """两阶段解析内存不足时都应返回节点错误，并归还名额。"""
    semaphore = threading.BoundedSemaphore(1)
    executor = PythonCodeExecutor(Mock(), process_semaphore=semaphore)
    owner = executor_module.json if phase == "json" else executor_module
    name = "loads" if phase == "json" else "_decode_wire_value"

    def out_of_memory(value):
        raise MemoryError

    monkeypatch.setattr(owner, name, out_of_memory)
    result = executor.execute_code('def main():\n    return "ok"')

    assert result.success is False
    assert result.error_phase == "executor"
    assert "内存不足" in result.message
    assert semaphore.acquire(blocking=False) is True
    semaphore.release()


@pytest.mark.parametrize(
    "factory",
    [
        collections.Counter,
        collections.OrderedDict,
        collections.deque,
        collections.defaultdict,
        Decimal,
        Fraction,
        datetime.timedelta,
    ],
)
def test_safe_defaultdict_factories_survive_engine_storage(factory):
    """元组键工厂字典经过协议和实际引擎存储后仍保留缺失键行为。"""
    executor = PythonCodeExecutor(Mock())
    first = executor.execute_code(
        "def main(value):\n    return value", {"value": collections.defaultdict(factory, {(1, 2): 1})}
    )
    assert first.success is True, first.message
    serializer = SerializerMixin()
    payload, kind = serializer._serialize(first.result)
    restored = serializer._deserialize(payload, kind)
    assert restored.default_factory is factory
    expected_type = type(factory())
    assert type(restored["missing"]) is expected_type


def test_unknown_defaultdict_factory_falls_back_only_for_json_output():
    """旧引擎本就会存成普通字典的未知工厂输出仍应成功。"""
    result = PythonCodeExecutor(Mock()).execute_code(
        'def main():\n    return collections.defaultdict(lambda: 1, {"present": [1, 2]})'
    )
    assert result.success is True, result.message
    assert type(result.result) is dict
    assert result.result == {"present": [1, 2]}


def test_unknown_defaultdict_input_is_not_silently_downgraded():
    """输入工厂不能丢失后再执行代码，无法传输时需明确报错。"""
    result = PythonCodeExecutor(Mock()).execute_code(
        "def main(value):\n    return value", {"value": collections.defaultdict(lambda: 1, {"present": 2})}
    )
    assert result.success is False
    assert "default_factory" in result.message


def test_unknown_defaultdict_with_non_json_values_is_not_silently_downgraded():
    """不能将旧版需要 pickle 保型的输出静默降级为普通字典。"""
    result = PythonCodeExecutor(Mock()).execute_code(
        "def main():\n    return collections.defaultdict(lambda: 1, {(1, 2): 3})"
    )
    assert result.success is False
    assert "default_factory" in result.message


@pytest.mark.parametrize(
    "value",
    [
        datetime.datetime(2026, 9, 9, 12, tzinfo=datetime.timezone(datetime.timedelta(hours=8), "CST")),
        datetime.time(12, tzinfo=datetime.timezone(datetime.timedelta(hours=8), "CST")),
    ],
)
def test_named_fixed_timezone_survives_the_process_boundary(value):
    """固定时差的自定义名称不能退化成 UTC+08:00。"""
    result = PythonCodeExecutor(Mock()).execute_code("def main(value):\n    return value", {"value": value})
    assert result.success is True, result.message
    assert result.result.tzname() == "CST"
    assert result.result == value


def test_zoneinfo_dst_rules_survive_workflow_input():
    """上下文日期跨夏令时加一天时应使用次日的时差。"""
    value = datetime.datetime(2026, 3, 7, 12, tzinfo=ZoneInfo("America/New_York"))
    serializer = SerializerMixin()
    payload, kind = serializer._serialize(value)
    restored = serializer._deserialize(payload, kind)
    result = PythonCodeExecutor(Mock()).execute_code(
        "def main(value):\n    return (value + datetime.timedelta(days=1)).isoformat()", {"value": restored}
    )
    assert result.success is True, result.message
    assert result.result == "2026-03-08T12:00:00-04:00"


@pytest.mark.parametrize(
    "value",
    [
        datetime.datetime(2026, 11, 1, 1, 30, fold=1, tzinfo=ZoneInfo("America/New_York")),
        datetime.time(1, 30, fold=1, tzinfo=ZoneInfo("America/New_York")),
        pytz.timezone("America/New_York").localize(datetime.datetime(2026, 11, 1, 1, 30), is_dst=False),
        pytz.timezone("America/New_York").localize(datetime.datetime(2026, 11, 1, 1, 30), is_dst=False).timetz(),
        datetime.datetime(2026, 9, 9, tzinfo=pytz.UTC),
        datetime.time(12, tzinfo=pytz.FixedOffset(480)),
    ],
)
def test_timezone_type_and_localized_offset_survive_round_trip(value):
    """保留 ZoneInfo/pytz、重复小时 fold 及 pytz 已定位的时差。"""
    result = PythonCodeExecutor(Mock()).execute_code("def main(value):\n    return value", {"value": value})
    assert result.success is True, result.message
    expected_timezone_type = type(value.tzinfo)
    assert type(result.result.tzinfo) is expected_timezone_type
    assert result.result.fold == value.fold
    assert result.result.isoformat() == value.isoformat()


@pytest.mark.parametrize("value", ["\ud800", "\udfff", "中文\ud800尾部", "正常中文😀"])
def test_surrogate_strings_can_be_passed_and_returned(value):
    """可被旧引擎 JSON 存储的代理字符不能导致输入失败或子进程崩溃。"""
    executor = PythonCodeExecutor(Mock())
    argument = executor.execute_code("def main(value):\n    return len(value)", {"value": value})
    returned = executor.execute_code("def main():\n    return " + repr(value))
    assert argument.success is True, argument.message
    assert argument.result == len(value)
    assert returned.success is True, returned.message
    assert returned.result == value


def test_surrogate_in_exception_keeps_the_original_error():
    """异常消息包含代理字符时仍返回执行错误，不能变为子进程异常退出。"""
    result = PythonCodeExecutor(Mock()).execute_code("def main():\n    raise ValueError(" + repr("\ud800") + ")")
    assert result.success is False
    assert result.error_phase == "execute"
    assert "\ud800" in result.message


def test_string_key_collections_keep_the_existing_engine_storage_contract():
    """协议保型不代表引擎 JSON 保型，保持旧存储规则即可。"""
    serializer = SerializerMixin()
    for code in ["collections.Counter({'key': 1})", "collections.defaultdict(list, {'key': 1})"]:
        result = PythonCodeExecutor(Mock()).execute_code("def main():\n    return " + code)
        assert result.success is True, result.message
        payload, kind = serializer._serialize(result.result)
        assert kind == "json"
        assert type(serializer._deserialize(payload, kind)) is dict


def test_nested_unknown_factory_is_not_downgraded_when_the_whole_output_needs_pickle():
    """兄弟字段迫使引擎走 pickle 时，不能单独把内部工厂字典当成 JSON 降级。"""
    result = PythonCodeExecutor(Mock()).execute_code(
        'def main():\n    return {"factory": collections.defaultdict(uuid.uuid4, {"a": 1}), "special": {1}}'
    )
    assert result.success is False
    assert "default_factory" in result.message


def test_surrogate_pairs_are_not_combined_into_different_python_strings():
    """pickle 上下文中的两个代理码点不能在协议 JSON 解码时合并成一个字符。"""
    value = {"\ud800\udc00": "\ud800\udc00"}
    executor = PythonCodeExecutor(Mock())
    result = executor.execute_code("def main(value):\n    return value", {"value": value})
    assert result.success is True, result.message
    assert result.result == value


@pytest.mark.parametrize(
    "value",
    [
        datetime.datetime(2026, 9, 9, tzinfo=pytz.timezone("Etc/GMT-8")),
        datetime.time(12, tzinfo=pytz.timezone("GMT")),
    ],
)
def test_pytz_static_timezones_do_not_require_dst_metadata(value):
    """pytz 固定时区没有 _dst 属性，仍应支持输入和返回。"""
    result = PythonCodeExecutor(Mock()).execute_code("def main(value):\n    return value", {"value": value})
    assert result.success is True, result.message
    assert result.result.tzinfo is value.tzinfo


def test_fixed_timezone_name_preserves_surrogate_codepoints():
    """时区名称也属于用户字符串，不能在 JSON 中合并其代理码点。"""
    value = datetime.datetime(2026, 9, 9, tzinfo=datetime.timezone(datetime.timedelta(hours=8), "\ud800\udc00"))
    result = PythonCodeExecutor(Mock()).execute_code("def main(value):\n    return value", {"value": value})
    assert result.success is True, result.message
    assert result.result.tzname() == "\ud800\udc00"
