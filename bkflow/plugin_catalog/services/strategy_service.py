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

from dataclasses import dataclass
from typing import Optional

from bkflow.plugin_catalog.models import PluginCatalogStatus, PluginType
from bkflow.space.configs import PluginAdmissionStrategyConfig
from bkflow.space.models import SpaceConfig


@dataclass
class AdmissionDecision:
    """新插件接入策略的判定结果，供 sync_service 在创建新目录条目时使用。"""

    status: str
    directory_id: Optional[int] = None
    need_ai: bool = False
    ai_scope: Optional[str] = None


class PluginAdmissionStrategyService:
    """
    新插件接入策略的读取、保存与判定：决定新发现的插件默认落什么状态。
    """

    Config = PluginAdmissionStrategyConfig

    @classmethod
    def get_strategy(cls, space_id):
        return SpaceConfig.get_config(space_id=space_id, config_name=cls.Config.name)

    @classmethod
    def save_strategy(cls, space_id, data, operator=None):
        cls.Config.validate(data)
        SpaceConfig.objects.batch_update(space_id=space_id, configs={cls.Config.name: data})
        return cls.get_strategy(space_id)

    @classmethod
    def decide(cls, space_id, plugin_type, source_key) -> AdmissionDecision:
        """
        判定一个新发现插件应该落什么状态/目录。只在"首次发现"（本地尚无目录条目）时调用，
        策略变更不回溯已存在的条目（存量不重审）。
        """
        strategy = cls.get_strategy(space_id) or {}
        mode = strategy.get("mode", cls.Config.Mode.REVIEW)

        if mode == cls.Config.Mode.REVIEW:
            return AdmissionDecision(status=PluginCatalogStatus.REVIEW)

        if mode == cls.Config.Mode.VISIBLE:
            return cls._decide_after_pass(
                after_pass=strategy.get("visible_after_pass", cls.Config.VisibleAfterPass.UNCATEGORIZED),
                ai_scope=strategy.get("visible_ai_scope"),
                assign_directory_id=None,
            )

        if mode == cls.Config.Mode.CONDITIONAL:
            match_key = cls._match_key(plugin_type, source_key)
            for condition in strategy.get("conditions") or []:
                if match_key in (condition.get("sources") or []):
                    return cls._decide_after_pass(
                        after_pass=condition.get("after_pass"),
                        ai_scope=condition.get("ai_scope"),
                        assign_directory_id=condition.get("assign_directory_id"),
                    )
            fallback = strategy.get("fallback")
            if not fallback:
                # fallback 未设置时兜底为待审核，更安全
                return AdmissionDecision(status=PluginCatalogStatus.REVIEW)
            return cls._decide_after_pass(
                after_pass=fallback.get("after_pass"),
                ai_scope=fallback.get("ai_scope"),
                assign_directory_id=fallback.get("assign_directory_id"),
            )

        # 未知 mode，兜底待审核，不放行未经校验的数据
        return AdmissionDecision(status=PluginCatalogStatus.REVIEW)

    @classmethod
    def _decide_after_pass(cls, after_pass, ai_scope, assign_directory_id) -> AdmissionDecision:
        if after_pass == cls.Config.ConditionAfterPass.ASSIGN:
            return AdmissionDecision(status=PluginCatalogStatus.VISIBLE, directory_id=assign_directory_id)
        if after_pass == cls.Config.ConditionAfterPass.AI:
            # AI 决策前先落"待审核"占位，等待 apply_automatic_classification_task 异步把它改成
            # visible + 目录；晚到/失败时保持待审核由人工兜底处理，不阻塞同步主流程。
            return AdmissionDecision(status=PluginCatalogStatus.REVIEW, need_ai=True, ai_scope=ai_scope)
        # uncategorized 及其他未知值，一律兜底为"未分类直接可见"
        return AdmissionDecision(status=PluginCatalogStatus.VISIBLE, directory_id=None)

    @staticmethod
    def _match_key(plugin_type, source_key):
        """
        策略条件组 `sources` 字段里存的是"来源匹配键"，与"直通来源"选择器里
        各分组/子项的 `id` 保持一致：
        - plugin_type == api 且 source_key 非空：匹配键 = source_key（如 "api_job"）
        - builtin / bk_plugin（source_key 恒为空）：匹配键 = plugin_type 本身
          （"builtin" / "bk_plugin"，对应"直通来源"里这两个分组自身的 id）
        """
        if plugin_type == PluginType.API and source_key:
            return source_key
        return plugin_type
