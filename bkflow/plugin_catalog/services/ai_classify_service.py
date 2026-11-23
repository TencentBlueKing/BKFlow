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

import json
import logging
import re

from django.db.models import Q

from bkflow.plugin_catalog.models import PluginDirectory, SpacePluginCatalogEntry
from bkflow.plugin_catalog.services.ai_agent_client import AiAgentClient

logger = logging.getLogger(__name__)


class AiClassifyService:
    """
    AI 智能分类服务，统一供以下三处调用：
    - 06 新插件策略"全部直接通过 / AI 自动决定分类"、"设条件自动通过"条件组里 after_pass=ai
      （由 apply_automatic_classification_task 异步调用，增量/自由范围见 ai_scope）
    - 08 目录批量管理"AI 智能分类"（人工手动触发，仅返回建议，不落库）

    模型侧走 aidev 智能体（`AiAgentClient`）：把「现有目录 + 待分类插件」交给智能体，
    要求它按固定 JSON 格式返回分类建议；本服务负责**解析**与**校验**——
    智能体返回的目录 id / 插件 key 必须都在本空间的合法集合内，否则整条建议丢弃
    （智能体可能编造 id，不能直接落库）。
    """

    RESULT_PATCH = "patch"
    RESULT_EMPTY = "empty"
    RESULT_ERROR = "error"

    @classmethod
    def classify(cls, space_id, plugin_keys, ai_scope, request_id=None):
        """
        对给定插件身份列表请求 AI 分类建议。

        :param space_id: 空间 ID
        :param plugin_keys: list[str]，格式 "{plugin_type}:{source_key}:{plugin_code}"
        :param ai_scope: "increment" | "free"
        :param request_id: 幂等标识，供调用方去重
        :return: {"result": "patch"|"empty"|"error", "patch": {plugin_key: directory_id}, "message": str}
        """
        if not plugin_keys:
            return {"result": cls.RESULT_EMPTY, "patch": {}, "message": ""}
        try:
            return cls._request_classification(
                space_id=space_id, plugin_keys=plugin_keys, ai_scope=ai_scope, request_id=request_id
            )
        except Exception as exc:  # noqa: BLE001 统一兜底，不让未知异常中断调用方流程
            logger.exception("AI 智能分类请求失败: space_id=%s, request_id=%s", space_id, request_id)
            return {"result": cls.RESULT_ERROR, "patch": {}, "message": str(exc)}

    @classmethod
    def _request_classification(cls, space_id, plugin_keys, ai_scope, request_id):
        """向智能体请求分类建议，并解析、校验成 `{plugin_key: directory_id}`。

        返回值三态：
        - `patch`：有可用的分类建议
        - `empty`：智能体正常响应但没给出任何建议（调用方按"自动空入未分类"处理）
        - `error`：调用失败 / 响应无法解析 / 建议里的 id 全是幻觉（调用方保持待审核）
        """
        prompt = cls._build_prompt(space_id=space_id, plugin_keys=plugin_keys, ai_scope=ai_scope)
        text = AiAgentClient.chat(prompt)["text"]
        data = cls._parse_json(text)
        raw_items = data.get("classifications")
        if not isinstance(raw_items, list) or not raw_items:
            logger.info("AI 智能分类未给出建议: space_id=%s, request_id=%s", space_id, request_id)
            return {"result": cls.RESULT_EMPTY, "patch": {}, "message": "AI 未给出分类建议"}

        patch = cls._validate_patch(space_id=space_id, plugin_keys=plugin_keys, raw_items=raw_items)
        if not patch:
            # 智能体给了建议但全是幻觉（目录 id / 插件 key 不在本空间合法集合内），
            # 当成错误处理：保持待审核交人工，不能把插件错误地放行到未分类。
            logger.warning(
                "AI 智能分类建议全部无效（目录 id 或插件 key 不合法）: space_id=%s, request_id=%s",
                space_id,
                request_id,
            )
            return {"result": cls.RESULT_ERROR, "patch": {}, "message": "AI 返回的分类建议无效"}
        return {"result": cls.RESULT_PATCH, "patch": patch, "message": ""}

    # ------------------------------------------------------------------ prompt ----

    @classmethod
    def _build_prompt(cls, space_id, plugin_keys, ai_scope):
        """拼给智能体的指令：现有目录 + 待分类插件 + 严格的输出格式要求。"""
        # 目录树：给 id + 名称 + 父目录名（让模型能看懂层级），只用本空间的目录
        parent_names = {
            directory.id: directory.name
            for directory in PluginDirectory.objects.filter(space_id=space_id).only("id", "name", "parent_id")
        }
        directories = [
            {
                "id": directory.id,
                "name": directory.name,
                "parent_name": parent_names.get(directory.parent_id, "") if directory.parent_id else "",
            }
            for directory in PluginDirectory.objects.filter(space_id=space_id)
            .order_by("parent_id", "order", "id")
            .only("id", "name", "parent_id")
        ]

        # 待分类插件：带插件名与描述，便于模型判断归属
        plugins = cls._load_plugins_for_prompt(space_id, plugin_keys)

        # 范围语义（由调用方决定实际传哪些插件进来，这里只告诉模型这批插件的性质）：
        # - increment：本次新增/新启用的一批
        # - free：本空间还没有归入任何目录的插件（含之前遗留的未分类插件）
        if ai_scope == "free":
            scope_desc = (
                "【待分类插件】是这个空间里还没有归入任何目录的插件，请为其中每一个都推荐最合适的目录。"
            )
        else:
            scope_desc = "【待分类插件】是本次需要分类的插件，请为其中每一个都推荐最合适的目录。"
        directories_text = json.dumps(directories, ensure_ascii=False)
        plugins_text = json.dumps(plugins, ensure_ascii=False)
        return (
            "你是「蓝鲸流程引擎」空间插件目录的分类助手。请为待分类的插件推荐最合适的目录。\n\n"
            f"【现有目录】\n{directories_text}\n\n"
            f"【待分类插件】\n{plugins_text}\n\n"
            "【要求】\n"
            "1. 为每个插件挑选一个最合适的目录 id；确实没有合适目录时用 null（表示未分类）。\n"
            "2. 目录 id 只能取自【现有目录】里出现过的值，不要编造。\n"
            "3. 插件 key 只能取自【待分类插件】里出现过的值，不要编造、不要遗漏。\n"
            f"4. {scope_desc}\n"
            "5. 只输出下面这个 JSON，不要任何解释、前后缀文字或 markdown 代码块：\n"
            '{"classifications": [{"key": "<插件 key>", "directory_id": <目录 id 或 null>}]}'
        )

    # ------------------------------------------------------------------ 解析 ----

    @classmethod
    def _load_plugins_for_prompt(cls, space_id, plugin_keys):
        """按插件身份列表取出「名称 + 描述」等上下文，给 prompt 用。

        一次批量查回来（逐个查的话，插件一多就是 N 次查询）。
        """
        plugin_keys = [plugin_key for plugin_key in plugin_keys if plugin_key.count(":") >= 2]
        query = Q()
        for plugin_key in plugin_keys:
            plugin_type, source_key, plugin_code = plugin_key.split(":", 2)
            query |= Q(plugin_type=plugin_type, source_key=source_key, plugin_code=plugin_code)
        entry_by_key = {}
        if plugin_keys:
            for entry in SpacePluginCatalogEntry.objects.filter(query, space_id=space_id, is_deleted=False).only(
                "plugin_type", "source_key", "plugin_code", "plugin_name", "plugin_desc", "directory_id"
            ):
                key = f"{entry.plugin_type}:{entry.source_key}:{entry.plugin_code}"
                entry_by_key[key] = entry

        plugins = []
        for plugin_key in plugin_keys:
            entry = entry_by_key.get(plugin_key)
            if entry is None:
                continue
            plugins.append(
                {
                    "key": plugin_key,
                    "name": entry.plugin_name or entry.plugin_code,
                    "description": (entry.plugin_desc or "")[:200],
                    # 当前归属（08 整理场景让模型参考；08 之外恒为空串）
                    "current_directory_id": str(entry.directory_id) if entry.directory_id else "",
                }
            )
        return plugins

    @classmethod
    def _parse_json(cls, text):
        """从模型回复文本里提取 JSON 对象。

        模型可能把 JSON 包在 markdown 代码块里、也可能前后带解释文字，
        这里做一次宽松提取；提取不到就抛异常（上层记为 error）。
        """
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned).strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("AI 回复里没有找到 JSON")
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"AI 回复的 JSON 解析失败: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("AI 回复的 JSON 不是对象")
        return data

    # ------------------------------------------------------------------ 校验 ----

    @classmethod
    def _build_manage_prompt(cls, space_id, plugin_keys, content=None):
        """拼给智能体的指令：现有目录 + 全部插件 + 完全重组的输出要求。

        这次是**完全重组**：现有目录只是参考（合理可沿用 id、不合理就别放进结果=删除），
        全部插件都要重新给出归属。服务端对结果不再做"是否该删/是否合理"的裁剪，
        所以规则全部写在这里约束模型。
        `content` 是用户额外提的需求，追加到固定指令末尾一起发给智能体（优先级最高）。
        """
        directories = list(
            PluginDirectory.objects.filter(space_id=space_id)
            .order_by("parent_id", "order", "id")
            .only("id", "name", "parent_id")
        )
        parent_names = {directory.id: directory.name for directory in directories if directory.parent_id}
        directories_text = json.dumps(
            [
                {
                    "id": str(directory.id),
                    "name": directory.name,
                    "parent_id": str(directory.parent_id) if directory.parent_id else "",
                    "parent_name": parent_names.get(directory.parent_id, ""),
                    "level": 2 if directory.parent_id else 1,
                }
                for directory in directories
            ],
            ensure_ascii=False,
        )
        plugins_text = json.dumps(cls._load_plugins_for_prompt(space_id, plugin_keys), ensure_ascii=False)

        return (
            "你是「蓝鲸流程引擎」空间插件目录的整理助手。现在要对这个空间的插件目录做**完全重组**："
            "由你重新设计整套目录结构，把全部插件安排到合适的目录里。\n\n"
            f"【现有目录（仅供参考，可以沿用、也可以删除重建）】\n{directories_text}\n\n"
            f"【全部插件】\n{plugins_text}\n\n"
            "【要求】\n"
            "1. 【全部插件】里的每一个插件都必须给出归属，不能遗漏：`directory_key` 填你最终目录树里的"
            " `key`（新建目录的 key，或你想沿用的现有目录 id）；确实没有合适目录时用 null（未分类）。\n"
            "2. 最终的目录树全部放进 `directories` 数组，每一项含 `key`（新建目录用自定义标识如 \"d1\"；"
            "沿用现有目录就填它的 id）、`name`、`parent_key`（父目录的 key/id；一级目录用 null）。"
            "目录**最多两级**。\n"
            "3. **删除目录不需要理由**：现有目录只要你不放进 `directories`，就等于删除它——不管它下面"
            "原来有没有插件或子目录（插件会由你在 `classifications` 里重新安排）。不要保留名字是纯数字、"
            "纯编号或无意义的现有目录，重新建名字清晰的目录。\n"
            "4. `name` 是给用户看的目录显示名，必须用**简洁的中文业务描述**（如「作业执行」「主机管理」"
            "「数据采集」），2～20 个字，能让人一眼看懂这个目录放什么；**禁止留空、禁止纯数字或编号**"
            "（如 \"1\"、\"234\"）、禁止无意义的占位文字（如 \"目录1\"、\"新目录\"）。"
            "（如果用户在补充说明里明确要求某个目录用数字名，以用户要求为准。）\n"
            "5. 目录 key 用你自己的编号（d1/d2…）或想沿用的现有目录 id；插件 key 只能取自【全部插件】，"
            "不要编造。\n"
            "6. 只输出下面这个 JSON，不要任何解释、前后缀文字或 markdown 代码块：\n"
            '{"directories": [{"key": "d1", "name": "作业执行", "parent_key": null}],'
            ' "classifications": [{"key": "<插件 key>", "directory_key": "d1"}]}'
            + (f"\n\n【用户补充需求（优先级最高，与上面冲突时以这里为准）】\n{content}" if content else "")
        )

    @classmethod
    def _validate_manage_plan(cls, space_id, plugin_keys, data):
        """把智能体的"完全重组"方案整理成目录文档结构——**不做合理性裁剪**。

        设计决定（完全重组）：规则全部写进 prompt 约束模型，服务端不再判断"这个目录
        该不该删/名字合不合理/层级对不对"，AI 给出的目录树和插件归属原样采纳。
        这里只做两类必要的结构整理：

        - `parent_key` / `directory_key` 统一成字符串（AI 可能返回数字 id）
        - 给每个目录分配 `order`（前端整页保存需要；按 AI 给出的先后顺序）

        现有目录里没出现在 AI `directories` 中的，即为删除（`omit_directory_ids`），
        不再要求"必须是空目录"——完全重组下插件会由 AI 重新安排归属。

        仅保留一层最基本的防越界插件 key 不在【全部插件】范围内时忽略（这是幻觉，
        不是"合理性判断"；否则文档里会混入不存在的插件 id，前端保存会报错）。
        """
        directories = list(PluginDirectory.objects.filter(space_id=space_id).only("id"))
        existing_ids = {str(directory.id) for directory in directories}
        valid_keys = set(plugin_keys)

        # ---------------------------------------------------- 目录树（原样采纳）----
        directories_out = []
        for index, item in enumerate(data.get("directories") or []):
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip()
            if not key:
                continue
            name = str(item.get("name") or "").strip()
            parent_key = item.get("parent_key")
            parent_key = str(parent_key).strip() if parent_key not in (None, "") else None
            directories_out.append(
                {"key": key, "name": name, "parent_key": parent_key, "order": index + 1}
            )

        # 现有目录中未被 AI 保留的 = 删除（不判断是否空目录/是否有子目录）
        kept_keys = {item["key"] for item in directories_out}
        omit_directory_ids = [id for id in existing_ids if id not in kept_keys]

        # ---------------------------------------------------- 插件归属（原样采纳）----
        assignments = {}
        for item in data.get("classifications") or []:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            if key not in valid_keys:
                continue  # 插件 key 不在本次范围内 = 模型幻觉，忽略
            directory_key = item.get("directory_key")
            if directory_key is None or directory_key == "":
                assignments[key] = None
                continue
            assignments[key] = str(directory_key)

        return {
            "result": cls.RESULT_PATCH,
            "message": "",
            "new_directories": directories_out,
            "assignments": assignments,
            "omit_directory_ids": omit_directory_ids,
        }

    @classmethod
    def classify_by_entry_ids(cls, space_id, entry_ids):
        """
        按**目录条目 id** 请求 AI 分类建议（**不写库**）。

        用于两处：
        - 「给某个插件单独设置目录」：传 1 个条目 id，返回该插件的建议目录
        - 新插件策略的批量场景：传多个条目 id，一次性拿一批建议

        返回的 `patch` key 是**条目 id 字符串**（与 08 目录批量管理的 AI 建议口径一致），
        前端拿到建议后自行应用（单个走 `update_entry` 落库；批量保存后续再做）。

        :return: {"result": "patch"|"empty"|"error", "patch": {str(entry_id): directory_id}, "message": str}
        """
        entry_ids = list(entry_ids or [])
        if not entry_ids:
            return {"result": cls.RESULT_EMPTY, "patch": {}, "message": ""}

        entries = list(
            SpacePluginCatalogEntry.objects.filter(
                space_id=space_id, id__in=entry_ids, is_deleted=False
            ).only("id", "plugin_type", "source_key", "plugin_code")
        )
        if not entries:
            return {"result": cls.RESULT_EMPTY, "patch": {}, "message": "插件不存在或已删除"}

        key_by_entry_id = {
            entry.id: f"{entry.plugin_type}:{entry.source_key}:{entry.plugin_code}" for entry in entries
        }
        entry_id_by_key = {key: entry_id for entry_id, key in key_by_entry_id.items()}

        # 范围就是调用方圈定的这些条目，不扩展
        result = cls.classify(
            space_id=space_id,
            plugin_keys=list(key_by_entry_id.values()),
            ai_scope="increment",
        )
        if result["result"] != cls.RESULT_PATCH:
            return result

        patch = {
            str(entry_id_by_key[key]): directory_id
            for key, directory_id in result["patch"].items()
            if key in entry_id_by_key
        }
        return {"result": result["result"], "patch": patch, "message": result.get("message", "")}

    # ---------------------------------------------- 08 目录批量管理（AI 整理） ----

    @classmethod
    def classify_for_directory_manage(cls, space_id, plugin_keys, content=None, thread_id=None):
        """
        08「目录批量管理」页的 AI 整理：让 AI 决定**目录结构 + 插件归属**。

        与普通分类建议（`classify`）的差别：这里 AI 还可以
        - **新建目录**：现有目录装不下时自己造一个；
        - **删除空目录**：从返回的目录树里不出现即可（整页替换语义）。

        :param space_id: 空间 ID
        :param plugin_keys: list[str]，格式 "{plugin_type}:{source_key}:{plugin_code}"
        :param content: 用户额外提的需求，追加到固定 prompt 末尾
        :param thread_id: 智能体会话 id；传了就延续该会话（智能体读取历史记录）
        :return: {
            "result": "patch"|"empty"|"error",
            "message": str,
            "thread_id": str, 智能体会话 id，下次追问时传回
            "new_directories": [...],
            "assignments": {...},
            "omit_directory_ids": [str, ...], 要从目录树里去掉的空目录
        }
        """
        empty = {
            "result": cls.RESULT_EMPTY,
            "message": "",
            "thread_id": thread_id or "",
            "new_directories": [],
            "assignments": {},
            "omit_directory_ids": [],
        }
        if not plugin_keys:
            return empty
        try:
            return cls._request_manage_plan(
                space_id=space_id, plugin_keys=plugin_keys, content=content, thread_id=thread_id
            )
        except Exception as exc:  # noqa: BLE001 统一兜底，不让未知异常中断调用方流程
            logger.exception("AI 目录整理请求失败: space_id=%s", space_id)
            return {**empty, "result": cls.RESULT_ERROR, "message": str(exc)}

    @classmethod
    def _request_manage_plan(cls, space_id, plugin_keys, content=None, thread_id=None):
        """向智能体请求"目录结构 + 插件归属"的整理方案，并解析、校验。

        `thread_id` 传了就延续会话；智能体响应里的 `threadId` 会一起返回给调用方。
        """
        prompt = cls._build_manage_prompt(space_id=space_id, plugin_keys=plugin_keys, content=content)
        resp = AiAgentClient.chat(prompt, thread_id=thread_id)
        data = cls._parse_json(resp["text"])
        plan = cls._validate_manage_plan(space_id=space_id, plugin_keys=plugin_keys, data=data)
        plan["thread_id"] = resp["thread_id"]
        if plan["result"] == cls.RESULT_ERROR:
            return plan
        if not plan["new_directories"] and not plan["assignments"] and not plan["omit_directory_ids"]:
            logger.info("AI 目录整理未给出建议: space_id=%s", space_id)
            return {**plan, "result": cls.RESULT_EMPTY, "message": "AI 未给出整理建议"}
        return plan

    @classmethod
    def _validate_patch(cls, space_id, plugin_keys, raw_items):
        """校验模型给的建议，只保留合法项。

        - 插件 key 必须在本次请求的范围内（防越界 / 防幻觉）
        - 目录 id 必须真实存在于本空间（防幻觉）；`null` 表示未分类，合法
        """
        valid_keys = set(plugin_keys)
        valid_directory_ids = set(
            PluginDirectory.objects.filter(space_id=space_id).values_list("id", flat=True)
        )
        patch = {}
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            if key not in valid_keys:
                continue
            directory_id = item.get("directory_id")
            if directory_id is not None:
                try:
                    directory_id = int(directory_id)
                except (TypeError, ValueError):
                    continue
                if directory_id not in valid_directory_ids:
                    continue
            patch[key] = directory_id
        return patch
