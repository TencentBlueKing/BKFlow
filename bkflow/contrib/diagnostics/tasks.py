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
from uuid import uuid4

from celery import current_app
from django.conf import settings
from django.core.management import call_command
from pipeline.contrib.diagnostics.callback_scan import scan_callbacks
from pipeline.contrib.diagnostics.recovery_runner import run_recovery
from pipeline.contrib.diagnostics.scanner import scan_stalled_roots
from pipeline.contrib.diagnostics.signature_scan import scan_signatures
from pipeline.contrib.diagnostics.window_scan import scan_silence_windows

from bkflow.contrib.diagnostics.constants import (
    CALLBACK_SCAN_LOCK,
    CLEANUP_LOCK,
    FAST_TASK_LOCK_EXPIRE_SECONDS,
    RECOVERY_LOCK,
    ROOT_SCAN_LOCK,
    SIGNATURE_SCAN_LOCK,
    SLOW_TASK_LOCK_EXPIRE_SECONDS,
)

logger = logging.getLogger("celery")


def _lock_key(name):
    module_code = getattr(getattr(settings, "BKFLOW_MODULE", None), "code", None) or "default"
    return "bkflow:{}:diagnostics:{}".format(module_code, name)


def _acquire_singleflight(name, expire):
    """非阻塞获取任务单例锁，Redis 不可用时安全跳过本轮。"""
    token = uuid4().hex
    try:
        acquired = settings.redis_inst.set(name=_lock_key(name), value=token, nx=True, ex=expire)
    except Exception:
        logger.exception("[diagnostics] acquire %s lock failed", name)
        return None
    return token if acquired else None


def _release_singleflight(name, token):
    """只释放当前任务持有的锁，避免误删下一轮新锁。"""
    try:
        key = _lock_key(name)
        current = settings.redis_inst.get(key)
        current = current.decode() if isinstance(current, bytes) else current
        if current == token:
            settings.redis_inst.delete(key)
    except Exception:
        logger.exception("[diagnostics] release %s lock failed", name)


def _run_singleflight(name, enabled, runner, expire=FAST_TASK_LOCK_EXPIRE_SECONDS):
    if not enabled:
        return None

    token = _acquire_singleflight(name, expire)
    if token is None:
        logger.info("[diagnostics] %s skipped: task lock unavailable", name)
        return None

    try:
        result = runner()
        logger.info("[diagnostics] %s finished: %s", name, result)
        return result
    except Exception:
        logger.exception("[diagnostics] %s failed", name)
        return None
    finally:
        _release_singleflight(name, token)


def _scan_roots():
    """窗口扫描启用时替代基础静默扫描，避免重复立案。"""
    if settings.PIPELINE_DIAGNOSTICS_WINDOW_SCAN_ENABLED:
        return scan_silence_windows()
    return scan_stalled_roots()


def _cleanup():
    call_command("cleanup_diagnostics")


@current_app.task(ignore_result=True)
def scan_stuck_diagnostics():
    """扫描长时间无进展的流程并记录诊断案例。"""
    enabled = settings.PIPELINE_DIAGNOSTICS_SCAN_ENABLED or settings.PIPELINE_DIAGNOSTICS_WINDOW_SCAN_ENABLED
    return _run_singleflight(ROOT_SCAN_LOCK, enabled, _scan_roots, SLOW_TASK_LOCK_EXPIRE_SECONDS)


@current_app.task(ignore_result=True)
def scan_stuck_signatures():
    """快速识别执行、轮询及父子流程消息丢失。"""
    return _run_singleflight(
        SIGNATURE_SCAN_LOCK,
        settings.PIPELINE_DIAGNOSTICS_SIGNATURE_SCAN_ENABLED,
        scan_signatures,
    )


@current_app.task(ignore_result=True)
def scan_stuck_callbacks():
    """扫描已落库但未被调度消费的回调。"""
    return _run_singleflight(
        CALLBACK_SCAN_LOCK,
        settings.PIPELINE_DIAGNOSTICS_CALLBACK_SCAN_ENABLED,
        scan_callbacks,
    )


@current_app.task(ignore_result=True)
def run_stuck_recovery():
    """回查恢复结果，并按安全开关预览或自动重放。"""
    return _run_singleflight(
        RECOVERY_LOCK,
        settings.PIPELINE_DIAGNOSTICS_RECOVERY_ENABLED,
        run_recovery,
    )


@current_app.task(ignore_result=True)
def cleanup_diagnostics():
    """按保留期限清理诊断数据。"""
    return _run_singleflight(
        CLEANUP_LOCK,
        settings.DIAGNOSTICS_CLEANUP_ENABLED,
        _cleanup,
        SLOW_TASK_LOCK_EXPIRE_SECONDS,
    )
