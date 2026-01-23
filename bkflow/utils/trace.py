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
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanProcessor
from opentelemetry.trace import (
    NonRecordingSpan,
    SpanContext,
    SpanKind,
    Status,
    StatusCode,
    TraceFlags,
)

logger = logging.getLogger("root")


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
        # Implement custom logic if needed on span end
        pass


def propagate_attributes(attributes: dict):
    """把attributes设置到span上，并继承到后面所有span

    :param attributes: 默认属性
    """

    provider = trace.get_tracer_provider()

    if not provider or isinstance(provider, trace.ProxyTracerProvider):
        provider = TracerProvider()
        trace.set_tracer_provider(provider)

    # Add a span processor that sets attributes on every new span
    provider.add_span_processor(AttributeInjectionSpanProcessor(attributes))


def append_attributes(attributes: dict):
    """追加属性到span上

    :param attributes: 需要追加的属性
    """
    current_span = trace.get_current_span()
    for key, value in attributes.items():
        current_span.set_attribute(f"bk_flow.{key}", value)


@contextmanager
def start_trace(span_name: str, propagate: bool = False, **attributes):
    """Start a trace

    :param span_name: 自定义Span名称
    :param propagate: 是否需要传播
    :param attributes: 需要跟span增加的属性, 默认为空
    :yield: 当前上下文的Span
    """
    tracer = trace.get_tracer(__name__)

    span_attributes = {f"bk_flow.{key}": value for key, value in attributes.items()}

    # 设置需要传播的属性
    if propagate:
        propagate_attributes(span_attributes)

    with tracer.start_as_current_span(span_name, kind=SpanKind.SERVER) as span:
        # 如果不进行传播，则在当前span手动配置需要添加的属性
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
                # 需要的属性只要在kwargs, request.GET, request.query_params(drf), request.POST, request.data(drf)中就可以
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


@contextmanager
def plugin_method_span(
    method_name: str,
    trace_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    **attributes,
):
    """
    追踪 plugin_execute 和 plugin_schedule 方法的 Span 上下文管理器

    :param method_name: 方法名称，如 'execute' 或 'schedule'
    :param trace_id: 父级 trace_id（十六进制字符串）
    :param parent_span_id: 父级 span_id（十六进制字符串）
    :param attributes: Span 属性（space_id, task_id, node_id, plugin_name 等）
    :yield: SpanResult 对象，用于记录执行结果
    """
    start_time_ns = time.time_ns()

    # 提取关键属性用于日志
    plugin_name = attributes.get("plugin_name", "unknown")
    task_id = attributes.get("task_id", "unknown")
    node_id = attributes.get("node_id", "unknown")
    schedule_count = attributes.get("schedule_count")

    # 构建 span 名称
    span_name = f"bk_flow.{plugin_name}.{method_name}"

    # 用于存储执行结果的容器
    class SpanResult:
        def __init__(self):
            self.success = True
            self.error_message = None

        def set_error(self, message: str):
            self.success = False
            self.error_message = message

    result = SpanResult()

    schedule_info = f", schedule_count={schedule_count}" if schedule_count is not None else ""
    logger.debug(
        f"[plugin_method_span] {method_name} started | plugin={plugin_name} "
        f"| task_id={task_id} | node_id={node_id}{schedule_info}"
    )

    try:
        yield result
    finally:
        end_time_ns = time.time_ns()
        duration_ms = (end_time_ns - start_time_ns) / 1_000_000

        tracer = trace.get_tracer(__name__)

        try:
            # 尝试重建 parent context
            parent_context = _build_parent_context(trace_id, parent_span_id)

            # 创建 span
            span = tracer.start_span(
                name=span_name,
                context=parent_context,
                start_time=start_time_ns,
                kind=SpanKind.INTERNAL,
            )

            # 设置属性
            span.set_attribute("bk_flow.plugin.method", method_name)
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(f"bk_flow.plugin.{key}", str(value))

            # 设置执行结果状态
            if result.success:
                span.set_status(Status(StatusCode.OK))
                span.set_attribute("bk_flow.plugin.success", True)
            else:
                span.set_status(Status(StatusCode.ERROR, result.error_message or f"{method_name} failed"))
                span.set_attribute("bk_flow.plugin.success", False)
                if result.error_message:
                    span.set_attribute("bk_flow.plugin.error", str(result.error_message)[:1000])

            # 结束 span
            span.end(end_time=end_time_ns)

            if result.success:
                logger.debug(
                    f"[plugin_method_span] {method_name} completed | plugin={plugin_name} "
                    f"| duration_ms={duration_ms:.2f} | task_id={task_id}"
                )
            else:
                logger.warning(
                    f"[plugin_method_span] {method_name} failed | plugin={plugin_name} | "
                    f"error={result.error_message[:200] if result.error_message else 'N/A'} | task_id={task_id}"
                )

        except Exception as e:
            logger.exception(
                f"[plugin_method_span] Failed to create span for {method_name} | "
                f"plugin={plugin_name} | "
                f"error={e} | "
                f"task_id={task_id} | "
                f"node_id={node_id}"
            )


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

    # 确保属性值可以序列化
    serializable_attributes = {k: str(v) if v is not None else "" for k, v in attributes.items()}
    data.set_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY, serializable_attributes)

    logger.debug(f"[plugin_span] Started span '{span_name}'")

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
            logger.debug(f"[plugin_span] Invalid parent span context: trace_id={trace_id_hex}")
            return None

        parent_span = NonRecordingSpan(parent_span_context)
        parent_context = trace.set_span_in_context(parent_span)
        return parent_context

    except (ValueError, TypeError) as e:
        logger.debug(f"[plugin_span] Failed to parse trace context: {e}")
        return None


def end_plugin_span(
    data,
    success: bool = True,
    error_message: Optional[str] = None,
    end_time_ns: Optional[int] = None,
):
    """
    结束插件Span，创建完整的Span并立即结束

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
        logger.debug(f"[plugin_span] No span start info found, skipping span end | task_id={task_id}")
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

        # 手动结束span，设置结束时间
        span.end(end_time=end_time_ns)

        if success:
            logger.debug(
                f"[plugin_span] Span ended | span_name={span_name} | duration_ms={duration_ms:.2f} | task_id={task_id}"
            )
        else:
            logger.warning(
                f"[plugin_span] Plugin execution failed | span_name={span_name} | "
                f"error={error_message[:200] if error_message else 'N/A'} | task_id={task_id}"
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
