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
import fractions
import re
import resource
import sys
import threading
import time
import unittest
import uuid
from unittest.mock import Mock

from django.test import SimpleTestCase

from bkflow.pipeline_plugins.components.collections.python_code.v1_0_0 import (
    PythonCodeExecutor,
)


class PythonCodeExecutorProcessIsolationTest(SimpleTestCase):
    """验证 Python 代码不在 er-e 主进程内执行。"""

    def setUp(self):
        self.service = Mock()
        self.executor = PythonCodeExecutor(service=self.service, timeout=1)

    def test_execute_code_keeps_parent_memory_limit_unchanged(self):
        """执行代码后不应修改父进程的地址空间限制。"""
        memory_limit_before = resource.getrlimit(resource.RLIMIT_AS)

        success, result, output_info = self.executor.execute_code(
            "def main(value):\n    return {'value': value}",
            input_args={"value": "ok"},
        )

        assert success is True
        assert result == {"value": "ok"}
        assert output_info == ""
        assert resource.getrlimit(resource.RLIMIT_AS) == memory_limit_before

    def test_execute_code_preserves_supported_non_json_types(self):
        """常见 pickle 类型应在父子进程间保真传递。"""
        expected = {
            "datetime": datetime.datetime(2026, 9, 7, 12, 34, 56, 789, tzinfo=datetime.timezone.utc),
            "date": datetime.date(2026, 9, 7),
            "time": datetime.time(12, 34, 56, 789),
            "timedelta": datetime.timedelta(days=2, seconds=3, microseconds=4),
            "decimal": decimal.Decimal("123.4500"),
            "fraction": fractions.Fraction(2, 3),
            "uuid": uuid.UUID("12345678-1234-5678-1234-567812345678"),
            "set": {1, "two"},
            "frozenset": frozenset({3, "four"}),
            "bytes": b"\x00bkflow\xff",
            "bytearray": bytearray(b"bkflow"),
            "tuple": (1, "two"),
            "range": range(1, 10, 2),
            "deque": collections.deque([1, "two"], maxlen=5),
        }

        success, result, output_info = self.executor.execute_code(
            "def main(value):\n    return value",
            input_args={"value": expected},
        )

        assert success is True
        assert result == expected
        assert output_info == ""
        for key, value in expected.items():
            assert type(result[key]) is type(value)

    @unittest.skipUnless(sys.platform.startswith("linux"), "RLIMIT_AS 仅在 Linux CI/部署环境验证")
    def test_execute_code_applies_memory_limit_on_linux(self):
        """Linux 子进程应成功应用 RLIMIT_AS，而不是仅记录降级 warning。"""
        execution_result = self.executor.execute_code("def main():\n    return 'ok'")

        assert execution_result.success is True
        self.service.logger.warning.assert_not_called()

    def test_execute_code_terminates_timed_out_process(self):
        """超时时应终止子进程并及时返回。"""
        started_at = time.monotonic()

        success, result, error = self.executor.execute_code(
            "def main():\n    while True:\n        pass",
            timeout=0.2,
        )

        assert success is False
        assert result is None
        assert error == "main函数执行超时（0.2秒）"
        assert time.monotonic() - started_at < 3

    def test_execute_code_reports_explicit_error_phase(self):
        """错误分类应由结构化阶段承载，不能依赖中文前缀猜测。"""
        compile_result = self.executor.execute_code("def main(:\n    pass")
        runtime_result = self.executor.execute_code("def main():\n    return 1 / 0")

        assert compile_result.error_phase == "compile"
        assert runtime_result.error_phase == "execute"

    def test_execute_code_limits_concurrent_subprocesses(self):
        """子进程并发额度用尽时不应继续启动新进程。"""
        process_semaphore = threading.BoundedSemaphore(1)
        process_semaphore.acquire()
        executor = PythonCodeExecutor(service=self.service, timeout=0.1, process_semaphore=process_semaphore)

        try:
            success, result, error = executor.execute_code("def main():\n    return {}")
        finally:
            process_semaphore.release()

        assert success is False
        assert result is None
        assert error == "Python代码执行等待超时（0.1秒）"

    def test_timeout_before_main_is_reported_as_wait_timeout(self):
        """顶层代码无限循环时应在准备阶段终止，不占用 main 的执行期限。"""
        executor = PythonCodeExecutor(service=self.service, timeout=0.2)
        started_at = time.monotonic()

        execution_result = executor.execute_code("while True:\n    pass\ndef main():\n    return {}")

        assert execution_result.error_phase == "wait"
        assert execution_result.message == "Python代码执行等待超时（0.2秒）"
        assert time.monotonic() - started_at < 3

    def test_execute_code_rejects_oversized_response(self):
        """超大返回值应在子进程内拦截，避免父进程无界读取。"""
        executor = PythonCodeExecutor(service=self.service, timeout=1, max_response_size_bytes=512)

        execution_result = executor.execute_code("def main():\n    return 'x' * 1000")

        assert execution_result.success is False
        assert execution_result.result is None
        assert execution_result.error_phase == "execute"
        error_match = re.fullmatch(
            r"执行错误: main函数返回结果跨进程编码后超过限制（实际(\d+)字节，最大512字节）",
            execution_result.message,
        )
        assert error_match is not None
        assert int(error_match.group(1)) > 512
