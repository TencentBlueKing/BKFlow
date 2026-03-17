"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import copy
import enum
import logging
import random
import time
from contextlib import contextmanager
from functools import wraps

from django.conf import settings
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Span as SDKSpan
from opentelemetry.sdk.trace import SpanLimits, TracerProvider
from opentelemetry.sdk.trace.export import SpanProcessor
from opentelemetry.sdk.util.instrumentation import InstrumentationScope
from opentelemetry.trace import (
    NonRecordingSpan,
    SpanContext,
    SpanKind,
    Status,
    StatusCode,
    TraceFlags,
)

logger = logging.getLogger("root")


class _CustomSpan(SDKSpan):
    """SDKSpan subclass to bypass direct instantiation check, allowing custom span_id creation

    WARNING: 此类与 OTel SDK 的私有实现细节耦合（SDKSpan 构造函数签名、
    _active_span_processor、provider.resource 等）。SDK 小版本升级可能导致
    兼容性问题。升级 opentelemetry-sdk 时需回归测试 _create_span_with_custom_id。
    当前已有 fallback 机制：若 _CustomSpan 创建失败，end_plugin_span 会回退到
    tracer.start_span() 普通方式创建（但 span_id 将不匹配预生成值）。
    """

    pass


class CallFrom(enum.Enum):
    """调用来源"""

    WEB = "web"
    APIGW = "apigw"
    BACKEND = "backend"


class AttributeInjectionSpanProcessor(SpanProcessor):
    """Span处理器，用于在Span开始时设置属性"""

    def __init__(self, attributes):
        self.attributes = attributes

    def on_start(self, span: trace.Span, parent_context):
        if not isinstance(span, trace.Span):
            return
        for key, value in self.attributes.items():
            span.set_attribute(key, value)

    def on_end(self, span: trace.Span):
        pass

    def set_attributes(self, attributes):
        self.attributes = attributes


def propagate_attributes(attributes: dict):
    """把attributes设置到span上，并继承到后面所有span，幂等更新已存在的 SpanProcessor

    :param attributes: 默认属性
    """
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


def append_attributes(attributes: dict):
    """追加属性到span上

    :param attributes: 需要追加的属性
    """
    current_span = trace.get_current_span()
    platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
    for key, value in attributes.items():
        current_span.set_attribute(f"{platform_code}.{key}", value)


@contextmanager
def start_trace(span_name: str, propagate: bool = False, **attributes):
    """Start a trace

    :param span_name: 自定义Span名称
    :param propagate: 是否需要传播
    :param attributes: 需要跟span增加的属性, 默认为空
    :yield: 当前上下文的Span
    """
    tracer = trace.get_tracer(__name__)
    platform_code = getattr(settings, "PLATFORM_CODE", "bkflow")
    span_attributes = {f"{platform_code}.{key}": value for key, value in attributes.items()}
    if propagate:
        propagate_attributes(span_attributes)
    with tracer.start_as_current_span(span_name, kind=SpanKind.SERVER) as span:
        for attr_key, attr_value in span_attributes.items():
            span.set_attribute(attr_key, attr_value)
        yield span


def trace_view(propagate: bool = True, attr_keys=None, **default_attributes):
    """用来装饰view的trace装饰器

    :param propagate: 是否需要传播
    :param attr_keys: 需要从request和url中获取的属性
    :param default_attributes: 默认属性
    :return: view_func
    """
    attr_keys = attr_keys or []

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            attributes = copy.deepcopy(default_attributes)
            for attr_key in attr_keys:
                query_params = getattr(request, "GET", {}) or getattr(request, "query_params", {})
                query_data = getattr(request, "POST", {}) or getattr(request, "data", {})
                for scope in (kwargs, query_params, query_data):
                    if attr_key in scope:
                        attributes[attr_key] = kwargs[attr_key]
                        break
            with start_trace(view_func.__name__, propagate, **attributes):
                return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def create_execution_span(
    task_id: int,
    space_id: int,
    pipeline_instance_id: str,
    operator: str = None,
) -> tuple:
    """创建执行级根 Span，作为任务内所有插件 Span 的统一父级

    该 Span 在任务启动时创建并立即结束，其 trace_id 和 span_id 被注入 pipeline data，
    后续插件 Span 通过这些 ID 建立父子关系，保证同一任务的所有 Span 在同一条 trace 下。

    :param task_id: 任务 ID
    :param space_id: 空间 ID
    :param pipeline_instance_id: pipeline 实例 ID
    :param operator: 操作人
    :return: (trace_id_hex, span_id_hex) 元组，失败时返回 (None, None)
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
        logger.warning(f"[plugin_span] Failed to create execution span: {e}")
        return None, None


# 用于存储插件Span信息的常量key
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


def clean_plugin_span_outputs(data):
    """清理 data.outputs 中的插件 Span 内部属性，防止内部追踪数据泄露到用户可见的输出中

    :param data: 插件的 data 对象
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
    return random.getrandbits(64)


def get_current_trace_context():
    """获取当前的 trace context（trace_id 和 span_id）

    :return: 包含 trace_id 和 span_id 的字典，如果没有有效的 trace context 则返回 None
    """
    try:
        current_span = trace.get_current_span()
        if current_span is None:
            logger.debug("[trace] No current span found")
            return None

        span_context = current_span.get_span_context()
        if not span_context.is_valid:
            logger.debug("[trace] Current span context is not valid")
            return None

        trace_id = format(span_context.trace_id, "032x")
        span_id = format(span_context.span_id, "016x")

        logger.debug(f"[trace] Captured trace context: trace_id={trace_id}, span_id={span_id}")
        return {
            "trace_id": trace_id,
            "span_id": span_id,
        }
    except Exception as e:
        logger.warning(f"[trace] Failed to get current trace context: {e}")
        return None


def start_plugin_span(
    span_name: str,
    data,
    trace_id=None,
    parent_span_id=None,
    **attributes,
) -> int:
    """记录插件Span的开始时间，将相关信息保存到data outputs中，用于跨schedule调用追踪

    同时预生成 plugin_span_id 并存储，确保后续 method span 能正确作为 plugin span 的子 span。

    :param span_name: Span名称
    :param data: 插件的data对象，用于持久化span信息
    :param trace_id: 父级 trace_id（十六进制字符串）
    :param parent_span_id: 父级 span_id（十六进制字符串）
    :param attributes: Span的属性
    :return: 开始时间戳（纳秒）
    """
    start_time_ns = time.time_ns()

    # 将span信息保存到data outputs中，以便在schedule中使用
    data.set_outputs(PLUGIN_SPAN_START_TIME_KEY, start_time_ns)
    data.set_outputs(PLUGIN_SPAN_NAME_KEY, span_name)

    # 保存 trace context，用于在 end_plugin_span 时重建 parent 关系
    if trace_id:
        data.set_outputs(PLUGIN_SPAN_TRACE_ID_KEY, trace_id)
    if parent_span_id:
        data.set_outputs(PLUGIN_SPAN_PARENT_SPAN_ID_KEY, parent_span_id)

    # 预生成 plugin_span_id，用于 method span 正确嵌套为 plugin span 的子 span
    plugin_span_id = _generate_span_id()
    plugin_span_id_hex = format(plugin_span_id, "016x")
    data.set_outputs(PLUGIN_SPAN_ID_KEY, plugin_span_id_hex)

    serializable_attributes = {k: str(v) if v is not None else "" for k, v in attributes.items()}
    data.set_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY, serializable_attributes)

    return start_time_ns


def _build_parent_context(trace_id_hex, parent_span_id_hex):
    """根据保存的 trace_id 和 parent_span_id 重建 parent context

    :param trace_id_hex: trace_id 的十六进制字符串
    :param parent_span_id_hex: parent_span_id 的十六进制字符串
    :return: parent context 对象，如果无法重建则返回 None
    """
    if not trace_id_hex or not parent_span_id_hex:
        return None

    try:
        trace_id_int = int(trace_id_hex, 16)
        parent_span_id_int = int(parent_span_id_hex, 16)

        parent_span_context = SpanContext(
            trace_id=trace_id_int,
            span_id=parent_span_id_int,
            is_remote=True,
            trace_flags=TraceFlags(0x01),
        )

        if not parent_span_context.is_valid:
            logger.debug(f"[plugin_span] Invalid parent span context: trace_id={trace_id_hex}")
            return None

        parent_span = NonRecordingSpan(parent_span_context)
        parent_context = trace.set_span_in_context(parent_span)
        return parent_context

    except (ValueError, TypeError) as e:
        logger.debug(f"[plugin_span] Failed to parse trace context: {e}")
        return None


def _create_span_with_custom_id(
    span_name,
    trace_id_hex,
    span_id_hex,
    parent_span_id_hex,
    start_time_ns,
    end_time_ns,
):
    """使用预生成的 span_id 创建 Span，通过 _CustomSpan 绕过 SDK 直接实例化限制

    这样 end_plugin_span 创建的 Span 与 start_plugin_span 预生成的 plugin_span_id 一致，
    确保 method span 通过 plugin_span_id 作为 parent 能正确建立父子层级。

    :param span_name: Span 名称
    :param trace_id_hex: trace_id 十六进制字符串
    :param span_id_hex: 预生成的 span_id 十六进制字符串
    :param parent_span_id_hex: 父级 span_id 十六进制字符串
    :param start_time_ns: 开始时间（纳秒）
    :param end_time_ns: 结束时间（纳秒）
    :return: Span 对象，失败时返回 None
    """
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


def end_plugin_span(
    data,
    success: bool = True,
    error_message=None,
    end_time_ns=None,
):
    """结束插件Span，使用预生成的 plugin_span_id 创建完整的Span并立即结束

    优先使用 _create_span_with_custom_id 精确还原 span_id，若失败则 fallback 到普通方式创建。

    :param data: 插件的data对象，包含span开始时间等信息
    :param success: 插件是否执行成功
    :param error_message: 如果失败，记录的错误信息
    :param end_time_ns: 结束时间戳（纳秒），如果不提供则使用当前时间
    """
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

        # 如果 _create_span_with_custom_id 失败，fallback 到普通方式创建 span
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

        span.set_attribute(f"{platform_code}.plugin.success", success)
        if success:
            span.set_status(Status(StatusCode.OK))
        else:
            span.set_status(Status(StatusCode.ERROR, str(error_message or "Plugin execution failed")[:1000]))

        span.end(end_time=end_time_ns)

    except Exception as e:
        logger.warning(f"[plugin_span] Failed to end plugin span: {e}")


@contextmanager
def plugin_method_span(
    method_name: str,
    trace_id=None,
    parent_span_id=None,
    plugin_span_id=None,
    **attributes,
):
    """追踪 plugin_execute 和 plugin_schedule 方法的 Span 上下文管理器

    优先使用 plugin_span_id 作为 parent，确保 method span 是 plugin span 的子 span，
    而非兄弟 span。若 plugin_span_id 不可用，则 fallback 到 parent_span_id。

    :param method_name: 方法名称，如 'execute' 或 'schedule'
    :param trace_id: 父级 trace_id（十六进制字符串）
    :param parent_span_id: 父级 span_id（十六进制字符串）
    :param plugin_span_id: 插件 span_id（十六进制字符串），优先用作 parent
    :param attributes: Span 属性（space_id, task_id, node_id, plugin_name 等）
    :yield: SpanResult 对象，用于记录执行结果
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

            # 优先使用 plugin_span_id 作为 parent，确保正确的父子层级
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

            span.set_attribute(f"{platform_code}.plugin.success", result.success)
            if result.success:
                span.set_status(Status(StatusCode.OK))
            else:
                span.set_status(Status(StatusCode.ERROR, str(result.error_message or f"{method_name} failed")[:1000]))

            span.end(end_time=end_time_ns)
        except Exception as e:
            logger.warning(f"[plugin_span] Failed to create method span: {e}")
