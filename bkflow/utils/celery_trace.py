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

import logging

from celery.signals import before_task_publish, task_postrun, task_prerun
from opentelemetry import trace
from opentelemetry.context import attach, detach

from bkflow.utils.trace import (
    extract_trace_from_celery,
    inject_baggage_to_span,
    inject_trace_to_celery_headers,
)

logger = logging.getLogger("celery")

# 用于存储 task 运行时的 context token，以便在 task 结束时 detach
_task_context_tokens = {}


@before_task_publish.connect
def inject_trace_on_publish(headers=None, **kwargs):
    """在任务发布前，将 trace context 和 baggage 注入到 task headers 中

    这样可以确保 trace 信息能够跨 Celery worker 传播
    """
    if headers is not None:
        inject_trace_to_celery_headers(headers)
        logger.info(
            "[celery_trace] Injected trace headers on task publish: traceparent=%s, baggage=%s",
            headers.get("traceparent"),
            headers.get("baggage"),
        )


@task_prerun.connect
def extract_trace_on_run(task_id=None, task=None, **kwargs):
    """在任务执行前，从 task headers 中提取 trace context 和 baggage

    这样可以确保 worker 中的 span 能够继承调用方的 trace 信息和自定义属性
    """
    if task is None:
        return

    task_headers = getattr(task.request, "headers", None) or {}

    # 从 headers 中提取 trace context
    ctx = extract_trace_from_celery(task_headers)
    token = attach(ctx)

    # 保存 token 以便在 task 结束时 detach
    _task_context_tokens[task_id] = token

    # 将 baggage 中的属性注入到当前 span
    current_span = trace.get_current_span()
    if current_span and hasattr(current_span, "set_attribute"):
        inject_baggage_to_span(current_span)

    logger.info(
        "[celery_trace] Extracted trace context on task prerun: task_id=%s, traceparent=%s, baggage=%s",
        task_id,
        task_headers.get("traceparent"),
        task_headers.get("baggage"),
    )


@task_postrun.connect
def cleanup_trace_on_done(task_id=None, **kwargs):
    """在任务执行完成后，清理 context token"""
    token = _task_context_tokens.pop(task_id, None)
    if token is not None:
        detach(token)
        logger.info("[celery_trace] Detached trace context on task postrun: task_id=%s", task_id)


def setup_celery_trace_signals():
    """显式调用以确保 signals 被注册

    可以在 Django AppConfig.ready() 或 celery worker 启动时调用
    """
    # signals 已通过装饰器自动注册，这个函数只是为了显式导入模块
    logger.info("[celery_trace] Celery trace signals registered")
