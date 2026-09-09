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
import decimal
import io
import json
import sys
import time
import uuid
from fractions import Fraction
from unittest.mock import Mock, patch

import pytest

from bkflow.pipeline_plugins.components.collections.python_code.executor import (
    WIRE_TYPE_KEY,
    PythonCodeExecutor,
    _decode_wire_value,
    _encode_wire_value,
    _execute_code_in_current_process,
    _write_response,
)


class RecordingSemaphore:
    """记录当前是否持有子进程执行槽位。"""

    def __init__(self):
        self.acquired = False

    def acquire(self, timeout):
        self.acquired = True
        return True

    def release(self):
        self.acquired = False


class GuardedDict(dict):
    """仅允许在持有执行槽位时编码的字典。"""

    def __init__(self, semaphore, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.semaphore = semaphore

    def items(self):
        assert self.semaphore.acquired, "输入编码发生在获取并发槽位之前"
        return super().items()


class SlowDict(dict):
    """模拟耗时的输入编码。"""

    def items(self):
        time.sleep(0.05)
        return super().items()


class StdoutBuffer:
    """为协议输出测试提供带 buffer 的文本流。"""

    def __init__(self):
        self.buffer = io.BytesIO()


def test_wire_codec_keeps_json_dense_payload_compact():
    """JSON 原生记录不能因类型协议产生数量级膨胀。"""
    value = [{"id": index, "ok": True, "name": "x"} for index in range(1000)]
    raw_size = len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    encoded = _encode_wire_value(value)
    wire_size = len(json.dumps(encoded, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    assert wire_size <= raw_size + 128


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        42,
        1.5,
        "text",
        [1, "two"],
        {"key": "value"},
        {1: "one", (2, 3): "tuple-key"},
        {WIRE_TYPE_KEY: "user-value"},
        (1, "two"),
        {1, "two"},
        frozenset({3, "four"}),
        datetime.datetime(2026, 9, 8, 12, 34, 56, tzinfo=datetime.timezone.utc),
        datetime.date(2026, 9, 8),
        datetime.time(12, 34, 56),
        datetime.timedelta(days=2, seconds=3, microseconds=4),
        decimal.Decimal("123.4500"),
        Fraction(2, 3),
        uuid.UUID("12345678-1234-5678-1234-567812345678"),
        b"\x00bkflow\xff",
        bytearray(b"bkflow"),
        range(1, 10, 2),
        collections.deque([1, "two"], maxlen=5),
    ],
)
def test_wire_codec_round_trip_preserves_supported_types(value):
    """声明支持的类型经过协议往返后必须保值且保型。"""
    restored = _decode_wire_value(_encode_wire_value(value))

    assert restored == value
    assert type(restored) is type(value)


def test_dense_json_result_below_limit_executes_successfully():
    """约 1MB 的标量密集结果不能被 10MB wire 上限误拒绝。"""
    executor = PythonCodeExecutor(service=Mock(), timeout=5, max_response_size_bytes=10 * 1024 * 1024)
    code = "def main():\n    return [{'id': i, 'ok': True, 'name': 'x'} for i in range(30000)]"

    result = executor.execute_code(code)

    assert result.success is True
    assert len(result.result) == 30000


def test_input_encoding_happens_after_concurrency_slot_is_acquired():
    """父 Worker 的输入协议展开必须受子进程并发槽位保护。"""
    semaphore = RecordingSemaphore()
    executor = PythonCodeExecutor(service=Mock(), timeout=1, process_semaphore=semaphore)

    result = executor.execute_code(
        "def main(value):\n    return value",
        input_args={"value": GuardedDict(semaphore, {"key": "value"})},
    )

    assert result.success is True
    assert result.result == {"key": "value"}
    assert semaphore.acquired is False


def test_input_encoding_consumes_preparation_timeout_budget():
    """输入编码耗尽准备阶段预算后不能再启动用户代码。"""
    executor = PythonCodeExecutor(service=Mock(), timeout=0.01)
    process = Mock(returncode=0)
    process.communicate.return_value = (
        json.dumps(
            {
                "success": False,
                "result": None,
                "message": "不应执行到子进程",
                "error_phase": "execute",
                "warnings": [],
            }
        ).encode("utf-8"),
        b"",
    )

    with patch(
        "bkflow.pipeline_plugins.components.collections.python_code.executor.subprocess.Popen",
        return_value=process,
    ):
        result = executor.execute_code(
            "def main(value):\n    return value",
            input_args={"value": SlowDict({"key": "value"})},
        )

    assert result.success is False
    assert result.error_phase == "wait"
    assert result.message == "Python代码执行等待超时（0.01秒）"


def test_response_limit_reports_encoded_actual_and_maximum_size():
    """响应超限错误必须说明限制针对编码后大小并给出实际值。"""
    executor = PythonCodeExecutor(service=Mock(), timeout=1, max_response_size_bytes=512)

    result = executor.execute_code("def main():\n    return 'x' * 1000")

    assert result.success is False
    assert result.error_phase == "execute"
    assert result.message.startswith("执行错误: main函数返回结果跨进程编码后超过限制（实际")
    assert result.message.endswith("字节，最大512字节）")


def test_result_encoding_memory_error_has_actionable_message():
    """结果编码内存不足时应返回明确错误而不是空异常信息。"""
    request = {
        "code": "def main():\n    return 'ok'",
        "input_args": _encode_wire_value({}),
        "max_code_length": 10240,
        "memory_limit_mb": 256,
    }

    with patch(
        "bkflow.pipeline_plugins.components.collections.python_code.executor._set_memory_limit",
        return_value=(True, ""),
    ), patch(
        "bkflow.pipeline_plugins.components.collections.python_code.executor._encode_wire_value",
        side_effect=MemoryError,
    ):
        response = _execute_code_in_current_process(request)

    assert response["success"] is False
    assert response["error_phase"] == "execute"
    assert response["message"] == "内存使用超出限制（256MB）"


def test_response_serialization_memory_error_uses_prebuilt_fallback():
    """响应 JSON 序列化内存不足时仍应写出可解析的失败协议。"""
    stdout = StdoutBuffer()
    response = {"success": True, "result": "ok", "message": "", "warnings": []}

    with patch.object(sys, "__stdout__", stdout), patch(
        "bkflow.pipeline_plugins.components.collections.python_code.executor.json.dumps",
        side_effect=MemoryError,
    ):
        _write_response(response, 1024)

    fallback = json.loads(stdout.buffer.getvalue().decode("utf-8"))
    assert fallback["success"] is False
    assert fallback["error_phase"] == "executor"
    assert fallback["message"] == "执行器错误: 子进程响应序列化内存不足"


def test_malformed_wire_result_is_reported_as_executor_error():
    """畸形的受信边界响应不能把协议解析异常泄漏到 Worker。"""
    process = Mock(returncode=0)
    process.communicate.return_value = (
        json.dumps(
            {
                "success": True,
                "result": {WIRE_TYPE_KEY: ["datetime"]},
                "message": "",
                "warnings": [],
            }
        ).encode("utf-8"),
        b"",
    )
    executor = PythonCodeExecutor(service=Mock(), timeout=1)

    with patch(
        "bkflow.pipeline_plugins.components.collections.python_code.executor.subprocess.Popen",
        return_value=process,
    ), patch.object(executor, "_communicate", return_value=process.communicate.return_value):
        result = executor.execute_code("def main():\n    return None")

    assert result.success is False
    assert result.error_phase == "executor"
    assert result.message.startswith("执行器错误: 无法解析子进程返回结果:")


def test_result_decode_memory_error_has_actionable_message():
    """父进程解析响应内存不足时应返回明确错误。"""
    process = Mock(returncode=0)
    process.communicate.return_value = (
        json.dumps({"success": True, "result": "ok", "message": "", "warnings": []}).encode("utf-8"),
        b"",
    )
    executor = PythonCodeExecutor(service=Mock(), timeout=1)

    with patch(
        "bkflow.pipeline_plugins.components.collections.python_code.executor.subprocess.Popen",
        return_value=process,
    ), patch.object(executor, "_communicate", return_value=process.communicate.return_value), patch(
        "bkflow.pipeline_plugins.components.collections.python_code.executor._decode_wire_value",
        side_effect=MemoryError,
    ):
        result = executor.execute_code("def main():\n    return None")

    assert result.success is False
    assert result.error_phase == "executor"
    assert result.message == "执行器错误: 子进程返回结果解析内存不足"
