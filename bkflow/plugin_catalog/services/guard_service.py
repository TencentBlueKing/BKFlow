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

from rest_framework import serializers

from bkflow.plugin.constants import WRAPPER_CODES
from bkflow.plugin_catalog.models import PluginCatalogStatus, PluginType, SpacePluginCatalogEntry
from bkflow.plugin_catalog.services.migration_service import PluginCatalogMigrationService
from bkflow.plugin_catalog.services.source_group_service import SourceGroupService

logger = logging.getLogger(__name__)


class PluginCatalogGuardService:
    """
    流程保存拦截：校验本次保存是否新增了「已下架」插件的节点。

    判定规则：
    - 判定时机：相对基线（原草稿 / 当前已发布版本）**新增**的节点才拦截，
      原本就存在的已下架节点保持原样放行。
    - 判定依据：按 (插件身份, node_id) **二元组**做差集，而不是只比插件身份集合。
      这样才能同时覆盖两种场景：
        a) node_id 没变但插件被换成另一个已下架插件 -> 身份变了，拦截；
        b) 复制一个已下架插件节点（node_id 变了、身份相同）-> node_id 是新的，拦截。
      若只按身份集合做差集，场景 b 会漏判。
    """

    @classmethod
    def extract_node_plugin_identities(cls, pipeline_tree):
        """
        从 pipeline_tree 中提取每个 ServiceActivity 节点引用的插件身份。

        覆盖 builtin/bk_plugin/api 三类（不是只覆盖开放插件），因此独立实现，
        不去改 `OpenPluginSnapshotService.collect_plugin_references` 的职责边界
        （那个只处理 uniform_api 开放插件）。

        :return: {node_id: {"plugin_type", "source_key", "plugin_code", "plugin_version",
                            "node_name", "resolved"}}
                 resolved=False 表示"无法解析身份的 API 节点"（连 plugin_id 都取不到），
                 供管理侧做存量治理；这类节点不计入插件引用计数。
        """
        activities = (pipeline_tree or {}).get("activities") or {}
        result = {}
        for node_id, node in activities.items():
            if not isinstance(node, dict) or node.get("type") != "ServiceActivity":
                continue
            component = node.get("component") or {}
            code = component.get("code") or ""
            if not code:
                continue

            data = component.get("data") or component.get("inputs") or {}
            if code == "remote_plugin":
                plugin_type, source_key = PluginType.BK_PLUGIN, ""
                plugin_code = cls._extract_value(data, "plugin_code")
                plugin_version = cls._extract_value(data, "plugin_version") or ""
            elif code == "uniform_api":
                api_meta = component.get("api_meta") or {}
                plugin_type = PluginType.API
                plugin_code = cls._extract_value(data, "uniform_api_plugin_id") or api_meta.get("id")
                source_key = (
                    cls._extract_value(data, "uniform_api_plugin_source_key") or api_meta.get("source_key") or ""
                )
                plugin_version = (
                    cls._extract_value(data, "uniform_api_plugin_version")
                    or api_meta.get("plugin_version")
                    or ""
                )
            else:
                if code in WRAPPER_CODES:
                    # 包装器（子流程/开放插件代理等）不是独立插件，不参与目录判定
                    continue
                plugin_type, source_key = PluginType.BUILTIN, ""
                plugin_code = code
                plugin_version = component.get("version") or ""

            result[node_id] = {
                "plugin_type": plugin_type,
                "source_key": source_key or "",
                "plugin_code": plugin_code or "",
                "plugin_version": plugin_version or "",
                "node_name": node.get("name") or "",
                "resolved": bool(plugin_code),
            }
        return result

    @classmethod
    def check_newly_added_offline_plugins(cls, space_id, pipeline_tree, baseline_pipeline_tree=None):
        """
        校验本次保存是否新增了"已下架"插件的节点，命中则抛结构化错误。

        :param space_id: 空间 ID
        :param pipeline_tree: 本次保存的流程树
        :param baseline_pipeline_tree: 基线流程树（原草稿 / 当前已发布版本）；
                                      为 None 表示无基线（新建流程），所有节点都算新增。
        :raises serializers.ValidationError: 命中拦截时抛出，错误体含 detail + blocked_nodes
        """
        if not space_id or not pipeline_tree:
            return

        # 未完成插件目录迁移的空间没有目录数据，本校验自然不生效（保持原有保存行为不变）
        if not PluginCatalogMigrationService.is_ready(space_id):
            return

        current = cls.extract_node_plugin_identities(pipeline_tree)
        baseline = cls.extract_node_plugin_identities(baseline_pipeline_tree)

        baseline_node_ids = {}
        for node_id, identity in baseline.items():
            key = cls._identity_key(identity)
            baseline_node_ids.setdefault(key, set()).add(node_id)

        newly_added = []
        for node_id, identity in current.items():
            if not identity.get("resolved", True):
                # 身份解析失败的 API 节点无法对应任何插件条目，不参与下架判定
                continue
            key = cls._identity_key(identity)
            if node_id not in baseline_node_ids.get(key, set()):
                newly_added.append((node_id, identity))
        if not newly_added:
            return

        offline_entries = cls._get_offline_entries(space_id, newly_added)
        if not offline_entries:
            return

        name_resolver = cls._build_name_resolver(space_id)
        blocked_nodes = []
        for node_id, identity in newly_added:
            entry = offline_entries.get(cls._identity_key(identity))
            if entry is None:
                continue
            blocked_nodes.append(cls._build_blocked_node(node_id, identity, entry, name_resolver))
        if not blocked_nodes:
            return

        raise serializers.ValidationError(
            {
                "detail": "流程中新增了已下架的插件，请移除或替换后再保存",
                "blocked_nodes": blocked_nodes,
            }
        )

    @classmethod
    def batch_get_status(cls, space_id, identities):
        """
        12 · 批量查询插件当前状态（节点配置面板打开时，对画布内全部节点引用的插件身份批量查一次）。

        查不到的身份（目录里没有这条记录，例如迁移前的老空间或边缘情况）按 `visible` 兜底——
        保守方向是"宁可不提示，也不要误报停用"，不阻塞节点正常展示。

        :param identities: [{"plugin_type","source_key","plugin_code"}, ...]
        :return: [{"plugin_type","source_key","plugin_code","status","offline_reason","replace_plugin"}, ...]
        """
        identities = list(identities or [])
        if not identities:
            return []

        keys = {
            (item.get("plugin_type"), item.get("source_key") or "", item.get("plugin_code")) for item in identities
        }
        entries = {}
        if keys:
            queryset = SpacePluginCatalogEntry.objects.filter(
                space_id=space_id, plugin_type__in={key[0] for key in keys}
            ).select_related("replace_plugin")
            for entry in queryset:
                key = (entry.plugin_type, entry.source_key, entry.plugin_code)
                if key in keys:
                    entries[key] = entry

        name_resolver = cls._build_name_resolver(space_id)
        results = []
        for item in identities:
            key = (item.get("plugin_type"), item.get("source_key") or "", item.get("plugin_code"))
            entry = entries.get(key)
            if entry is None:
                results.append(
                    {
                        "plugin_type": key[0],
                        "source_key": key[1],
                        "plugin_code": key[2],
                        "status": PluginCatalogStatus.VISIBLE,
                        "offline_reason": "",
                        "replace_plugin": None,
                    }
                )
                continue

            replace_plugin = None
            if entry.replace_plugin_id:
                replace_entry = entry.replace_plugin
                if replace_entry is not None:
                    replace_plugin = {
                        "plugin_type": replace_entry.plugin_type,
                        "source_key": replace_entry.source_key,
                        "plugin_code": replace_entry.plugin_code,
                        "name": name_resolver(
                            replace_entry.plugin_type, replace_entry.source_key, replace_entry.plugin_code
                        ),
                        "status": replace_entry.status,
                    }
            results.append(
                {
                    "plugin_type": key[0],
                    "source_key": key[1],
                    "plugin_code": key[2],
                    "status": entry.status,
                    "offline_reason": entry.offline_reason,
                    "replace_plugin": replace_plugin,
                }
            )
        return results

    @classmethod
    def get_baseline_pipeline_tree(cls, template):
        """
        取某个流程当前的基线树：优先当前草稿快照（更新草稿场景），
        其次当前已发布版本（从已发布版本再次编辑场景），都没有则返回 None。

        实现放在 `Template.get_baseline_pipeline_tree()`（模板侧的领域逻辑），
        这里只做转发，避免 plugin_catalog 反向依赖 template.models 形成循环导入。
        """
        if template is None:
            return None
        return template.get_baseline_pipeline_tree()

    # ------------------------------------------------------------------ 内部方法 ----

    @staticmethod
    def _identity_key(identity):
        return (identity["plugin_type"], identity["source_key"], identity["plugin_code"])

    @staticmethod
    def _extract_value(data, key):
        raw = data.get(key)
        if isinstance(raw, dict):
            return raw.get("value")
        return raw

    @staticmethod
    def _get_offline_entries(space_id, newly_added):
        """批量查出新增节点里命中的"已下架"插件条目，按身份三元组做 key。"""
        identities = {PluginCatalogGuardService._identity_key(identity) for _, identity in newly_added}
        if not identities:
            return {}
        entries = SpacePluginCatalogEntry.objects.filter(
            space_id=space_id,
            status=PluginCatalogStatus.OFFLINE,
            plugin_type__in={item[0] for item in identities},
        )
        return {
            (entry.plugin_type, entry.source_key, entry.plugin_code): entry
            for entry in entries
            if (entry.plugin_type, entry.source_key, entry.plugin_code) in identities
        }

    @staticmethod
    def _build_name_resolver(space_id):
        """一次性拿全三类插件的展示名，避免逐节点查库。"""
        builtin_names = SourceGroupService.builtin_display_names()
        bk_plugin_names = SourceGroupService.bk_plugin_display_names(space_id)
        api_names = SourceGroupService.api_display_names(space_id)

        def resolve(plugin_type, source_key, plugin_code):
            if plugin_type == PluginType.API:
                return api_names.get((source_key, plugin_code), plugin_code)
            if plugin_type == PluginType.BK_PLUGIN:
                return bk_plugin_names.get(plugin_code, plugin_code)
            return builtin_names.get(plugin_code, plugin_code)

        return resolve

    @classmethod
    def _build_blocked_node(cls, node_id, identity, entry, name_resolver):
        replace_plugin = None
        if entry.replace_plugin_id:
            replace_entry = SpacePluginCatalogEntry.objects.filter(pk=entry.replace_plugin_id).first()
            if replace_entry is not None:
                replace_plugin = {
                    "plugin_type": replace_entry.plugin_type,
                    "source_key": replace_entry.source_key,
                    "plugin_code": replace_entry.plugin_code,
                    "name": name_resolver(
                        replace_entry.plugin_type, replace_entry.source_key, replace_entry.plugin_code
                    ),
                }
        return {
            "plugin_type": identity["plugin_type"],
            "source_key": identity["source_key"],
            "plugin_code": identity["plugin_code"],
            "plugin_name": name_resolver(
                identity["plugin_type"], identity["source_key"], identity["plugin_code"]
            ),
            "node_id": node_id,
            "node_name": identity["node_name"],
            "offline_reason": entry.offline_reason,
            "replace_plugin": replace_plugin,
        }
