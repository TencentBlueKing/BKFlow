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

from pipeline.component_framework.models import ComponentModel

from bkflow.exceptions import ValidationError
from bkflow.plugin.models import OpenPluginCatalogIndex
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService
from bkflow.plugin_catalog.models import PluginType

logger = logging.getLogger(__name__)


class PluginVersionDiffService:
    """
    版本切换 / 换插件 的参数差异计算。

    纯计算工具：只读 schema、不读写 `TemplatePluginReference`/`SpacePluginCatalogEntry`，
    不产生任何管理侧副作用。

    关键简化点：参数按 `key` **精确匹配**，不做模糊/重命名猜测。
    新版本里改了参数名 = 旧参数被移除 + 新参数新增，用户需要按"旧版本参数"抽屉手动补值。
    """

    # 插件目录的 plugin_type -> PluginSchemaService 内部的 plugin_type
    SCHEMA_TYPE_MAP = {
        PluginType.BUILTIN: "component",
        PluginType.BK_PLUGIN: "remote_plugin",
        PluginType.API: "uniform_api",
    }

    @classmethod
    def diff(cls, space_id, from_identity, to_identity, current_inputs=None):
        """
        :param from_identity: {"plugin_type","source_key","plugin_code","plugin_version"}
        :param to_identity: 同上
        :param current_inputs: 当前节点上已有的输入参数值 {key: value}
        :return: {"kept","added","removed","mapped_values","old_schema_inputs","output_key_bindings_unchanged"}
        """
        from_schema, from_outputs = cls._get_schema(space_id, from_identity)
        to_schema, to_outputs = cls._get_schema(space_id, to_identity)

        from_keys = list(from_schema.keys())
        to_keys = list(to_schema.keys())
        kept = [key for key in from_keys if key in to_schema]
        added = [key for key in to_keys if key not in from_schema]
        removed = [key for key in from_keys if key not in to_schema]

        current_inputs = current_inputs or {}
        mapped_values = {key: current_inputs[key] for key in kept if key in current_inputs}

        return {
            "kept": kept,
            "added": added,
            "removed": removed,
            "mapped_values": mapped_values,
            "old_schema_inputs": from_schema,
            "output_key_bindings_unchanged": set(from_outputs) == set(to_outputs),
        }

    @classmethod
    def list_versions(cls, space_id, plugin_type, source_key, plugin_code):
        """
        返回该插件的可选版本列表。

        - `api`：读 `OpenPluginCatalogIndex.versions` / `default_version` / `latest_version`；
        - `builtin`：内置组件的版本由 `ComponentModel` 自身决定，透传其全部版本；
        - `bk_plugin`：蓝鲸标准插件目前没有版本模型，先返回「仅当前版本」的兜底结果。
        """
        source_key = source_key or ""

        if plugin_type == PluginType.API:
            catalog = (
                OpenPluginCatalogIndex.objects.filter(
                    space_id=space_id, source_key=source_key, plugin_id=plugin_code
                )
                .order_by("-update_time", "-id")
                .first()
            )
            if catalog is None:
                return {"versions": [], "default_version": "", "latest_version": ""}
            return {
                "versions": list(catalog.versions or []),
                "default_version": catalog.default_version or "",
                "latest_version": catalog.latest_version or "",
            }

        if plugin_type == PluginType.BUILTIN:
            versions = list(
                ComponentModel.objects.filter(code=plugin_code, status=True).values_list("version", flat=True)
            )
            return {
                "versions": versions,
                "default_version": versions[-1] if versions else "",
                "latest_version": versions[-1] if versions else "",
            }

        return {"versions": [], "default_version": "", "latest_version": ""}

    # ------------------------------------------------------------------ 内部方法 ----

    @classmethod
    def _get_schema(cls, space_id, identity):
        """取指定插件版本的 inputs/outputs schema，返回 ({key: schema}, {output_key})。"""
        plugin_type = identity.get("plugin_type")
        schema_type = cls.SCHEMA_TYPE_MAP.get(plugin_type)
        if not schema_type:
            raise ValidationError(f"不支持的插件类型: {plugin_type}")

        service = PluginSchemaService(space_id=space_id)
        try:
            plugin_info = service.get_plugin_schema(
                code=identity.get("plugin_code"),
                version=identity.get("plugin_version") or None,
                plugin_type=schema_type,
                source_key=identity.get("source_key") or None,
            )
        except ValueError as exc:
            raise ValidationError(str(exc))

        inputs = {}
        for item in plugin_info.get("inputs") or []:
            key = item.get("key")
            if key:
                inputs[key] = item
        outputs = {
            item.get("key")
            for item in (plugin_info.get("outputs") or [])
            if item.get("key")
        }
        return inputs, outputs
