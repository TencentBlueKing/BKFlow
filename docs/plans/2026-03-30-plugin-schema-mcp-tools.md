# Plugin Schema MCP Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement three APIGW endpoints (`list_plugins`, `get_plugin_schema`, `validate_a2flow`) that let AI Agents discover available plugins and their parameter schemas before generating a2flow workflows.

**Architecture:** Service layer (`PluginSchemaService`) aggregates three plugin types (built-in component, remote_plugin, uniform_api) into a unified schema format. Three APIGW views call this service. Caching via Django cache framework protects against excessive remote calls. `validate_a2flow` is a standalone view that dry-runs the existing `A2FlowV2Converter`.

**Tech Stack:** Django 3.2, DRF, bamboo-pipeline ComponentLibrary, pytest, unittest.mock

**Spec:** `docs/specs/2026-03-30-plugin-schema-mcp-tools-design.md`

**TAPD:** Run `tapd-workitem-sync` before first commit to obtain story ID.

---

## File Structure

### New Files

| File | Responsibility |
|---|---|
| `bkflow/plugin/services/__init__.py` | Package init |
| `bkflow/plugin/services/plugin_schema_service.py` | `PluginSchemaService` — unified plugin query + schema extraction for all three types |
| `bkflow/apigw/serializers/plugin.py` | `ListPluginsSerializer`, `GetPluginSchemaSerializer`, `ValidateA2FlowSerializer` |
| `bkflow/apigw/views/list_plugins.py` | `list_plugins` APIGW view |
| `bkflow/apigw/views/get_plugin_schema.py` | `get_plugin_schema` APIGW view |
| `bkflow/apigw/views/validate_a2flow.py` | `validate_a2flow` APIGW view |
| `bkflow/apigw/docs/zh/list_plugins.md` | API documentation |
| `bkflow/apigw/docs/zh/get_plugin_schema.md` | API documentation |
| `bkflow/apigw/docs/zh/validate_a2flow.md` | API documentation |
| `tests/interface/plugin/__init__.py` | Package init |
| `tests/interface/plugin/services/__init__.py` | Package init |
| `tests/interface/plugin/services/test_plugin_schema_service.py` | Service layer tests |
| `tests/interface/apigw/test_list_plugins.py` | View tests |
| `tests/interface/apigw/test_get_plugin_schema.py` | View tests |
| `tests/interface/apigw/test_validate_a2flow.py` | View tests |

### Modified Files

| File | Change |
|---|---|
| `bkflow/apigw/urls.py` | Register 3 new URL patterns |

---

### Task 1: Service Layer Foundation — PluginSchemaService Skeleton

**Files:**
- Create: `bkflow/plugin/services/__init__.py`
- Create: `bkflow/plugin/services/plugin_schema_service.py`
- Create: `tests/interface/plugin/__init__.py`
- Create: `tests/interface/plugin/services/__init__.py`
- Create: `tests/interface/plugin/services/test_plugin_schema_service.py`

- [ ] **Step 1: Write failing test for component plugin listing**

```python
# tests/interface/plugin/services/test_plugin_schema_service.py
import pytest
from unittest.mock import MagicMock, patch

from bkflow.plugin.services.plugin_schema_service import PluginSchemaService


class TestListComponentPlugins:
    """测试内置插件列表查询"""

    @patch("bkflow.plugin.services.plugin_schema_service.SpacePluginConfigModel")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_list_component_plugins_basic(self, mock_cm, mock_sc, mock_spcm):
        """测试基本的内置插件列表查询"""
        mock_spcm.objects.get_space_allow_list.return_value = []
        mock_sc.get_config.return_value = None

        mock_obj1 = MagicMock()
        mock_obj1.code = "job_fast_execute_script"
        mock_obj1.name = "作业平台(JOB)-快速执行脚本"
        mock_obj1.version = "v1.0.0"

        mock_obj2 = MagicMock()
        mock_obj2.code = "bk_notify"
        mock_obj2.name = "蓝鲸服务(BK)-发送通知"
        mock_obj2.version = "v1.0.0"

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_obj1, mock_obj2]))
        mock_qs.count.return_value = 2
        mock_cm.objects.filter.return_value.exclude.return_value = mock_qs

        service = PluginSchemaService(space_id=1)
        plugins, count = service.list_plugins(plugin_type="component", without_detail=True)

        assert count == 2
        assert plugins[0]["code"] == "job_fast_execute_script"
        assert plugins[0]["plugin_type"] == "component"
        assert plugins[0]["name"] == "快速执行脚本"
        assert plugins[0]["group_name"] == "作业平台(JOB)"
        assert "inputs" not in plugins[0]

    @patch("bkflow.plugin.services.plugin_schema_service.SpacePluginConfigModel")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_list_component_plugins_keyword_filter(self, mock_cm, mock_sc, mock_spcm):
        """测试 keyword 搜索过滤"""
        mock_spcm.objects.get_space_allow_list.return_value = []
        mock_sc.get_config.return_value = None

        mock_obj1 = MagicMock()
        mock_obj1.code = "job_fast_execute_script"
        mock_obj1.name = "作业平台(JOB)-快速执行脚本"
        mock_obj1.version = "v1.0.0"

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_obj1]))
        mock_qs.count.return_value = 1
        mock_cm.objects.filter.return_value.exclude.return_value = mock_qs

        service = PluginSchemaService(space_id=1)
        plugins, count = service.list_plugins(plugin_type="component", keyword="脚本", without_detail=True)

        assert count == 1
        assert plugins[0]["code"] == "job_fast_execute_script"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/interface/plugin/services/test_plugin_schema_service.py::TestListComponentPlugins -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bkflow.plugin.services'`

- [ ] **Step 3: Create package structure and service skeleton**

```python
# bkflow/plugin/services/__init__.py
```

```python
# bkflow/plugin/services/plugin_schema_service.py
import logging

from django.conf import settings
from pipeline.component_framework.library import ComponentLibrary
from pipeline.component_framework.models import ComponentModel

from django.core.cache import cache
from pipeline.component_framework.library import ComponentLibrary
from pipeline.component_framework.models import ComponentModel

from bkflow.bk_plugin.models import AuthStatus, BKPlugin, BKPluginAuthorization
from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
from bkflow.plugin.models import SpacePluginConfig as SpacePluginConfigModel
from bkflow.plugin.space_plugin_config_parser import SpacePluginConfigParser
from bkflow.space.configs import ApiGatewayCredentialConfig, SpacePluginConfig, UniformApiConfig, UniformAPIConfigHandler
from bkflow.space.models import Credential, SpaceConfig

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

    def _list_remote_plugins(self, keyword=None):
        raise NotImplementedError("Task 3")

    def _list_uniform_api_plugins(self, keyword=None):
        raise NotImplementedError("Task 4")

    def _get_single_by_type(self, code, plugin_type, version=None):
        raise NotImplementedError("Task 5")

    def _get_single_auto_resolve(self, code, version=None):
        raise NotImplementedError("Task 5")

    def _fill_schema_batch(self, plugins):
        raise NotImplementedError("Task 5")

    def _fill_schema_single(self, plugin_info):
        raise NotImplementedError("Task 5")

    @staticmethod
    def _match_keyword(info, keyword):
        kw = keyword.lower()
        return kw in info["code"].lower() or kw in info["name"].lower()

    @staticmethod
    def _pick_latest_version(versions):
        """选择最新版本号（语义化排序）"""
        import re

        def parse(v):
            v = v.lstrip("vV")
            m = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", v)
            return (int(m.group(1) or 0), int(m.group(2) or 0), int(m.group(3) or 0)) if m else (0, 0, 0)

        return max(versions, key=parse) if versions else "legacy"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/interface/plugin/services/test_plugin_schema_service.py::TestListComponentPlugins -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bkflow/plugin/services/ tests/interface/plugin/
git commit -m "feat(plugin): 添加 PluginSchemaService 骨架和内置插件列表查询 --story=TAPD_ID"
```

---

### Task 2: Component Plugin Schema Extraction

**Files:**
- Modify: `bkflow/plugin/services/plugin_schema_service.py`
- Modify: `tests/interface/plugin/services/test_plugin_schema_service.py`

- [ ] **Step 1: Write failing tests for component schema**

```python
# tests/interface/plugin/services/test_plugin_schema_service.py — append

class TestComponentSchema:
    """测试内置插件 schema 提取"""

    @patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_component_schema(self, mock_cm, mock_lib):
        """测试从 ComponentLibrary 提取 inputs/outputs"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0"]

        mock_component = MagicMock()
        mock_component.desc = "执行脚本"
        mock_component.inputs_format.return_value = [
            {"key": "script_content", "name": "脚本内容", "type": "string", "required": True, "schema": {}},
        ]
        mock_component.outputs_format.return_value = [
            {"key": "_result", "name": "执行结果", "type": "bool", "schema": {}},
        ]
        mock_lib.get_component_class.return_value = mock_component

        service = PluginSchemaService(space_id=1)
        schema = service._get_component_schema("job_fast_execute_script")

        assert schema["inputs"][0]["key"] == "script_content"
        assert schema["outputs"][0]["key"] == "_result"
        assert schema["description"] == "执行脚本"

    @patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_component_schema_with_version(self, mock_cm, mock_lib):
        """测试指定版本查询"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0", "v2.0.0"]

        mock_component = MagicMock()
        mock_component.desc = "v2 版本"
        mock_component.inputs_format.return_value = []
        mock_component.outputs_format.return_value = []
        mock_lib.get_component_class.return_value = mock_component

        service = PluginSchemaService(space_id=1)
        schema = service._get_component_schema("test_code", version="v2.0.0")

        mock_lib.get_component_class.assert_called_with("test_code", "v2.0.0")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/interface/plugin/services/test_plugin_schema_service.py::TestComponentSchema -v`
Expected: FAIL

- [ ] **Step 3: Implement `_get_component_schema`**

Add to `PluginSchemaService` in `plugin_schema_service.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/interface/plugin/services/test_plugin_schema_service.py::TestComponentSchema -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bkflow/plugin/services/plugin_schema_service.py tests/interface/plugin/services/test_plugin_schema_service.py
git commit -m "feat(plugin): 添加内置插件 schema 提取 --story=TAPD_ID"
```

---

### Task 3: Remote Plugin (BKPlugin) List + Schema

**Files:**
- Modify: `bkflow/plugin/services/plugin_schema_service.py`
- Modify: `tests/interface/plugin/services/test_plugin_schema_service.py`

- [ ] **Step 1: Write failing tests for remote plugin listing and schema**

```python
# tests/interface/plugin/services/test_plugin_schema_service.py — append

class TestRemotePlugins:
    """测试蓝鲸标准插件查询"""

    @patch("bkflow.plugin.services.plugin_schema_service.BKPluginAuthorization")
    @patch("bkflow.plugin.services.plugin_schema_service.BKPlugin")
    def test_list_remote_plugins(self, mock_bp, mock_auth):
        """测试蓝鲸插件列表"""
        mock_plugin = MagicMock()
        mock_plugin.code = "my_plugin"
        mock_plugin.name = "我的插件"
        mock_plugin.introduction = "自定义插件"

        mock_bp.objects.filter.return_value = [mock_plugin]

        mock_auth_obj = MagicMock()
        mock_auth_obj.code = "my_plugin"
        mock_auth_obj.white_list = ["*"]
        mock_auth.objects.filter.return_value = [mock_auth_obj]

        service = PluginSchemaService(space_id=1)
        results = service._list_remote_plugins()

        assert len(results) == 1
        assert results[0]["code"] == "my_plugin"
        assert results[0]["plugin_type"] == "remote_plugin"
        assert results[0]["description"] == "自定义插件"

    @patch("bkflow.plugin.services.plugin_schema_service.BKPluginAuthorization")
    @patch("bkflow.plugin.services.plugin_schema_service.BKPlugin")
    def test_list_remote_plugins_auth_filter(self, mock_bp, mock_auth):
        """测试蓝鲸插件授权过滤 — 非授权空间的插件不展示"""
        mock_plugin = MagicMock()
        mock_plugin.code = "restricted_plugin"
        mock_plugin.name = "受限插件"
        mock_plugin.introduction = ""

        mock_bp.objects.filter.return_value = [mock_plugin]

        mock_auth_obj = MagicMock()
        mock_auth_obj.code = "restricted_plugin"
        mock_auth_obj.white_list = ["999"]
        mock_auth.objects.filter.return_value = [mock_auth_obj]

        service = PluginSchemaService(space_id=1)
        results = service._list_remote_plugins()

        assert len(results) == 0

    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.PluginServiceApiClient")
    def test_get_remote_plugin_schema(self, mock_client_cls, mock_cache):
        """测试蓝鲸插件 schema 获取"""
        mock_cache.get.return_value = None

        mock_client = MagicMock()
        mock_client.get_meta.return_value = {
            "result": True,
            "data": {
                "versions": ["1.0.0", "1.2.0"],
                "inputs": [
                    {"key": "param1", "name": "参数1", "type": "string", "required": True},
                ],
                "outputs": [
                    {"key": "result_data", "name": "结果", "type": "string"},
                ],
            },
        }
        mock_client_cls.return_value = mock_client

        service = PluginSchemaService(space_id=1)
        schema = service._get_remote_plugin_schema("my_plugin")

        assert schema["inputs"][0]["key"] == "param1"
        assert schema["outputs"][0]["key"] == "result_data"
        assert schema["version"] == "1.2.0"
        mock_cache.set.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/interface/plugin/services/test_plugin_schema_service.py::TestRemotePlugins -v`
Expected: FAIL

- [ ] **Step 3: Implement remote plugin list and schema methods**

Add to `PluginSchemaService`:

```python
def _list_remote_plugins(self, keyword=None):
    plugins = BKPlugin.objects.filter()
    authorized = BKPluginAuthorization.objects.filter(status=AuthStatus.authorized.value)
    auth_map = {a.code: a.white_list for a in authorized}

    results = []
    for plugin in plugins:
        white_list = auth_map.get(plugin.code)
        if white_list is None:
            continue
        if "*" not in white_list and str(self.space_id) not in white_list:
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
    from plugin_service.plugin_client import PluginServiceApiClient

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
```

Also add the `cache` import and `PluginServiceApiClient` to the lazy import section.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/interface/plugin/services/test_plugin_schema_service.py::TestRemotePlugins -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bkflow/plugin/services/plugin_schema_service.py tests/interface/plugin/services/test_plugin_schema_service.py
git commit -m "feat(plugin): 添加蓝鲸标准插件列表和 schema 查询 --story=TAPD_ID"
```

---

### Task 4: Uniform API Plugin List + Schema

**Files:**
- Modify: `bkflow/plugin/services/plugin_schema_service.py`
- Modify: `tests/interface/plugin/services/test_plugin_schema_service.py`

- [ ] **Step 1: Write failing tests for uniform API plugins**

```python
# tests/interface/plugin/services/test_plugin_schema_service.py — append

class TestUniformApiPlugins:
    """测试 API 插件查询"""

    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.Credential")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIClient")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    def test_list_uniform_api_plugins(self, mock_sc, mock_client_cls, mock_cred, mock_cache):
        """测试 API 插件列表查询"""
        mock_cache.get.return_value = None

        mock_sc.get_config.side_effect = lambda space_id, config_name, scope=None: {
            "uniform_api": {"api": {"default": {"meta_apis": "http://example.com/meta_apis"}}},
            "api_gateway_credential": "test_cred",
        }.get(config_name)

        mock_cred_obj = MagicMock()
        mock_cred_obj.content = {"bk_app_code": "app", "bk_app_secret": "secret"}
        mock_cred.objects.filter.return_value.first.return_value = mock_cred_obj

        mock_client = MagicMock()
        list_resp = MagicMock()
        list_resp.json_resp = {
            "data": {
                "total": 1,
                "apis": [
                    {"id": "sops_execute", "name": "标准运维执行", "meta_url": "http://example.com/meta/sops"}
                ],
            }
        }
        mock_client.request.return_value = list_resp
        mock_client_cls.return_value = mock_client

        service = PluginSchemaService(space_id=1)
        results = service._list_uniform_api_plugins()

        assert len(results) == 1
        assert results[0]["code"] == "sops_execute"
        assert results[0]["plugin_type"] == "uniform_api"

    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.Credential")
    @patch("bkflow.plugin.services.plugin_schema_service.UniformAPIClient")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    def test_get_uniform_api_schema(self, mock_sc, mock_client_cls, mock_cred, mock_cache):
        """测试 API 插件 schema 获取"""
        mock_cache.get.return_value = None

        mock_sc.get_config.side_effect = lambda space_id, config_name, scope=None: {
            "uniform_api": {"api": {"default": {"meta_apis": "http://example.com/meta_apis"}}},
            "api_gateway_credential": "test_cred",
        }.get(config_name)

        mock_cred_obj = MagicMock()
        mock_cred_obj.content = {"bk_app_code": "app", "bk_app_secret": "secret"}
        mock_cred.objects.filter.return_value.first.return_value = mock_cred_obj

        mock_client = MagicMock()

        list_resp = MagicMock()
        list_resp.json_resp = {
            "data": {
                "total": 1,
                "apis": [
                    {"id": "sops_execute", "name": "标准运维执行", "meta_url": "http://example.com/meta/sops"}
                ],
            }
        }
        meta_resp = MagicMock()
        meta_resp.json_resp = {
            "data": {
                "id": "sops_execute",
                "name": "标准运维执行",
                "desc": "执行标准运维流程",
                "inputs": [
                    {"key": "biz_id", "name": "业务ID", "type": "int", "required": True},
                ],
            }
        }
        mock_client.request.side_effect = [list_resp, meta_resp]
        mock_client.validate_response_data = MagicMock()
        mock_client_cls.return_value = mock_client

        service = PluginSchemaService(space_id=1)
        schema = service._get_uniform_api_schema("sops_execute")

        assert schema["inputs"][0]["key"] == "biz_id"
        assert schema["description"] == "执行标准运维流程"
        mock_cache.set.assert_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/interface/plugin/services/test_plugin_schema_service.py::TestUniformApiPlugins -v`
Expected: FAIL

- [ ] **Step 3: Implement uniform API plugin list and schema methods**

Add to `PluginSchemaService`:

```python
def _list_uniform_api_plugins(self, keyword=None):
    cache_key = "plugin_list:uniform_api:{}".format(self.space_id)
    cached = cache.get(cache_key)
    if cached is not None:
        api_list = cached
    else:
        uniform_api_config = SpaceConfig.get_config(
            space_id=self.space_id, config_name=UniformApiConfig.name
        )
        if not uniform_api_config:
            return []

        config = UniformAPIConfigHandler(uniform_api_config).handle()
        api_key = UniformApiConfig.Keys.DEFAULT_API_KEY.value
        meta_apis_url = config.api.get(api_key, {}).get(UniformApiConfig.Keys.META_APIS.value)
        if not meta_apis_url:
            return []

        scope = "{}_{}".format(self.scope_type, self.scope_id) if self.scope_type and self.scope_id else None
        credential_name = SpaceConfig.get_config(
            space_id=self.space_id, config_name=ApiGatewayCredentialConfig.name, scope=scope
        )
        credential = Credential.objects.filter(space_id=self.space_id, name=credential_name).first()
        if not credential:
            return []

        client = UniformAPIClient()
        headers = client.gen_default_apigw_header(
            app_code=credential.content["bk_app_code"],
            app_secret=credential.content["bk_app_secret"],
            username=self.username or "admin",
        )
        list_result = client.request(
            url=meta_apis_url, method="GET",
            data={"limit": 200, "offset": 0}, headers=headers,
            username=self.username or "admin",
        )
        client.validate_response_data(
            list_result.json_resp.get("data", {}),
            client.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA,
        )
        api_list = list_result.json_resp["data"]["apis"]
        cache.set(cache_key, api_list, PLUGIN_SCHEMA_CACHE_TTL)

    results = []
    for api_item in api_list:
        info = {
            "code": api_item["id"],
            "name": api_item["name"],
            "plugin_type": "uniform_api",
            "version": "",
            "description": api_item.get("description", ""),
            "group_name": api_item.get("category", ""),
            "_meta_url": api_item.get("meta_url", ""),
        }
        if keyword and not self._match_keyword(info, keyword):
            continue
        results.append(info)
    return results

def _get_uniform_api_schema(self, code):
    """从 meta_url 提取 schema，带缓存"""
    cache_key = "plugin_schema:uniform_api:{}:{}".format(self.space_id, code)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    api_list = self._list_uniform_api_plugins()
    api_item = next((a for a in api_list if a["code"] == code), None)
    if not api_item or not api_item.get("_meta_url"):
        raise ValueError("未找到 API 插件 '{}'".format(code))

    scope = "{}_{}".format(self.scope_type, self.scope_id) if self.scope_type and self.scope_id else None
    credential_name = SpaceConfig.get_config(
        space_id=self.space_id, config_name=ApiGatewayCredentialConfig.name, scope=scope
    )
    credential = Credential.objects.filter(space_id=self.space_id, name=credential_name).first()
    if not credential:
        raise ValueError("空间缺少 API Gateway 凭证，无法查询 API 插件 '{}'".format(code))

    client = UniformAPIClient()
    headers = client.gen_default_apigw_header(
        app_code=credential.content["bk_app_code"],
        app_secret=credential.content["bk_app_secret"],
        username=self.username or "admin",
    )
    meta_result = client.request(
        url=api_item["_meta_url"], method="GET", data={}, headers=headers,
        username=self.username or "admin",
    )
    client.validate_response_data(
        meta_result.json_resp.get("data", {}),
        client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA,
    )
    meta = meta_result.json_resp["data"]

    inputs = self._normalize_io_fields(meta.get("inputs", []))
    outputs = self._normalize_io_fields(meta.get("outputs", []), is_output=True)

    schema_result = {
        "version": meta.get("version", ""),
        "description": meta.get("desc", ""),
        "inputs": inputs,
        "outputs": outputs,
    }
    cache.set(cache_key, schema_result, PLUGIN_SCHEMA_CACHE_TTL)
    return schema_result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/interface/plugin/services/test_plugin_schema_service.py::TestUniformApiPlugins -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bkflow/plugin/services/plugin_schema_service.py tests/interface/plugin/services/test_plugin_schema_service.py
git commit -m "feat(plugin): 添加 API 插件列表和 schema 查询 --story=TAPD_ID"
```

---

### Task 5: Unified get_plugin_schema + Schema Batch Fill + Caching

**Files:**
- Modify: `bkflow/plugin/services/plugin_schema_service.py`
- Modify: `tests/interface/plugin/services/test_plugin_schema_service.py`

- [ ] **Step 1: Write failing tests for unified get_plugin_schema and auto-resolve**

```python
# tests/interface/plugin/services/test_plugin_schema_service.py — append

class TestGetPluginSchema:
    """测试统一 get_plugin_schema 方法"""

    @patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_plugin_schema_component(self, mock_cm, mock_lib):
        """测试指定 plugin_type=component 查询"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0"]
        mock_cm.objects.filter.return_value.first.return_value = MagicMock(
            code="test_code", name="分组-插件", version="v1.0.0"
        )

        mock_component = MagicMock()
        mock_component.desc = "测试描述"
        mock_component.inputs_format.return_value = []
        mock_component.outputs_format.return_value = []
        mock_lib.get_component_class.return_value = mock_component

        service = PluginSchemaService(space_id=1)
        result = service.get_plugin_schema(code="test_code", plugin_type="component")

        assert result["code"] == "test_code"
        assert result["plugin_type"] == "component"
        assert "inputs" in result
        assert "outputs" in result

    @patch("bkflow.plugin.services.plugin_schema_service.BKPlugin")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_plugin_schema_auto_resolve_not_found(self, mock_cm, mock_bp):
        """测试自动解析失败 — 所有注册表未命中"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        mock_bp.objects.filter.return_value.exists.return_value = False

        service = PluginSchemaService(space_id=1)
        with pytest.raises(ValueError, match="未找到插件"):
            service.get_plugin_schema(code="nonexistent")

    @patch("bkflow.plugin.services.plugin_schema_service.BKPlugin")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_plugin_schema_auto_resolve_ambiguous(self, mock_cm, mock_bp):
        """测试自动解析歧义"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0"]
        mock_bp.objects.filter.return_value.exists.return_value = True

        service = PluginSchemaService(space_id=1)
        with pytest.raises(ValueError, match="请指定 plugin_type"):
            service.get_plugin_schema(code="ambiguous_code")


class TestCaching:
    """测试缓存行为"""

    @patch("bkflow.plugin.services.plugin_schema_service.cache")
    @patch("bkflow.plugin.services.plugin_schema_service.PluginServiceApiClient")
    def test_cache_hit_skips_remote_call(self, mock_client_cls, mock_cache):
        """缓存命中时不触发远程调用"""
        mock_cache.get.return_value = {
            "version": "1.0.0",
            "inputs": [{"key": "p1", "name": "P1", "type": "string", "required": True, "description": ""}],
            "outputs": [],
        }

        service = PluginSchemaService(space_id=1)
        schema = service._get_remote_plugin_schema("cached_plugin")

        assert schema["version"] == "1.0.0"
        mock_client_cls.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/interface/plugin/services/test_plugin_schema_service.py::TestGetPluginSchema tests/interface/plugin/services/test_plugin_schema_service.py::TestCaching -v`
Expected: FAIL

- [ ] **Step 3: Implement _get_single_by_type, _get_single_auto_resolve, _fill_schema_batch, _fill_schema_single**

Replace the `NotImplementedError` stubs with full implementations. Key logic:

```python
def _get_single_by_type(self, code, plugin_type, version=None):
    if plugin_type == "component":
        obj = ComponentModel.objects.filter(code=code, status=True).first()
        if not obj:
            raise ValueError("未找到内置插件 '{}'".format(code))
        parts = obj.name.split("-", 1) if "-" in obj.name else ["", obj.name]
        return {
            "code": obj.code,
            "name": (parts[1].strip() if len(parts) > 1 else parts[0].strip()),
            "plugin_type": "component",
            "version": obj.version,
            "description": "",
            "group_name": (parts[0].strip() if len(parts) > 1 else ""),
            "_component_version": version or obj.version,
        }
    elif plugin_type == "remote_plugin":
        obj = BKPlugin.objects.filter(code=code).first()
        if not obj:
            raise ValueError("未找到蓝鲸标准插件 '{}'".format(code))
        return {
            "code": obj.code,
            "name": obj.name,
            "plugin_type": "remote_plugin",
            "version": "",
            "description": obj.introduction or "",
            "group_name": "",
        }
    elif plugin_type == "uniform_api":
        api_list = self._list_uniform_api_plugins()
        api_item = next((a for a in api_list if a["code"] == code), None)
        if not api_item:
            raise ValueError("未找到 API 插件 '{}'".format(code))
        return api_item
    else:
        raise ValueError("不支持的 plugin_type: {}".format(plugin_type))

def _get_single_auto_resolve(self, code, version=None):
    is_component = ComponentModel.objects.filter(code=code, status=True).exists()
    is_bk_plugin = BKPlugin.objects.filter(code=code).exists()

    is_uniform_api = False
    try:
        api_list = self._list_uniform_api_plugins()
        api_item = next((a for a in api_list if a["code"] == code), None)
        is_uniform_api = api_item is not None
    except Exception:
        api_item = None

    hits = []
    if is_component:
        hits.append("component")
    if is_bk_plugin:
        hits.append("remote_plugin")
    if is_uniform_api:
        hits.append("uniform_api")

    if len(hits) > 1:
        raise ValueError(
            "插件 code '{}' 在多个注册表中同时存在，请指定 plugin_type 参数消歧。可选值: {}".format(code, hits)
        )
    if not hits:
        raise ValueError("未找到插件 code '{}'".format(code))

    resolved_type = hits[0]
    if resolved_type == "uniform_api":
        return api_item
    return self._get_single_by_type(code, resolved_type, version=version)

def _fill_schema_single(self, plugin_info, strict=False):
    """填充单个插件的 schema。strict=True 时失败抛异常（用于 get_plugin_schema），
    strict=False 时失败返回空 schema（用于 list_plugins batch fill）。"""
    ptype = plugin_info["plugin_type"]
    try:
        if ptype == "component":
            schema = self._get_component_schema(
                plugin_info["code"],
                version=plugin_info.get("_component_version"),
            )
        elif ptype == "remote_plugin":
            schema = self._get_remote_plugin_schema(plugin_info["code"])
        elif ptype == "uniform_api":
            schema = self._get_uniform_api_schema(plugin_info["code"])
        else:
            schema = {"inputs": [], "outputs": []}

        plugin_info["inputs"] = schema.get("inputs", [])
        plugin_info["outputs"] = schema.get("outputs", [])
        if schema.get("description") and not plugin_info.get("description"):
            plugin_info["description"] = schema["description"]
        if schema.get("version") and not plugin_info.get("version"):
            plugin_info["version"] = schema["version"]
    except Exception:
        if strict:
            raise
        logger.exception("获取插件 '%s' schema 失败", plugin_info["code"])
        plugin_info["inputs"] = []
        plugin_info["outputs"] = []

    plugin_info.pop("_component_version", None)
    plugin_info.pop("_meta_url", None)

def _fill_schema_batch(self, plugins):
    import concurrent.futures

    component_plugins = [p for p in plugins if p["plugin_type"] == "component"]
    for p in component_plugins:
        self._fill_schema_single(p)

    remote_plugins = [p for p in plugins if p["plugin_type"] in ("remote_plugin", "uniform_api")]
    if not remote_plugins:
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(self._fill_schema_single, p): p for p in remote_plugins}
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception:
                plugin = futures[future]
                logger.exception("并发获取插件 '%s' schema 失败", plugin.get("code"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/interface/plugin/services/test_plugin_schema_service.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add bkflow/plugin/services/plugin_schema_service.py tests/interface/plugin/services/test_plugin_schema_service.py
git commit -m "feat(plugin): 实现统一 schema 查询、自动解析和缓存 --story=TAPD_ID"
```

---

### Task 6: Serializers

**Files:**
- Create: `bkflow/apigw/serializers/plugin.py`

- [ ] **Step 1: Write failing test for serializers**

```python
# tests/interface/apigw/test_list_plugins.py (partial — serializer test)
from bkflow.apigw.serializers.plugin import ListPluginsSerializer, GetPluginSchemaSerializer

class TestListPluginsSerializer:
    def test_default_values(self):
        ser = ListPluginsSerializer(data={})
        assert ser.is_valid()
        assert ser.validated_data["without_detail"] is True
        assert ser.validated_data["limit"] == 100
        assert ser.validated_data["offset"] == 0

    def test_keyword_filter(self):
        ser = ListPluginsSerializer(data={"keyword": "脚本"})
        assert ser.is_valid()
        assert ser.validated_data["keyword"] == "脚本"

    def test_invalid_plugin_type(self):
        ser = ListPluginsSerializer(data={"plugin_type": "invalid"})
        assert not ser.is_valid()

class TestGetPluginSchemaSerializer:
    def test_code_required(self):
        ser = GetPluginSchemaSerializer(data={})
        assert not ser.is_valid()
        assert "code" in ser.errors

    def test_valid(self):
        ser = GetPluginSchemaSerializer(data={"code": "test_code"})
        assert ser.is_valid()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/interface/apigw/test_list_plugins.py::TestListPluginsSerializer tests/interface/apigw/test_list_plugins.py::TestGetPluginSchemaSerializer -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement serializers**

```python
# bkflow/apigw/serializers/plugin.py
from rest_framework import serializers


VALID_PLUGIN_TYPES = ("component", "remote_plugin", "uniform_api")


class ListPluginsSerializer(serializers.Serializer):
    keyword = serializers.CharField(required=False, allow_blank=True, help_text="模糊搜索 code 或 name")
    plugin_type = serializers.ChoiceField(
        required=False, choices=[(t, t) for t in VALID_PLUGIN_TYPES], help_text="按类型过滤"
    )
    without_detail = serializers.BooleanField(required=False, default=True, help_text="true 只返回摘要")
    scope_type = serializers.CharField(required=False, help_text="scope 类型")
    scope_id = serializers.CharField(required=False, help_text="scope ID")
    limit = serializers.IntegerField(required=False, default=100, min_value=1, max_value=200, help_text="分页大小")
    offset = serializers.IntegerField(required=False, default=0, min_value=0, help_text="分页偏移")


class GetPluginSchemaSerializer(serializers.Serializer):
    code = serializers.CharField(required=True, help_text="插件 code")
    version = serializers.CharField(required=False, help_text="插件版本，不传取最新")
    plugin_type = serializers.ChoiceField(
        required=False, choices=[(t, t) for t in VALID_PLUGIN_TYPES], help_text="消歧用"
    )
    scope_type = serializers.CharField(required=False, help_text="scope 类型")
    scope_id = serializers.CharField(required=False, help_text="scope ID")


class ValidateA2FlowSerializer(serializers.Serializer):
    a2flow = serializers.JSONField(required=True, help_text="a2flow v2 JSON 定义")
    scope_type = serializers.CharField(required=False, help_text="scope 类型")
    scope_value = serializers.CharField(required=False, help_text="scope 值")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/interface/apigw/test_list_plugins.py::TestListPluginsSerializer tests/interface/apigw/test_list_plugins.py::TestGetPluginSchemaSerializer -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bkflow/apigw/serializers/plugin.py tests/interface/apigw/test_list_plugins.py
git commit -m "feat(apigw): 添加插件查询接口 serializers --story=TAPD_ID"
```

---

### Task 7: list_plugins APIGW View

**Files:**
- Create: `bkflow/apigw/views/list_plugins.py`
- Modify: `tests/interface/apigw/test_list_plugins.py`

- [ ] **Step 1: Write failing test for list_plugins view**

```python
# tests/interface/apigw/test_list_plugins.py — append

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, RequestFactory, override_settings

from bkflow.apigw.views.list_plugins import list_plugins


class TestListPluginsView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(BK_APIGW_REQUIRE_EXEMPT=True)
    @patch("bkflow.plugin.services.plugin_schema_service.SpacePluginConfigModel")
    @patch("bkflow.plugin.services.plugin_schema_service.SpaceConfig")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    @patch("bkflow.plugin.services.plugin_schema_service.BKPlugin")
    @patch("bkflow.plugin.services.plugin_schema_service.BKPluginAuthorization")
    def test_list_plugins_success(self, mock_auth, mock_bp, mock_cm, mock_sc, mock_spcm):
        """测试正常调用 list_plugins"""
        mock_spcm.objects.get_space_allow_list.return_value = []
        mock_sc.get_config.return_value = None

        mock_obj = MagicMock()
        mock_obj.code = "test_plugin"
        mock_obj.name = "分组-测试插件"
        mock_obj.version = "v1.0.0"

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_obj]))
        mock_qs.count.return_value = 1
        mock_cm.objects.filter.return_value.exclude.return_value = mock_qs

        mock_bp.objects.filter.return_value = []
        mock_auth.objects.filter.return_value = []

        request = self.factory.get("/space/1/list_plugins/", {"plugin_type": "component"})
        request.user = MagicMock(username="admin")
        response = list_plugins(request, space_id="1")

        data = json.loads(response.content)
        assert data["result"] is True
        assert data["count"] == 1
        assert data["data"][0]["code"] == "test_plugin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/interface/apigw/test_list_plugins.py::TestListPluginsView -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement list_plugins view**

```python
# bkflow/apigw/views/list_plugins.py
import logging

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.plugin import ListPluginsSerializer
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService
from bkflow.utils import err_code

logger = logging.getLogger("root")


@login_exempt
@csrf_exempt
@require_GET
@apigw_require
@check_jwt_and_space
@return_json_response
def list_plugins(request, space_id):
    """查询空间可用插件列表"""
    ser = ListPluginsSerializer(data=request.GET)
    ser.is_valid(raise_exception=True)
    params = ser.validated_data

    service = PluginSchemaService(
        space_id=int(space_id),
        username=request.user.username,
        scope_type=params.get("scope_type"),
        scope_id=params.get("scope_id"),
    )

    plugins, count = service.list_plugins(
        keyword=params.get("keyword"),
        plugin_type=params.get("plugin_type"),
        without_detail=params.get("without_detail", True),
        limit=params.get("limit", 100),
        offset=params.get("offset", 0),
    )

    return {"result": True, "data": plugins, "count": count, "code": err_code.SUCCESS.code}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/interface/apigw/test_list_plugins.py::TestListPluginsView -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bkflow/apigw/views/list_plugins.py tests/interface/apigw/test_list_plugins.py
git commit -m "feat(apigw): 添加 list_plugins 网关接口 --story=TAPD_ID"
```

---

### Task 8: get_plugin_schema APIGW View

**Files:**
- Create: `bkflow/apigw/views/get_plugin_schema.py`
- Create: `tests/interface/apigw/test_get_plugin_schema.py`

- [ ] **Step 1: Write failing test for get_plugin_schema view**

```python
# tests/interface/apigw/test_get_plugin_schema.py
import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, RequestFactory, override_settings

from bkflow.apigw.views.get_plugin_schema import get_plugin_schema


class TestGetPluginSchemaView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(BK_APIGW_REQUIRE_EXEMPT=True)
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentLibrary")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_schema_success(self, mock_cm, mock_lib):
        """测试正常查询单个插件 schema"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0"]
        mock_cm.objects.filter.return_value.first.return_value = MagicMock(
            code="test_code", name="分组-插件", version="v1.0.0"
        )

        mock_component = MagicMock()
        mock_component.desc = "测试描述"
        mock_component.inputs_format.return_value = [
            {"key": "p1", "name": "参数1", "type": "string", "required": True, "schema": {}},
        ]
        mock_component.outputs_format.return_value = []
        mock_lib.get_component_class.return_value = mock_component

        request = self.factory.get("/space/1/get_plugin_schema/", {"code": "test_code", "plugin_type": "component"})
        request.user = MagicMock(username="admin")
        response = get_plugin_schema(request, space_id="1")

        data = json.loads(response.content)
        assert data["result"] is True
        assert data["data"]["code"] == "test_code"
        assert len(data["data"]["inputs"]) == 1

    @override_settings(BK_APIGW_REQUIRE_EXEMPT=True)
    @patch("bkflow.plugin.services.plugin_schema_service.BKPlugin")
    @patch("bkflow.plugin.services.plugin_schema_service.ComponentModel")
    def test_get_schema_not_found(self, mock_cm, mock_bp):
        """测试插件不存在"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        mock_bp.objects.filter.return_value.exists.return_value = False

        request = self.factory.get("/space/1/get_plugin_schema/", {"code": "nonexistent"})
        request.user = MagicMock(username="admin")
        response = get_plugin_schema(request, space_id="1")

        data = json.loads(response.content)
        assert data["result"] is False
        assert "未找到" in data["message"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/interface/apigw/test_get_plugin_schema.py -v`
Expected: FAIL

- [ ] **Step 3: Implement get_plugin_schema view**

```python
# bkflow/apigw/views/get_plugin_schema.py
import logging

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.plugin import GetPluginSchemaSerializer
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService
from bkflow.utils import err_code

logger = logging.getLogger("root")


@login_exempt
@csrf_exempt
@require_GET
@apigw_require
@check_jwt_and_space
@return_json_response
def get_plugin_schema(request, space_id):
    """查询单个插件的完整参数 schema"""
    ser = GetPluginSchemaSerializer(data=request.GET)
    ser.is_valid(raise_exception=True)
    params = ser.validated_data

    service = PluginSchemaService(
        space_id=int(space_id),
        username=request.user.username,
        scope_type=params.get("scope_type"),
        scope_id=params.get("scope_id"),
    )

    try:
        result = service.get_plugin_schema(
            code=params["code"],
            version=params.get("version"),
            plugin_type=params.get("plugin_type"),
        )
    except ValueError as e:
        return {
            "result": False,
            "message": str(e),
            "code": err_code.VALIDATION_ERROR.code,
            "data": None,
        }
    except Exception as e:
        logger.exception("get_plugin_schema: unexpected error - %s", str(e))
        return {
            "result": False,
            "message": "查询插件 schema 失败: {}".format(str(e)),
            "code": err_code.ERROR.code,
            "data": None,
        }

    return {"result": True, "data": result, "code": err_code.SUCCESS.code}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/interface/apigw/test_get_plugin_schema.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bkflow/apigw/views/get_plugin_schema.py tests/interface/apigw/test_get_plugin_schema.py
git commit -m "feat(apigw): 添加 get_plugin_schema 网关接口 --story=TAPD_ID"
```

---

### Task 9: validate_a2flow APIGW View

**Files:**
- Create: `bkflow/apigw/views/validate_a2flow.py`
- Create: `tests/interface/apigw/test_validate_a2flow.py`

- [ ] **Step 1: Write failing tests for validate_a2flow view**

```python
# tests/interface/apigw/test_validate_a2flow.py
import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, RequestFactory, override_settings

from bkflow.apigw.views.validate_a2flow import validate_a2flow


class TestValidateA2FlowView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(BK_APIGW_REQUIRE_EXEMPT=True)
    @patch("bkflow.apigw.views.validate_a2flow.A2FlowV2Converter")
    def test_validate_success(self, mock_converter_cls):
        """测试合法流程校验通过"""
        mock_converter = MagicMock()
        mock_converter.convert.return_value = {
            "activities": {
                "n1": {"component": {"code": "job_fast_execute_script"}},
            },
            "start_event": {},
            "end_event": {},
        }
        mock_converter_cls.return_value = mock_converter

        body = json.dumps({
            "a2flow": {
                "version": "2.0",
                "name": "测试流程",
                "nodes": [
                    {"id": "n1", "name": "执行脚本", "code": "job_fast_execute_script",
                     "data": {"script_content": "echo hello"}, "next": "end"},
                ],
            }
        })
        request = self.factory.post(
            "/space/1/validate_a2flow/", data=body, content_type="application/json"
        )
        request.user = MagicMock(username="admin")
        response = validate_a2flow(request, space_id="1")

        data = json.loads(response.content)
        assert data["result"] is True
        assert data["data"]["valid"] is True
        assert data["data"]["node_count"] == 1
        assert "job_fast_execute_script" in data["data"]["plugin_codes"]

    @override_settings(BK_APIGW_REQUIRE_EXEMPT=True)
    def test_validate_missing_a2flow(self):
        """测试缺少 a2flow 字段"""
        body = json.dumps({})
        request = self.factory.post(
            "/space/1/validate_a2flow/", data=body, content_type="application/json"
        )
        request.user = MagicMock(username="admin")
        response = validate_a2flow(request, space_id="1")

        data = json.loads(response.content)
        assert data["result"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/interface/apigw/test_validate_a2flow.py -v`
Expected: FAIL

- [ ] **Step 3: Implement validate_a2flow view**

```python
# bkflow/apigw/views/validate_a2flow.py
import json
import logging

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from pydantic import ValidationError

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.plugin import ValidateA2FlowSerializer
from bkflow.pipeline_converter.exceptions import A2FlowConvertError, A2FlowValidationError
from bkflow.utils import err_code

logger = logging.getLogger("root")


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
def validate_a2flow(request, space_id):
    """预校验 a2flow v2 流程定义（dry-run，不创建模板）"""
    data = json.loads(request.body)

    ser = ValidateA2FlowSerializer(data=data)
    if not ser.is_valid():
        from bkflow.apigw.serializers.a2flow import build_structured_serializer_errors

        return {
            "result": False,
            "errors": build_structured_serializer_errors(ser.errors, prefix="a2flow"),
            "code": err_code.VALIDATION_ERROR.code,
        }

    validated_data = ser.validated_data
    a2flow_data = validated_data["a2flow"]

    try:
        from bkflow.pipeline_converter.converters.a2flow_v2 import A2FlowV2Converter

        converter = A2FlowV2Converter(
            a2flow_data,
            space_id=int(space_id),
            username=request.user.username,
            scope_type=validated_data.get("scope_type"),
            scope_value=validated_data.get("scope_value"),
        )
        pipeline_tree = converter.convert()
    except ValidationError as e:
        return {
            "result": False,
            "errors": [{"type": "MISSING_REQUIRED_FIELD", "message": str(e)}],
            "code": err_code.VALIDATION_ERROR.code,
        }
    except A2FlowValidationError as e:
        response = e.to_response()
        response["code"] = err_code.VALIDATION_ERROR.code
        return response
    except A2FlowConvertError as e:
        return {
            "result": False,
            "errors": [e.to_dict()],
            "code": err_code.VALIDATION_ERROR.code,
        }
    except Exception as e:
        logger.exception("validate_a2flow: unexpected error - %s", str(e))
        return {
            "result": False,
            "message": "流程校验失败: {}".format(str(e)),
            "code": err_code.ERROR.code,
            "data": None,
        }

    activities = pipeline_tree.get("activities", {})
    plugin_codes = list({act["component"]["code"] for act in activities.values()})

    return {
        "result": True,
        "data": {
            "valid": True,
            "version": a2flow_data.get("version", "2.0"),
            "node_count": len(activities),
            "plugin_codes": plugin_codes,
        },
        "code": err_code.SUCCESS.code,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/interface/apigw/test_validate_a2flow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bkflow/apigw/views/validate_a2flow.py tests/interface/apigw/test_validate_a2flow.py
git commit -m "feat(apigw): 添加 validate_a2flow 网关接口 --story=TAPD_ID"
```

---

### Task 10: URL Registration + API Documentation

**Files:**
- Modify: `bkflow/apigw/urls.py`
- Create: `bkflow/apigw/docs/zh/list_plugins.md`
- Create: `bkflow/apigw/docs/zh/get_plugin_schema.md`
- Create: `bkflow/apigw/docs/zh/validate_a2flow.md`

- [ ] **Step 1: Register URLs**

Add to `bkflow/apigw/urls.py`, inside the `if settings.BKFLOW_MODULE.type == BKFLOWModuleType.interface:` block:

Import section:
```python
from bkflow.apigw.views.get_plugin_schema import get_plugin_schema
from bkflow.apigw.views.list_plugins import list_plugins
from bkflow.apigw.views.validate_a2flow import validate_a2flow
```

URL patterns (add before the `# 基于 bk_app_code 权限控制的接口` comment):
```python
url(r"^space/(?P<space_id>\d+)/list_plugins/$", list_plugins),
url(r"^space/(?P<space_id>\d+)/get_plugin_schema/$", get_plugin_schema),
url(r"^space/(?P<space_id>\d+)/validate_a2flow/$", validate_a2flow),
```

- [ ] **Step 2: Write API documentation**

Create `bkflow/apigw/docs/zh/list_plugins.md`, `get_plugin_schema.md`, `validate_a2flow.md` following the api-doc-sync skill pattern. Use the spec document section 1 as source material. Each doc should include:
- 接口说明
- 请求参数表
- 请求示例
- 响应参数表
- 响应示例（成功 + 失败）

- [ ] **Step 3: Commit**

```bash
git add bkflow/apigw/urls.py bkflow/apigw/docs/zh/list_plugins.md bkflow/apigw/docs/zh/get_plugin_schema.md bkflow/apigw/docs/zh/validate_a2flow.md
git commit -m "feat(apigw): 注册插件查询接口 URL 和 API 文档 --story=TAPD_ID"
```

---

### Task 11: Run All Tests and Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Run all new tests**

```bash
pytest tests/interface/plugin/services/test_plugin_schema_service.py tests/interface/apigw/test_list_plugins.py tests/interface/apigw/test_get_plugin_schema.py tests/interface/apigw/test_validate_a2flow.py -v
```

Expected: ALL PASS

- [ ] **Step 2: Run existing apigw tests to check for regressions**

```bash
pytest tests/interface/apigw/ -v
```

Expected: ALL PASS (no regressions)

- [ ] **Step 3: Run linting**

```bash
cd /root/Projects/bk-flow && flake8 bkflow/plugin/services/ bkflow/apigw/views/list_plugins.py bkflow/apigw/views/get_plugin_schema.py bkflow/apigw/views/validate_a2flow.py bkflow/apigw/serializers/plugin.py --max-line-length=120
```

Expected: No errors

- [ ] **Step 4: Final commit (if any fixes needed)**

Fix any issues found and commit.
