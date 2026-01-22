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
from opentelemetry.trace import SpanKind, Status, StatusCode

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


def start_plugin_span(span_name: str, data, **attributes) -> int:
    """
    记录插件Span的开始时间，将相关信息保存到data outputs中，用于跨schedule调用追踪

    :param span_name: Span名称
    :param data: 插件的data对象，用于持久化span信息
    :param attributes: Span的属性
    :return: 开始时间戳（纳秒）
    """
    start_time_ns = time.time_ns()

    # 将span信息保存到data outputs中，以便在schedule中使用
    data.set_outputs(PLUGIN_SPAN_START_TIME_KEY, start_time_ns)
    data.set_outputs(PLUGIN_SPAN_NAME_KEY, span_name)
    # 确保属性值可以序列化
    serializable_attributes = {k: str(v) if v is not None else "" for k, v in attributes.items()}
    data.set_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY, serializable_attributes)

    logger.info(f"[plugin_span] started span '{span_name}' at {start_time_ns}")

    return start_time_ns


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
    start_time_ns = data.get_one_of_outputs(PLUGIN_SPAN_START_TIME_KEY)
    span_name = data.get_one_of_outputs(PLUGIN_SPAN_NAME_KEY)
    attributes = data.get_one_of_outputs(PLUGIN_SPAN_ATTRIBUTES_KEY) or {}

    if not start_time_ns or not span_name:
        # 没有找到span开始信息，可能是旧数据或异常情况
        logger.warning("[plugin_span] No span start info found, skipping span end")
        return

    if end_time_ns is None:
        end_time_ns = time.time_ns()

    tracer = trace.get_tracer(__name__)

    try:
        # 使用start_span创建span，并手动设置开始时间
        span = tracer.start_span(
            name=span_name,
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

        # 计算并记录耗时
        duration_ms = (end_time_ns - start_time_ns) / 1_000_000
        span.set_attribute("bk_flow.plugin.duration_ms", duration_ms)

        # 手动结束span，设置结束时间
        span.end(end_time=end_time_ns)

        logger.info(f"[plugin_span] ended span '{span_name}', success={success}, duration_ms={duration_ms:.2f}")
    except Exception as e:
        logger.exception(f"[plugin_span] Failed to end span '{span_name}': {e}")
