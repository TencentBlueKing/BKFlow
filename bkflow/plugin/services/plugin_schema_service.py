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
import re

from django.conf import settings
from django.core.cache import cache
from pipeline.component_framework.library import ComponentLibrary
from pipeline.component_framework.models import ComponentModel

from bkflow.bk_plugin.models import AuthStatus, BKPlugin, BKPluginAuthorization
from bkflow.constants import ALL_SPACE
from bkflow.plugin.models import SpacePluginConfig as SpacePluginConfigModel
from bkflow.plugin.space_plugin_config_parser import SpacePluginConfigParser
from bkflow.space.configs import SpacePluginConfig
from bkflow.space.models import SpaceConfig
from plugin_service.plugin_client import PluginServiceApiClient

logger = logging.getLogger("root")

PLUGIN_SCHEMA_CACHE_TTL = 300

WRAPPER_CODES = {"remote_plugin", "uniform_api", "subprocess_plugin"}

EXTERNAL_PLUGIN_TYPE_MAP = {
    "component": "component",
    "remote_plugin": "blueking",
    "uniform_api": "uniform_api",
}

INTERNAL_TO_EXTERNAL_MAP = {v: k for k, v in EXTERNAL_PLUGIN_TYPE_MAP.items()}


class PluginSchemaService:
    """统一查询三种插件类型的信息和参数 schema"""

    def __init__(self, space_id, username=None, scope_type=None, scope_id=None):
        self.space_id = space_id
        self.username = username
        self.scope_type = scope_type
        self.scope_id = scope_id

    def list_plugins(self, keyword=None, plugin_type=None, without_detail=True, limit=100, offset=0):
        """
        查询空间可用插件列表，聚合三种来源。

        :param keyword: 模糊搜索 code 或 name
        :param plugin_type: 按类型过滤
        :param without_detail: True 只返回摘要，False 返回完整 schema
        :param limit: 分页大小
        :param offset: 分页偏移
        :return: (plugins_list, total_count)
        """
        all_plugins = []

        type_handlers = {
            "component": self._list_component_plugins,
            "remote_plugin": self._list_remote_plugins,
            "uniform_api": self._list_uniform_api_plugins,
        }

        if plugin_type:
            handlers = {plugin_type: type_handlers[plugin_type]}
        else:
            handlers = type_handlers

        for ptype, handler in handlers.items():
            try:
                plugins = handler(keyword=keyword)
                all_plugins.extend(plugins)
            except Exception:
                logger.exception("查询 %s 类型插件列表失败", ptype)

        if not without_detail:
            self._fill_schema_batch(all_plugins)

        total_count = len(all_plugins)
        limit = min(limit, 200)
        paginated = all_plugins[offset : offset + limit]
        return paginated, total_count

    def get_plugin_schema(self, code, version=None, plugin_type=None):
        """
        查询单个插件的完整 schema。

        :param code: 插件 code
        :param version: 指定版本（仅 component 生效）
        :param plugin_type: 消歧用
        :return: 统一格式的插件信息 dict
        :raises: ValueError
        """
        if plugin_type:
            plugin_info = self._get_single_by_type(code, plugin_type, version=version)
        else:
            plugin_info = self._get_single_auto_resolve(code, version=version)

        self._fill_schema_single(plugin_info, strict=True)
        return plugin_info

    # === 列表查询 ===

    def _list_component_plugins(self, keyword=None):
        qs = ComponentModel.objects.filter(status=True).exclude(code__in=WRAPPER_CODES)

        system_allow_list = SpacePluginConfigModel.objects.get_space_allow_list(self.space_id)
        space_plugins = set(settings.SPACE_PLUGIN_LIST) - set(system_allow_list)
        if space_plugins:
            qs = qs.exclude(code__in=list(space_plugins))

        scope_code = "{}_{}".format(self.scope_type, self.scope_id) if self.scope_type and self.scope_id else None
        space_plugin_config = SpaceConfig.get_config(space_id=self.space_id, config_name=SpacePluginConfig.name)
        if space_plugin_config and scope_code:
            parser = SpacePluginConfigParser(space_plugin_config)
            qs = parser.get_filtered_plugin_qs(scope_code, qs)

        results = []
        seen_codes = {}
        for obj in qs:
            if obj.code in seen_codes:
                continue
            parts = obj.name.split("-", 1) if "-" in obj.name else ["", obj.name]
            group_name = parts[0].strip() if len(parts) > 1 else ""
            plugin_name = parts[1].strip() if len(parts) > 1 else parts[0].strip()

            info = {
                "code": obj.code,
                "name": plugin_name,
                "plugin_type": "component",
                "version": obj.version,
                "description": "",
                "group_name": group_name,
            }

            if keyword and not self._match_keyword(info, keyword):
                continue

            seen_codes[obj.code] = True
            info["_component_version"] = obj.version
            results.append(info)
        return results

    def _get_component_schema(self, code, version=None):
        """从 ComponentLibrary 提取 inputs_format / outputs_format"""
        versions = list(ComponentModel.objects.filter(code=code, status=True).values_list("version", flat=True))
        if not versions:
            raise ValueError("未找到内置插件 code '{}'".format(code))

        if version and version in versions:
            target_version = version
        else:
            target_version = self._pick_latest_version(versions)

        try:
            component_cls = ComponentLibrary.get_component_class(code, target_version)
        except Exception as e:
            raise ValueError("获取内置插件 '{}' v{} 的组件类失败: {}".format(code, target_version, e))

        inputs = self._normalize_io_fields(component_cls.inputs_format())
        outputs = self._normalize_io_fields(component_cls.outputs_format(), is_output=True)

        return {
            "inputs": inputs,
            "outputs": outputs,
            "description": getattr(component_cls, "desc", "") or "",
        }

    @staticmethod
    def _normalize_io_fields(fields, is_output=False):
        """将各类型的 IO 字段列表标准化为统一格式"""
        result = []
        for f in fields:
            item = {
                "key": f.get("key", ""),
                "name": f.get("name", ""),
                "type": f.get("type", "string"),
                "description": f.get("description", f.get("desc", "")),
            }
            if not is_output:
                item["required"] = f.get("required", False)
            if "default" in f:
                item["default"] = f["default"]
            if f.get("schema"):
                item["schema"] = f["schema"]
            result.append(item)
        return result

    def _list_remote_plugins(self, keyword=None):
        plugins = BKPlugin.objects.filter()
        authorized = BKPluginAuthorization.objects.filter(status=AuthStatus.authorized.value)
        auth_map = {a.code: a.white_list for a in authorized}

        results = []
        for plugin in plugins:
            white_list = auth_map.get(plugin.code)
            if white_list is None:
                continue
            if ALL_SPACE not in white_list and str(self.space_id) not in white_list:
                continue

            info = {
                "code": plugin.code,
                "name": plugin.name,
                "plugin_type": "remote_plugin",
                "version": "",
                "description": plugin.introduction or "",
                "group_name": "",
            }

            if keyword and not self._match_keyword(info, keyword):
                continue

            results.append(info)
        return results

    def _get_remote_plugin_schema(self, code):
        """从 PluginServiceApiClient.get_meta() 提取 schema，带缓存"""
        cache_key = "plugin_schema:remote_plugin:{}".format(code)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        client = PluginServiceApiClient(code)
        result = client.get_meta()
        if not result.get("result"):
            raise ValueError("查询蓝鲸标准插件 '{}' meta 失败: {}".format(code, result.get("message")))

        data = result.get("data", {})
        versions = data.get("versions") or []
        latest_version = versions[-1] if versions else ""

        inputs = self._normalize_io_fields(data.get("inputs", []))
        outputs = self._normalize_io_fields(data.get("outputs", []), is_output=True)

        schema_result = {
            "version": latest_version,
            "inputs": inputs,
            "outputs": outputs,
        }
        cache.set(cache_key, schema_result, PLUGIN_SCHEMA_CACHE_TTL)
        return schema_result

    def _list_uniform_api_plugins(self, keyword=None):
        raise NotImplementedError("Task 4")

    def _get_single_by_type(self, code, plugin_type, version=None):
        raise NotImplementedError("Task 5")

    def _get_single_auto_resolve(self, code, version=None):
        raise NotImplementedError("Task 5")

    def _fill_schema_batch(self, plugins):
        raise NotImplementedError("Task 5")

    def _fill_schema_single(self, plugin_info, strict=False):
        raise NotImplementedError("Task 5")

    @staticmethod
    def _match_keyword(info, keyword):
        kw = keyword.lower()
        return kw in info["code"].lower() or kw in info["name"].lower()

    @staticmethod
    def _pick_latest_version(versions):
        """选择最新版本号（语义化排序）"""

        def parse(v):
            v = v.lstrip("vV")
            m = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", v)
            return (int(m.group(1) or 0), int(m.group(2) or 0), int(m.group(3) or 0)) if m else (0, 0, 0)

        return max(versions, key=parse) if versions else "legacy"
