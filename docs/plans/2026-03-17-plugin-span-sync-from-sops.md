# Plugin Span 增强同步 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 从 bk-sops 同步 plugin span 的 6 项增强到 bk-flow，修复 span 层级、增加 execution span、清理输出、精简属性。

**Architecture:** 分 3 个 Phase（trace.py → base.py → operations.py），每个 Phase 对应一个 commit。trace.py 是核心工具层，base.py 是插件基类适配层，operations.py 是任务启动适配层。

**Tech Stack:** Python, OpenTelemetry SDK, Django, bamboo_engine (Pipeline)

**Design Doc:** `docs/plans/2026-03-17-plugin-span-sync-from-sops-design.md`

---

## Task 1: Phase 1 — trace.py 核心能力增强

**Files:**
- Modify: `bkflow/utils/trace.py`
- Modify: `tests/engine/utils/test_trace.py`

### Step 1: 更新 imports 和新增 `_CustomSpan`

在 `bkflow/utils/trace.py` 顶部增加必要的 import 并新增 `_CustomSpan` 类。

新增 import（在已有 import 区域添加）：
```python
import random
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Span as SDKSpan, SpanLimits
from opentelemetry.sdk.util.instrumentation import InstrumentationScope
```

在 `CallFrom` 类之前新增：
```python
class _CustomSpan(SDKSpan):
    """SDKSpan 子类，用于绕过 __new__ 中的直接实例化检查，允许使用自定义 span_id 创建 Span"""
    pass
```

### Step 2: 给 `AttributeInjectionSpanProcessor` 新增 `set_attributes()` 方法

在现有 `on_end` 方法之后新增：
```python
def set_attributes(self, attributes):
    self.attributes = attributes
```

### Step 3: 更新 `propagate_attributes()` 增加幂等检测

将现有函数体替换为：
```python
def propagate_attributes(attributes: dict):
    """把attributes设置到span上，并继承到后面所有span"""
    provider = trace.get_tracer_provider()

    if not provider or isinstance(provider, trace.ProxyTracerProvider):
        provider = TracerProvider()
        trace.set_tracer_provider(provider)

    inject_attributes = False
    for sp in getattr(provider._active_span_processor, "_span_processors", []):
        if isinstance(sp, AttributeInjectionSpanProcessor):
            inject_attributes = True
            sp.set_attributes(attributes)
            break

    if not inject_attributes:
        provider.add_span_processor(AttributeInjectionSpanProcessor(attributes))
```

### Step 4: 新增 `create_execution_span()`

在 `trace_view` 函数之后、现有常量之前，添加分隔注释和新函数：
```python
# ==================== Execution Span 相关功能 ====================


def create_execution_span(
    task_id: int,
    space_id: int,
    pipeline_instance_id: str,
    operator: str = None,
) -> tuple:
    """
    创建 execution span 作为所有插件 span 的根 span

    :param task_id: 任务 ID
    :param space_id: 空间 ID
    :param pipeline_instance_id: Pipeline 实例 ID
    :param operator: 操作员
    :return: (trace_id_hex, span_id_hex) 元组，如果创建失败则返回 (None, None)
    """
    if not settings.ENABLE_OTEL_TRACE:
        return None, None

    try:
        tracer = trace.get_tracer(__name__)
        platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
        span_name = f"{platform_code}.execution"

        current_span = trace.get_current_span()
        parent_context = None
        if current_span and current_span.get_span_context().is_valid:
            parent_context = trace.set_span_in_context(current_span)

        start_time_ns = time.time_ns()
        span = tracer.start_span(
            name=span_name,
            context=parent_context,
            start_time=start_time_ns,
            kind=SpanKind.INTERNAL,
        )

        span.set_attribute(f"{platform_code}.task_id", str(task_id))
        span.set_attribute(f"{platform_code}.space_id", str(space_id))
        span.set_attribute(f"{platform_code}.pipeline_instance_id", str(pipeline_instance_id))
        if operator is not None:
            span.set_attribute(f"{platform_code}.operator", str(operator))

        span_context = span.get_span_context()
        trace_id_hex = format(span_context.trace_id, "032x")
        span_id_hex = format(span_context.span_id, "016x")

        span.set_status(Status(StatusCode.OK))
        span.end()

        return trace_id_hex, span_id_hex

    except Exception as e:
        logger.debug(f"[plugin_span] Failed to create execution span: {e}")
        return None, None
```

### Step 5: 更新常量区域

将现有常量替换为完整版本（增加 `PLUGIN_SPAN_ID_KEY`、`PLUGIN_SPAN_ENDED_KEY`、`PLUGIN_SCHEDULE_COUNT_KEY`、`PLUGIN_SPAN_OUTPUT_KEYS`）：

```python
# ==================== Plugin Span 相关功能 ====================

# Span 信息在 data.outputs 中的 key
PLUGIN_SPAN_START_TIME_KEY = "_plugin_span_start_time_ns"
PLUGIN_SPAN_NAME_KEY = "_plugin_span_name"
PLUGIN_SPAN_TRACE_ID_KEY = "_plugin_span_trace_id"
PLUGIN_SPAN_PARENT_SPAN_ID_KEY = "_plugin_span_parent_span_id"
PLUGIN_SPAN_ID_KEY = "_plugin_span_id"
PLUGIN_SPAN_ATTRIBUTES_KEY = "_plugin_span_attributes"
PLUGIN_SPAN_ENDED_KEY = "_plugin_span_ended"
PLUGIN_SCHEDULE_COUNT_KEY = "_plugin_schedule_count"

PLUGIN_SPAN_OUTPUT_KEYS = [
    PLUGIN_SPAN_START_TIME_KEY,
    PLUGIN_SPAN_NAME_KEY,
    PLUGIN_SPAN_TRACE_ID_KEY,
    PLUGIN_SPAN_PARENT_SPAN_ID_KEY,
    PLUGIN_SPAN_ID_KEY,
    PLUGIN_SPAN_ATTRIBUTES_KEY,
    PLUGIN_SPAN_ENDED_KEY,
    PLUGIN_SCHEDULE_COUNT_KEY,
]
```

### Step 6: 新增 `clean_plugin_span_outputs()` 和 `_generate_span_id()`

在常量之后、`get_current_trace_context` 之前添加：
```python
def clean_plugin_span_outputs(data):
    """
    清理 data.outputs 中所有 span 相关的内部属性。
    在 plugin span 结束后调用，避免这些内部属性污染用户可见的任务输出。
    """
    try:
        outputs = getattr(data, "outputs", None)
        if outputs is None:
            return
        for key in PLUGIN_SPAN_OUTPUT_KEYS:
            outputs.pop(key, None)
    except Exception as e:
        logger.debug(f"[plugin_span] Failed to clean plugin span outputs: {e}")


def _generate_span_id() -> int:
    """生成一个 64 位的随机 span_id"""
    return random.getrandbits(64)
```

### Step 7: 更新 `start_plugin_span()`

在现有函数中增加预生成 `plugin_span_id` 的逻辑。替换整个函数为：
```python
def start_plugin_span(
    span_name: str,
    data,
    trace_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    **attributes,
) -> int:
    """
    记录插件 Span 的开始信息，将相关信息保存到 data outputs 中，用于跨 schedule 调用追踪。
    同时预先生成 plugin span 的 span_id，用于作为 execute/schedule 方法 span 的父 span。
    """
    start_time_ns = time.time_ns()

    data.set_outputs(PLUGIN_SPAN_START_TIME_KEY, start_time_ns)
    data.set_outputs(PLUGIN_SPAN_NAME_KEY, span_name)

    if trace_id:
        data.set_outputs(PLUGIN_SPAN_TRACE_ID_KEY, trace_id)
    if parent_span_id:
        data.set_outputs(PLUGIN_SPAN_PARENT_SPAN_ID_KEY, parent_span_id)

    plugin_span_id = _generate_span_id()
    plugin_span_id_hex = format(plugin_span_id, "016x")
    data.set_outputs(PLUGIN_SPAN_ID_KEY, plugin_span_id_hex)

    serializable_attributes = {k: str(v) if v is not None else "" for k, v in attributes.items()}
    data.set_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY, serializable_attributes)

    return start_time_ns
```

### Step 8: 新增 `_create_span_with_custom_id()`

在 `_build_parent_context` 之后添加：
```python
def _create_span_with_custom_id(
    span_name: str,
    trace_id_hex: Optional[str],
    span_id_hex: Optional[str],
    parent_span_id_hex: Optional[str],
    start_time_ns: int,
    end_time_ns: int,
):
    """使用自定义的 span_id 创建 span，确保 execute/schedule method span 能正确指向 plugin span 作为父 span"""
    if not trace_id_hex or not span_id_hex:
        return None

    try:
        trace_id_int = int(trace_id_hex, 16)
        span_id_int = int(span_id_hex, 16)
        parent_span_id_int = int(parent_span_id_hex, 16) if parent_span_id_hex else 0

        span_context = SpanContext(
            trace_id=trace_id_int,
            span_id=span_id_int,
            is_remote=False,
            trace_flags=TraceFlags(0x01),
        )

        if not span_context.is_valid:
            return None

        parent_span_context = None
        if parent_span_id_int:
            parent_span_context = SpanContext(
                trace_id=trace_id_int,
                span_id=parent_span_id_int,
                is_remote=True,
                trace_flags=TraceFlags(0x01),
            )

        provider = trace.get_tracer_provider()
        span_processor = None
        resource = Resource.create({})
        if hasattr(provider, "_active_span_processor"):
            span_processor = provider._active_span_processor
        if hasattr(provider, "resource"):
            resource = provider.resource

        instrumentation_scope = InstrumentationScope(name=__name__, version="")

        span = _CustomSpan(
            name=span_name,
            context=span_context,
            parent=parent_span_context,
            resource=resource,
            attributes=None,
            events=None,
            links=None,
            kind=SpanKind.CLIENT,
            span_processor=span_processor,
            limits=SpanLimits(),
            instrumentation_scope=instrumentation_scope,
            record_exception=True,
            set_status_on_exception=True,
        )

        span.start(start_time=start_time_ns)
        return span

    except Exception as e:
        logger.debug(f"[plugin_span] Failed to create span with custom id: {e}")
        return None
```

### Step 9: 更新 `end_plugin_span()`

替换整个函数为：
```python
def end_plugin_span(
    data,
    success: bool = True,
    error_message: Optional[str] = None,
    end_time_ns: Optional[int] = None,
):
    """结束插件 Span，创建完整的 Span 并立即结束。使用预生成的 span_id 确保正确的层级关系。"""
    if not settings.ENABLE_OTEL_TRACE:
        return

    try:
        start_time_ns = data.get_one_of_outputs(PLUGIN_SPAN_START_TIME_KEY)
        span_name = data.get_one_of_outputs(PLUGIN_SPAN_NAME_KEY)
        attributes = data.get_one_of_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY) or {}
        trace_id_hex = data.get_one_of_outputs(PLUGIN_SPAN_TRACE_ID_KEY)
        parent_span_id_hex = data.get_one_of_outputs(PLUGIN_SPAN_PARENT_SPAN_ID_KEY)
        plugin_span_id_hex = data.get_one_of_outputs(PLUGIN_SPAN_ID_KEY)

        if not start_time_ns or not span_name:
            return

        if end_time_ns is None:
            end_time_ns = time.time_ns()

        platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")

        span = _create_span_with_custom_id(
            span_name=span_name,
            trace_id_hex=trace_id_hex,
            span_id_hex=plugin_span_id_hex,
            parent_span_id_hex=parent_span_id_hex,
            start_time_ns=start_time_ns,
            end_time_ns=end_time_ns,
        )

        if span is None:
            tracer = trace.get_tracer(__name__)
            parent_context = _build_parent_context(trace_id_hex, parent_span_id_hex)
            span = tracer.start_span(
                name=span_name,
                context=parent_context,
                start_time=start_time_ns,
                kind=SpanKind.CLIENT,
            )

        for key, value in attributes.items():
            span.set_attribute(f"{platform_code}.plugin.{key}", value)

        if success:
            span.set_status(Status(StatusCode.OK))
        else:
            span.set_status(Status(StatusCode.ERROR, error_message or "Plugin execution failed"))

        span.end(end_time=end_time_ns)

    except Exception as e:
        logger.debug(f"[plugin_span] Failed to end plugin span: {e}")
```

### Step 10: 更新 `plugin_method_span()`

替换整个函数为：
```python
@contextmanager
def plugin_method_span(
    method_name: str,
    trace_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    plugin_span_id: Optional[str] = None,
    **attributes,
):
    """
    追踪 plugin_execute 和 plugin_schedule 方法的 Span 上下文管理器

    :param plugin_span_id: 预生成的 plugin span ID，作为首选父 span
    """
    if not settings.ENABLE_OTEL_TRACE:
        yield None
        return

    start_time_ns = time.time_ns()

    plugin_name = attributes.get("plugin_name", "unknown")

    platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
    span_name = f"{platform_code}.plugin.{plugin_name}.{method_name}"

    class SpanResult:
        def __init__(self):
            self.success = True
            self.error_message = None

        def set_error(self, message: str):
            self.success = False
            self.error_message = message

    result = SpanResult()

    try:
        yield result
    finally:
        try:
            end_time_ns = time.time_ns()
            tracer = trace.get_tracer(__name__)

            actual_parent_span_id = plugin_span_id if plugin_span_id else parent_span_id
            parent_context = _build_parent_context(trace_id, actual_parent_span_id)

            span = tracer.start_span(
                name=span_name,
                context=parent_context,
                start_time=start_time_ns,
                kind=SpanKind.INTERNAL,
            )

            span.set_attribute(f"{platform_code}.plugin.method", method_name)
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(f"{platform_code}.plugin.{key}", str(value))

            if result.success:
                span.set_status(Status(StatusCode.OK))
            else:
                span.set_status(Status(StatusCode.ERROR, result.error_message or f"{method_name} failed"))

            span.end(end_time=end_time_ns)
        except Exception as e:
            logger.debug(f"[plugin_span] Failed to create method span: {e}")
```

### Step 11: 更新 tests/engine/utils/test_trace.py

为新增的函数编写测试，更新已有测试以覆盖新行为。需测试：
- `create_execution_span` 正常和异常路径
- `_generate_span_id` 生成有效 64 位整数
- `_create_span_with_custom_id` 正常和回退路径
- `clean_plugin_span_outputs` 清理行为
- `start_plugin_span` 预生成 `plugin_span_id`
- `end_plugin_span` 使用自定义 span_id
- `plugin_method_span` 使用 `plugin_span_id` 作为父 span
- `plugin_method_span` disabled-trace 时 yield None
- `propagate_attributes` 幂等行为

Run: `cd /root/Projects/bk-flow && python -m pytest tests/engine/utils/test_trace.py -v`
Expected: ALL PASS

### Step 12: Commit Phase 1

```bash
git add bkflow/utils/trace.py tests/engine/utils/test_trace.py
git commit -m "refactor(trace): 从bk-sops同步plugin span核心能力增强 --story=<TAPD_ID>"
```

---

## Task 2: Phase 2 — base.py 插件基类适配

**Files:**
- Modify: `bkflow/pipeline_plugins/components/collections/base.py`
- Modify: `tests/engine/task/test_bkflow_base_plugin_service.py`

### Step 1: 更新 imports

替换现有导入为：
```python
from bkflow.utils.trace import (
    PLUGIN_SPAN_ENDED_KEY,
    PLUGIN_SPAN_ID_KEY,
    PLUGIN_SCHEDULE_COUNT_KEY,
    clean_plugin_span_outputs,
    end_plugin_span,
    plugin_method_span,
    start_plugin_span,
)
```

删除文件中原有的 `PLUGIN_SPAN_ENDED_KEY` 和 `PLUGIN_SCHEDULE_COUNT_KEY` 常量定义。

### Step 2: 更新 `_get_span_name()`

```python
def _get_span_name(self):
    platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
    return f"{platform_code}.plugin.{self.plugin_name}"
```

### Step 3: 更新 `_get_trace_context()` 签名

```python
def _get_trace_context(self, data, parent_data):
    return {
        "trace_id": parent_data.get_one_of_inputs("_trace_id"),
        "parent_span_id": parent_data.get_one_of_inputs("_parent_span_id"),
        "plugin_span_id": data.get_one_of_outputs(PLUGIN_SPAN_ID_KEY),
    }
```

### Step 4: 更新 `_end_plugin_span()` 增加输出清理

```python
def _end_plugin_span(self, data, success, error_message=None):
    if not self.enable_plugin_span or not settings.ENABLE_OTEL_TRACE:
        return
    if data.get_one_of_outputs(PLUGIN_SPAN_ENDED_KEY, False):
        return
    end_plugin_span(data, success=success, error_message=error_message)
    clean_plugin_span_outputs(data)
```

### Step 5: 更新 `execute()` 方法

关键变更：`_get_trace_context` 传入 `data`，`plugin_method_span` 传入 `plugin_span_id`：

```python
def execute(self, data, parent_data):
    if parent_data.get_one_of_inputs("is_mock") and self.is_mock_node(
        parent_data.get_one_of_inputs("task_id"), self.id
    ):
        return self.mock_execute(data, parent_data)

    self._start_plugin_span(data, parent_data)

    trace_context = self._get_trace_context(data, parent_data)
    method_attrs = self._get_method_span_attributes(data, parent_data)
    if self.enable_plugin_span and settings.ENABLE_OTEL_TRACE:
        data.set_outputs(PLUGIN_SCHEDULE_COUNT_KEY, 0)
        with plugin_method_span(
            method_name="execute",
            trace_id=trace_context.get("trace_id"),
            parent_span_id=trace_context.get("parent_span_id"),
            plugin_span_id=trace_context.get("plugin_span_id"),
            **method_attrs,
        ) as span_result:
            result = self.plugin_execute(data, parent_data)
            if not result:
                span_result.set_error(self._get_error_message(data))
    else:
        result = self.plugin_execute(data, parent_data)

    if not result:
        self._end_plugin_span(data, success=False, error_message=self._get_error_message(data))
    elif not self.need_schedule():
        self._end_plugin_span(data, success=True)

    return result
```

### Step 6: 更新 `schedule()` 方法

同样传入 `data` 和 `plugin_span_id`：

```python
def schedule(self, data, parent_data, callback_data=None):
    if parent_data.get_one_of_inputs("is_mock") and self.is_mock_node(
        parent_data.get_one_of_inputs("task_id"), self.id
    ):
        return self.mock_schedule(data, parent_data)

    trace_context = self._get_trace_context(data, parent_data)
    method_attrs = self._get_method_span_attributes(data, parent_data)
    if self.enable_plugin_span and settings.ENABLE_OTEL_TRACE:
        schedule_count = data.get_one_of_outputs(PLUGIN_SCHEDULE_COUNT_KEY, 0) + 1
        data.set_outputs(PLUGIN_SCHEDULE_COUNT_KEY, schedule_count)
        method_attrs["schedule_count"] = schedule_count
        with plugin_method_span(
            method_name="schedule",
            trace_id=trace_context.get("trace_id"),
            parent_span_id=trace_context.get("parent_span_id"),
            plugin_span_id=trace_context.get("plugin_span_id"),
            **method_attrs,
        ) as span_result:
            result = self.plugin_schedule(data, parent_data, callback_data)
            if not result:
                span_result.set_error(self._get_error_message(data))
    else:
        result = self.plugin_schedule(data, parent_data, callback_data)

    if not result:
        self._end_plugin_span(data, success=False, error_message=self._get_error_message(data))
    elif self.is_schedule_finished():
        self._end_plugin_span(data, success=True)

    return result
```

### Step 7: 更新测试

更新 `tests/engine/task/test_bkflow_base_plugin_service.py` 以覆盖：
- `_get_trace_context` 新签名（返回 `plugin_span_id`）
- `_end_plugin_span` 调用 `clean_plugin_span_outputs`
- `execute`/`schedule` 传入 `plugin_span_id`
- Span 名称新格式 `{platform}.plugin.{name}`

Run: `cd /root/Projects/bk-flow && python -m pytest tests/engine/task/test_bkflow_base_plugin_service.py -v`
Expected: ALL PASS

### Step 8: Commit Phase 2

```bash
git add bkflow/pipeline_plugins/components/collections/base.py tests/engine/task/test_bkflow_base_plugin_service.py
git commit -m "refactor(plugin): 适配plugin span层级修复和输出清理 --story=<TAPD_ID>"
```

---

## Task 3: Phase 3 — operations.py 任务启动适配

**Files:**
- Modify: `bkflow/task/operations.py`
- Modify: `tests/engine/task/test_task_operations.py`

### Step 1: 更新 imports

```python
from bkflow.utils.trace import create_execution_span, start_trace
```

移除 `get_current_trace_context` 的导入（不再需要）。

### Step 2: 更新 `trace_task_operation` 装饰器

移除 `_external_trace_context` 相关逻辑：

```python
def trace_task_operation(operation_name: str, operation_type: str = "task"):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if not settings.ENABLE_OTEL_TRACE:
                return func(self, *args, **kwargs)

            platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
            span_name = f"{platform_code}.{operation_type}.{operation_name}"

            attributes = {
                "task_id": getattr(self.task_instance, "id", None),
                "space_id": getattr(self.task_instance, "space_id", None),
                "operator": kwargs.get("operator") or (args[0] if args else None),
            }

            if operation_type == "task_node" and hasattr(self, "node_id"):
                attributes["node_id"] = self.node_id

            with start_trace(span_name=span_name, propagate=False, **attributes):
                return func(self, *args, **kwargs)

        return wrapper
    return decorator
```

### Step 3: 更新 `TaskOperation.start()` 中的 trace context 注入

将现有的 `_external_trace_context` 逻辑替换为 `create_execution_span()`：

```python
# 替换原来的 trace context 注入代码块为：
if settings.ENABLE_OTEL_TRACE:
    try:
        trace_id, execution_span_id = create_execution_span(
            task_id=self.task_instance.id,
            space_id=self.task_instance.space_id,
            pipeline_instance_id=self.task_instance.instance_id,
            operator=operator,
        )
        if trace_id and execution_span_id:
            root_pipeline_data["_trace_id"] = trace_id
            root_pipeline_data["_parent_span_id"] = execution_span_id
    except Exception as e:
        logger.debug(f"[plugin_span] Failed to create execution span: {e}")
```

### Step 4: 更新测试

更新 `tests/engine/task/test_task_operations.py` 以覆盖：
- `start()` 使用 `create_execution_span` 而非 `_external_trace_context`
- `trace_task_operation` 不再传递 `_external_trace_context`

Run: `cd /root/Projects/bk-flow && python -m pytest tests/engine/task/test_task_operations.py -v`
Expected: ALL PASS

### Step 5: 运行完整测试

Run: `cd /root/Projects/bk-flow && python -m pytest tests/engine/ -v`
Expected: ALL PASS

### Step 6: Commit Phase 3

```bash
git add bkflow/task/operations.py tests/engine/task/test_task_operations.py
git commit -m "refactor(task): 使用create_execution_span替换直接trace context注入 --story=<TAPD_ID>"
```

---

## Task 4: 验证与收尾

### Step 1: 运行完整测试套件

Run: `cd /root/Projects/bk-flow && python -m pytest tests/ -v --timeout=60`
Expected: ALL PASS

### Step 2: 检查 linter

Run: `cd /root/Projects/bk-flow && flake8 bkflow/utils/trace.py bkflow/pipeline_plugins/components/collections/base.py bkflow/task/operations.py`
Expected: No errors (or only pre-existing warnings)
