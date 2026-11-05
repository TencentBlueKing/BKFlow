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

import base64
import builtins
import collections
import datetime
import decimal
import fractions
import json
import os
import re
import selectors
import subprocess
import sys
import time
import uuid
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from types import ModuleType
from typing import Any, Dict, Iterator, List, Optional, Tuple
from zoneinfo import ZoneInfo

import pytz

try:
    import resource

    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False

try:
    from RestrictedPython import compile_restricted, safe_builtins
    from RestrictedPython import safe_globals as rp_safe_globals
    from RestrictedPython.Guards import guarded_iter_unpack_sequence, safer_getattr

    HAS_RESTRICTED_PYTHON = True
except ImportError:
    compile_restricted = None
    guarded_iter_unpack_sequence = None
    safe_builtins = None
    rp_safe_globals = None
    safer_getattr = None
    HAS_RESTRICTED_PYTHON = False


SAFE_BUILTINS = {
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
    "format",
}

# 可按部署配置开放的模块；json 和 jsonschema 以兼容名称注入，其余模块使用原名称。
SUPPORTED_MODULES = (
    "json",
    "jsonschema",
    "math",
    "statistics",
    "decimal",
    "fractions",
    "datetime",
    "collections",
    "itertools",
    "functools",
    "string",
    "textwrap",
    "base64",
    "hashlib",
    "hmac",
    "uuid",
    "copy",
)
ALL_MODULES_FLAG = "*"

# 这些成员可以读取函数全局变量、对字符串注解求值或绕过 str.format 限制，开放模块时也不提供。
DENIED_MODULE_ATTRIBUTES = {
    "collections": {"UserString"},
    "copy": {"dispatch_table"},
    "datetime": {"datetime_CAPI"},
    "functools": {"singledispatch", "singledispatchmethod", "update_wrapper", "wraps"},
    "string": {"Formatter"},
}

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
}

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

WIRE_TYPE_KEY = "__bkflow_python_code_type__"
SURROGATE_PATTERN = re.compile("[\ud800-\udfff]")
ERROR_PHASE_COMPILE = "compile"
ERROR_PHASE_EXECUTE = "execute"
ERROR_PHASE_WAIT = "wait"
ERROR_PHASE_EXECUTOR = "executor"
EXECUTION_STARTED_MARKER = "__BKFLOW_PYTHON_CODE_MAIN_STARTED__\n"
DEFAULT_MAX_RESPONSE_SIZE_BYTES = 0
# 只恢复已知构造器，禁止通过协议导入模块或反序列化任意 callable。
DEFAULTDICT_FACTORIES = {
    "counter": collections.Counter,
    "ordered_dict": collections.OrderedDict,
    "defaultdict": collections.defaultdict,
    "deque": collections.deque,
    "decimal": decimal.Decimal,
    "fraction": fractions.Fraction,
    "timedelta": datetime.timedelta,
    "none": None,
    **{
        name: getattr(builtins, name)
        for name in (
            "bool",
            "int",
            "float",
            "complex",
            "str",
            "bytes",
            "bytearray",
            "list",
            "dict",
            "tuple",
            "set",
            "frozenset",
        )
    },
}
RESPONSE_SERIALIZATION_MEMORY_ERROR_PAYLOAD = json.dumps(
    {
        "success": False,
        "result": None,
        "message": "执行器错误: 子进程响应序列化内存不足",
        "error_phase": ERROR_PHASE_EXECUTOR,
        "warnings": [],
    },
    ensure_ascii=False,
    separators=(",", ":"),
).encode("utf-8")


class WireCodecError(ValueError):
    """父子进程受控数据协议编解码失败。"""


class UnsupportedDefaultdictFactory(WireCodecError):
    """需要由整个输出的旧存储方式决定是否允许工厂降级。"""


@dataclass(frozen=True)
class PythonCodeExecutionResult:
    """Python 代码执行结果及结构化错误阶段。"""

    success: bool
    result: Any
    message: str
    error_phase: Optional[str] = None

    def __iter__(self) -> Iterator[Any]:
        """兼容原有三元组解包方式。"""
        yield self.success
        yield self.result
        yield self.message


def _wire_tag(value_type: str, *values: Any) -> Dict[str, Any]:
    """构造不会和普通用户字典冲突的类型标记。"""
    return {WIRE_TYPE_KEY: [value_type, *values]}


def _encode_timezone(tz: Optional[datetime.tzinfo]) -> Any:
    """只传递已知时区的标识和参数，保留名称及夏令时规则。"""
    if tz is None:
        return None
    if isinstance(tz, datetime.timezone):
        return ["fixed", _encode_wire_value(tz.utcoffset(None)), _encode_wire_value(tz.tzname(None))]
    if isinstance(tz, ZoneInfo) and tz.key is not None:
        return ["zoneinfo", tz.key]
    if isinstance(tz, pytz.tzinfo.BaseTzInfo):
        # pytz 的已定位时区还需要保存当前时差，time 对象本身没有日期可供重新定位。
        return [
            "pytz",
            tz.zone,
            _encode_wire_value(tz._utcoffset),
            _encode_wire_value(getattr(tz, "_dst", datetime.timedelta(0))),
            _encode_wire_value(tz._tzname),
        ]
    if isinstance(tz, type(pytz.FixedOffset(1))):
        return ["pytz_fixed", int(tz.utcoffset(None).total_seconds() // 60)]
    raise WireCodecError(f"不支持的时区类型: {type(tz).__name__}")


def _decode_timezone(payload: Any) -> Optional[datetime.tzinfo]:
    """从固定白名单恢复时区，不加载任意类或 callable。"""
    if payload is None:
        return None
    kind, *values = payload
    if kind == "fixed":
        return datetime.timezone(_decode_wire_value(values[0]), _decode_wire_value(values[1]))
    if kind == "zoneinfo":
        return ZoneInfo(values[0])
    if kind == "pytz_fixed":
        return pytz.FixedOffset(values[0])
    if kind == "pytz":
        tz = pytz.timezone(values[0])
        if isinstance(tz, pytz.tzinfo.DstTzInfo):
            key = (_decode_wire_value(values[1]), _decode_wire_value(values[2]), _decode_wire_value(values[3]))
            return tz._tzinfos[key]
        return tz
    raise WireCodecError(f"不支持的时区标记: {kind}")


def _can_store_as_json(value: Any) -> bool:
    """未知工厂仅在旧引擎本就会 JSON 降级时回退，避免构造完整 JSON 副本。"""
    try:
        for _ in json.JSONEncoder().iterencode(value):
            pass
    except (TypeError, ValueError):
        return False
    return True


def _encode_wire_value(value: Any, seen: Optional[set] = None, allow_defaultdict_fallback: bool = False) -> Any:
    """将受支持的 Python 值编码为无歧义的 JSON 数据节点。"""
    if seen is None and allow_defaultdict_fallback:
        try:
            return _encode_wire_value(value)
        except UnsupportedDefaultdictFactory:
            if not _can_store_as_json(value):
                raise
    seen = seen if seen is not None else set()

    if value is None or type(value) in {bool, int, float}:
        return value
    if type(value) is str:
        if SURROGATE_PATTERN.search(value):
            return _wire_tag("str", base64.b64encode(value.encode("utf-8", errors="surrogatepass")).decode("ascii"))
        return value
    if isinstance(value, complex):
        return _wire_tag("complex", value.real, value.imag)
    if isinstance(value, datetime.datetime):
        return _wire_tag("datetime", value.isoformat(), value.fold, _encode_timezone(value.tzinfo))
    if isinstance(value, datetime.date):
        return _wire_tag("date", value.isoformat())
    if isinstance(value, datetime.time):
        return _wire_tag("time", value.isoformat(), value.fold, _encode_timezone(value.tzinfo))
    if isinstance(value, datetime.timedelta):
        return _wire_tag("timedelta", value.days, value.seconds, value.microseconds)
    if isinstance(value, decimal.Decimal):
        return _wire_tag("decimal", str(value))
    if isinstance(value, fractions.Fraction):
        return _wire_tag("fraction", value.numerator, value.denominator)
    if isinstance(value, uuid.UUID):
        return _wire_tag("uuid", str(value))
    if isinstance(value, bytes):
        return _wire_tag("bytes", base64.b64encode(value).decode("ascii"))
    if isinstance(value, bytearray):
        return _wire_tag("bytearray", base64.b64encode(value).decode("ascii"))
    if isinstance(value, range):
        return _wire_tag("range", value.start, value.stop, value.step)

    container_types = (dict, list, tuple, set, frozenset, collections.deque)
    if isinstance(value, container_types):
        value_id = id(value)
        if value_id in seen:
            raise WireCodecError("不支持循环引用的数据结构")
        seen.add(value_id)
        try:
            if isinstance(value, dict):
                if isinstance(value, (collections.Counter, collections.OrderedDict, collections.defaultdict)):
                    items = [
                        [
                            _encode_wire_value(key, seen, allow_defaultdict_fallback),
                            _encode_wire_value(item, seen, allow_defaultdict_fallback),
                        ]
                        for key, item in value.items()
                    ]
                    if isinstance(value, collections.Counter):
                        return _wire_tag("counter", items)
                    if isinstance(value, collections.OrderedDict):
                        return _wire_tag("ordered_dict", items)
                    for name, factory in DEFAULTDICT_FACTORIES.items():
                        if value.default_factory is factory:
                            return _wire_tag("defaultdict", name, items)
                    if allow_defaultdict_fallback:
                        return _wire_tag("dict", items)
                    raise UnsupportedDefaultdictFactory("不支持的 defaultdict default_factory")
                if all(type(key) is str and not SURROGATE_PATTERN.search(key) for key in value) and not (
                    len(value) == 1 and WIRE_TYPE_KEY in value
                ):
                    return {
                        key: _encode_wire_value(item, seen, allow_defaultdict_fallback) for key, item in value.items()
                    }
                items = [
                    [
                        _encode_wire_value(key, seen, allow_defaultdict_fallback),
                        _encode_wire_value(item, seen, allow_defaultdict_fallback),
                    ]
                    for key, item in value.items()
                ]
                return _wire_tag("dict", items)

            if isinstance(value, list):
                return [_encode_wire_value(item, seen, allow_defaultdict_fallback) for item in value]

            items = [_encode_wire_value(item, seen, allow_defaultdict_fallback) for item in value]
            if isinstance(value, tuple):
                return _wire_tag("tuple", items)
            if isinstance(value, set):
                return _wire_tag("set", items)
            if isinstance(value, frozenset):
                return _wire_tag("frozenset", items)
            return _wire_tag("deque", items, value.maxlen)
        finally:
            seen.remove(value_id)

    raise WireCodecError(f"不支持的数据类型: {type(value).__name__}")


def _decode_wire_value(node: Any) -> Any:
    """从父子进程 JSON 协议恢复受支持的 Python 值。"""
    if node is None or type(node) in {bool, int, float, str}:
        return node
    if isinstance(node, list):
        return [_decode_wire_value(item) for item in node]
    if not isinstance(node, dict):
        raise WireCodecError("数据节点格式无效")

    if len(node) != 1 or WIRE_TYPE_KEY not in node:
        return {key: _decode_wire_value(value) for key, value in node.items()}

    type_payload = node[WIRE_TYPE_KEY]
    if not isinstance(type_payload, list) or not type_payload or not isinstance(type_payload[0], str):
        raise WireCodecError("类型标记格式无效")

    value_type, *values = type_payload
    if value_type == "str":
        return base64.b64decode(values[0]).decode("utf-8", errors="surrogatepass")
    if value_type == "complex":
        return complex(values[0], values[1])
    if value_type == "datetime":
        value = datetime.datetime.fromisoformat(values[0]).replace(fold=values[1])
        return value.replace(tzinfo=_decode_timezone(values[2])) if len(values) > 2 else value
    if value_type == "date":
        return datetime.date.fromisoformat(values[0])
    if value_type == "time":
        value = datetime.time.fromisoformat(values[0]).replace(fold=values[1])
        return value.replace(tzinfo=_decode_timezone(values[2])) if len(values) > 2 else value
    if value_type == "timedelta":
        return datetime.timedelta(days=values[0], seconds=values[1], microseconds=values[2])
    if value_type == "decimal":
        return decimal.Decimal(values[0])
    if value_type == "fraction":
        return fractions.Fraction(values[0], values[1])
    if value_type == "uuid":
        return uuid.UUID(values[0])
    if value_type == "bytes":
        return base64.b64decode(values[0].encode("ascii"))
    if value_type == "bytearray":
        return bytearray(base64.b64decode(values[0].encode("ascii")))
    if value_type == "range":
        return range(values[0], values[1], values[2])
    if value_type == "dict":
        return {_decode_wire_value(key): _decode_wire_value(value) for key, value in values[0]}
    if value_type in {"counter", "ordered_dict"}:
        items = [(_decode_wire_value(key), _decode_wire_value(value)) for key, value in values[0]]
        return collections.Counter(dict(items)) if value_type == "counter" else collections.OrderedDict(items)
    if value_type == "defaultdict":
        if values[0] not in DEFAULTDICT_FACTORIES:
            raise WireCodecError("不支持的 defaultdict default_factory")
        items = {_decode_wire_value(key): _decode_wire_value(value) for key, value in values[1]}
        return collections.defaultdict(DEFAULTDICT_FACTORIES[values[0]], items)
    if value_type in {"tuple", "set", "frozenset"}:
        items = [_decode_wire_value(item) for item in values[0]]
        return {"tuple": tuple, "set": set, "frozenset": frozenset}[value_type](items)
    if value_type == "deque":
        return collections.deque((_decode_wire_value(item) for item in values[0]), maxlen=values[1])

    raise WireCodecError(f"未知的数据类型标记: {value_type}")


def _validate_code(code: str, max_code_length: int) -> Tuple[bool, str]:
    """验证用户代码的长度和禁用关键字。"""
    if not code or not isinstance(code, str):
        return False, "代码不能为空"

    if len(code) > max_code_length:
        return False, f"代码长度超过限制（最大{max_code_length}字符）"

    for keyword in FORBIDDEN_KEYWORDS:
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, code):
            return False, f"禁止使用关键字: {keyword}"

    for module in FORBIDDEN_MODULES:
        if f"import {module}" in code or f"from {module}" in code:
            return False, f"禁止导入模块: {module}"

    return True, ""


def _create_safe_builtins() -> Dict[str, Any]:
    """创建 RestrictedPython 执行所需的安全 builtins。"""
    if rp_safe_globals is not None and "__builtins__" in rp_safe_globals:
        restricted_builtins = rp_safe_globals["__builtins__"].copy()
    elif safe_builtins is not None:
        restricted_builtins = safe_builtins.copy()
    else:
        restricted_builtins = {}

    for func_name in SAFE_BUILTINS:
        if hasattr(builtins, func_name):
            restricted_builtins[func_name] = getattr(builtins, func_name)

    if "_getiter_" not in restricted_builtins:
        restricted_builtins["_getiter_"] = iter

    if guarded_iter_unpack_sequence is not None and "_iter_unpack_sequence_" not in restricted_builtins:
        restricted_builtins["_iter_unpack_sequence_"] = guarded_iter_unpack_sequence
    if safer_getattr is not None:
        restricted_builtins["_getattr_"] = _safe_getattr

    return {
        "__name__": "__main__",
        "__builtins__": restricted_builtins,
    }


def _safe_getattr(obj: Any, name: str, *args: Any) -> Any:
    """在 RestrictedPython 属性守卫上禁止取回模块、解释器或进程能力。"""
    if isinstance(obj, ModuleType):
        # 模块只提供显式复制的成员，不回退到默认值，以便用户看到明确的禁用提示。
        try:
            raw_value = object.__getattribute__(obj, name)
        except AttributeError as error:
            raise AttributeError(f"禁止访问模块属性: {name}") from error
        if isinstance(raw_value, ModuleType):
            raise AttributeError(f"禁止访问模块属性: {name}")
    value = safer_getattr(obj, name, *args)
    if isinstance(value, ModuleType):
        raise AttributeError(f"禁止访问模块属性: {name}")
    return value


def _safe_module(name: str, source: ModuleType) -> ModuleType:
    """复制模块的公开成员，去掉子模块和可读取解释器状态的成员。"""
    safe_module = ModuleType(name)
    public_names = getattr(source, "__all__", None)
    if public_names is None:
        public_names = [attribute_name for attribute_name in dir(source) if not attribute_name.startswith("_")]
    denied_names = DENIED_MODULE_ATTRIBUTES.get(name, set())
    for attribute_name in public_names:
        if attribute_name in denied_names or not hasattr(source, attribute_name):
            continue
        value = getattr(source, attribute_name)
        if isinstance(value, ModuleType):
            continue
        setattr(safe_module, attribute_name, value)
    return safe_module


def _normalize_allowed_modules(allowed_modules: Optional[List[str]]) -> Tuple[List[str], List[str]]:
    """按支持顺序返回开放模块，并单独返回无法识别的名称。"""
    requested = {str(item).strip() for item in (allowed_modules or []) if str(item).strip()}
    if ALL_MODULES_FLAG in requested:
        return list(SUPPORTED_MODULES), sorted(requested - set(SUPPORTED_MODULES) - {ALL_MODULES_FLAG})
    return [name for name in SUPPORTED_MODULES if name in requested], sorted(requested - set(SUPPORTED_MODULES))


def _create_jsonschema_module() -> ModuleType:
    """只提供不访问远程引用的校验入口和异常类型。"""
    import jsonschema
    import referencing

    jsonschema_module = ModuleType("jsonschema")

    def validate(instance, schema, cls=None, *args, **kwargs):
        """与旧 jsonschema 一致，未声明版本时使用 Draft 4；只解析内置元 schema 和当前文档内引用。"""
        if args:
            raise TypeError("validate() 只支持 instance、schema、cls 三个位置参数")
        # 引用解析器由执行器固定，不接受用户传入的 resolver 或内部参数。
        for key in [key for key in kwargs if key == "resolver" or key.startswith("_")]:
            kwargs.pop(key)
        # 空注册表会与内置元 schema 合并，远程或文件 $ref 无法解析时直接失败，不发起请求。
        kwargs["registry"] = referencing.Registry()
        if cls is None:
            cls = jsonschema.validators.validator_for(schema, default=jsonschema.Draft4Validator)
        return jsonschema.validate(instance, schema, cls, **kwargs)

    jsonschema_module.validate = validate
    jsonschema_module.ValidationError = jsonschema.ValidationError
    jsonschema_module.SchemaError = jsonschema.SchemaError
    return jsonschema_module


def _create_safe_globals(allowed_modules: Optional[List[str]] = None) -> Dict[str, Any]:
    """创建用户代码可使用的全局命名空间，只导入部署配置开放的模块。"""
    import importlib

    module_names, _ = _normalize_allowed_modules(allowed_modules)
    safe_builtins_dict = _create_safe_builtins()
    safe_globals = {
        **safe_builtins_dict,
        "__builtins__": safe_builtins_dict["__builtins__"],
    }
    for module_name in module_names:
        if module_name == "json":
            import json as json_module

            safe_globals["json_dumps"] = json_module.dumps
            safe_globals["json_loads"] = json_module.loads
        elif module_name == "jsonschema":
            safe_globals["jsonschema_module"] = _create_jsonschema_module()
        else:
            safe_globals[module_name] = _safe_module(module_name, importlib.import_module(module_name))
    return safe_globals


def _set_memory_limit(memory_limit_mb: int) -> Tuple[bool, str]:
    """在当前子进程内设置虚拟地址空间限制。

    硬限制降低后普通进程无法恢复，因此此函数只能在执行后立即退出的子进程中调用。
    """
    if not HAS_RESOURCE:
        return False, "resource模块不可用（仅Unix系统支持）"

    try:
        memory_limit_bytes = memory_limit_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
        return True, ""
    except (ValueError, OSError) as e:
        return False, f"设置内存限制失败: {str(e)}"


def _set_resource_limits() -> List[str]:
    """在执行子进程内限制可创建进程和可打开文件数量。"""
    warnings = []
    if not HAS_RESOURCE:
        return warnings
    # macOS 把当前进程计入 RLIMIT_NPROC，限制值至少要保留 worker 自身。
    for limit_name, limit_value in (("RLIMIT_NPROC", 2), ("RLIMIT_NOFILE", 64)):
        limit = getattr(resource, limit_name, None)
        if limit is None:
            continue
        try:
            resource.setrlimit(limit, (limit_value, limit_value))
        except (ValueError, OSError) as e:
            warnings.append(f"无法设置{limit_name}: {str(e)}")
    return warnings


def _format_output(stdout_capture: StringIO, stderr_capture: StringIO) -> str:
    """合并用户代码的标准输出和标准错误。"""
    output_info = ""
    if stdout_capture.getvalue():
        output_info += f"标准输出:\n{stdout_capture.getvalue()}\n"
    if stderr_capture.getvalue():
        output_info += f"标准错误:\n{stderr_capture.getvalue()}\n"
    return output_info


def _failure(message: str, error_phase: str, warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    """构造子进程失败响应。"""
    return {
        "success": False,
        "result": None,
        "message": message,
        "error_phase": error_phase,
        "warnings": warnings or [],
    }


def _execute_code_in_current_process(request: Dict[str, Any], apply_limits: bool = False) -> Dict[str, Any]:
    """在独立子进程内完成代码校验、编译和执行。

    资源限制无法在当前进程内恢复，只有执行完即退出的 worker 子进程才开启 apply_limits。
    """
    code = request.get("code")
    input_args = _decode_wire_value(request["input_args"])
    max_code_length = request["max_code_length"]
    memory_limit_mb = request["memory_limit_mb"]

    is_valid, error_message = _validate_code(code, max_code_length)
    if not is_valid:
        return _failure(error_message, ERROR_PHASE_COMPILE)

    if not HAS_RESTRICTED_PYTHON:
        return _failure("RestrictedPython未安装。请运行: pip install RestrictedPython", ERROR_PHASE_EXECUTOR)

    safe_globals = _create_safe_globals(request.get("allowed_modules"))
    safe_locals: Dict[str, Any] = {}
    warnings = []
    if apply_limits:
        memory_limit_success, memory_limit_error = _set_memory_limit(memory_limit_mb)
        if not memory_limit_success:
            warnings.append(f"无法设置内存限制: {memory_limit_error}")
        warnings.extend(_set_resource_limits())

    stdout_capture = StringIO()
    stderr_capture = StringIO()

    try:
        byte_code = compile_restricted(code, filename="<inline>", mode="exec")
    except Exception as e:
        return _failure(f"执行器错误: {str(e)}", ERROR_PHASE_COMPILE, warnings)

    if hasattr(byte_code, "errors") and byte_code.errors:
        error_messages = "\n".join(byte_code.errors)
        return _failure(f"代码编译错误: {error_messages}", ERROR_PHASE_COMPILE, warnings)

    try:
        code_to_execute = byte_code.code if hasattr(byte_code, "code") else byte_code
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            exec(code_to_execute, safe_globals, safe_locals)
    except Exception as e:
        return _failure(f"编译错误: {str(e)}", ERROR_PHASE_COMPILE, warnings)

    if "main" not in safe_locals:
        return _failure("编译错误: 代码中必须定义main函数", ERROR_PHASE_COMPILE, warnings)

    main_func = safe_locals["main"]
    if not callable(main_func):
        return _failure("编译错误: main必须是一个可调用的函数", ERROR_PHASE_COMPILE, warnings)

    try:
        sys.__stderr__.write(EXECUTION_STARTED_MARKER)
        sys.__stderr__.flush()
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            result = main_func(**input_args)
    except MemoryError:
        return _failure(f"内存使用超出限制（{memory_limit_mb}MB）", ERROR_PHASE_EXECUTE, warnings)
    except Exception as e:
        return _failure(f"执行错误: {str(e)}", ERROR_PHASE_EXECUTE, warnings)

    try:
        output_key = _decode_wire_value(request.get("output_key", ""))
        if output_key:
            if output_key not in result:
                return _failure(f"输出key '{output_key}' 不存在于main函数返回的字典中", ERROR_PHASE_EXECUTE, warnings)
            result = result[output_key]
        encoded_result = _encode_wire_value(result, allow_defaultdict_fallback=True)
    except MemoryError:
        return _failure(f"内存使用超出限制（{memory_limit_mb}MB）", ERROR_PHASE_EXECUTE, warnings)
    except WireCodecError as e:
        return _failure(f"执行错误: main函数返回值无法序列化: {str(e)}", ERROR_PHASE_EXECUTE, warnings)
    except Exception as e:
        return _failure(f"执行错误: 输出结果处理失败: {str(e)}", ERROR_PHASE_EXECUTE, warnings)

    return {
        "success": True,
        "result": encoded_result,
        "message": _format_output(stdout_capture, stderr_capture),
        "error_phase": None,
        "warnings": warnings,
    }


def _write_response(response: Dict[str, Any], max_response_size_bytes: int) -> None:
    """将结构化响应写入协议标准输出。"""
    try:
        payload = json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8", errors="backslashreplace"
        )
        payload_size = len(payload)
        if max_response_size_bytes > 0 and payload_size > max_response_size_bytes:
            payload = json.dumps(
                _failure(
                    f"执行错误: main函数返回结果跨进程编码后超过限制（实际{payload_size}字节，" f"最大{max_response_size_bytes}字节）",
                    ERROR_PHASE_EXECUTE,
                    response.get("warnings"),
                ),
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
    except MemoryError:
        payload = RESPONSE_SERIALIZATION_MEMORY_ERROR_PAYLOAD
    sys.__stdout__.buffer.write(payload)
    sys.__stdout__.buffer.flush()


def _worker_timezone() -> str:
    """保持 datetime.now() 的本地时区与 er-e 进程一致。"""
    timezone_name = os.environ.get("TZ", "")
    if timezone_name:
        return timezone_name
    try:
        from django.conf import settings

        return getattr(settings, "TIME_ZONE", "") or ""
    except Exception:
        return ""


def _build_worker_env() -> Dict[str, str]:
    """构造用户代码子进程的最小环境。"""
    worker_env = {
        "PATH": os.environ.get("PATH", ""),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
    }
    timezone_name = _worker_timezone()
    if timezone_name:
        worker_env["TZ"] = timezone_name
    return worker_env


def _run_subprocess_worker() -> None:
    """读取父进程请求并执行 Python 代码。"""
    max_response_size_bytes = DEFAULT_MAX_RESPONSE_SIZE_BYTES
    try:
        request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        max_response_size_bytes = request["max_response_size_bytes"]
        response = _execute_code_in_current_process(request, apply_limits=True)
    except Exception as e:
        response = _failure(f"执行器错误: 子进程执行异常: {str(e)}", ERROR_PHASE_EXECUTOR)
    _write_response(response, max_response_size_bytes)


class PythonCodeExecutor:
    """Python代码子进程执行器。"""

    def __init__(
        self,
        service,
        timeout: int = 30,
        max_code_length: int = 10240,
        memory_limit_mb: int = 256,
        max_response_size_bytes: int = DEFAULT_MAX_RESPONSE_SIZE_BYTES,
        process_semaphore=None,
        queue_timeout: Optional[float] = None,
        allowed_modules: Optional[List[str]] = None,
    ):
        self.service = service
        self.allowed_modules, self.unsupported_modules = _normalize_allowed_modules(allowed_modules)
        self.timeout = timeout
        self.max_code_length = max_code_length
        self.memory_limit_mb = memory_limit_mb
        self.max_response_size_bytes = max(0, max_response_size_bytes)
        self.process_semaphore = process_semaphore
        self.queue_timeout = queue_timeout
        if not HAS_RESTRICTED_PYTHON:
            raise ImportError("RestrictedPython未安装。请运行: pip install RestrictedPython")

    def execute_code(
        self,
        code: str,
        input_args: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        output_key: str = "",
    ) -> PythonCodeExecutionResult:
        """在独立子进程内执行 Python 代码。"""
        is_valid, error_message = _validate_code(code, self.max_code_length)
        if not is_valid:
            return PythonCodeExecutionResult(False, None, error_message, ERROR_PHASE_COMPILE)
        if self.unsupported_modules:
            self.service.logger.warning(
                "PYTHON_CODE_PLUGIN_ALLOWED_MODULES 包含不支持的模块，已忽略: %s", ", ".join(self.unsupported_modules)
            )

        exec_timeout = timeout if timeout is not None else self.timeout
        queue_timeout = self.queue_timeout if self.queue_timeout is not None else exec_timeout
        semaphore_acquired = False
        if self.process_semaphore is not None:
            semaphore_acquired = self.process_semaphore.acquire(timeout=queue_timeout)
            if not semaphore_acquired:
                return PythonCodeExecutionResult(False, None, f"Python代码执行等待超时（{queue_timeout}秒）", ERROR_PHASE_WAIT)

        try:
            # 排队单独限时；获取名额后开始计算输入编码、启动和编译的准备期限。
            deadline = time.monotonic() + exec_timeout
            try:
                request = {
                    "code": code,
                    "input_args": _encode_wire_value(input_args or {}),
                    "max_code_length": self.max_code_length,
                    "memory_limit_mb": self.memory_limit_mb,
                    "max_response_size_bytes": self.max_response_size_bytes,
                    "output_key": _encode_wire_value(output_key),
                    "allowed_modules": self.allowed_modules,
                }
                input_payload = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode(
                    "utf-8", errors="backslashreplace"
                )
                del request
            except MemoryError:
                return PythonCodeExecutionResult(
                    False,
                    None,
                    "执行器错误: 输入参数序列化内存不足",
                    ERROR_PHASE_EXECUTOR,
                )
            except (TypeError, ValueError, WireCodecError) as e:
                return PythonCodeExecutionResult(
                    False,
                    None,
                    f"执行器错误: 输入参数无法序列化: {str(e)}",
                    ERROR_PHASE_EXECUTOR,
                )

            remaining_timeout = deadline - time.monotonic()
            if remaining_timeout <= 0:
                return PythonCodeExecutionResult(
                    False,
                    None,
                    f"Python代码执行等待超时（{exec_timeout}秒）",
                    ERROR_PHASE_WAIT,
                )

            # er-e 使用线程池，不在 preexec_fn 内执行 Python 逻辑；资源限制由新解释器自行设置。
            # 子进程只继承运行所需的环境变量，不把密钥和数据库配置交给用户代码。
            process = subprocess.Popen(
                [sys.executable, "-I", os.path.abspath(__file__), "--worker"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                env=_build_worker_env(),
                close_fds=True,
                start_new_session=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                stdout, stderr = self._communicate(process, input_payload, deadline, exec_timeout)
            except subprocess.TimeoutExpired as e:
                process.kill()
                process.wait()
                main_started = EXECUTION_STARTED_MARKER.encode("utf-8") in (e.stderr or b"")
                error_phase = ERROR_PHASE_EXECUTE if main_started else ERROR_PHASE_WAIT
                error_message = f"main函数执行超时（{exec_timeout}秒）" if main_started else f"Python代码执行等待超时（{exec_timeout}秒）"
                return PythonCodeExecutionResult(False, None, error_message, error_phase)
            except BaseException:
                process.kill()
                process.wait()
                raise
            if process.returncode != 0:
                error_detail = stderr.decode("utf-8", errors="replace").replace(EXECUTION_STARTED_MARKER, "").strip()
                error_suffix = f": {error_detail[:500]}" if error_detail else ""
                return PythonCodeExecutionResult(
                    False,
                    None,
                    f"执行器错误: 子进程异常退出（{process.returncode}）{error_suffix}",
                    ERROR_PHASE_EXECUTOR,
                )

            try:
                response = json.loads(stdout.decode("utf-8"))
            except MemoryError:
                return PythonCodeExecutionResult(False, None, "执行器错误: 子进程返回结果解析内存不足", ERROR_PHASE_EXECUTOR)
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                return PythonCodeExecutionResult(False, None, f"执行器错误: 无法解析子进程返回结果: {str(e)}", ERROR_PHASE_EXECUTOR)

            for warning in response.get("warnings", []):
                self.service.logger.warning(warning)

            result = response.get("result")
            if response["success"]:
                try:
                    result = _decode_wire_value(result)
                except MemoryError:
                    return PythonCodeExecutionResult(
                        False,
                        None,
                        "执行器错误: 子进程返回结果解析内存不足",
                        ERROR_PHASE_EXECUTOR,
                    )
                except Exception as e:
                    return PythonCodeExecutionResult(False, None, f"执行器错误: 无法解析子进程返回结果: {str(e)}", ERROR_PHASE_EXECUTOR)

            return PythonCodeExecutionResult(
                response["success"], result, response.get("message", ""), response.get("error_phase")
            )
        finally:
            if semaphore_acquired:
                self.process_semaphore.release()

    def _communicate(self, process, input_payload: bytes, deadline: float, exec_timeout: float) -> Tuple[bytes, bytes]:
        """在 Linux/macOS 上同时读写管道，并在 main 开始时切换执行期限。

        Python 3.9 的 communicate 超时重试可能停止发送未完成的 stdin，故使用非阻塞管道。
        """
        main_started = False
        marker = EXECUTION_STARTED_MARKER.encode("utf-8")
        marker_tail = b""
        stdout_chunks, stderr_chunks = [], []
        streams = (process.stdin, process.stdout, process.stderr)
        try:
            with selectors.DefaultSelector() as selector, memoryview(input_payload) as input_view:
                input_offset = 0
                for stream in streams:
                    os.set_blocking(stream.fileno(), False)
                    selector.register(
                        stream, selectors.EVENT_WRITE if stream is process.stdin else selectors.EVENT_READ
                    )

                while selector.get_map():
                    remaining_timeout = deadline - time.monotonic()
                    if remaining_timeout <= 0:
                        raise subprocess.TimeoutExpired(process.args, exec_timeout)
                    for key, _ in selector.select(remaining_timeout):
                        stream = key.fileobj
                        if stream is process.stdin:
                            try:
                                input_offset += os.write(key.fd, input_view[input_offset : input_offset + 65536])
                            except BlockingIOError:
                                continue
                            except BrokenPipeError:
                                selector.unregister(stream)
                                stream.close()
                                continue
                            if input_offset == len(input_view):
                                selector.unregister(stream)
                                stream.close()
                            continue

                        try:
                            chunk = os.read(key.fd, 65536)
                        except BlockingIOError:
                            continue
                        if not chunk:
                            selector.unregister(stream)
                            stream.close()
                            continue
                        if stream is process.stdout:
                            stdout_chunks.append(chunk)
                        else:
                            stderr_chunks.append(chunk)
                            if not main_started:
                                marker_tail += chunk
                                if marker in marker_tail:
                                    main_started = True
                                    deadline = time.monotonic() + exec_timeout
                                marker_tail = marker_tail[-len(marker) :]

                process.wait(timeout=max(0, deadline - time.monotonic()))
            return b"".join(stdout_chunks), b"".join(stderr_chunks)
        except subprocess.TimeoutExpired as e:
            e.stderr = marker if main_started else b""
            raise
        finally:
            for stream in streams:
                stream.close()


if __name__ == "__main__" and "--worker" in sys.argv:
    _run_subprocess_worker()
