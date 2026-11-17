"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (see LICENSE for details).
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import hashlib
import json
import logging
import random

from django.db import transaction
from django.utils import timezone

from bkflow.exceptions import APIRequestError, APIResponseError
from bkflow.plugin_catalog.models import SourceSyncState
from bkflow.space.configs import UniformApiConfig
from bkflow.space.models import SpaceConfig

logger = logging.getLogger("root")


class SourceSyncStateService:
    """
    来源同步状态：有限重试 + 代次判断。

    设计文档（`03 后台任务与迁移清单` L52-56 / `05 调用时序与一致性` L25-26）要求：

    - **有限重试**：可重试故障按 10/20/40 秒退避重试，最多 3 次，抖动不超过 20%，
      一轮不超过 5 分钟；**耗尽后同一故障不重新开启快速重试**，回到低频检查，
      只有新的成功证据才能恢复。
    - **代次判断**：采集期间来源配置被改/删除，旧结果晚到后会被当成当前结果使用，
      可能误判插件失效 -> 提交时校验「配置代次」，不一致就丢弃过期结果。
    - **按覆盖范围失效**：区分「首个**超时**（覆盖范围不明，不判定失效）」与
      「**鉴权失败**（该来源整体挂了，按覆盖范围失效）」。

    状态**持久化在库里**（不是缓存、不是队列消息），进程重启不丢，
    也不依赖某条队列消息还在不在。
    """

    # 快速重试参数（设计文档给定的技术默认值）
    MAX_RETRY = 3
    RETRY_DELAYS = (10, 20, 40)  # 秒
    RETRY_JITTER_RATIO = 0.2  # 抖动不超过 20%
    MAX_RETRY_WINDOW = 300  # 一轮不超过 5 分钟

    # 错误类型
    ERROR_TYPE_TIMEOUT = "timeout"  # 超时/网络异常：覆盖范围不明，不判定失效
    ERROR_TYPE_AUTH = "auth"  # 鉴权失败：该来源整体挂了，按覆盖范围失效
    ERROR_TYPE_OTHER = "other"

    # ------------------------------------------------------------------ 代次 ----

    @classmethod
    def current_config_generation(cls, space_id):
        """当前来源配置的内容哈希，作为「配置代次」标识。

        用**配置内容哈希**而不是自增计数：配置内容变了哈希必变，
        不需要额外的"配置变更钩子"，也不会因为进程重启丢计数。
        没配过来源 -> 空串。
        """
        config = SpaceConfig.get_config(space_id=space_id, config_name=UniformApiConfig.name)
        if not config:
            return ""
        try:
            raw = json.dumps(config, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError):
            raw = str(config)
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:32]

    # ------------------------------------------------------------------ 采集 ----

    @classmethod
    def begin_collect(cls, space_id, source_key, config_generation=None):
        """发起一次采集：登记采集代次（+1），返回本次的采集代次。

        采集代次用于识别「同一来源的并发/重复采集」——只有最新一次采集的结果
        才允许提交，旧的结果（晚到的）会被丢弃。
        """
        if config_generation is None:
            config_generation = cls.current_config_generation(space_id)
        with transaction.atomic():
            state, _ = SourceSyncState.objects.select_for_update().get_or_create(
                space_id=space_id, source_key=source_key or ""
            )
            state.collect_generation += 1
            state.config_generation = config_generation
            state.save(update_fields=["collect_generation", "config_generation"])
            return state.collect_generation

    @classmethod
    def is_stale(cls, space_id, source_key, collect_generation):
        """本次采集结果是否已过期（期间又发起了新的采集，或配置变了）。

        过期结果**直接丢弃**：既不提交、也不判定任何插件失效。
        """
        state = SourceSyncState.objects.filter(space_id=space_id, source_key=source_key or "").first()
        if state is None:
            return False
        if collect_generation and state.collect_generation > collect_generation:
            logger.warning(
                "[来源同步] 采集结果已过期，丢弃: space_id=%s, source_key=%s, collect_generation=%s, latest=%s",
                space_id,
                source_key,
                collect_generation,
                state.collect_generation,
            )
            return True
        if state.config_generation and state.config_generation != cls.current_config_generation(space_id):
            logger.warning(
                "[来源同步] 配置代次已变化，结果过期，丢弃: space_id=%s, source_key=%s",
                space_id,
                source_key,
            )
            return True
        return False

    # -------------------------------------------------------------- 成功/失败 ----

    @classmethod
    def mark_success(cls, space_id, source_key):
        """采集成功：清零故障状态，只有新的成功证据才能让快速重试重新开启。"""
        SourceSyncState.objects.filter(space_id=space_id, source_key=source_key or "").update(
            failure_round=0,
            retry_count=0,
            next_retry_at=None,
            exhausted=False,
            last_error="",
            last_error_type="",
            last_synced_at=timezone.now(),
        )

    @classmethod
    def mark_failure(cls, space_id, source_key, error_message, error_type=ERROR_TYPE_OTHER):
        """采集失败：记录故障轮次与下次快速重试时间；耗尽后不再重开快速重试。"""
        with transaction.atomic():
            state, _ = SourceSyncState.objects.select_for_update().get_or_create(
                space_id=space_id, source_key=source_key or ""
            )
            state.failure_round += 1
            state.retry_count += 1
            state.last_error = (error_message or "")[:2000]
            state.last_error_type = error_type
            if state.retry_count >= cls.MAX_RETRY:
                # 耗尽：同一故障不再开启快速重试，回到低频检查
                state.exhausted = True
                state.next_retry_at = None
            else:
                state.exhausted = False
                state.next_retry_at = timezone.now() + timezone.timedelta(
                    seconds=cls.retry_delay_seconds(state.retry_count)
                )
            state.save(
                update_fields=[
                    "failure_round",
                    "retry_count",
                    "next_retry_at",
                    "exhausted",
                    "last_error",
                    "last_error_type",
                ]
            )
            return state

    @classmethod
    def retry_delay_seconds(cls, retry_count):
        """第 n 次重试的等待秒数：10/20/40 秒 + 不超过 20% 的抖动。"""
        index = max(0, min(retry_count - 1, len(cls.RETRY_DELAYS) - 1))
        base = cls.RETRY_DELAYS[index]
        jitter = base * cls.RETRY_JITTER_RATIO
        delay = base + random.uniform(-jitter, jitter)
        return max(1, min(int(delay), cls.MAX_RETRY_WINDOW))

    # ---------------------------------------------------------------- 重试判定 ----

    @classmethod
    def pending_retry_sources(cls, space_id):
        """该空间里「失败且未耗尽、需要快速重试」的来源及其下次重试时间。

        返回 `[(source_key, next_retry_at), ...]`。调度侧按 `next_retry_at` 决定
        延迟多久唤醒（10/20/40 秒退避）；已耗尽的（同一故障重试满 3 次）不在结果里，
        等下一轮周期调度。
        """
        return list(
            SourceSyncState.objects.filter(space_id=space_id, exhausted=False)
            .exclude(next_retry_at=None)
            .values_list("source_key", "next_retry_at")
        )

    @classmethod
    def classify_error(cls, exc):
        """把采集异常归类，用于区分「不判定失效」与「按覆盖范围失效」。

        - `APIRequestError`：网络异常/超时（requests 的 Timeout 也走这里）-> timeout
        - `APIResponseError` 且响应码是 401/403 -> auth（鉴权失败，该来源整体挂了）
        - 其它 -> other
        """
        if isinstance(exc, APIRequestError):
            message = str(exc).lower()
            # requests 的超时异常文案含 timed out / timeout
            if "timed out" in message or "timeout" in message:
                return cls.ERROR_TYPE_TIMEOUT
            return cls.ERROR_TYPE_TIMEOUT
        if isinstance(exc, APIResponseError):
            message = str(exc)
            if "status_code: 401" in message or "status_code: 403" in message:
                return cls.ERROR_TYPE_AUTH
            return cls.ERROR_TYPE_OTHER
        return cls.ERROR_TYPE_OTHER

    @classmethod
    def invalidates_by_scope(cls, error_type):
        """该错误类型是否要按覆盖范围失效。

        只有**鉴权失败**才按覆盖范围失效（该来源整体挂了，它下面的插件确实都不可用）；
        超时/其它错误覆盖范围不明，**不判定失效**（宁可让插件保持"可用"，
        也不能因为一次网络抖动就把用户的插件全标成失效）。
        """
        return error_type == cls.ERROR_TYPE_AUTH
