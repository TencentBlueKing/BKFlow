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
import time
from contextlib import contextmanager
from functools import wraps
from typing import Dict, Optional

from django.conf import settings
from opentelemetry import baggage, trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.context import attach, detach, get_current
from opentelemetry.propagate import get_global_textmap, set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.trace.export import SpanProcessor
from opentelemetry.trace import (
    NonRecordingSpan,
    SpanContext,
    SpanKind,
    Status,
    StatusCode,
    TraceFlags,
)
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger("root")


class CallFrom(enum.Enum):
    """调用来源"""

    WEB = "web"
    APIGW = "apigw"
    BACKEND = "backend"


# ============ Baggage 相关常量 ============
BAGGAGE_PREFIX = f"{settings.PLATFORM_CODE}."  # baggage key 前缀，避免冲突


def setup_propagators():
    """设置全局的 propagator 和 SpanProcessor，确保 baggage 能够跨服务传播

    应该在应用启动时调用（如 Django AppConfig.ready() 或 celery worker 启动时）
    """
    import logging

    logger = logging.getLogger("root")

    # 1. 设置 propagator，支持 W3C Trace Context 和 Baggage
    propagator = CompositePropagator(
        [
            TraceContextTextMapPropagator(),  # W3C Trace Context (traceparent, tracestate)
            W3CBaggagePropagator(),  # W3C Baggage
        ]
    )
    set_global_textmap(propagator)
    logger.info("[setup_propagators] Global textmap propagator set")

    # 2. 注册 BaggageToSpanProcessor，确保每个 span 自动从 baggage 中获取属性
    provider = trace.get_tracer_provider()
    logger.info(f"[setup_propagators] Current tracer provider: {type(provider).__name__}")

    if provider is None:
        logger.warning("[setup_propagators] No tracer provider found, skipping BaggageToSpanProcessor registration")
        return

    if isinstance(provider, trace.ProxyTracerProvider):
        logger.warning(
            "[setup_propagators] Provider is ProxyTracerProvider, BaggageToSpanProcessor will not be registered. "
            "Make sure OpenTelemetry is properly initialized before calling setup_propagators()."
        )
        return

    # 检查是否已经注册过 BaggageToSpanProcessor
    already_registered = False
    for sp in getattr(provider._active_span_processor, "_span_processors", []):
        if isinstance(sp, BaggageToSpanProcessor):
            already_registered = True
            break

    if already_registered:
        logger.info("[setup_propagators] BaggageToSpanProcessor already registered")
    else:
        provider.add_span_processor(BaggageToSpanProcessor())
        logger.info("[setup_propagators] BaggageToSpanProcessor registered successfully")


def set_baggage_attributes(attributes: Dict[str, str]) -> object:
    """将属性设置到 baggage 中，这些属性会随 trace context 跨服务传播

    :param attributes: 需要传播的属性字典
    :return: context token，用于后续 detach
    """
    ctx = get_current()
    for key, value in attributes.items():
        # 添加前缀避免 key 冲突，同时移除已有的 platform code 前缀避免重复
        clean_key = key
        platform_prefix = f"{settings.PLATFORM_CODE}."
        if clean_key.startswith(platform_prefix):
            clean_key = clean_key[len(platform_prefix) :]
        baggage_key = f"{BAGGAGE_PREFIX}{clean_key}"
        ctx = baggage.set_baggage(baggage_key, str(value), context=ctx)
    return attach(ctx)


def get_baggage_attributes() -> Dict[str, str]:
    """从当前 context 中获取 bkflow 相关的 baggage 属性

    :return: 属性字典
    """
    result = {}
    all_baggage = baggage.get_all()
    for key, value in all_baggage.items():
        if key.startswith(BAGGAGE_PREFIX):
            # 移除前缀，恢复原始 key
            original_key = key[len(BAGGAGE_PREFIX) :]
            result[original_key] = value
    return result


def inject_baggage_to_span(span: trace.Span):
    """将 baggage 中的属性注入到 span 的 attributes 中

    :param span: 当前 span
    """
    if span is None or not hasattr(span, "set_attribute"):
        return

    attrs = get_baggage_attributes()
    for key, value in attrs.items():
        span.set_attribute(f"{settings.PLATFORM_CODE}.{key}", value)


class BaggageToSpanProcessor(SpanProcessor):
    """Span 处理器，在 Span 开始时自动将 baggage 中的属性设置到 span 上"""

    def on_start(self, span: trace.Span, parent_context):
        inject_baggage_to_span(span)

    def on_end(self, span: trace.Span):
        pass

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 30000):
        return True


# ============ HTTP 请求工具函数 ============
def inject_trace_headers(headers: Optional[dict] = None) -> dict:
    """在发送 HTTP 请求前，注入 trace context 和 baggage 到 headers 中

    使用示例:
        headers = inject_trace_headers()
        response = requests.get(url, headers=headers)

    :param headers: 已有的 headers，如果为 None 则创建新的
    :return: 包含 trace context 和 baggage 的 headers
    """
    if headers is None:
        headers = {}

    propagator = get_global_textmap()
    propagator.inject(headers)
    return headers


def extract_trace_context(carrier: dict):
    """从 HTTP headers 中提取 trace context 和 baggage

    使用示例（在 view 或中间件中）:
        ctx = extract_trace_context(request.META)
        token = attach(ctx)
        try:
            # 处理请求...
        finally:
            detach(token)

    :param carrier: HTTP headers（Django 中是 request.META）
    :return: context 对象
    """
    propagator = get_global_textmap()
    # Django 的 META 使用 HTTP_ 前缀，需要转换
    normalized_carrier = {}
    for key, value in carrier.items():
        if key.startswith("HTTP_"):
            # 转换 HTTP_TRACEPARENT -> traceparent
            normalized_key = key[5:].lower().replace("_", "-")
            normalized_carrier[normalized_key] = value

    return propagator.extract(normalized_carrier)


# ============ Celery 工具函数 ============
def inject_trace_to_celery_headers(headers: Optional[dict] = None) -> dict:
    """在调度 Celery 任务时，注入 trace context 和 baggage 到 task headers 中

    使用示例:
        task.apply_async(
            args=[...],
            headers=inject_trace_to_celery_headers()
        )

    :param headers: 已有的 headers
    :return: 包含 trace context 和 baggage 的 headers
    """
    if headers is None:
        headers = {}

    propagator = get_global_textmap()
    propagator.inject(headers)
    return headers


def extract_trace_from_celery(task_headers: dict):
    """从 Celery task headers 中提取 trace context 和 baggage

    :param task_headers: Celery task 的 headers
    :return: context 对象
    """
    propagator = get_global_textmap()
    return propagator.extract(task_headers or {})


# ============ 原有函数的改进版本 ============
def propagate_attributes(attributes: dict):
    """把 attributes 设置到 baggage 中，实现跨服务传播

    属性会通过 BaggageToSpanProcessor 自动设置到每个新创建的 span 上，
    同时也会通过 HTTP headers 和 Celery task headers 跨服务传播。

    :param attributes: 需要传播的属性
    """
    set_baggage_attributes(attributes)


def append_attributes(attributes: dict):
    """追加属性到span上

    :param attributes: 需要追加的属性
    """
    current_span = trace.get_current_span()
    for key, value in attributes.items():
        current_span.set_attribute(f"{settings.PLATFORM_CODE}.{key}", value)


@contextmanager
def start_trace(span_name: str, propagate: bool = False, **attributes):
    """Start a trace

    :param span_name: 自定义Span名称
    :param propagate: 是否需要传播（通过 baggage 跨服务传播）
    :param attributes: 需要跟span增加的属性, 默认为空
    :yield: 当前上下文的Span
    """
    tracer = trace.get_tracer(__name__)

    span_attributes = {f"{settings.PLATFORM_CODE}.{key}": value for key, value in attributes.items()}

    # 设置需要传播的属性到 baggage 中
    if propagate:
        propagate_attributes(span_attributes)

    with tracer.start_as_current_span(span_name, kind=SpanKind.SERVER) as span:
        # 从 baggage 中恢复属性到 span（处理跨服务传播的情况）
        # 注：即使 BaggageToSpanProcessor 已注册，这里也手动调用以确保兼容性
        inject_baggage_to_span(span)

        # 手动设置本次传入的属性到当前 span
        for attr_key, attr_value in span_attributes.items():
            span.set_attribute(attr_key, attr_value)

        yield span


def trace_view(propagate: bool = True, attr_keys=None, **default_attributes):
    """用来装饰view的trace装饰器

    :param propagate: 是否需要传播（通过 baggage 跨服务传播）
    :param attr_keys: 需要从request和url中获取的属性
    :param default_attributes: 默认属性
    :return: view_func
    """
    attr_keys = attr_keys or []

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # 先从请求中提取 trace context 和 baggage
            ctx = extract_trace_context(request.META)
            token = attach(ctx)

            try:
                attributes = copy.deepcopy(default_attributes)

                for attr_key in attr_keys:
                    # 需要的属性只要在kwargs, request.GET, request.query_params(drf), request.POST, request.data(drf)中就可以
                    query_params = getattr(request, "GET", {}) or getattr(request, "query_params", {})
                    query_data = getattr(request, "POST", {}) or getattr(request, "data", {})
                    for scope in (kwargs, query_params, query_data):
                        if attr_key in scope:
                            attributes[attr_key] = scope[attr_key]
                            break

                with start_trace(view_func.__name__, propagate, **attributes):
                    return view_func(request, *args, **kwargs)
            finally:
                detach(token)

        return _wrapped_view

    return decorator


# 用于存储插件Span信息的常量key
PLUGIN_SPAN_START_TIME_KEY = "_plugin_span_start_time_ns"
PLUGIN_SPAN_NAME_KEY = "_plugin_span_name"
PLUGIN_SPAN_ATTRIBUTES_KEY = "_plugin_span_attributes"
PLUGIN_SPAN_TRACE_ID_KEY = "_plugin_span_trace_id"
PLUGIN_SPAN_PARENT_SPAN_ID_KEY = "_plugin_span_parent_span_id"


def get_current_trace_context() -> Optional[dict]:
    """
    获取当前的 trace context（trace_id 和 span_id）

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

        # 将 trace_id 和 span_id 转换为十六进制字符串
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
    trace_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    **attributes,
) -> int:
    """
    记录插件Span的开始时间，将相关信息保存到data outputs中，用于跨schedule调用追踪

    :param span_name: Span名称
    :param data: 插件的data对象，用于持久化span信息
    :param trace_id: 父级 trace_id（十六进制字符串），用于关联到 start_task 的 trace
    :param parent_span_id: 父级 span_id（十六进制字符串），用于建立父子关系
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

    # 确保属性值可以序列化
    serializable_attributes = {k: str(v) if v is not None else "" for k, v in attributes.items()}
    data.set_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY, serializable_attributes)

    # 日志记录
    trace_info = ""
    if trace_id:
        trace_info = f", trace_id={trace_id}"
        if parent_span_id:
            trace_info += f", parent_span_id={parent_span_id}"
    logger.info(f"[plugin_span] Started span '{span_name}' at {start_time_ns}{trace_info}")

    return start_time_ns


def _build_parent_context(trace_id_hex: Optional[str], parent_span_id_hex: Optional[str]):
    """
    根据保存的 trace_id 和 parent_span_id 重建 parent context

    :param trace_id_hex: trace_id 的十六进制字符串
    :param parent_span_id_hex: parent_span_id 的十六进制字符串
    :return: parent context 对象，如果无法重建则返回 None
    """
    if not trace_id_hex or not parent_span_id_hex:
        return None

    try:
        # 将十六进制字符串转换为整数
        trace_id_int = int(trace_id_hex, 16)
        parent_span_id_int = int(parent_span_id_hex, 16)

        # 创建 SpanContext
        parent_span_context = SpanContext(
            trace_id=trace_id_int,
            span_id=parent_span_id_int,
            is_remote=True,
            trace_flags=TraceFlags(0x01),  # SAMPLED
        )

        if not parent_span_context.is_valid:
            logger.warning(
                f"[plugin_span] Invalid parent span context: trace_id={trace_id_hex}, span_id={parent_span_id_hex}"
            )
            return None

        # 使用 NonRecordingSpan 包装 SpanContext，然后设置到 context 中
        parent_span = NonRecordingSpan(parent_span_context)
        parent_context = trace.set_span_in_context(parent_span)
        return parent_context

    except (ValueError, TypeError) as e:
        logger.warning(f"[plugin_span] Failed to parse trace context: {e}")
        return None


def end_plugin_span(
    data,
    success: bool = True,
    error_message: Optional[str] = None,
    end_time_ns: Optional[int] = None,
):
    """
    结束插件Span，创建一个完整的Span并立即结束

    :param data: 插件的data对象，包含span开始时间等信息
    :param success: 插件是否执行成功
    :param error_message: 如果失败，记录的错误信息
    :param end_time_ns: 结束时间戳（纳秒），如果不提供则使用当前时间
    """
    # 获取 span 信息
    start_time_ns = data.get_one_of_outputs(PLUGIN_SPAN_START_TIME_KEY)
    span_name = data.get_one_of_outputs(PLUGIN_SPAN_NAME_KEY)
    attributes = data.get_one_of_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY) or {}
    trace_id_hex = data.get_one_of_outputs(PLUGIN_SPAN_TRACE_ID_KEY)
    parent_span_id_hex = data.get_one_of_outputs(PLUGIN_SPAN_PARENT_SPAN_ID_KEY)

    # 提取关键属性用于日志
    space_id = attributes.get("space_id", "unknown")
    task_id = attributes.get("task_id", "unknown")
    node_id = attributes.get("node_id", "unknown")

    if not start_time_ns or not span_name:
        # 没有找到span开始信息，可能是旧数据或异常情况
        logger.warning(
            f"[plugin_span] No span start info found, skipping span end. "
            f"space_id={space_id}, task_id={task_id}, node_id={node_id}"
        )
        return

    if end_time_ns is None:
        end_time_ns = time.time_ns()

    # 计算耗时
    duration_ms = (end_time_ns - start_time_ns) / 1_000_000

    tracer = trace.get_tracer(__name__)

    try:
        # 尝试重建 parent context
        parent_context = _build_parent_context(trace_id_hex, parent_span_id_hex)

        # 创建 span，如果有 parent context 则使用
        span = tracer.start_span(
            name=span_name,
            context=parent_context,  # 如果为 None，则创建新的 trace
            start_time=start_time_ns,
            kind=SpanKind.CLIENT,
        )

        # 获取实际的 span context 用于日志
        span_context = span.get_span_context()
        actual_trace_id = format(span_context.trace_id, "032x") if span_context.is_valid else "invalid"
        actual_span_id = format(span_context.span_id, "016x") if span_context.is_valid else "invalid"

        # 设置属性
        for key, value in attributes.items():
            span.set_attribute(f"bk_flow.plugin.{key}", value)

        # 设置执行结果状态
        if success:
            span.set_status(Status(StatusCode.OK))
            span.set_attribute("bk_flow.plugin.success", True)
        else:
            span.set_status(Status(StatusCode.ERROR, error_message or "Plugin execution failed"))
            span.set_attribute("bk_flow.plugin.success", False)
            if error_message:
                span.set_attribute("bk_flow.plugin.error", str(error_message)[:1000])

        # 记录耗时
        span.set_attribute("bk_flow.plugin.duration_ms", duration_ms)

        # 记录 trace 关联信息
        span.set_attribute("bk_flow.plugin.has_parent_trace", parent_context is not None)
        if trace_id_hex:
            span.set_attribute("bk_flow.plugin.parent_trace_id", trace_id_hex)
        if parent_span_id_hex:
            span.set_attribute("bk_flow.plugin.parent_span_id", parent_span_id_hex)

        # 手动结束span，设置结束时间
        span.end(end_time=end_time_ns)

        # 完善的日志输出
        parent_info = ""
        if trace_id_hex:
            parent_info = f", parent_trace_id={trace_id_hex}, parent_span_id={parent_span_id_hex}"
            if parent_context:
                parent_info += " (linked)"
            else:
                parent_info += " (unlinked - new trace created)"

        logger.info(
            f"[plugin_span] Span ended successfully | "
            f"span_name={span_name} | "
            f"success={success} | "
            f"duration_ms={duration_ms:.2f} | "
            f"trace_id={actual_trace_id} | "
            f"span_id={actual_span_id} | "
            f"space_id={space_id} | "
            f"task_id={task_id} | "
            f"node_id={node_id}"
            f"{parent_info}"
        )

        if not success:
            logger.warning(
                f"[plugin_span] Plugin execution failed | "
                f"span_name={span_name} | "
                f"error={error_message[:200] if error_message else 'N/A'} | "
                f"trace_id={actual_trace_id} | "
                f"task_id={task_id} | "
                f"node_id={node_id}"
            )

    except Exception as e:
        logger.exception(
            f"[plugin_span] Failed to end span | "
            f"span_name={span_name} | "
            f"error={e} | "
            f"space_id={space_id} | "
            f"task_id={task_id} | "
            f"node_id={node_id}"
        )
