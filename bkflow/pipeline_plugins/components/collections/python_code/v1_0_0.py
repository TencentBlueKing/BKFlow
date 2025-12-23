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
import sys
import threading
from io import StringIO
from typing import Any, Dict

try:
    import resource

    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from pipeline.component_framework.component import Component
from pipeline.core.flow.io import ObjectItemSchema, StringItemSchema
from pipeline.eri.runtime import BambooDjangoRuntime

from bkflow.pipeline_plugins.components.collections.base import BKFlowBaseService

try:
    # RestrictedPython 8.1: 使用 safe_globals 包含所有必需的守卫函数
    from RestrictedPython import compile_restricted, safe_builtins
    from RestrictedPython import safe_globals as rp_safe_globals

    HAS_RESTRICTED_PYTHON = True
except ImportError:
    compile_restricted = None
    safe_builtins = None
    rp_safe_globals = None
    HAS_RESTRICTED_PYTHON = False

__group_name__ = _("蓝鲸服务(BK)")

# 默认执行超时时间（秒）
DEFAULT_TIMEOUT = getattr(settings, "PYTHON_CODE_PLUGIN_TIMEOUT", 30)

# 默认最大代码长度（字符）
MAX_CODE_LENGTH = getattr(settings, "PYTHON_CODE_PLUGIN_MAX_LENGTH", 10240)

# 默认最大内存限制（MB，仅Unix系统）
DEFAULT_MEMORY_LIMIT_MB = getattr(settings, "PYTHON_CODE_PLUGIN_MEMORY_LIMIT_MB", 256)

# 允许的安全内置函数和模块
SAFE_BUILTINS = {
    # 基本类型
    "int",
    "float",
    "str",
    "bool",
    "list",
    "dict",
    "tuple",
    "set",
    "frozenset",
    "type",
    "isinstance",
    "len",
    "range",
    "enumerate",
    "zip",
    "sorted",
    "reversed",
    "min",
    "max",
    "sum",
    "abs",
    "round",
    "divmod",
    "pow",
    "bin",
    "hex",
    "oct",
    "ord",
    "chr",
    "any",
    "all",
    # 字符串操作
    "format",
    # 字典操作
    "dict",
    # 列表操作
    "list",
    # 类型转换
    "str",
    "int",
    "float",
    "bool",
    # JSON操作（通过json模块提供）
}

# 禁止的关键字和函数
FORBIDDEN_KEYWORDS = {
    "import",
    "__import__",
    "eval",
    "exec",
    "compile",
    "open",
    "file",
    "__builtins__",
    "__builtin__",
    "__import__",
}

# 禁止的模块
FORBIDDEN_MODULES = {
    "os",
    "sys",
    "subprocess",
    "shutil",
    "socket",
    "urllib",
    "requests",
    "multiprocessing",
    "threading",
    "ctypes",
    "pickle",
    "marshal",
    "pathlib",
    "glob",
    "fnmatch",
}


class TimeoutError(Exception):
    """执行超时异常"""

    pass


def execute_with_timeout(func, timeout_seconds, *args, **kwargs):
    """在子线程中执行函数，支持超时控制"""
    import queue

    result_queue = queue.Queue()
    exception_queue = queue.Queue()

    def target():
        try:
            result = func(*args, **kwargs)
            result_queue.put(result)
        except Exception as e:
            exception_queue.put(e)

    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout_seconds)

    if thread.is_alive():
        return False, None, TimeoutError(f"执行超时（{timeout_seconds}秒）")

    if not exception_queue.empty():
        return False, None, exception_queue.get()

    if result_queue.empty():
        return False, None, Exception("执行完成但未返回结果")

    return True, result_queue.get(), None


def timeout_handler(signum, frame):
    """超时信号处理（Unix系统，仅在主线程中使用）"""
    # 保留此函数以便在主线程中使用signal模块
    raise TimeoutError("代码执行超时")


class PythonCodeExecutor:
    """Python代码安全执行器"""

    def __init__(
        self,
        service,
        timeout=DEFAULT_TIMEOUT,
        max_code_length=MAX_CODE_LENGTH,
        memory_limit_mb=DEFAULT_MEMORY_LIMIT_MB,
    ):
        self.service = service
        self.timeout = timeout
        self.max_code_length = max_code_length
        self.memory_limit_mb = memory_limit_mb
        self._check_restricted_python()

    def _check_restricted_python(self):
        """检查RestrictedPython是否可用"""
        if compile_restricted is None:
            raise ImportError("RestrictedPython未安装。请运行: pip install RestrictedPython")

    def _set_memory_limit(self, memory_limit_mb: int):
        """
        设置内存限制（仅Unix系统）

        Args:
            memory_limit_mb: 内存限制（MB）

        Returns:
            (success, error_message)
        """
        if not HAS_RESOURCE:
            return False, "resource模块不可用（仅Unix系统支持）"

        try:
            # 将MB转换为字节
            memory_limit_bytes = memory_limit_mb * 1024 * 1024

            # 设置内存限制（RLIMIT_AS = 虚拟内存限制）
            # 软限制和硬限制都设置为相同值
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
            return True, ""
        except (ValueError, OSError) as e:
            return False, f"设置内存限制失败: {str(e)}"

    def _validate_code(self, code: str):
        """验证代码安全性"""
        if not code or not isinstance(code, str):
            return False, "代码不能为空"

        if len(code) > self.max_code_length:
            return False, f"代码长度超过限制（最大{self.max_code_length}字符）"

        # 检查禁止的关键字（使用更精确的匹配）
        for keyword in FORBIDDEN_KEYWORDS:
            # 使用正则表达式匹配，避免误判字符串中的内容
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, code):
                return False, f"禁止使用关键字: {keyword}"

        # 检查禁止的模块导入
        for module in FORBIDDEN_MODULES:
            if f"import {module}" in code or f"from {module}" in code:
                return False, f"禁止导入模块: {module}"

        return True, ""

    def _create_safe_builtins(self) -> Dict[str, Any]:
        """创建安全的builtins"""
        # RestrictedPython 8.1+: 使用 safe_globals 中的 __builtins__
        # 它已经包含了部分守卫函数（如 _getattr_ 等）
        if rp_safe_globals is not None and "__builtins__" in rp_safe_globals:
            # 使用 RestrictedPython 提供的完整 builtins，已包含部分守卫函数
            restricted_builtins = rp_safe_globals["__builtins__"].copy()
        elif safe_builtins is not None:
            # 降级方案：使用旧版本的 safe_builtins
            restricted_builtins = safe_builtins.copy()
        else:
            restricted_builtins = {}

        # 添加允许的安全函数
        for func_name in SAFE_BUILTINS:
            if func_name in __builtins__:
                restricted_builtins[func_name] = __builtins__[func_name]

        # 添加 RestrictedPython 必需的守卫函数
        # RestrictedPython 编译后的代码会调用这些守卫函数
        # _getiter_: 用于 for 循环，实际上就是 iter()
        if "_getiter_" not in restricted_builtins:
            restricted_builtins["_getiter_"] = iter

        # _iter_unpack_sequence_: 用于序列解包，如 for a, b in items
        # 需要从 RestrictedPython.Guards 导入
        try:
            from RestrictedPython.Guards import guarded_iter_unpack_sequence

            if "_iter_unpack_sequence_" not in restricted_builtins:
                restricted_builtins["_iter_unpack_sequence_"] = guarded_iter_unpack_sequence
        except ImportError:
            pass

        safe_builtins_dict = {
            "__name__": "__main__",
            "__builtins__": restricted_builtins,
        }
        return safe_builtins_dict

    def _create_safe_globals(self, context_vars: Dict[str, Any]) -> Dict[str, Any]:
        """创建安全的全局命名空间"""
        # 导入安全的内置模块
        import base64 as base64_module
        import collections as collections_module
        import copy as copy_module
        import datetime as datetime_module
        import decimal as decimal_module
        import fractions as fractions_module
        import functools as functools_module
        import hashlib as hashlib_module
        import hmac as hmac_module
        import itertools as itertools_module
        import json as json_module
        import math as math_module
        import statistics as statistics_module
        import string as string_module
        import textwrap as textwrap_module
        import uuid as uuid_module

        # 导入存量的第三方模块
        import jsonschema as jsonschema_module

        safe_globals_dict = {
            **self._create_safe_builtins(),
            "__builtins__": self._create_safe_builtins()["__builtins__"],
            # 数据格式
            "json_dumps": json_module.dumps,
            "json_loads": json_module.loads,
            "jsonschema_module": jsonschema_module,
            # 数学与统计
            "math": math_module,
            "statistics": statistics_module,
            "decimal": decimal_module,
            "fractions": fractions_module,
            # 日期时间
            "datetime": datetime_module,
            # 数据结构与迭代
            "collections": collections_module,
            "itertools": itertools_module,
            "functools": functools_module,
            # 字符串处理
            "string": string_module,
            "textwrap": textwrap_module,
            # 编码与哈希
            "base64": base64_module,
            "hashlib": hashlib_module,
            "hmac": hmac_module,
            "uuid": uuid_module,
            # 随机数和复制
            "copy": copy_module,
        }

        # 注入工作流上下文变量
        safe_globals_dict.update(context_vars)

        return safe_globals_dict

    def compile_code(self, code: str, timeout: int = None):
        """
        编译Python代码并返回main函数

        Args:
            code: 要编译的Python代码
            timeout: 超时时间（秒），None使用默认值

        Returns:
            (success, main_func, error_message)
        """
        # 验证代码
        is_valid, error_msg = self._validate_code(code)
        if not is_valid:
            return False, None, error_msg

        # 设置超时
        exec_timeout = timeout if timeout is not None else self.timeout

        try:
            # 编译代码
            byte_code = compile_restricted(code, filename="<inline>", mode="exec")

            # RestrictedPython 8.1: 检查返回对象是否有 errors 属性
            if hasattr(byte_code, "errors") and byte_code.errors:
                error_msgs = "\n".join(byte_code.errors)
                return False, None, f"代码编译错误: {error_msgs}"

            # 准备执行环境（不注入context_vars，因为main函数参数由用户配置）
            safe_globals = self._create_safe_globals({})
            safe_locals = {}

            # 定义编译函数
            def _compile_in_thread():
                # 重定向标准输出
                stdout_capture = StringIO()
                stderr_capture = StringIO()

                # 设置内存限制（仅Unix系统）
                old_memory_limit = None
                if HAS_RESOURCE:
                    try:
                        # 保存当前内存限制
                        old_memory_limit = resource.getrlimit(resource.RLIMIT_AS)
                        # 设置新的内存限制
                        success, error_msg = self._set_memory_limit(self.memory_limit_mb)
                        if not success:
                            self.service.logger.warning(f"无法设置内存限制: {error_msg}")
                    except Exception as e:
                        self.service.logger.warning(f"设置内存限制时出错: {e}")

                try:
                    # 重定向输出
                    old_stdout = sys.stdout
                    old_stderr = sys.stderr
                    sys.stdout = stdout_capture
                    sys.stderr = stderr_capture

                    # 执行代码（定义main函数）
                    # RestrictedPython 8.1: byte_code 可能是 code 对象本身，也可能是包装对象
                    code_to_exec = byte_code.code if hasattr(byte_code, "code") else byte_code
                    exec(code_to_exec, safe_globals, safe_locals)

                    # 恢复输出
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr

                    # 获取输出
                    stdout_output = stdout_capture.getvalue()
                    stderr_output = stderr_capture.getvalue()

                    # 查找main函数
                    if "main" not in safe_locals:
                        raise ValueError("代码中必须定义main函数")

                    main_func = safe_locals["main"]
                    if not callable(main_func):
                        raise ValueError("main必须是一个可调用的函数")

                    # 合并输出信息
                    output_info = ""
                    if stdout_output:
                        output_info += f"标准输出:\n{stdout_output}\n"
                    if stderr_output:
                        output_info += f"标准错误:\n{stderr_output}\n"

                    return main_func, output_info

                finally:
                    # 恢复内存限制
                    if HAS_RESOURCE and old_memory_limit:
                        try:
                            resource.setrlimit(resource.RLIMIT_AS, old_memory_limit)
                        except Exception as e:
                            self.service.logger.warning(f"恢复内存限制时出错: {e}")

            # 使用线程超时控制执行编译
            success, result, exception = execute_with_timeout(_compile_in_thread, exec_timeout)

            if not success:
                if isinstance(exception, TimeoutError):
                    return False, None, f"代码编译超时（{exec_timeout}秒）"
                else:
                    return False, None, f"编译错误: {str(exception)}"

            main_func, output_info = result
            return True, main_func, output_info

        except Exception as e:
            return False, None, f"执行器错误: {str(e)}"

    def execute_main(self, main_func, input_args: Dict[str, Any] = None, timeout: int = None):
        """
        执行main函数

        Args:
            main_func: main函数对象
            input_args: 输入参数字典
            timeout: 超时时间（秒），None使用默认值

        Returns:
            (success, result, error_message)
        """
        if input_args is None:
            input_args = {}

        # 设置超时
        exec_timeout = timeout if timeout is not None else self.timeout

        try:
            # 定义执行函数
            def _execute_in_thread():
                # 重定向标准输出
                stdout_capture = StringIO()
                stderr_capture = StringIO()

                # 设置内存限制（仅Unix系统）
                old_memory_limit = None
                if HAS_RESOURCE:
                    try:
                        # 保存当前内存限制
                        old_memory_limit = resource.getrlimit(resource.RLIMIT_AS)
                        # 设置新的内存限制
                        success, error_msg = self._set_memory_limit(self.memory_limit_mb)
                        if not success:
                            self.service.logger.warning(f"无法设置内存限制: {error_msg}")
                    except Exception as e:
                        self.service.logger.warning(f"设置内存限制时出错: {e}")

                try:
                    # 重定向输出
                    old_stdout = sys.stdout
                    old_stderr = sys.stderr
                    sys.stdout = stdout_capture
                    sys.stderr = stderr_capture

                    # 调用main函数
                    result = main_func(**input_args)

                    # 恢复输出
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr

                    # 获取输出
                    stdout_output = stdout_capture.getvalue()
                    stderr_output = stderr_capture.getvalue()

                    # 验证返回值 - 不做类型限制，由用户自行决定
                    # if not isinstance(result, dict):
                    #     raise ValueError("main函数必须返回一个字典")

                    # 合并输出信息
                    output_info = ""
                    if stdout_output:
                        output_info += f"标准输出:\n{stdout_output}\n"
                    if stderr_output:
                        output_info += f"标准错误:\n{stderr_output}\n"

                    return result, output_info

                finally:
                    # 恢复内存限制
                    if HAS_RESOURCE and old_memory_limit:
                        try:
                            resource.setrlimit(resource.RLIMIT_AS, old_memory_limit)
                        except Exception as e:
                            self.service.logger.warning(f"恢复内存限制时出错: {e}")

            # 使用线程超时控制执行main函数
            success, result, exception = execute_with_timeout(_execute_in_thread, exec_timeout)

            if not success:
                if isinstance(exception, MemoryError):
                    return False, None, f"内存使用超出限制（{self.memory_limit_mb}MB）"
                elif isinstance(exception, TimeoutError):
                    return False, None, f"main函数执行超时（{exec_timeout}秒）"
                else:
                    return False, None, f"执行错误: {str(exception)}"

            main_result, output_info = result
            return True, main_result, output_info

        except Exception as e:
            return False, None, f"执行器错误: {str(e)}"


class PythonCodeService(BKFlowBaseService):
    """Python代码执行服务"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executor = PythonCodeExecutor(service=self)

    def inputs_format(self):
        return [
            self.InputItem(
                name=_("Python代码"),
                key="bk_python_code",
                type="string",
                schema=StringItemSchema(description=_("请输入包含main函数的Python代码。\n" "main函数签名可以根据实际需要自定义参数。")),
            ),
            self.InputItem(
                name=_("输入变量"),
                key="bk_input_vars",
                type="object",
                schema=ObjectItemSchema(
                    property_schemas={},
                    description=_("配置main函数的输入参数。\n" "key为参数名，value为对应的值（支持变量引用）"),
                ),
            ),
        ]

    def outputs_format(self):
        return [
            self.OutputItem(
                name=_("执行结果"),
                key="output",
                type="object",
                schema=ObjectItemSchema(
                    property_schemas={},
                    description=_("main函数的返回结果"),
                ),
            ),
            self.OutputItem(
                name=_("错误信息"),
                key="error",
                type="string",
                schema=StringItemSchema(description=_("执行错误信息，正常执行时为空字符串")),
            ),
        ]

    def plugin_execute(self, data, parent_data):
        """执行Python代码"""
        # 获取输入参数
        python_code = data.get_one_of_inputs("bk_python_code")
        input_vars_config = data.get_one_of_inputs("bk_input_vars") or {}
        output_key = data.get_one_of_inputs("bk_output_key") or ""

        if not python_code:
            error_msg = "Python代码不能为空"
            self.logger.error(error_msg)
            data.outputs.ex_data = error_msg
            return False

        # 编译代码获取main函数
        try:
            success, main_func, compile_info = self.executor.compile_code(python_code)
            if not success:
                error_msg = compile_info or "代码编译失败"
                self.logger.error(f"Python代码编译失败: {error_msg}")
                data.outputs.ex_data = error_msg
                return False
        except Exception as e:
            error_msg = f"代码编译异常: {str(e)}"
            self.logger.exception(error_msg)
            data.outputs.ex_data = error_msg
            return False

        # 获取输入变量值
        input_args = {}
        if input_vars_config:
            try:
                # input_vars_config格式: {"arg1": "value1", "arg2": "${var1}", ...}
                input_args = self._get_input_args(parent_data, input_vars_config)
            except Exception as e:
                error_msg = f"获取输入变量失败: {str(e)}"
                self.logger.exception(error_msg)
                data.outputs.ex_data = error_msg
                return False

        # 记录执行信息
        self.logger.info(f"执行main函数，输入参数: {list(input_args.keys())}")

        # 执行main函数
        try:
            success, result, output_info = self.executor.execute_main(main_func, input_args=input_args)

            if success:
                # 根据output_key提取结果
                if output_key and output_key in result:
                    final_result = result[output_key]
                elif output_key:
                    error_msg = f"输出key '{output_key}' 不存在于main函数返回的字典中"
                    self.logger.error(error_msg)
                    data.set_outputs("output", {})
                    data.set_outputs("error", error_msg)
                    data.outputs.ex_data = error_msg
                    return False
                else:
                    # 如果没有指定output_key，返回整个字典
                    final_result = result

                # 设置输出：正常执行时，output为结果，error为空字符串
                data.set_outputs("output", final_result)
                data.set_outputs("error", "")
                self.logger.info(f"main函数执行成功，结果: {final_result}")
                return True
            else:
                # 执行失败：output为空字典，error为错误信息
                error_msg = output_info or "执行失败"
                self.logger.error(f"main函数执行失败: {error_msg}")
                data.set_outputs("output", {})
                data.set_outputs("error", error_msg)
                data.outputs.ex_data = error_msg
                return False

        except Exception as e:
            error_msg = f"执行器异常: {str(e)}"
            self.logger.exception(error_msg)
            data.set_outputs("output", {})
            data.set_outputs("error", error_msg)
            data.outputs.ex_data = error_msg
            return False

    def _get_input_args(self, parent_data, input_vars_config: dict) -> Dict[str, Any]:
        """获取main函数的输入参数

        Args:
            parent_data: 父数据
            input_vars_config: 输入变量配置，格式为 {"arg1": "value1", "arg2": "${var1}"}

        Returns:
            main函数的输入参数字典
        """
        runtime = BambooDjangoRuntime()
        pipeline_id = self.top_pipeline_id

        # 收集需要渲染的变量（格式为 ${var_name}）
        var_pattern = re.compile(r"\$\{(\w+)\}")
        workflow_var_keys = set()

        for value in input_vars_config.values():
            if isinstance(value, str):
                # 提取所有变量引用
                matches = var_pattern.findall(value)
                for var_name in matches:
                    workflow_var_keys.add(var_name)

        # 如果没有变量引用，直接返回配置的值
        if not workflow_var_keys:
            return input_vars_config

        try:
            # 查询上下文变量
            context_values = runtime.get_context_values(pipeline_id=pipeline_id, keys=workflow_var_keys)
        except Exception as e:
            self.logger.warning(f"获取上下文变量失败: {e}")
            return input_vars_config

        # 构建变量字典
        context_dict = {}
        for cv in context_values:
            context_dict[cv.key] = cv.value

        # 渲染变量值
        input_args = {}
        for param_key, value in input_vars_config.items():
            if isinstance(value, str) and "${" in value:
                # 替换变量引用
                rendered_value = value
                for var_name, var_value in context_dict.items():
                    var_ref = f"${{{var_name}}}"
                    if var_ref in rendered_value:
                        # 如果整个字符串就是一个变量引用，直接使用变量值（保持类型）
                        if rendered_value == var_ref:
                            rendered_value = var_value
                            break
                        # 否则进行字符串替换
                        rendered_value = rendered_value.replace(var_ref, str(var_value))
                input_args[param_key] = rendered_value
            else:
                # 非字符串或不包含变量引用，直接使用原值
                input_args[param_key] = value

        return input_args


class PythonCodeComponent(Component):
    name = _("Python代码")
    code = "python_code"
    bound_service = PythonCodeService
    form = settings.STATIC_URL + "components/python_code/v1_0_0.js"
    version = "v1.0.0"
    desc = _(
        "在受控环境中安全执行Python代码\n"
        "使用：定义main函数，通过输入变量配置映射工作流变量到main参数\n"
        "限制：禁止导入危险模块(os/sys/subprocess等)和使用eval/exec等危险函数\n\n"
        "支持内置模块：json_dumps, json_loads, math, statistics, decimal, fractions, datetime"
        ", collections, itertools, functools, string, textwrap, base64, hashlib, hmac, uuid, copy\n"
        "支持第三方模块：jsonschema\n\n"
        "示例：\n"
        "def main(arg1: str, arg2: str):\n"
        '&nbsp;&nbsp;&nbsp;&nbsp;return {"result": arg1 + arg2}'
    )
