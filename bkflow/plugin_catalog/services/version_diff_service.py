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

    关键简化点：**只管输入参数**，不管输出。
    判定「没变」的标准：**key 和中文名都相同**才算保留（`kept`），其余一律算新增（`added`）——
    不做隐式的改名映射，改了 key 的参数让用户按「旧版本参数」抽屉手填。
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
        :return: {"kept","added","inputs"}
        """
        from_schema, _ = cls._get_schema(space_id, from_identity)
        to_schema, _ = cls._get_schema(space_id, to_identity)

        # 判定「没变」的标准很严：**key 和中文名都相同**才算保留。
        # 只要 key 变了（哪怕中文名一样）就当新增——前端按"新增参数"提示用户手填，
        # 不做隐式的改名映射。
        kept = []
        for from_key, field in from_schema.items():
            to_field = to_schema.get(from_key)
            if to_field is not None and to_field.get("name") == field.get("name"):
                kept.append(from_key)
        added = [key for key in to_schema if key not in kept]

        # 旧版本输入参数 + 当前现值合成一份，供右侧「旧版本参数」抽屉渲染。
        # to_key 只是"这个旧参数在新版本里有个对得上的 key"的提示（key 或中文名对得上就给），
        # **不参与 kept / added 的判定**，前端用不用都行。
        to_key_by_name = {
            field.get("name"): key for key, field in to_schema.items() if field.get("name")
        }
        current_inputs = current_inputs or {}
        inputs = {}
        for from_key, field in from_schema.items():
            item = dict(field)
            if from_key in current_inputs:
                item["value"] = current_inputs[from_key]
            target_key = from_key if from_key in to_schema else to_key_by_name.get(field.get("name"))
            if target_key and target_key != from_key:
                item["to_key"] = target_key
            inputs[from_key] = item

        return {
            "kept": kept,
            "added": added,
            "inputs": inputs,
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
