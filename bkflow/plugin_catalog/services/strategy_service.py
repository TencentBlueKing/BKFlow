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

from bkflow.exceptions import ValidationError
from bkflow.plugin_catalog.models import PluginCatalogStatus, PluginType
from bkflow.plugin_catalog.services.source_group_service import SourceGroupService
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
        cls._validate_sources(space_id, data)
        SpaceConfig.objects.batch_update(space_id=space_id, configs={cls.Config.name: data})
        return cls.get_strategy(space_id)

    @classmethod
    def _validate_sources(cls, space_id, data):
        """校验条件组里的 `sources` 必须是该空间真实存在的来源。

        `PluginAdmissionStrategyConfig.validate` 只能做结构性校验（拿不到 space_id），
        而"来源 id 是否存在"是空间维度的：不存在的来源永远匹配不到，会让条件组
        静默失效（前端看不出任何异常，插件却一直落待审核）。

        例外：当前已保存策略里出现过的 source 允许继续保留——来源后来被删除会留下
        悬空引用，此时不应该阻断管理员保存其它字段的调整。
        """
        conditions = data.get("conditions") or []
        if not conditions:
            return

        valid_source_ids = cls._valid_source_ids(space_id)
        previous = cls.get_strategy(space_id) or {}
        previous_sources = {
            source for condition in (previous.get("conditions") or []) for source in (condition.get("sources") or [])
        }

        invalid = []
        for condition in conditions:
            for source in condition.get("sources") or []:
                if source in valid_source_ids or source in previous_sources:
                    continue
                if source not in invalid:
                    invalid.append(source)

        if invalid:
            raise ValidationError(
                "启用来源不存在或不合法：{}。可选来源：{}。"
                "来源列表取自 GET /api/plugin_catalog/strategy/sources/".format(
                    invalid, sorted(valid_source_ids)
                )
            )

    @classmethod
    def _valid_source_ids(cls, space_id):
        """该空间当前合法的来源 id 集合。

        只收 `whole=true` 的分组 id 和各分组的子项 id：
        - `whole=true`（内置插件 / 蓝鲸插件）：本身没有"来源"细分，整体就是一个可选单元，
          它的 id（`builtin` / `bk_plugin`）就是 `_match_key` 的匹配键，可直接用。
        - `whole=false`（API 插件）：还能再展开到具体来源，**分组 id 本身不能用作 source**——
          `_match_key` 对 api 返回的是 `source_key`，传 `"api"` 匹配不到任何插件，条件组会静默失效。
        """
        source_ids = set()
        for group in SourceGroupService.list_groups(space_id=space_id):
            if group.get("whole"):
                source_ids.add(group["id"])
            for child in group.get("children") or []:
                source_ids.add(child["id"])
        return source_ids

    @classmethod
    def decide(cls, space_id, plugin_type, source_key) -> AdmissionDecision:
        """
        判定一个新发现插件应该落什么状态/目录。只在"首次发现"（本地尚无目录条目）时调用，
        策略变更不回溯已存在的条目（存量不重审）。
        """
        strategy = cls.get_strategy(space_id) or {}
        mode = strategy.get("mode", cls.Config.Mode.REVIEW)

        if mode == cls.Config.Mode.REVIEW:
            return AdmissionDecision(status=PluginCatalogStatus.PENDING_REVIEW)

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
            # 未命中任何条件组：固定兜底为待审核（更安全）。
            # 接口契约里不提供可配置的兜底规则（设计稿 6.png 的"设条件自动通过"也没有兜底配置项），
            # 前端无需也无法配置。
            return AdmissionDecision(status=PluginCatalogStatus.PENDING_REVIEW)

        # 未知 mode，兜底待审核，不放行未经校验的数据
        return AdmissionDecision(status=PluginCatalogStatus.PENDING_REVIEW)

    @classmethod
    def _decide_after_pass(cls, after_pass, ai_scope, assign_directory_id) -> AdmissionDecision:
        if after_pass == cls.Config.ConditionAfterPass.ASSIGN:
            return AdmissionDecision(status=PluginCatalogStatus.ENABLE, directory_id=assign_directory_id)
        if after_pass == cls.Config.ConditionAfterPass.AI:
            # AI 决策前先落"待审核"占位，等待 apply_automatic_classification_task 异步把它改成
            # enable + 目录；晚到/失败时保持待审核由人工兜底处理，不阻塞同步主流程。
            return AdmissionDecision(status=PluginCatalogStatus.PENDING_REVIEW, need_ai=True, ai_scope=ai_scope)
        # uncategorized 及其他未知值，一律兜底为"未分类直接可见"
        return AdmissionDecision(status=PluginCatalogStatus.ENABLE, directory_id=None)

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
