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
import subprocess
import sys
import threading
import time
from unittest.mock import Mock

import pytest
from pipeline.eri.imp.serializer import SerializerMixin

from bkflow.pipeline_plugins.components.collections.python_code.executor import (
    PythonCodeExecutor,
    _decode_wire_value,
    _encode_wire_value,
)

TIMED_MAIN = """
def main():
    started = datetime.datetime.now()
    while (datetime.datetime.now() - started).total_seconds() < 0.6:
        pass
    return 'ok'
"""


def test_queue_wait_does_not_reduce_execution_timeout():
    """等待名额后仍应有完整的执行时间，不能把正常节点误判为超时。"""
    semaphore = threading.BoundedSemaphore(1)
    semaphore.acquire()
    timer = threading.Timer(0.7, semaphore.release)
    timer.start()
    executor = PythonCodeExecutor(service=Mock(), timeout=1, process_semaphore=semaphore)
    try:
        result = executor.execute_code(TIMED_MAIN)
    finally:
        timer.join()

    assert result.success is True, result.message
    assert result.result == "ok"
    assert semaphore.acquire(blocking=False) is True
    semaphore.release()


def test_main_has_separate_timeout_from_preparation():
    """顶层代码准备和 main 各自未超时的节点应成功。"""
    code = (
        """
started = datetime.datetime.now()
while (datetime.datetime.now() - started).total_seconds() < 0.6:
    pass
"""
        + TIMED_MAIN
    )
    result = PythonCodeExecutor(service=Mock(), timeout=1).execute_code(code)

    assert result.success is True, result.message
    assert result.result == "ok"


def test_queue_timeout_can_be_shorter_than_execution_timeout():
    """队列等待应遵循独立配置，且不释放未获得的名额。"""
    semaphore = threading.BoundedSemaphore(1)
    semaphore.acquire()
    executor = PythonCodeExecutor(service=Mock(), timeout=2, queue_timeout=0.05, process_semaphore=semaphore)
    started = time.monotonic()
    try:
        result = executor.execute_code('def main():\n    return "ok"')
        assert result.success is False
        assert result.error_phase == "wait"
        assert time.monotonic() - started < 1
        assert semaphore.acquire(blocking=False) is False
    finally:
        semaphore.release()


@pytest.mark.parametrize("scratch", ["'x' * 2000", "itertools.count()"])
def test_output_selection_precedes_serialization_and_size_limit(scratch):
    """未选择的字段不能因为超大或无法编码而阻断实际的小输出。"""
    executor = PythonCodeExecutor(service=Mock(), timeout=2, max_response_size_bytes=512)
    result = executor.execute_code(
        "def main():\n    return {'selected': 'ok', 'scratch': " + scratch + "}",
        output_key="selected",
    )

    assert result.success is True, result.message
    assert result.result == "ok"


def test_missing_output_key_is_reported_before_encoding_other_fields():
    """输出字段不存在时应保持原来的错误，而非报告其他字段无法编码。"""
    result = PythonCodeExecutor(service=Mock()).execute_code(
        "def main():\n    return {'scratch': itertools.count()}", output_key="missing"
    )

    assert result.success is False
    assert result.error_phase == "execute"
    assert result.message == "输出key 'missing' 不存在于main函数返回的字典中"


def test_default_response_limit_does_not_reject_legacy_large_results():
    """默认配置不能新增 10MB 门槛，显式配置上限的场景由另一个用例保护。"""
    result = PythonCodeExecutor(service=Mock(), timeout=5).execute_code(
        "def main():\n    return 'x' * (11 * 1024 * 1024)"
    )

    assert result.success is True, result.message
    assert len(result.result) == 11 * 1024 * 1024


@pytest.mark.parametrize(
    "value",
    [1 + 2j, collections.Counter({(1, 2): 2, (3, 4): 1}), collections.OrderedDict([("b", 2), ("a", 1)])],
)
def test_additional_legacy_types_survive_wire_round_trip(value):
    """存量支持的值不能被拒绝或静默降级为基本容器。"""
    restored = _decode_wire_value(_encode_wire_value(value))

    assert restored == value
    assert type(restored) is type(value)


@pytest.mark.parametrize("factory", [None, list, int, set, dict])
def test_defaultdict_retains_its_default_factory(factory):
    """defaultdict 输入恢复后仍应保留缺失键行为。"""
    value = collections.defaultdict(factory, {"present": 3})
    executor = PythonCodeExecutor(service=Mock(), timeout=2)
    result = executor.execute_code("def main(value):\n    return value", {"value": value})

    assert result.success is True, result.message
    assert isinstance(result.result, collections.defaultdict)
    assert result.result.default_factory is factory
    if factory is None:
        with pytest.raises(KeyError):
            result.result["missing"]
    else:
        assert result.result["missing"] == factory()


def test_counter_survives_engine_storage_and_a_following_node():
    """元组键 Counter 经实际引擎序列化器保存后，后续节点仍能调用 most_common。"""
    executor = PythonCodeExecutor(service=Mock(), timeout=2)
    first = executor.execute_code("def main():\n    return collections.Counter([(1, 2), (1, 2), (3, 4)])")
    assert first.success is True, first.message
    serializer = SerializerMixin()
    payload, kind = serializer._serialize(first.result)
    value = serializer._deserialize(payload, kind)

    second = executor.execute_code("def main(value):\n    return value.most_common(1)", {"value": value})

    assert second.success is True, second.message
    assert second.result == [((1, 2), 2)]


def test_large_input_is_fully_sent_before_worker_reads_eof():
    """首次管道写入未完成时，父进程必须继续发送大输入并关闭 stdin。"""
    value = "x" * (11 * 1024 * 1024)
    result = PythonCodeExecutor(service=Mock(), timeout=3).execute_code(
        "def main(value):\n    return len(value)", {"value": value}
    )

    assert result.success is True, result.message
    assert result.result == 11 * 1024 * 1024


def test_slow_stdin_reader_does_not_stall_input_transmission():
    """子进程启动后延迟读取时，管道写满也必须最终发送全部参数。"""
    process = subprocess.Popen(
        [sys.executable, "-c", "import sys,time; time.sleep(0.15); print(len(sys.stdin.buffer.read()))"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    executor = PythonCodeExecutor(service=Mock())
    try:
        stdout, stderr = executor._communicate(process, b"x" * (1024 * 1024), time.monotonic() + 2, 2)
        assert stdout.strip() == b"1048576"
        assert stderr == b""
        assert process.returncode == 0
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()
