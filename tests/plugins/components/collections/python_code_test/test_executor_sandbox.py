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

import http.server
import os
import threading
from unittest.mock import Mock, patch

import pytest
from django.test import override_settings

from bkflow.pipeline_plugins.components.collections.python_code.executor import (
    SUPPORTED_MODULES,
    PythonCodeExecutor,
    _encode_wire_value,
    _execute_code_in_current_process,
)

ALL_MODULES = list(SUPPORTED_MODULES)
POPEN_PATH = "bkflow.pipeline_plugins.components.collections.python_code.executor.subprocess.Popen"
SUCCESS_RESPONSE = b'{"success":true,"result":null,"message":""}'


def _run(code, allowed_modules=ALL_MODULES):
    """在当前进程执行用户代码，便于检查沙箱命名空间。"""
    request = {
        "code": code,
        "input_args": _encode_wire_value({}),
        "max_code_length": 10240,
        "memory_limit_mb": 256,
        "output_key": _encode_wire_value(""),
        "allowed_modules": allowed_modules,
    }
    return _execute_code_in_current_process(request)


@pytest.mark.parametrize(
    "code, expected",
    (
        ("def main():\n    return uuid.os.getpid()", "禁止访问模块属性: os"),
        ("def main():\n    return fractions.sys.version", "禁止访问模块属性: sys"),
        ("def main():\n    return statistics.sys.modules", "禁止访问模块属性: sys"),
        ("def main():\n    return str(jsonschema_module.validators)", "validators"),
        ("def main():\n    return str(jsonschema_module.Draft4Validator)", "Draft4Validator"),
        ("def main():\n    return str(base64.main)", "禁止访问模块属性: main"),
        ("def main():\n    return str(statistics.itemgetter)", "禁止访问模块属性: itemgetter"),
        (
            "def main():\n    return collections.UserString('{0.__globals__[_sys].version}')"
            ".format(collections.namedtuple)",
            "UserString",
        ),
        (
            "def main():\n    return string.Formatter().vformat('{0.__globals__[_sys].version}', "
            "[collections.namedtuple], {})",
            "Formatter",
        ),
        (
            "def main():\n    target = lambda: 1\n"
            "    functools.update_wrapper(target, uuid.uuid4, assigned=(), updated=('__globals__',))\n"
            "    return 'ok'",
            "update_wrapper",
        ),
        ("def main():\n    return str(functools.wraps(collections.namedtuple))", "wraps"),
        (
            "def main():\n    def base(x):\n        return x\n    return str(functools.singledispatch(base))",
            "singledispatch",
        ),
    ),
)
def test_allowed_modules_do_not_expose_system_capabilities(code, expected):
    """开放全部模块后，子模块、解释器全局变量和注解求值入口仍不可用。"""
    response = _run(code)

    assert response["success"] is False
    assert response["error_phase"] in {"compile", "execute"}
    assert expected in response["message"]


def test_jsonschema_does_not_fetch_remote_references():
    """jsonschema 校验不能通过远程 $ref 访问网络。"""
    hits = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        response = _run(
            "def main():\n    return jsonschema_module.validate(1, {'$ref': 'http://127.0.0.1:%d/x'})" % port
        )
    finally:
        server.shutdown()
        server.server_close()

    assert response["success"] is False
    assert "Unresolvable" in response["message"]
    assert hits == []


def test_modules_are_not_available_by_default():
    """未配置开放模块时，用户代码不能使用任何模块。"""
    response = _run("def main():\n    return math.pi", allowed_modules=None)

    assert response["success"] is False
    assert "math" in response["message"]


def test_only_configured_modules_are_available():
    """只注入配置中列出的模块，未列出的模块保持不可用。"""
    assert _run("def main():\n    return math.floor(1.5)", allowed_modules=["math"])["success"] is True

    response = _run("def main():\n    return statistics.mean([1, 2])", allowed_modules=["math"])
    assert response["success"] is False
    assert "statistics" in response["message"]


@pytest.mark.parametrize(
    "code",
    (
        "def main():\n    return math.isclose(0.1 + 0.2, 0.3)",
        "def main():\n    return decimal.getcontext().prec > 0",
        "def main():\n    return functools.reduce(lambda a, b: a + b, [1, 2, 3]) == 6",
        "def main():\n    @functools.lru_cache(maxsize=None)\n    def double(x):\n        return x * 2\n"
        "    return double(2) == 4",
        "def main():\n    return list(itertools.starmap(pow, [(2, 3)])) == [8]",
        "def main():\n    return statistics.pstdev([1, 1, 1]) == 0",
        "def main():\n    return dict(collections.ChainMap({'a': 1}, {'b': 2})) == {'a': 1, 'b': 2}",
        "def main():\n    return len(hashlib.sha224(b'abc').hexdigest()) == 56",
        "def main():\n    return string.Template('$name').substitute(name='ok') == 'ok'",
        "def main():\n    return base64.b32encode(b'a') == b'ME======'",
        "def main():\n    return textwrap.indent('a', '  ') == '  a'",
        "def main():\n    return uuid.getnode() > 0",
        "def main():\n    def impl(x: 'int'):\n        return x\n    return impl(1) == 1",
        "def main():\n    schema = {'definitions': {'n': {'type': 'integer'}}, '$ref': '#/definitions/n'}\n"
        "    jsonschema_module.validate(1, schema)\n    return True",
        "def main():\n    try:\n        jsonschema_module.validate('x', {'type': 'integer'})\n"
        "    except jsonschema_module.ValidationError as error:\n        return 'integer' in error.message\n"
        "    return False",
    ),
)
def test_common_module_usage_still_works(code):
    """收紧后常见的计算、编码和本地 schema 校验写法保持可用。"""
    response = _run(code)

    assert response["success"] is True, response["message"]
    assert response["result"] is True


def test_unsupported_configured_modules_are_reported():
    """配置了不支持的模块名称时记录告警，且不注入该名称。"""
    service = Mock()
    executor = PythonCodeExecutor(service=service, timeout=1, allowed_modules=["math", "os"])

    with patch(POPEN_PATH, return_value=Mock(returncode=0)), patch.object(
        executor, "_communicate", return_value=(SUCCESS_RESPONSE, b"")
    ):
        executor.execute_code("def main():\n    return None")

    assert executor.allowed_modules == ["math"]
    assert executor.unsupported_modules == ["os"]
    service.logger.warning.assert_called_once()
    assert "os" in service.logger.warning.call_args.args[1]


def test_all_modules_flag_opens_every_supported_module():
    """配置为 * 时开放全部受支持模块。"""
    executor = PythonCodeExecutor(service=Mock(), allowed_modules=["*"])

    assert executor.allowed_modules == ALL_MODULES
    assert executor.unsupported_modules == []


def _worker_popen_kwargs(environ):
    """返回执行器启动用户代码子进程时传入的参数。"""
    executor = PythonCodeExecutor(service=Mock(), timeout=1)
    with patch.dict(os.environ, environ, clear=True), patch(
        POPEN_PATH, return_value=Mock(returncode=0)
    ) as popen, patch.object(executor, "_communicate", return_value=(SUCCESS_RESPONSE, b"")):
        executor.execute_code("def main():\n    return None")
    return popen.call_args.kwargs


def test_worker_process_receives_minimal_environment():
    """用户代码子进程不能继承父进程中的密钥和数据库配置。"""
    kwargs = _worker_popen_kwargs({"SECRET_KEY": "secret", "PATH": "/usr/bin", "TZ": "Asia/Shanghai"})

    assert kwargs["env"] == {
        "PATH": "/usr/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
        "TZ": "Asia/Shanghai",
    }
    assert kwargs["close_fds"] is True
    assert kwargs["start_new_session"] is True


@override_settings(TIME_ZONE="Asia/Shanghai")
def test_worker_timezone_falls_back_to_django_setting():
    """父进程未设置 TZ 时，子进程使用 Django 配置的时区。"""
    kwargs = _worker_popen_kwargs({"PATH": "/usr/bin", "SECRET_KEY": "secret"})

    assert kwargs["env"]["TZ"] == "Asia/Shanghai"
    assert "SECRET_KEY" not in kwargs["env"]
