# a2flow v2.0 AI-Friendly Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a2flow v2 AI-friendly protocol (alongside preserved v1) that reduces token consumption ~35-40%, unifies three plugin types under a single input format, and supports protocol versioning.

**Architecture:** Two-phase approach: (1) Pydantic v1 DataModels validate & normalize the v2 input JSON, (2) converter transforms it into a `pipeline_tree` dict. The v1 converter (`bkflow/utils/a2flow.py`) is preserved for backward compatibility; the view routes by `version` field. A `PluginResolver` handles three plugin types (built-in ComponentModel, BK Standard BKPlugin, uniform_api) transparently.

**Tech Stack:** Python 3, Django, DRF, Pydantic v1 (1.10.6), pytest + Django TestCase, pipeline.component_framework.models.ComponentModel

**Spec:** `docs/specs/2026-03-30-a2flow-v2-ai-friendly-protocol-design.md`

---

## File Structure

```
bkflow/pipeline_converter/                    # New module (pipeline_converter doesn't exist yet)
├── __init__.py                               # Empty
├── constants.py                              # NodeType, A2FlowVersion enums
├── exceptions.py                             # Structured error classes (A2FlowConvertError, etc.)
├── converters/
│   ├── __init__.py                           # Empty
│   └── a2flow_v2/
│       ├── __init__.py                       # Exports A2FlowV2Converter
│       ├── data_models.py                    # Pydantic v1 input models
│       ├── plugin_resolver.py                # Plugin type detection & wrapping
│       ├── converter.py                      # Main orchestrator (a2flow → pipeline_tree)
│       ├── node_builder.py                   # Activity/Start/End node → pipeline_tree node
│       ├── gateway_builder.py                # Gateway nodes → pipeline_tree gateways
│       └── variable_builder.py               # Variable → pipeline_tree constant

bkflow/apigw/serializers/a2flow.py            # Modify: add v2 format support
bkflow/apigw/views/create_template_with_a2flow.py  # Modify: version routing
bkflow/apigw/docs/zh/create_template_with_a2flow.md  # Modify: update API doc

tests/interface/pipeline_converter/           # New test directory
├── __init__.py
├── test_data_models.py                       # DataModel validation tests
├── test_plugin_resolver.py                   # Plugin resolution tests
├── test_converter.py                         # Main converter tests
├── test_node_builder.py                      # Node building tests
├── test_gateway_builder.py                   # Gateway building tests
└── test_variable_builder.py                  # Variable building tests

tests/interface/apigw/test_create_template_with_a2flow.py  # Modify: add v2 tests
```

**Files NOT changed:**
- `bkflow/utils/a2flow.py` — v1 converter preserved as-is
- `tests/interface/utils/test_a2flow_converter.py` — v1 tests preserved

---

### Task 1: Foundation — Constants and Exceptions

**Files:**
- Create: `bkflow/pipeline_converter/__init__.py`
- Create: `bkflow/pipeline_converter/constants.py`
- Create: `bkflow/pipeline_converter/exceptions.py`
- Create: `bkflow/pipeline_converter/converters/__init__.py`
- Create: `bkflow/pipeline_converter/converters/a2flow_v2/__init__.py`
- Test: `tests/interface/pipeline_converter/__init__.py`
- Test: `tests/interface/pipeline_converter/test_constants.py`

- [ ] **Step 1: Create package structure**

```bash
mkdir -p bkflow/pipeline_converter/converters/a2flow_v2
touch bkflow/pipeline_converter/__init__.py
touch bkflow/pipeline_converter/converters/__init__.py
touch bkflow/pipeline_converter/converters/a2flow_v2/__init__.py
mkdir -p tests/interface/pipeline_converter
touch tests/interface/pipeline_converter/__init__.py
```

- [ ] **Step 2: Write constants test**

Create `tests/interface/pipeline_converter/test_constants.py`:

```python
from django.test import TestCase


class TestNodeType(TestCase):
    def test_node_type_values(self):
        from bkflow.pipeline_converter.constants import NodeType

        self.assertEqual(NodeType.START_EVENT, "StartEvent")
        self.assertEqual(NodeType.END_EVENT, "EndEvent")
        self.assertEqual(NodeType.ACTIVITY, "Activity")
        self.assertEqual(NodeType.PARALLEL_GATEWAY, "ParallelGateway")
        self.assertEqual(NodeType.CONDITIONAL_PARALLEL_GATEWAY, "ConditionalParallelGateway")
        self.assertEqual(NodeType.EXCLUSIVE_GATEWAY, "ExclusiveGateway")
        self.assertEqual(NodeType.CONVERGE_GATEWAY, "ConvergeGateway")

    def test_branch_gateway_types(self):
        from bkflow.pipeline_converter.constants import BRANCH_GATEWAY_TYPES

        self.assertIn("ParallelGateway", BRANCH_GATEWAY_TYPES)
        self.assertIn("ExclusiveGateway", BRANCH_GATEWAY_TYPES)
        self.assertIn("ConditionalParallelGateway", BRANCH_GATEWAY_TYPES)
        self.assertNotIn("ConvergeGateway", BRANCH_GATEWAY_TYPES)


class TestPluginTypeEnum(TestCase):
    def test_plugin_type_values(self):
        from bkflow.pipeline_converter.constants import A2FlowPluginType

        self.assertEqual(A2FlowPluginType.COMPONENT, "component")
        self.assertEqual(A2FlowPluginType.REMOTE_PLUGIN, "remote_plugin")
        self.assertEqual(A2FlowPluginType.UNIFORM_API, "uniform_api")


class TestA2FlowVersion(TestCase):
    def test_version_values(self):
        from bkflow.pipeline_converter.constants import A2FlowVersion

        self.assertEqual(A2FlowVersion.V1, "1.0")
        self.assertEqual(A2FlowVersion.V2, "2.0")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/interface/pipeline_converter/test_constants.py -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError`

- [ ] **Step 4: Implement constants**

Create `bkflow/pipeline_converter/constants.py`:

```python
from enum import Enum


class NodeType:
    START_EVENT = "StartEvent"
    END_EVENT = "EndEvent"
    ACTIVITY = "Activity"
    PARALLEL_GATEWAY = "ParallelGateway"
    CONDITIONAL_PARALLEL_GATEWAY = "ConditionalParallelGateway"
    EXCLUSIVE_GATEWAY = "ExclusiveGateway"
    CONVERGE_GATEWAY = "ConvergeGateway"


BRANCH_GATEWAY_TYPES = {
    NodeType.PARALLEL_GATEWAY,
    NodeType.CONDITIONAL_PARALLEL_GATEWAY,
    NodeType.EXCLUSIVE_GATEWAY,
}

GATEWAY_TYPES = BRANCH_GATEWAY_TYPES | {NodeType.CONVERGE_GATEWAY}

RESERVED_IDS = {"start", "end"}


class A2FlowPluginType(str, Enum):
    COMPONENT = "component"
    REMOTE_PLUGIN = "remote_plugin"
    UNIFORM_API = "uniform_api"


class A2FlowVersion(str, Enum):
    V1 = "1.0"
    V2 = "2.0"


DEFAULT_ACTIVITY_CONFIG = {
    "auto_retry": {"enable": False, "interval": 0, "times": 1},
    "timeout_config": {"action": "forced_fail", "enable": False, "seconds": 10},
    "error_ignorable": False,
    "retryable": True,
    "skippable": True,
    "optional": True,
    "labels": [],
    "loop": None,
}
```

- [ ] **Step 5: Implement exceptions**

Create `bkflow/pipeline_converter/exceptions.py`:

```python
class A2FlowConvertError(Exception):
    """a2flow 转换过程中的结构化错误基类"""

    def __init__(self, error_type, message, node_id=None, field=None, value=None, hint=None):
        self.error_type = error_type
        self.message = message
        self.node_id = node_id
        self.field = field
        self.value = value
        self.hint = hint
        super().__init__(message)

    def to_dict(self):
        result = {"type": self.error_type, "message": self.message}
        if self.node_id is not None:
            result["node_id"] = self.node_id
        if self.field is not None:
            result["field"] = self.field
        if self.value is not None:
            result["value"] = self.value
        if self.hint is not None:
            result["hint"] = self.hint
        return result


class A2FlowValidationError(Exception):
    """包含多个结构化错误的校验异常"""

    def __init__(self, errors):
        self.errors = errors if isinstance(errors, list) else [errors]
        messages = "; ".join(e.message if isinstance(e, A2FlowConvertError) else str(e) for e in self.errors)
        super().__init__(messages)

    def to_response(self):
        return {
            "result": False,
            "errors": [e.to_dict() if isinstance(e, A2FlowConvertError) else {"message": str(e)} for e in self.errors],
        }


class ErrorTypes:
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_REFERENCE = "INVALID_REFERENCE"
    DUPLICATE_NODE_ID = "DUPLICATE_NODE_ID"
    CONDITIONS_MISMATCH = "CONDITIONS_MISMATCH"
    INVALID_DEFAULT_NEXT = "INVALID_DEFAULT_NEXT"
    UNKNOWN_PLUGIN_CODE = "UNKNOWN_PLUGIN_CODE"
    AMBIGUOUS_PLUGIN_CODE = "AMBIGUOUS_PLUGIN_CODE"
    CONVERGE_INFER_FAILED = "CONVERGE_INFER_FAILED"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
    RESERVED_ID_CONFLICT = "RESERVED_ID_CONFLICT"
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/interface/pipeline_converter/test_constants.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 7: Commit**

```bash
git add bkflow/pipeline_converter/ tests/interface/pipeline_converter/
git commit -m "feat(pipeline_converter): 创建 a2flow v2 基础模块 — 常量和异常类 --story=133123272"
```

---

### Task 2: a2flow v2 Input DataModels

**Files:**
- Create: `bkflow/pipeline_converter/converters/a2flow_v2/data_models.py`
- Test: `tests/interface/pipeline_converter/test_data_models.py`

**Context:** Uses Pydantic v1.10.6 syntax (`validator` not `field_validator`, `class Config` not `model_config`).

- [ ] **Step 1: Write DataModel tests**

Create `tests/interface/pipeline_converter/test_data_models.py`:

```python
from django.test import TestCase
from pydantic import ValidationError


def _get_models():
    from bkflow.pipeline_converter.converters.a2flow_v2.data_models import (
        A2FlowCondition,
        A2FlowNode,
        A2FlowPipeline,
        A2FlowVariable,
    )

    return A2FlowNode, A2FlowPipeline, A2FlowVariable, A2FlowCondition


class TestA2FlowNode(TestCase):
    """a2flow v2 节点 DataModel 测试"""

    def test_activity_defaults_type(self):
        """缺省 type 应为 Activity"""
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(id="n1", name="测试", code="sleep_timer", next="n2")
        self.assertEqual(node.type, "Activity")

    def test_activity_explicit_type(self):
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(id="n1", name="测试", type="Activity", code="sleep_timer", next="n2")
        self.assertEqual(node.type, "Activity")

    def test_gateway_type(self):
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(id="pg1", name="并行", type="ParallelGateway", next=["n1", "n2"])
        self.assertEqual(node.type, "ParallelGateway")
        self.assertEqual(node.next, ["n1", "n2"])

    def test_start_event(self):
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(id="start", name="开始", type="StartEvent", next="n1")
        self.assertEqual(node.type, "StartEvent")

    def test_end_event(self):
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(id="end", name="结束", type="EndEvent")
        self.assertIsNone(node.next)

    def test_exclusive_gateway_with_conditions(self):
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(
            id="eg1",
            name="判断",
            type="ExclusiveGateway",
            next=["n1", "n2"],
            conditions=[{"evaluate": "${x} > 0"}, {"evaluate": "${x} <= 0"}],
            default_next="n2",
        )
        self.assertEqual(len(node.conditions), 2)
        self.assertEqual(node.default_next, "n2")

    def test_activity_with_plugin_type(self):
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(
            id="n1", name="远程插件", code="my_plugin", plugin_type="remote_plugin", next="n2"
        )
        self.assertEqual(node.plugin_type, "remote_plugin")

    def test_activity_allows_missing_next_for_late_converter_validation(self):
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(id="n1", name="测试", code="sleep_timer")
        self.assertIsNone(node.next)

    def test_node_id_required(self):
        A2FlowNode, *_ = _get_models()
        with self.assertRaises(ValidationError):
            A2FlowNode(name="无ID")

    def test_node_data_defaults_empty(self):
        A2FlowNode, *_ = _get_models()
        node = A2FlowNode(id="n1", name="测试", code="sleep_timer", next="n2")
        self.assertEqual(node.data, {})


class TestA2FlowVariable(TestCase):
    """a2flow v2 变量 DataModel 测试"""

    def test_variable_defaults(self):
        _, A2FlowPipeline, A2FlowVariable, _ = _get_models()
        var = A2FlowVariable(key="${ip}")
        self.assertEqual(var.name, "")
        self.assertEqual(var.value, "")
        self.assertEqual(var.source_type, "custom")
        self.assertEqual(var.custom_type, "input")
        self.assertEqual(var.show_type, "show")

    def test_variable_key_required(self):
        _, _, A2FlowVariable, _ = _get_models()
        with self.assertRaises(ValidationError):
            A2FlowVariable()


class TestA2FlowPipeline(TestCase):
    """a2flow v2 顶层结构测试"""

    def test_minimal_pipeline(self):
        _, A2FlowPipeline, _, _ = _get_models()
        pipeline = A2FlowPipeline(
            name="简单流程",
            nodes=[{"id": "n1", "name": "步骤1", "code": "sleep_timer", "next": "end"}],
        )
        self.assertEqual(pipeline.version, "2.0")
        self.assertEqual(len(pipeline.nodes), 1)
        self.assertEqual(pipeline.variables, [])

    def test_pipeline_name_required(self):
        _, A2FlowPipeline, _, _ = _get_models()
        with self.assertRaises(ValidationError):
            A2FlowPipeline(nodes=[{"id": "n1", "name": "x", "code": "y", "next": "end"}])

    def test_pipeline_nodes_required(self):
        _, A2FlowPipeline, _, _ = _get_models()
        with self.assertRaises(ValidationError):
            A2FlowPipeline(name="空流程")

    def test_pipeline_empty_nodes_rejected(self):
        _, A2FlowPipeline, _, _ = _get_models()
        with self.assertRaises(ValidationError):
            A2FlowPipeline(name="空流程", nodes=[])

    def test_pipeline_version_default(self):
        _, A2FlowPipeline, _, _ = _get_models()
        pipeline = A2FlowPipeline(
            name="测试", nodes=[{"id": "n1", "name": "x", "code": "y", "next": "end"}]
        )
        self.assertEqual(pipeline.version, "2.0")

    def test_pipeline_with_variables(self):
        _, A2FlowPipeline, _, _ = _get_models()
        pipeline = A2FlowPipeline(
            name="带变量",
            nodes=[{"id": "n1", "name": "x", "code": "y", "next": "end"}],
            variables=[{"key": "${ip}", "name": "IP地址"}],
        )
        self.assertEqual(len(pipeline.variables), 1)
        self.assertEqual(pipeline.variables[0].key, "${ip}")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/interface/pipeline_converter/test_data_models.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement DataModels**

Create `bkflow/pipeline_converter/converters/a2flow_v2/data_models.py`:

```python
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, validator

from bkflow.pipeline_converter.constants import A2FlowPluginType, NodeType


class A2FlowCondition(BaseModel):
    evaluate: str = "True"
    name: str = ""


class A2FlowNode(BaseModel):
    id: str
    name: str = ""
    type: str = NodeType.ACTIVITY
    code: Optional[str] = None
    data: Dict[str, Any] = {}
    next: Union[str, List[str], None] = None
    stage_name: Optional[str] = None
    plugin_type: Optional[str] = None
    conditions: Optional[List[A2FlowCondition]] = None
    default_next: Optional[str] = None
    converge_gateway_id: Optional[str] = None

    @validator("type", pre=True, always=True)
    def set_default_type(cls, v):
        return v or NodeType.ACTIVITY

    @validator("plugin_type")
    def validate_plugin_type(cls, v):
        if v is not None:
            valid_values = {e.value for e in A2FlowPluginType}
            if v not in valid_values:
                raise ValueError(f"plugin_type 必须是 {valid_values} 之一，收到: {v}")
        return v

    class Config:
        extra = "forbid"


class A2FlowVariable(BaseModel):
    key: str
    name: str = ""
    value: Any = ""
    source_type: str = "custom"
    custom_type: str = "input"
    description: str = ""
    show_type: str = "show"

    class Config:
        extra = "forbid"


class A2FlowPipeline(BaseModel):
    version: str = "2.0"
    name: str
    desc: str = ""
    nodes: List[A2FlowNode]
    variables: List[A2FlowVariable] = []

    @validator("nodes")
    def nodes_not_empty(cls, v):
        if not v:
            raise ValueError("nodes 不能为空")
        return v

    class Config:
        extra = "forbid"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/interface/pipeline_converter/test_data_models.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add bkflow/pipeline_converter/converters/a2flow_v2/data_models.py tests/interface/pipeline_converter/test_data_models.py
git commit -m "feat(pipeline_converter): 添加 a2flow v2 Pydantic 输入 DataModel --story=133123272"
```

---

### Task 3: Plugin Resolver

**Files:**
- Create: `bkflow/pipeline_converter/converters/a2flow_v2/plugin_resolver.py`
- Test: `tests/interface/pipeline_converter/test_plugin_resolver.py`

**Context:**
- Built-in plugins: `ComponentModel.objects.filter(code=code, status=1)` from `pipeline.component_framework.models`
- BK Standard plugins: `BKPlugin.objects.filter(code=code)` from `bkflow.bk_plugin.models`
- API plugins: support explicit `plugin_type="uniform_api"` and also auto-detect against the space uniform API list so behavior matches the spec
- Version resolution for built-in: parse semver from ComponentModel, pick latest
- Version for remote_plugin wrapper: fixed `"1.0.0"`; per-node actual plugin version must query the plugin service newest deployed version and写入 `component.data.plugin_version`
- Version for uniform_api wrapper: latest registered version of the `uniform_api` component
- Reuse existing uniform API facilities where possible:
  - `bkflow.space.configs.UniformApiConfig`, `UniformAPIConfigHandler`
  - `bkflow.space.configs.ApiGatewayCredentialConfig`
  - `bkflow.pipeline_plugins.query.uniform_api.uniform_api._get_api_credential`
  - `bkflow.pipeline_plugins.query.uniform_api.utils.UniformAPIClient`

- [ ] **Step 1: Write plugin resolver tests**

Create `tests/interface/pipeline_converter/test_plugin_resolver.py`:

```python
from collections import namedtuple
from unittest.mock import MagicMock, patch

from django.test import TestCase

MockComponent = namedtuple("MockComponent", ["code", "version"])


class TestPluginResolver(TestCase):
    """插件类型识别与包装测试"""

    def _get_resolver_class(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver import PluginResolver

        return PluginResolver

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._safe_fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_resolve_builtin_plugin(self, mock_cm, mock_safe_fetch_meta):
        """内置插件：code 在 ComponentModel 中找到"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0", "v2.0.0"]
        mock_safe_fetch_meta.return_value = None
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        result = resolver.resolve("sleep_timer", plugin_type_hint=None)
        self.assertEqual(result.plugin_type, "component")
        self.assertEqual(result.wrapper_code, "sleep_timer")
        self.assertEqual(result.wrapper_version, "v2.0.0")

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._safe_fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._fetch_remote_plugin_version")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.BKPlugin")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_resolve_bk_standard_plugin(self, mock_cm, mock_bkp, mock_fetch_version, mock_safe_fetch_meta):
        """蓝鲸标准插件：code 不在 ComponentModel，在 BKPlugin 中找到"""
        mock_cm.objects.filter.return_value.values_list.return_value = []
        mock_bkp.objects.filter.return_value.exists.return_value = True
        mock_fetch_version.return_value = "1.2.3"
        mock_safe_fetch_meta.return_value = None
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        result = resolver.resolve("custom_bk_plugin", plugin_type_hint=None)
        self.assertEqual(result.plugin_type, "remote_plugin")
        self.assertEqual(result.wrapper_code, "remote_plugin")
        self.assertEqual(result.original_code, "custom_bk_plugin")
        self.assertEqual(result.remote_plugin_version, "1.2.3")

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_resolve_uniform_api_with_explicit_type(self, mock_cm, mock_fetch_meta):
        """API 插件：必须显式指定 plugin_type"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v3.0.0"]
        mock_fetch_meta.return_value = {
            "id": "my_api_plugin",
            "name": "测试API",
            "category": {},
            "meta_url": "http://example.com/meta",
            "url": "http://example.com/run",
            "methods": ["POST"],
            "api_key": "default",
        }
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        result = resolver.resolve("my_api_plugin", plugin_type_hint="uniform_api")
        self.assertEqual(result.plugin_type, "uniform_api")
        self.assertEqual(result.wrapper_code, "uniform_api")
        self.assertEqual(result.original_code, "my_api_plugin")
        self.assertEqual(result.api_meta["id"], "my_api_plugin")

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_resolve_with_explicit_component_type(self, mock_cm):
        """显式指定 plugin_type=component"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0"]
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        result = resolver.resolve("sleep_timer", plugin_type_hint="component")
        self.assertEqual(result.plugin_type, "component")

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._safe_fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.BKPlugin")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_resolve_unknown_plugin(self, mock_cm, mock_bkp, mock_safe_fetch_meta):
        """未知 code 应报 UNKNOWN_PLUGIN_CODE"""
        from bkflow.pipeline_converter.exceptions import A2FlowConvertError

        mock_cm.objects.filter.return_value.values_list.return_value = []
        mock_bkp.objects.filter.return_value.exists.return_value = False
        mock_safe_fetch_meta.return_value = None
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        with self.assertRaises(A2FlowConvertError) as ctx:
            resolver.resolve("nonexistent_plugin", plugin_type_hint=None)
        self.assertEqual(ctx.exception.error_type, "UNKNOWN_PLUGIN_CODE")

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._safe_fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.BKPlugin")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_resolve_ambiguous_plugin(self, mock_cm, mock_bkp, mock_safe_fetch_meta):
        """code 同时在 ComponentModel 和 BKPlugin 中找到应报 AMBIGUOUS_PLUGIN_CODE"""
        from bkflow.pipeline_converter.exceptions import A2FlowConvertError

        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0"]
        mock_bkp.objects.filter.return_value.exists.return_value = True
        mock_safe_fetch_meta.return_value = None
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        with self.assertRaises(A2FlowConvertError) as ctx:
            resolver.resolve("ambiguous_code", plugin_type_hint=None)
        self.assertEqual(ctx.exception.error_type, "AMBIGUOUS_PLUGIN_CODE")

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.BKPlugin")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_auto_resolve_uniform_api(self, mock_cm, mock_bkp, mock_fetch_meta):
        mock_cm.objects.filter.return_value.values_list.return_value = []
        mock_bkp.objects.filter.return_value.exists.return_value = False
        mock_fetch_meta.return_value = {
            "id": "my_api",
            "name": "测试API",
            "category": {},
            "meta_url": "http://example.com/meta",
            "url": "http://example.com/run",
            "methods": ["POST"],
            "api_key": "default",
        }
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        result = resolver.resolve("my_api", plugin_type_hint=None)
        self.assertEqual(result.plugin_type, "uniform_api")

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._safe_fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.BKPlugin")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_resolve_batch(self, mock_cm, mock_bkp, mock_safe_fetch, mock_fetch_meta):
        """批量解析多个 Activity 节点的插件"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["v1.0.0"]
        mock_bkp.objects.filter.return_value.exists.return_value = False
        mock_safe_fetch.return_value = None
        mock_fetch_meta.return_value = {
            "id": "my_api",
            "name": "测试API",
            "category": {},
            "meta_url": "http://example.com/meta",
            "url": "http://example.com/run",
            "methods": ["POST"],
            "api_key": "default",
        }
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        nodes_info = [
            {"code": "sleep_timer", "plugin_type": None},
            {"code": "my_api", "plugin_type": "uniform_api"},
        ]
        results = resolver.resolve_batch(nodes_info)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[("sleep_timer", None)].plugin_type, "component")
        self.assertEqual(results[("my_api", "uniform_api")].plugin_type, "uniform_api")

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_version_parsing_picks_latest(self, mock_cm):
        """版本选择应取语义化最新"""
        mock_cm.objects.filter.return_value.values_list.return_value = ["legacy", "v1.0.0", "v2.1.0", "v2.0.0"]
        PluginResolver = self._get_resolver_class()
        resolver = PluginResolver(space_id=1)
        result = resolver.resolve("test_code", plugin_type_hint="component")
        self.assertEqual(result.wrapper_version, "v2.1.0")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/interface/pipeline_converter/test_plugin_resolver.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement plugin resolver**

Create `bkflow/pipeline_converter/converters/a2flow_v2/plugin_resolver.py`:

```python
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from bkflow.bk_plugin.models import BKPlugin
from bkflow.pipeline_converter.constants import A2FlowPluginType
from bkflow.pipeline_converter.exceptions import A2FlowConvertError, ErrorTypes
from pipeline.component_framework.models import ComponentModel

logger = logging.getLogger("root")


@dataclass
class ResolvedPlugin:
    """插件类型识别后的中间表示"""

    plugin_type: str
    original_code: str
    wrapper_code: str
    wrapper_version: str
    api_meta: Optional[dict] = None
    remote_plugin_version: Optional[str] = None


class PluginResolver:
    """
    根据 code 和可选的 plugin_type 提示，识别插件类型并生成 pipeline_tree 所需的包装信息。

    识别策略：
    1. 如果 plugin_type 已指定 → 直接按指定类型处理
    2. 如果未指定 → 依次查 ComponentModel、BKPlugin，都不匹配则报错
    3. 如果同时匹配多个注册表 → 报 AMBIGUOUS_PLUGIN_CODE
    """

    REMOTE_PLUGIN_VERSION = "1.0.0"

    def __init__(self, space_id, username=None, scope_type=None, scope_value=None):
        self.space_id = space_id
        self.username = username
        self.scope_type = scope_type
        self.scope_value = scope_value

    def resolve(self, code, plugin_type_hint=None):
        if plugin_type_hint:
            return self._resolve_by_type(code, plugin_type_hint)
        return self._auto_resolve(code)

    def resolve_batch(self, nodes_info):
        """
        批量解析插件。

        :param nodes_info: list of {"code": str, "plugin_type": str|None}
        :return: dict of {(code, plugin_type_hint): ResolvedPlugin}
        """
        results = {}
        for info in nodes_info:
            code = info["code"]
            cache_key = (code, info.get("plugin_type"))
            if cache_key not in results:
                results[cache_key] = self.resolve(code, info.get("plugin_type"))
        return results

    def _resolve_by_type(self, code, plugin_type):
        if plugin_type == A2FlowPluginType.COMPONENT.value:
            return self._resolve_as_component(code)
        elif plugin_type == A2FlowPluginType.REMOTE_PLUGIN.value:
            return self._resolve_as_remote_plugin(code)
        elif plugin_type == A2FlowPluginType.UNIFORM_API.value:
            return self._resolve_as_uniform_api(code)
        else:
            raise A2FlowConvertError(
                error_type=ErrorTypes.MISSING_REQUIRED_FIELD,
                message=f"不支持的 plugin_type: {plugin_type}",
                field="plugin_type",
                value=plugin_type,
                hint=f"可选值: {[e.value for e in A2FlowPluginType]}",
            )

    def _auto_resolve(self, code):
        is_component = bool(ComponentModel.objects.filter(code=code, status=1).values_list("version", flat=True))
        is_bk_plugin = BKPlugin.objects.filter(code=code).exists()
        uniform_api_meta = self._safe_fetch_uniform_api_meta(code)

        hit_types = [flag for flag, ok in [("component", is_component), ("remote_plugin", is_bk_plugin), ("uniform_api", bool(uniform_api_meta))] if ok]
        if len(hit_types) > 1:
            raise A2FlowConvertError(
                error_type=ErrorTypes.AMBIGUOUS_PLUGIN_CODE,
                message=f"插件 code '{code}' 在多个插件注册表中同时存在，请指定 plugin_type 消歧",
                field="plugin_type",
                value=code,
                hint="在节点中添加 plugin_type 字段，可选值: component, remote_plugin, uniform_api",
            )

        if is_component:
            return self._resolve_as_component(code)
        if is_bk_plugin:
            return self._resolve_as_remote_plugin(code)
        if uniform_api_meta:
            return self._resolve_as_uniform_api(code)

        raise A2FlowConvertError(
            error_type=ErrorTypes.UNKNOWN_PLUGIN_CODE,
            message=f"未找到插件 code '{code}'，请检查插件是否存在或是否需要指定 plugin_type",
            field="code",
            value=code,
            hint="请检查 code 是否存在；若发生同名冲突，可显式指定 plugin_type",
        )

    def _safe_fetch_uniform_api_meta(self, code):
        try:
            return self._fetch_uniform_api_meta(code)
        except A2FlowConvertError:
            return None

    def _resolve_as_component(self, code):
        versions = list(ComponentModel.objects.filter(code=code, status=1).values_list("version", flat=True))
        version = self._pick_latest_version(versions) if versions else "legacy"
        return ResolvedPlugin(
            plugin_type=A2FlowPluginType.COMPONENT.value,
            original_code=code,
            wrapper_code=code,
            wrapper_version=version,
        )

    def _resolve_as_remote_plugin(self, code):
        return ResolvedPlugin(
            plugin_type=A2FlowPluginType.REMOTE_PLUGIN.value,
            original_code=code,
            wrapper_code="remote_plugin",
            wrapper_version=self.REMOTE_PLUGIN_VERSION,
            remote_plugin_version=self._fetch_remote_plugin_version(code),
        )

    def _fetch_remote_plugin_version(self, code):
        from plugin_service.plugin_client import PluginServiceApiClient

        client = PluginServiceApiClient(code)
        result = client.get_meta()
        if not result["result"]:
            raise A2FlowConvertError(
                error_type=ErrorTypes.UNKNOWN_PLUGIN_CODE,
                message="查询蓝鲸标准插件版本失败: {}".format(result.get("message")),
                value=code,
            )

        versions = result["data"].get("versions") or []
        if not versions:
            raise A2FlowConvertError(
                error_type=ErrorTypes.UNKNOWN_PLUGIN_CODE,
                message="蓝鲸标准插件 '{}' 没有可用版本".format(code),
                value=code,
            )
        return self._pick_latest_version(versions)

    def _resolve_as_uniform_api(self, code):
        versions = list(ComponentModel.objects.filter(code="uniform_api", status=1).values_list("version", flat=True))
        version = self._pick_latest_version(versions) if versions else "v2.0.0"
        api_meta = self._fetch_uniform_api_meta(code)
        return ResolvedPlugin(
            plugin_type=A2FlowPluginType.UNIFORM_API.value,
            original_code=code,
            wrapper_code="uniform_api",
            wrapper_version=version,
            api_meta=api_meta,
        )

    def _fetch_uniform_api_meta(self, code):
        from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
        from bkflow.space.configs import ApiGatewayCredentialConfig, UniformApiConfig, UniformAPIConfigHandler
        from bkflow.space.models import Credential, SpaceConfig

        uniform_api_config = SpaceConfig.get_config(space_id=self.space_id, config_name=UniformApiConfig.name)
        if not uniform_api_config:
            raise A2FlowConvertError(
                error_type=ErrorTypes.UNKNOWN_PLUGIN_CODE,
                message="空间未配置 uniform_api，无法解析 API 插件 '{}'".format(code),
                value=code,
            )

        config = UniformAPIConfigHandler(uniform_api_config).handle()
        api_key = UniformApiConfig.Keys.DEFAULT_API_KEY.value
        meta_apis_url = config.api.get(api_key, {}).get(UniformApiConfig.Keys.META_APIS.value)
        if not meta_apis_url:
            raise A2FlowConvertError(
                error_type=ErrorTypes.UNKNOWN_PLUGIN_CODE,
                message="空间 uniform_api 配置缺少 meta_apis 地址，无法解析 '{}'".format(code),
                value=code,
            )

        scope = "{}_{}".format(self.scope_type, self.scope_value) if self.scope_type and self.scope_value else None
        credential_name = SpaceConfig.get_config(
            space_id=self.space_id, config_name=ApiGatewayCredentialConfig.name, scope=scope
        )
        credential = Credential.objects.filter(space_id=self.space_id, name=credential_name).first()
        if not credential:
            raise A2FlowConvertError(
                error_type=ErrorTypes.UNKNOWN_PLUGIN_CODE,
                message="空间缺少 API Gateway 凭证，无法解析 API 插件 '{}'".format(code),
                value=code,
            )

        client = UniformAPIClient()
        headers = client.gen_default_apigw_header(
            app_code=credential.content["bk_app_code"],
            app_secret=credential.content["bk_app_secret"],
            username=self.username or "admin",
        )
        list_result = client.request(
            url=meta_apis_url,
            method="GET",
            data={"limit": 200, "offset": 0},
            headers=headers,
            username=self.username or "admin",
        )
        client.validate_response_data(list_result.json_resp.get("data", {}), client.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA)
        api_item = next((item for item in list_result.json_resp["data"]["apis"] if item["id"] == code), None)
        if not api_item:
            raise A2FlowConvertError(
                error_type=ErrorTypes.UNKNOWN_PLUGIN_CODE,
                message="未在空间 uniform_api 列表中找到 API 插件 '{}'".format(code),
                value=code,
            )

        meta_result = client.request(
            url=api_item["meta_url"],
            method="GET",
            data={},
            headers=headers,
            username=self.username or "admin",
        )
        client.validate_response_data(meta_result.json_resp.get("data", {}), client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)
        meta = meta_result.json_resp["data"]
        meta.update({"meta_url": api_item["meta_url"], "api_key": api_key})
        return meta

    @staticmethod
    def _parse_version(version_str):
        if not version_str or version_str == "legacy":
            return (0, 0, 0)
        version_str = version_str.lstrip("vV")
        match = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", version_str)
        if match:
            return (
                int(match.group(1) or 0),
                int(match.group(2) or 0),
                int(match.group(3) or 0),
            )
        return (0, 0, 0)

    @classmethod
    def _pick_latest_version(cls, versions):
        if not versions:
            return "legacy"
        latest = None
        latest_tuple = (0, 0, 0)
        for v in versions:
            vt = cls._parse_version(v)
            if vt > latest_tuple:
                latest_tuple = vt
                latest = v
        return latest or "legacy"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/interface/pipeline_converter/test_plugin_resolver.py -v`
Expected: PASS (all 9 tests)

- [ ] **Step 5: Commit**

```bash
git add bkflow/pipeline_converter/converters/a2flow_v2/plugin_resolver.py tests/interface/pipeline_converter/test_plugin_resolver.py
git commit -m "feat(pipeline_converter): 添加插件类型识别器 PluginResolver --story=133123272"
```

---

### Task 4: Node Builder — Activity, StartEvent, EndEvent

**Files:**
- Create: `bkflow/pipeline_converter/converters/a2flow_v2/node_builder.py`
- Test: `tests/interface/pipeline_converter/test_node_builder.py`

**Context:** The v1 converter outputs nodes as dicts with specific structures:
- StartEvent: `{id, name, type: "EmptyStartEvent", incoming: "", outgoing: flow_id, labels: []}`
- EndEvent: `{id, name, type: "EmptyEndEvent", incoming: [flow_ids], outgoing: "", labels: []}`
- Activity: `{id, name, type: "ServiceActivity", incoming, outgoing, stage_name, component: {code, version, data}, ...DEFAULT_ACTIVITY_CONFIG}`
- `uniform_api` v3 execution additionally expects at least:
  - `component.data.uniform_api_plugin_url`
  - `component.data.uniform_api_plugin_method`
  - optional `component.data.uniform_api_plugin_credential_key`
  - `component.api_meta`

The v2 node builder takes DataModel nodes + `ResolvedPlugin` and produces these dict structures. Flow IDs are generated later by the main converter; the builder takes incoming/outgoing as parameters.

- [ ] **Step 1: Write node builder tests**

Create `tests/interface/pipeline_converter/test_node_builder.py`:

```python
from django.test import TestCase


class TestBuildStartEvent(TestCase):
    def _get_builder(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.node_builder import build_start_event

        return build_start_event

    def test_start_event_structure(self):
        build = self._get_builder()
        result = build(node_id="n_start_001", name="开始", outgoing="flow_001")
        self.assertEqual(result["id"], "n_start_001")
        self.assertEqual(result["type"], "EmptyStartEvent")
        self.assertEqual(result["incoming"], "")
        self.assertEqual(result["outgoing"], "flow_001")
        self.assertEqual(result["labels"], [])

    def test_start_event_default_name(self):
        build = self._get_builder()
        result = build(node_id="n_start_001", name="", outgoing="flow_001")
        self.assertEqual(result["name"], "")


class TestBuildEndEvent(TestCase):
    def _get_builder(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.node_builder import build_end_event

        return build_end_event

    def test_end_event_structure(self):
        build = self._get_builder()
        result = build(node_id="n_end_001", name="结束", incoming=["flow_001", "flow_002"])
        self.assertEqual(result["id"], "n_end_001")
        self.assertEqual(result["type"], "EmptyEndEvent")
        self.assertEqual(result["incoming"], ["flow_001", "flow_002"])
        self.assertEqual(result["outgoing"], "")


class TestBuildActivity(TestCase):
    def _get_builder(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.node_builder import build_activity

        return build_activity

    def test_builtin_activity(self):
        """内置插件的 Activity 结构"""
        from bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver import ResolvedPlugin

        build = self._get_builder()
        plugin = ResolvedPlugin(
            plugin_type="component",
            original_code="sleep_timer",
            wrapper_code="sleep_timer",
            wrapper_version="v1.0.0",
        )
        result = build(
            node_id="n001",
            name="等待",
            data={"bk_timing": 5},
            plugin=plugin,
            incoming=["flow_in"],
            outgoing="flow_out",
            stage_name="等待阶段",
        )
        self.assertEqual(result["id"], "n001")
        self.assertEqual(result["type"], "ServiceActivity")
        self.assertEqual(result["component"]["code"], "sleep_timer")
        self.assertEqual(result["component"]["version"], "v1.0.0")
        self.assertEqual(result["component"]["data"]["bk_timing"]["value"], 5)
        self.assertEqual(result["component"]["data"]["bk_timing"]["hook"], False)
        self.assertEqual(result["stage_name"], "等待阶段")
        self.assertTrue(result["retryable"])
        self.assertTrue(result["skippable"])

    def test_remote_plugin_activity(self):
        """蓝鲸标准插件的 Activity 包装"""
        from bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver import ResolvedPlugin

        build = self._get_builder()
        plugin = ResolvedPlugin(
            plugin_type="remote_plugin",
            original_code="my_bk_plugin",
            wrapper_code="remote_plugin",
            wrapper_version="1.0.0",
            remote_plugin_version="1.2.3",
        )
        result = build(
            node_id="n002",
            name="远程",
            data={"param1": "hello"},
            plugin=plugin,
            incoming=["flow_in"],
            outgoing="flow_out",
        )
        comp = result["component"]
        self.assertEqual(comp["code"], "remote_plugin")
        self.assertEqual(comp["version"], "1.0.0")
        self.assertEqual(comp["data"]["plugin_code"]["value"], "my_bk_plugin")
        self.assertEqual(comp["data"]["plugin_version"]["value"], "1.2.3")
        self.assertEqual(comp["data"]["param1"]["value"], "hello")

    def test_uniform_api_activity(self):
        """API 插件的 Activity 包装"""
        from bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver import ResolvedPlugin

        build = self._get_builder()
        plugin = ResolvedPlugin(
            plugin_type="uniform_api",
            original_code="my_api",
            wrapper_code="uniform_api",
            wrapper_version="v3.0.0",
            api_meta={
                "id": "my_api",
                "name": "测试API",
                "category": {},
                "meta_url": "http://example.com/meta",
                "url": "http://example.com/run",
                "methods": ["POST"],
                "api_key": "default",
            },
        )
        result = build(
            node_id="n003",
            name="API调用",
            data={"biz_id": 123},
            plugin=plugin,
            incoming=["flow_in"],
            outgoing="flow_out",
        )
        comp = result["component"]
        self.assertEqual(comp["code"], "uniform_api")
        self.assertEqual(comp["version"], "v3.0.0")
        self.assertEqual(comp["api_meta"]["id"], "my_api")
        self.assertIn("meta_url", comp["api_meta"])
        self.assertEqual(comp["api_meta"]["id"], "my_api")

    def test_data_wrapping_preserves_pre_wrapped(self):
        """已有 hook/value 结构的 data 不重复包装"""
        from bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver import ResolvedPlugin

        build = self._get_builder()
        plugin = ResolvedPlugin(
            plugin_type="component", original_code="test", wrapper_code="test", wrapper_version="v1.0.0"
        )
        result = build(
            node_id="n004",
            name="测试",
            data={"already_wrapped": {"hook": True, "value": "ref"}},
            plugin=plugin,
            incoming=["f1"],
            outgoing="f2",
        )
        self.assertEqual(result["component"]["data"]["already_wrapped"]["hook"], True)
        self.assertEqual(result["component"]["data"]["already_wrapped"]["value"], "ref")

    def test_stage_name_defaults_to_name(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver import ResolvedPlugin

        build = self._get_builder()
        plugin = ResolvedPlugin(
            plugin_type="component", original_code="test", wrapper_code="test", wrapper_version="v1.0.0"
        )
        result = build(
            node_id="n005", name="节点名", data={}, plugin=plugin, incoming=["f1"], outgoing="f2"
        )
        self.assertEqual(result["stage_name"], "节点名")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/interface/pipeline_converter/test_node_builder.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement node builder**

Create `bkflow/pipeline_converter/converters/a2flow_v2/node_builder.py`:

```python
from typing import Any, Dict, List, Optional, Union

from bkflow.pipeline_converter.constants import DEFAULT_ACTIVITY_CONFIG, A2FlowPluginType
from bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver import ResolvedPlugin


def build_start_event(node_id, name, outgoing):
    return {
        "id": node_id,
        "name": name,
        "type": "EmptyStartEvent",
        "incoming": "",
        "outgoing": outgoing,
        "labels": [],
    }


def build_end_event(node_id, name, incoming):
    return {
        "id": node_id,
        "name": name,
        "type": "EmptyEndEvent",
        "incoming": incoming,
        "outgoing": "",
        "labels": [],
    }


def _wrap_data_value(value):
    if isinstance(value, dict) and "hook" in value and "value" in value:
        return value
    return {"hook": False, "need_render": True, "value": value}


def _build_component_data(data, plugin):
    """根据插件类型构造 component.data 字典"""
    normalized = {k: _wrap_data_value(v) for k, v in data.items()}

    if plugin.plugin_type == A2FlowPluginType.REMOTE_PLUGIN.value:
        normalized["plugin_code"] = _wrap_data_value(plugin.original_code)
        normalized["plugin_version"] = _wrap_data_value(plugin.remote_plugin_version or "")
    elif plugin.plugin_type == A2FlowPluginType.UNIFORM_API.value and plugin.api_meta:
        normalized["uniform_api_plugin_url"] = _wrap_data_value(plugin.api_meta["url"])
        normalized["uniform_api_plugin_method"] = _wrap_data_value(plugin.api_meta["methods"][0])
        if plugin.api_meta.get("api_key"):
            normalized["uniform_api_plugin_credential_key"] = _wrap_data_value(plugin.api_meta["api_key"])

    return normalized


def build_activity(
    node_id: str,
    name: str,
    data: Dict[str, Any],
    plugin: ResolvedPlugin,
    incoming: Union[str, List[str]],
    outgoing: Union[str, List[str]],
    stage_name: Optional[str] = None,
) -> dict:
    component_data = _build_component_data(data, plugin)

    activity = {
        "id": node_id,
        "name": name,
        "type": "ServiceActivity",
        "incoming": incoming,
        "outgoing": outgoing,
        "stage_name": stage_name or name,
        "component": {
            "code": plugin.wrapper_code,
            "version": plugin.wrapper_version,
            "data": component_data,
        },
    }

    if plugin.plugin_type == A2FlowPluginType.UNIFORM_API.value and plugin.api_meta:
        activity["component"]["api_meta"] = plugin.api_meta

    activity.update(DEFAULT_ACTIVITY_CONFIG)
    return activity
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/interface/pipeline_converter/test_node_builder.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add bkflow/pipeline_converter/converters/a2flow_v2/node_builder.py tests/interface/pipeline_converter/test_node_builder.py
git commit -m "feat(pipeline_converter): 添加节点构建器 — Activity/Start/End --story=133123272"
```

---

### Task 5: Gateway Builder

**Files:**
- Create: `bkflow/pipeline_converter/converters/a2flow_v2/gateway_builder.py`
- Test: `tests/interface/pipeline_converter/test_gateway_builder.py`

**Context:** v1 gateway output structure:
- All gateways: `{id, name, type, incoming: [flow_ids], outgoing: [flow_ids] or flow_id}`
- ExclusiveGateway/ConditionalParallelGateway: + `conditions: {flow_id: {evaluate, name, tag}}`
- ExclusiveGateway: + `default_condition: {flow_id, name}` (or `{}`)
- ParallelGateway/ConditionalParallelGateway: + `converge_gateway_id: str`

In v2, conditions come from the node's `conditions` array (positionally aligned with `next` array). The builder needs the mapping from next-index to flow_id.

- [ ] **Step 1: Write gateway builder tests**

Create `tests/interface/pipeline_converter/test_gateway_builder.py`:

```python
from django.test import TestCase


class TestBuildParallelGateway(TestCase):
    def _get_builder(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.gateway_builder import build_gateway

        return build_gateway

    def test_parallel_gateway(self):
        build = self._get_builder()
        result = build(
            node_id="pg1",
            name="并行",
            node_type="ParallelGateway",
            incoming=["f_in"],
            outgoing=["f_out1", "f_out2"],
            converge_gateway_id="cg1",
        )
        self.assertEqual(result["id"], "pg1")
        self.assertEqual(result["type"], "ParallelGateway")
        self.assertEqual(result["outgoing"], ["f_out1", "f_out2"])
        self.assertEqual(result["converge_gateway_id"], "cg1")
        self.assertNotIn("conditions", result)


class TestBuildExclusiveGateway(TestCase):
    def _get_builder(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.gateway_builder import build_gateway

        return build_gateway

    def test_exclusive_gateway_with_conditions(self):
        build = self._get_builder()
        result = build(
            node_id="eg1",
            name="判断",
            node_type="ExclusiveGateway",
            incoming=["f_in"],
            outgoing=["f_out1", "f_out2"],
            conditions=[{"evaluate": "${x} > 0"}, {"evaluate": "${x} <= 0"}],
            default_next_flow_id="f_out2",
        )
        self.assertEqual(result["type"], "ExclusiveGateway")
        self.assertIn("f_out1", result["conditions"])
        self.assertIn("f_out2", result["conditions"])
        self.assertEqual(result["conditions"]["f_out1"]["evaluate"], "${x} > 0")
        self.assertEqual(result["default_condition"]["flow_id"], "f_out2")

    def test_exclusive_gateway_no_default(self):
        build = self._get_builder()
        result = build(
            node_id="eg2",
            name="判断",
            node_type="ExclusiveGateway",
            incoming=["f_in"],
            outgoing=["f_out1", "f_out2"],
            conditions=[{"evaluate": "${x} > 0"}, {"evaluate": "${x} <= 0"}],
        )
        self.assertEqual(result["default_condition"], {})


class TestBuildConditionalParallelGateway(TestCase):
    def _get_builder(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.gateway_builder import build_gateway

        return build_gateway

    def test_conditional_parallel_with_conditions(self):
        build = self._get_builder()
        result = build(
            node_id="cpg1",
            name="条件并行",
            node_type="ConditionalParallelGateway",
            incoming=["f_in"],
            outgoing=["f_out1", "f_out2"],
            conditions=[{"evaluate": "${env} == 'prod'"}, {"evaluate": "${env} == 'test'"}],
            converge_gateway_id="cg1",
        )
        self.assertEqual(result["type"], "ConditionalParallelGateway")
        self.assertIn("conditions", result)
        self.assertEqual(result["converge_gateway_id"], "cg1")


class TestBuildConvergeGateway(TestCase):
    def _get_builder(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.gateway_builder import build_gateway

        return build_gateway

    def test_converge_gateway(self):
        build = self._get_builder()
        result = build(
            node_id="cg1",
            name="汇聚",
            node_type="ConvergeGateway",
            incoming=["f1", "f2"],
            outgoing=["f_out"],
        )
        self.assertEqual(result["type"], "ConvergeGateway")
        self.assertEqual(result["outgoing"], "f_out")
        self.assertNotIn("conditions", result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/interface/pipeline_converter/test_gateway_builder.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement gateway builder**

Create `bkflow/pipeline_converter/converters/a2flow_v2/gateway_builder.py`:

```python
from typing import Dict, List, Optional


def _build_conditions(outgoing_flow_ids, conditions_data):
    """
    将 a2flow v2 的 conditions 数组（与 next 位置对应）转换为 pipeline_tree 的 conditions dict。

    :param outgoing_flow_ids: 与 next 一一对应的 flow ID 列表
    :param conditions_data: a2flow conditions 列表 [{"evaluate": "..."}]
    :return: {flow_id: {"evaluate": expr, "name": "", "tag": "branch_{flow_id}"}}
    """
    result = {}
    for idx, flow_id in enumerate(outgoing_flow_ids):
        if idx < len(conditions_data):
            cond = conditions_data[idx]
            evaluate = cond.get("evaluate", "True") if isinstance(cond, dict) else "True"
            name = cond.get("name", "") if isinstance(cond, dict) else ""
        else:
            evaluate = "True"
            name = ""
        result[flow_id] = {
            "evaluate": evaluate,
            "name": name,
            "tag": "branch_{}".format(flow_id),
        }
    return result


def build_gateway(
    node_id: str,
    name: str,
    node_type: str,
    incoming: List[str],
    outgoing: List[str],
    conditions: Optional[List[dict]] = None,
    default_next_flow_id: Optional[str] = None,
    converge_gateway_id: Optional[str] = None,
) -> dict:
    if node_type == "ConvergeGateway":
        outgoing_value = outgoing[0] if outgoing else ""
    else:
        outgoing_value = outgoing

    gateway = {
        "id": node_id,
        "name": name,
        "type": node_type,
        "incoming": incoming,
        "outgoing": outgoing_value,
    }

    if node_type in ("ExclusiveGateway", "ConditionalParallelGateway"):
        gateway["conditions"] = _build_conditions(outgoing, conditions or [])

    if node_type == "ExclusiveGateway":
        if default_next_flow_id:
            gateway["default_condition"] = {"flow_id": default_next_flow_id, "name": "默认分支"}
        else:
            gateway["default_condition"] = {}

    if node_type in ("ParallelGateway", "ConditionalParallelGateway"):
        gateway["converge_gateway_id"] = converge_gateway_id or ""

    return gateway
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/interface/pipeline_converter/test_gateway_builder.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add bkflow/pipeline_converter/converters/a2flow_v2/gateway_builder.py tests/interface/pipeline_converter/test_gateway_builder.py
git commit -m "feat(pipeline_converter): 添加网关构建器 --story=133123272"
```

---

### Task 6: Variable Builder

**Files:**
- Create: `bkflow/pipeline_converter/converters/a2flow_v2/variable_builder.py`
- Test: `tests/interface/pipeline_converter/test_variable_builder.py`

- [ ] **Step 1: Write variable builder tests**

Create `tests/interface/pipeline_converter/test_variable_builder.py`:

```python
from django.test import TestCase


class TestBuildConstant(TestCase):
    def _get_builder(self):
        from bkflow.pipeline_converter.converters.a2flow_v2.variable_builder import build_constant

        return build_constant

    def test_basic_constant(self):
        build = self._get_builder()
        from bkflow.pipeline_converter.converters.a2flow_v2.data_models import A2FlowVariable

        var = A2FlowVariable(key="${ip}", name="服务器IP", value="10.0.0.1", description="目标机器")
        result = build(var, index=0)
        self.assertEqual(result["key"], "${ip}")
        self.assertEqual(result["name"], "服务器IP")
        self.assertEqual(result["value"], "10.0.0.1")
        self.assertEqual(result["desc"], "目标机器")
        self.assertEqual(result["custom_type"], "input")
        self.assertEqual(result["source_type"], "custom")
        self.assertEqual(result["show_type"], "show")
        self.assertEqual(result["index"], 0)
        self.assertFalse(result["hook"])
        self.assertTrue(result["need_render"])

    def test_hidden_variable(self):
        build = self._get_builder()
        from bkflow.pipeline_converter.converters.a2flow_v2.data_models import A2FlowVariable

        var = A2FlowVariable(key="${secret}", show_type="hide", value="token123")
        result = build(var, index=1)
        self.assertEqual(result["show_type"], "hide")
        self.assertEqual(result["index"], 1)

    def test_defaults(self):
        build = self._get_builder()
        from bkflow.pipeline_converter.converters.a2flow_v2.data_models import A2FlowVariable

        var = A2FlowVariable(key="${x}")
        result = build(var, index=0)
        self.assertEqual(result["name"], "")
        self.assertEqual(result["value"], "")
        self.assertEqual(result["desc"], "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/interface/pipeline_converter/test_variable_builder.py -v`
Expected: FAIL

- [ ] **Step 3: Implement variable builder**

Create `bkflow/pipeline_converter/converters/a2flow_v2/variable_builder.py`:

```python
from bkflow.pipeline_converter.converters.a2flow_v2.data_models import A2FlowVariable


def build_constant(var: A2FlowVariable, index: int) -> dict:
    return {
        "key": var.key,
        "name": var.name,
        "value": var.value,
        "desc": var.description,
        "custom_type": var.custom_type,
        "source_type": var.source_type,
        "source_tag": "",
        "source_info": {},
        "show_type": var.show_type,
        "validation": "",
        "index": index,
        "version": "legacy",
        "form_schema": {},
        "hook": False,
        "need_render": True,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/interface/pipeline_converter/test_variable_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bkflow/pipeline_converter/converters/a2flow_v2/variable_builder.py tests/interface/pipeline_converter/test_variable_builder.py
git commit -m "feat(pipeline_converter): 添加变量构建器 --story=133123272"
```

---

### Task 7: Main Converter — A2FlowV2Converter

**Files:**
- Create: `bkflow/pipeline_converter/converters/a2flow_v2/converter.py`
- Modify: `bkflow/pipeline_converter/converters/a2flow_v2/__init__.py`
- Test: `tests/interface/pipeline_converter/test_converter.py`

**Context:** This is the orchestrator that:
1. Parses input via `A2FlowPipeline` DataModel
2. Injects implicit StartEvent/EndEvent
3. Validates node references (next → valid node IDs)
4. Resolves plugins via `PluginResolver`
5. Generates flow IDs and connects nodes via `next` field
6. Infers converge_gateway_id via topo sort + stack
7. Builds pipeline_tree dict using node/gateway/variable builders

- [ ] **Step 1: Write converter tests**

Create `tests/interface/pipeline_converter/test_converter.py`:

```python
from unittest.mock import MagicMock, patch

from django.test import TestCase

COMPONENT_PATCH = "bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel"
BKPLUGIN_PATCH = "bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.BKPlugin"


def _mock_component_model(mock_cm, codes_versions=None):
    """Helper: ComponentModel mock that returns versions for given codes."""
    codes_versions = codes_versions or {}

    def filter_side_effect(**kwargs):
        result = MagicMock()
        code = kwargs.get("code") or kwargs.get("code__in", [None])
        if isinstance(code, (list, set)):
            all_versions = []
            for c in code:
                all_versions.extend(codes_versions.get(c, []))
            result.values_list.return_value = all_versions
        else:
            result.values_list.return_value = codes_versions.get(code, [])
        result.exists.return_value = bool(result.values_list.return_value)
        return result

    mock_cm.objects.filter.side_effect = filter_side_effect


def _get_converter_class():
    from bkflow.pipeline_converter.converters.a2flow_v2.converter import A2FlowV2Converter

    return A2FlowV2Converter


class TestConverterLinearFlow(TestCase):
    """线性流程转换测试"""

    @patch(BKPLUGIN_PATCH)
    @patch(COMPONENT_PATCH)
    def test_single_activity(self, mock_cm, mock_bkp):
        """最简流程：1 个 Activity，隐式 Start/End"""
        _mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False

        Converter = _get_converter_class()
        a2flow_data = {
            "version": "2.0",
            "name": "简单流程",
            "nodes": [
                {"id": "n1", "name": "等待", "code": "sleep_timer", "data": {"bk_timing": 5}, "next": "end"},
            ],
        }
        result = Converter(a2flow_data, space_id=1).convert()

        self.assertIn("start_event", result)
        self.assertIn("end_event", result)
        self.assertEqual(len(result["activities"]), 1)
        self.assertEqual(result["start_event"]["type"], "EmptyStartEvent")
        self.assertEqual(result["end_event"]["type"], "EmptyEndEvent")
        self.assertEqual(len(result["flows"]), 2)
        self.assertEqual(result["constants"], {})

    @patch(BKPLUGIN_PATCH)
    @patch(COMPONENT_PATCH)
    def test_two_activities_linear(self, mock_cm, mock_bkp):
        """2 个 Activity 串行"""
        _mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"], "bk_notify": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "两步流程",
            "nodes": [
                {"id": "n1", "name": "等待", "code": "sleep_timer", "data": {"bk_timing": 5}, "next": "n2"},
                {"id": "n2", "name": "通知", "code": "bk_notify", "data": {"title": "done"}, "next": "end"},
            ],
        }
        result = Converter(a2flow_data, space_id=1).convert()

        self.assertEqual(len(result["activities"]), 2)
        self.assertEqual(len(result["flows"]), 3)

    @patch(BKPLUGIN_PATCH)
    @patch(COMPONENT_PATCH)
    def test_explicit_start_and_end(self, mock_cm, mock_bkp):
        """显式声明 StartEvent/EndEvent 不重复注入"""
        _mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "显式事件",
            "nodes": [
                {"type": "StartEvent", "id": "my_start", "name": "开始", "next": "n1"},
                {"id": "n1", "name": "等待", "code": "sleep_timer", "next": "my_end"},
                {"type": "EndEvent", "id": "my_end", "name": "结束"},
            ],
        }
        result = Converter(a2flow_data, space_id=1).convert()

        self.assertEqual(len(result["activities"]), 1)
        self.assertNotEqual(result["start_event"]["id"], "start")

    @patch(BKPLUGIN_PATCH)
    @patch(COMPONENT_PATCH)
    def test_variables(self, mock_cm, mock_bkp):
        """变量转换"""
        _mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "带变量",
            "nodes": [{"id": "n1", "name": "x", "code": "sleep_timer", "next": "end"}],
            "variables": [{"key": "${ip}", "name": "IP", "value": "10.0.0.1"}],
        }
        result = Converter(a2flow_data, space_id=1).convert()

        self.assertIn("${ip}", result["constants"])
        self.assertEqual(result["constants"]["${ip}"]["value"], "10.0.0.1")


class TestConverterGatewayFlow(TestCase):
    """包含网关的流程转换测试"""

    @patch(BKPLUGIN_PATCH)
    @patch(COMPONENT_PATCH)
    def test_parallel_gateway(self, mock_cm, mock_bkp):
        """并行网关 + 汇聚网关"""
        _mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "并行流程",
            "nodes": [
                {"id": "n1", "name": "入口", "code": "sleep_timer", "next": "pg1"},
                {"type": "ParallelGateway", "id": "pg1", "name": "并行", "next": ["n2", "n3"]},
                {"id": "n2", "name": "分支A", "code": "sleep_timer", "next": "cg1"},
                {"id": "n3", "name": "分支B", "code": "sleep_timer", "next": "cg1"},
                {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚", "next": "end"},
            ],
        }
        result = Converter(a2flow_data, space_id=1).convert()

        self.assertEqual(len(result["gateways"]), 2)
        pg = [g for g in result["gateways"].values() if g["type"] == "ParallelGateway"][0]
        cg = [g for g in result["gateways"].values() if g["type"] == "ConvergeGateway"][0]
        self.assertEqual(pg["converge_gateway_id"], cg["id"])

    @patch(BKPLUGIN_PATCH)
    @patch(COMPONENT_PATCH)
    def test_exclusive_gateway(self, mock_cm, mock_bkp):
        """排他网关 + 条件"""
        _mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "条件流程",
            "nodes": [
                {"id": "n1", "name": "入口", "code": "sleep_timer", "next": "eg1"},
                {
                    "type": "ExclusiveGateway",
                    "id": "eg1",
                    "name": "判断",
                    "next": ["n2", "n3"],
                    "conditions": [{"evaluate": "${x} > 0"}, {"evaluate": "${x} <= 0"}],
                    "default_next": "n3",
                },
                {"id": "n2", "name": "成功", "code": "sleep_timer", "next": "cg1"},
                {"id": "n3", "name": "失败", "code": "sleep_timer", "next": "cg1"},
                {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚", "next": "end"},
            ],
        }
        result = Converter(a2flow_data, space_id=1).convert()

        eg = [g for g in result["gateways"].values() if g["type"] == "ExclusiveGateway"][0]
        self.assertIn("conditions", eg)
        self.assertIn("default_condition", eg)


class TestConverterValidation(TestCase):
    """转换校验测试"""

    def test_invalid_next_reference(self):
        """引用不存在的节点应报错"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "错误引用",
            "nodes": [{"id": "n1", "name": "x", "code": "y", "next": "nonexistent"}],
        }
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "INVALID_REFERENCE" for e in errors))

    def test_duplicate_node_id(self):
        """重复节点 ID 应报错"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "重复ID",
            "nodes": [
                {"id": "n1", "name": "a", "code": "x", "next": "end"},
                {"id": "n1", "name": "b", "code": "y", "next": "end"},
            ],
        }
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "DUPLICATE_NODE_ID" for e in errors))

    def test_conditions_mismatch(self):
        """conditions 数量与 next 分支数不一致应报错"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "条件不匹配",
            "nodes": [
                {"id": "n1", "name": "入口", "code": "x", "next": "eg1"},
                {
                    "type": "ExclusiveGateway",
                    "id": "eg1",
                    "name": "判断",
                    "next": ["n2", "n3"],
                    "conditions": [{"evaluate": "True"}],
                },
                {"id": "n2", "name": "a", "code": "x", "next": "cg1"},
                {"id": "n3", "name": "b", "code": "x", "next": "cg1"},
                {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚", "next": "end"},
            ],
        }
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "CONDITIONS_MISMATCH" for e in errors))

    def test_activity_missing_next(self):
        """Activity 缺少 next 应报 MISSING_REQUIRED_FIELD"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "缺少next",
            "nodes": [{"id": "n1", "name": "x", "code": "y"}],
        }
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "MISSING_REQUIRED_FIELD" and e.field == "next" for e in errors))

    def test_gateway_missing_conditions(self):
        """ExclusiveGateway 缺少 conditions 应报 MISSING_REQUIRED_FIELD"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "缺少conditions",
            "nodes": [
                {"id": "n1", "name": "入口", "code": "x", "next": "eg1"},
                {"type": "ExclusiveGateway", "id": "eg1", "name": "判断", "next": ["n2", "n3"]},
                {"id": "n2", "name": "a", "code": "x", "next": "cg1"},
                {"id": "n3", "name": "b", "code": "x", "next": "cg1"},
                {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚", "next": "end"},
            ],
        }
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "MISSING_REQUIRED_FIELD" and e.field == "conditions" for e in errors))

    def test_parallel_gateway_next_must_be_list(self):
        """ParallelGateway 的 next 必须是数组"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "错误并行",
            "nodes": [
                {"id": "n1", "name": "入口", "code": "x", "next": "pg1"},
                {"type": "ParallelGateway", "id": "pg1", "name": "并行", "next": "n2"},
                {"id": "n2", "name": "a", "code": "x", "next": "end"},
            ],
        }
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "MISSING_REQUIRED_FIELD" and e.field == "next" for e in errors))

    def test_converge_gateway_next_must_be_string(self):
        """ConvergeGateway 的 next 必须是字符串"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "错误汇聚",
            "nodes": [
                {"id": "n1", "name": "入口", "code": "x", "next": "cg1"},
                {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚", "next": ["end"]},
            ],
        }
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "MISSING_REQUIRED_FIELD" and e.field == "next" for e in errors))

    def test_unsupported_version(self):
        """不支持的 version 应报 UNSUPPORTED_VERSION"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {
            "version": "9.9",
            "name": "错误版本",
            "nodes": [{"id": "n1", "name": "x", "code": "y", "next": "end"}],
        }
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "UNSUPPORTED_VERSION" for e in errors))

    def test_reserved_id_conflict(self):
        """保留 ID start/end 仅允许对应事件类型"""
        from bkflow.pipeline_converter.exceptions import A2FlowValidationError

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "保留ID冲突",
            "nodes": [{"id": "start", "name": "非法", "code": "y", "next": "end"}],
        }
        with self.assertRaises(A2FlowValidationError) as ctx:
            Converter(a2flow_data, space_id=1).convert()
        errors = ctx.exception.errors
        self.assertTrue(any(e.error_type == "RESERVED_ID_CONFLICT" for e in errors))

    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._fetch_uniform_api_meta")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.PluginResolver._safe_fetch_uniform_api_meta")
    @patch(BKPLUGIN_PATCH)
    @patch(COMPONENT_PATCH)
    def test_plugin_type_flow(self, mock_cm, mock_bkp, mock_safe_fetch, mock_fetch_meta):
        """混合插件类型流程"""
        _mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False
        mock_safe_fetch.return_value = None
        mock_fetch_meta.return_value = {
            "id": "my_api",
            "name": "测试API",
            "category": {},
            "meta_url": "http://example.com/meta",
            "url": "http://example.com/run",
            "methods": ["POST"],
            "api_key": "default",
        }

        Converter = _get_converter_class()
        a2flow_data = {
            "name": "混合插件",
            "nodes": [
                {"id": "n1", "name": "内置", "code": "sleep_timer", "next": "n2"},
                {
                    "id": "n2",
                    "name": "API调用",
                    "code": "my_api",
                    "plugin_type": "uniform_api",
                    "data": {"biz_id": 1},
                    "next": "end",
                },
            ],
        }
        result = Converter(a2flow_data, space_id=1).convert()

        activities = list(result["activities"].values())
        self.assertEqual(activities[0]["component"]["code"], "sleep_timer")
        self.assertEqual(activities[1]["component"]["code"], "uniform_api")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/interface/pipeline_converter/test_converter.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement main converter**

Create `bkflow/pipeline_converter/converters/a2flow_v2/converter.py`:

```python
import logging
import uuid
from collections import defaultdict, deque

from bkflow.pipeline_converter.constants import BRANCH_GATEWAY_TYPES, GATEWAY_TYPES, RESERVED_IDS, NodeType
from bkflow.pipeline_converter.converters.a2flow_v2.data_models import A2FlowPipeline
from bkflow.pipeline_converter.converters.a2flow_v2.gateway_builder import build_gateway
from bkflow.pipeline_converter.converters.a2flow_v2.node_builder import build_activity, build_end_event, build_start_event
from bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver import PluginResolver
from bkflow.pipeline_converter.converters.a2flow_v2.variable_builder import build_constant
from bkflow.pipeline_converter.exceptions import A2FlowConvertError, A2FlowValidationError, ErrorTypes

logger = logging.getLogger("root")


class A2FlowV2Converter:
    """
    a2flow v2.0 JSON → pipeline_tree dict 转换器

    处理流程:
    1. Pydantic DataModel 解析输入
    2. 隐式注入 StartEvent / EndEvent
    3. 校验节点引用、条件数量等
    4. 批量识别插件类型
    5. 生成 flow 连接 (从 next 字段)
    6. 推断 converge_gateway_id
    7. 组装 pipeline_tree
    """

    def __init__(self, a2flow_data: dict, space_id: int, username: str = "", scope_type: str = None, scope_value: str = None):
        self.a2flow_data = a2flow_data
        self.space_id = space_id
        self.username = username
        self.scope_type = scope_type
        self.scope_value = scope_value

    def convert(self) -> dict:
        pipeline = A2FlowPipeline(**self.a2flow_data)
        normalized_version = str(pipeline.version)
        if normalized_version in ("2", "2.0"):
            pipeline.version = "2.0"
        if pipeline.version != "2.0":
            raise A2FlowValidationError(
                A2FlowConvertError(
                    error_type=ErrorTypes.UNSUPPORTED_VERSION,
                    message="不支持的 a2flow 版本: '{}'".format(pipeline.version),
                    field="version",
                    value=pipeline.version,
                    hint="当前仅支持版本: 2.0",
                )
            )

        nodes = list(pipeline.nodes)
        nodes = self._inject_start_end(nodes)

        node_map = {}
        for node in nodes:
            node_map[node.id] = node

        self._validate(nodes, node_map)

        id_mapping = self._generate_id_mapping(nodes)

        plugin_resolver = PluginResolver(
            self.space_id, username=self.username, scope_type=self.scope_type, scope_value=self.scope_value
        )
        activity_infos = [
            {"code": n.code, "plugin_type": n.plugin_type}
            for n in nodes
            if n.type == NodeType.ACTIVITY and n.code
        ]
        plugin_map = plugin_resolver.resolve_batch(activity_infos)

        flows, node_incoming, node_outgoing, next_to_flow = self._build_flows(nodes, id_mapping)

        self._infer_converge_gateway_ids(nodes, node_map, id_mapping)

        activities = {}
        gateways = {}
        start_event = None
        end_event = None

        for node in nodes:
            new_id = id_mapping[node.id]
            incoming = node_incoming.get(new_id, [])
            outgoing = node_outgoing.get(new_id, [])

            if node.type == NodeType.START_EVENT:
                start_event = build_start_event(
                    node_id=new_id,
                    name=node.name,
                    outgoing=outgoing[0] if outgoing else "",
                )
            elif node.type == NodeType.END_EVENT:
                end_event = build_end_event(
                    node_id=new_id,
                    name=node.name,
                    incoming=incoming,
                )
            elif node.type == NodeType.ACTIVITY:
                plugin = plugin_map.get((node.code, node.plugin_type))
                outgoing_val = outgoing[0] if len(outgoing) == 1 else outgoing
                activities[new_id] = build_activity(
                    node_id=new_id,
                    name=node.name,
                    data=node.data,
                    plugin=plugin,
                    incoming=incoming,
                    outgoing=outgoing_val,
                    stage_name=node.stage_name,
                )
            elif node.type in GATEWAY_TYPES:
                default_next_flow_id = None
                if node.type == NodeType.EXCLUSIVE_GATEWAY and node.default_next:
                    default_next_flow_id = next_to_flow.get((node.id, node.default_next))

                converge_gw_id = None
                if node.converge_gateway_id:
                    converge_gw_id = id_mapping.get(node.converge_gateway_id, node.converge_gateway_id)

                conditions_data = None
                if node.conditions:
                    conditions_data = [{"evaluate": c.evaluate, "name": c.name} for c in node.conditions]

                gateways[new_id] = build_gateway(
                    node_id=new_id,
                    name=node.name,
                    node_type=node.type,
                    incoming=incoming,
                    outgoing=outgoing,
                    conditions=conditions_data,
                    default_next_flow_id=default_next_flow_id,
                    converge_gateway_id=converge_gw_id,
                )

        constants = {}
        for idx, var in enumerate(pipeline.variables):
            constants[var.key] = build_constant(var, idx)

        return {
            "activities": activities,
            "gateways": gateways,
            "flows": flows,
            "start_event": start_event,
            "end_event": end_event,
            "constants": constants,
            "outputs": [],
            "canvas_mode": "horizontal",
        }

    def _inject_start_end(self, nodes):
        """如果没有 StartEvent/EndEvent，自动注入"""
        from bkflow.pipeline_converter.converters.a2flow_v2.data_models import A2FlowNode

        has_start = any(n.type == NodeType.START_EVENT for n in nodes)
        has_end = any(n.type == NodeType.END_EVENT for n in nodes)

        if not has_start:
            first_node_id = nodes[0].id if nodes else "end"
            start_node = A2FlowNode(id="start", name="开始", type=NodeType.START_EVENT, next=first_node_id)
            nodes.insert(0, start_node)

        if not has_end:
            end_node = A2FlowNode(id="end", name="结束", type=NodeType.END_EVENT)
            nodes.append(end_node)

        return nodes

    def _validate(self, nodes, node_map):
        """校验节点引用和约束"""
        errors = []
        seen_ids = set()
        valid_ids = set(node_map.keys())

        for node in nodes:
            if node.id in RESERVED_IDS and (
                (node.id == "start" and node.type != NodeType.START_EVENT)
                or (node.id == "end" and node.type != NodeType.END_EVENT)
            ):
                errors.append(
                    A2FlowConvertError(
                        error_type=ErrorTypes.RESERVED_ID_CONFLICT,
                        message="保留 ID '{}' 只能用于对应的开始/结束事件节点".format(node.id),
                        node_id=node.id,
                        field="id",
                        value=node.id,
                        hint="start 仅允许 StartEvent，end 仅允许 EndEvent",
                    )
                )

            if node.type != NodeType.END_EVENT and node.next is None:
                errors.append(
                    A2FlowConvertError(
                        error_type=ErrorTypes.MISSING_REQUIRED_FIELD,
                        message="节点 '{}' 缺少 next 字段".format(node.id),
                        node_id=node.id,
                        field="next",
                    )
                )

            if node.type in (NodeType.PARALLEL_GATEWAY, NodeType.EXCLUSIVE_GATEWAY, NodeType.CONDITIONAL_PARALLEL_GATEWAY):
                if node.next is not None and not isinstance(node.next, list):
                    errors.append(
                        A2FlowConvertError(
                            error_type=ErrorTypes.MISSING_REQUIRED_FIELD,
                            message="节点 '{}' 的 next 必须是数组".format(node.id),
                            node_id=node.id,
                            field="next",
                            value=node.next,
                            hint="分支网关的 next 需为分支目标 ID 数组",
                        )
                    )

            if node.type in (NodeType.ACTIVITY, NodeType.START_EVENT, NodeType.CONVERGE_GATEWAY):
                if isinstance(node.next, list):
                    errors.append(
                        A2FlowConvertError(
                            error_type=ErrorTypes.MISSING_REQUIRED_FIELD,
                            message="节点 '{}' 的 next 必须是单个字符串 ID".format(node.id),
                            node_id=node.id,
                            field="next",
                            value=node.next,
                            hint="该类型节点只允许一个下游节点",
                        )
                    )

            if node.id in seen_ids:
                errors.append(
                    A2FlowConvertError(
                        error_type=ErrorTypes.DUPLICATE_NODE_ID,
                        message=f"重复的节点 ID: '{node.id}'",
                        node_id=node.id,
                    )
                )
            seen_ids.add(node.id)

            if node.next is not None:
                next_ids = [node.next] if isinstance(node.next, str) else node.next
                for nid in next_ids:
                    if nid not in valid_ids:
                        errors.append(
                            A2FlowConvertError(
                                error_type=ErrorTypes.INVALID_REFERENCE,
                                message=f"节点 '{node.id}' 的 next 引用了未定义的节点 '{nid}'",
                                node_id=node.id,
                                field="next",
                                value=nid,
                                hint=f"可用的节点 ID: {sorted(valid_ids)}",
                            )
                        )

            if node.type in (NodeType.EXCLUSIVE_GATEWAY, NodeType.CONDITIONAL_PARALLEL_GATEWAY):
                if not node.conditions:
                    errors.append(
                        A2FlowConvertError(
                            error_type=ErrorTypes.MISSING_REQUIRED_FIELD,
                            message="节点 '{}' 缺少 conditions 字段".format(node.id),
                            node_id=node.id,
                            field="conditions",
                        )
                    )
                if node.conditions and node.next:
                    next_count = len(node.next) if isinstance(node.next, list) else 1
                    if len(node.conditions) != next_count:
                        errors.append(
                            A2FlowConvertError(
                                error_type=ErrorTypes.CONDITIONS_MISMATCH,
                                message=f"节点 '{node.id}' 的 conditions 数量 ({len(node.conditions)}) 与 next 分支数 ({next_count}) 不一致",
                                node_id=node.id,
                                field="conditions",
                            )
                        )

            if node.type == NodeType.EXCLUSIVE_GATEWAY and node.default_next:
                next_ids = node.next if isinstance(node.next, list) else [node.next] if node.next else []
                if node.default_next not in next_ids:
                    errors.append(
                        A2FlowConvertError(
                            error_type=ErrorTypes.INVALID_DEFAULT_NEXT,
                            message=f"节点 '{node.id}' 的 default_next '{node.default_next}' 不在 next 列表中",
                            node_id=node.id,
                            field="default_next",
                            value=node.default_next,
                            hint=f"default_next 必须是 next 中的某一个: {next_ids}",
                        )
                    )

            if node.type == NodeType.ACTIVITY and not node.code:
                errors.append(
                    A2FlowConvertError(
                        error_type=ErrorTypes.MISSING_REQUIRED_FIELD,
                        message=f"Activity 节点 '{node.id}' 缺少 code 字段",
                        node_id=node.id,
                        field="code",
                    )
                )

        if errors:
            raise A2FlowValidationError(errors)

    def _generate_id_mapping(self, nodes):
        """为每个节点生成唯一 ID"""
        mapping = {}
        for node in nodes:
            mapping[node.id] = "n{}".format(uuid.uuid4().hex[:31])
        return mapping

    def _build_flows(self, nodes, id_mapping):
        """从 next 字段生成 flow 连接"""
        flows = {}
        node_incoming = defaultdict(list)
        node_outgoing = defaultdict(list)
        next_to_flow = {}

        for node in nodes:
            if node.next is None:
                continue
            next_ids = [node.next] if isinstance(node.next, str) else node.next
            source = id_mapping[node.id]

            for target_original_id in next_ids:
                target = id_mapping.get(target_original_id, target_original_id)
                flow_id = "l{}".format(uuid.uuid4().hex[:30])
                is_default = bool(
                    node.type == NodeType.EXCLUSIVE_GATEWAY
                    and getattr(node, "default_next", None)
                    and target_original_id == node.default_next
                )
                flows[flow_id] = {
                    "id": flow_id,
                    "is_default": is_default,
                    "source": source,
                    "target": target,
                }
                node_outgoing[source].append(flow_id)
                node_incoming[target].append(flow_id)
                next_to_flow[(node.id, target_original_id)] = flow_id

        return flows, dict(node_incoming), dict(node_outgoing), next_to_flow

    def _infer_converge_gateway_ids(self, nodes, node_map, id_mapping):
        """拓扑排序 + 栈配对推断 converge_gateway_id"""
        needs_infer = {}
        for node in nodes:
            if node.type in (NodeType.PARALLEL_GATEWAY, NodeType.CONDITIONAL_PARALLEL_GATEWAY):
                if not node.converge_gateway_id:
                    needs_infer[node.id] = node

        if not needs_infer:
            return

        adj = defaultdict(list)
        in_degree = defaultdict(int)
        for node in nodes:
            in_degree.setdefault(node.id, 0)
            if node.next is not None:
                next_ids = [node.next] if isinstance(node.next, str) else node.next
                for nid in next_ids:
                    adj[node.id].append(nid)
                    in_degree[nid] = in_degree.get(nid, 0) + 1

        queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
        topo_order = []
        while queue:
            curr = queue.popleft()
            topo_order.append(curr)
            for nxt in adj[curr]:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)

        stack = []
        for nid in topo_order:
            node = node_map.get(nid)
            if not node:
                continue
            if node.type in BRANCH_GATEWAY_TYPES:
                stack.append(nid)
            elif node.type == NodeType.CONVERGE_GATEWAY and stack:
                branch_id = stack.pop()
                if branch_id in needs_infer:
                    needs_infer[branch_id].converge_gateway_id = nid

        unresolved = [node_id for node_id, node in needs_infer.items() if not node.converge_gateway_id]
        if unresolved:
            raise A2FlowValidationError(
                [
                    A2FlowConvertError(
                        error_type=ErrorTypes.CONVERGE_INFER_FAILED,
                        message="节点 '{}' 无法自动推断 converge_gateway_id".format(node_id),
                        node_id=node_id,
                        field="converge_gateway_id",
                        hint="请补充显式 converge_gateway_id，或检查网关拓扑是否缺少汇聚节点",
                    )
                    for node_id in unresolved
                ]
            )
```

- [ ] **Step 4: Export from `__init__.py`**

Update `bkflow/pipeline_converter/converters/a2flow_v2/__init__.py`:

```python
from bkflow.pipeline_converter.converters.a2flow_v2.converter import A2FlowV2Converter

__all__ = ["A2FlowV2Converter"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/interface/pipeline_converter/test_converter.py -v`
Expected: PASS (all tests)

- [ ] **Step 6: Commit**

```bash
git add bkflow/pipeline_converter/converters/a2flow_v2/converter.py bkflow/pipeline_converter/converters/a2flow_v2/__init__.py tests/interface/pipeline_converter/test_converter.py
git commit -m "feat(pipeline_converter): 实现 A2FlowV2Converter 主转换器 --story=133123272"
```

---

### Task 8: Update Serializer

**Files:**
- Modify: `bkflow/apigw/serializers/a2flow.py`
- Modify: `tests/interface/apigw/test_create_template_with_a2flow.py` (add v2 serializer tests)

**Context:** The serializer currently requires `a2flow` as a JSON array (v1 format). For v2, the input is a JSON object with `{version, name, nodes, ...}`. The serializer needs to accept both formats and detect version. Field `name` moves into the `a2flow` object for v2, but remains top-level for v1 compatibility.

Strategy: Add a new serializer `CreateTemplateWithA2FlowV2Serializer` for v2, keep v1 serializer unchanged. The view routes by top-level `a2flow.version`; dict-shaped payload with missing `version` defaults to `"2.0"`, while unknown versions must return `UNSUPPORTED_VERSION`. For v2, serializer errors must also be converted into the same structured `errors` array shape as converter errors rather than relying on DRF default exception formatting.

Add helper in `bkflow/apigw/serializers/a2flow.py`:

```python
def build_structured_serializer_errors(errors, prefix="a2flow"):
    result = []
    for field, detail in errors.items():
        if isinstance(detail, (list, tuple)):
            for item in detail:
                result.append(
                    {
                        "type": "MISSING_REQUIRED_FIELD",
                        "field": "{}.{}".format(prefix, field) if field != "non_field_errors" else prefix,
                        "message": str(item),
                    }
                )
        else:
            result.append(
                {
                    "type": "MISSING_REQUIRED_FIELD",
                    "field": "{}.{}".format(prefix, field) if field != "non_field_errors" else prefix,
                    "message": str(detail),
                }
            )
    return result
```

- [ ] **Step 1: Write v2 serializer tests**

Add to `tests/interface/apigw/test_create_template_with_a2flow.py` (append new class):

```python
class TestCreateTemplateWithA2FlowV2Serializer(TestCase):
    """v2 序列化器测试"""

    def _get_serializer_class(self):
        from bkflow.apigw.serializers.a2flow import CreateTemplateWithA2FlowV2Serializer

        return CreateTemplateWithA2FlowV2Serializer

    def test_valid_v2_input(self):
        Ser = self._get_serializer_class()
        data = {
            "a2flow": {
                "version": "2.0",
                "name": "测试流程",
                "nodes": [{"id": "n1", "name": "步骤", "code": "sleep_timer", "next": "end"}],
            }
        }
        ser = Ser(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_a2flow_must_be_dict(self):
        Ser = self._get_serializer_class()
        data = {"a2flow": [{"type": "name", "value": "test"}]}
        ser = Ser(data=data)
        self.assertFalse(ser.is_valid())

    def test_a2flow_must_have_nodes(self):
        Ser = self._get_serializer_class()
        data = {"a2flow": {"version": "2.0", "name": "空流程"}}
        ser = Ser(data=data)
        self.assertFalse(ser.is_valid())

    def test_a2flow_name_required(self):
        Ser = self._get_serializer_class()
        data = {
            "a2flow": {
                "version": "2.0",
                "nodes": [{"id": "n1", "name": "步骤", "code": "sleep_timer", "next": "end"}],
            }
        }
        ser = Ser(data=data)
        self.assertFalse(ser.is_valid())

    def test_optional_fields(self):
        Ser = self._get_serializer_class()
        data = {
            "a2flow": {
                "version": "2.0",
                "name": "测试",
                "nodes": [{"id": "n1", "name": "步骤", "code": "x", "next": "end"}],
            },
            "creator": "admin",
            "auto_release": True,
            "scope_type": "biz",
            "scope_value": "123",
        }
        ser = Ser(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/interface/apigw/test_create_template_with_a2flow.py::TestCreateTemplateWithA2FlowV2Serializer -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Add v2 serializer**

Modify `bkflow/apigw/serializers/a2flow.py` — add the v2 serializer class after the existing one:

```python
class CreateTemplateWithA2FlowV2Serializer(serializers.Serializer):
    a2flow = serializers.JSONField(help_text=_("a2flow v2 JSON 对象"))
    creator = serializers.CharField(help_text=_("创建人"), max_length=USER_NAME_MAX_LENGTH, required=False)
    scope_type = serializers.CharField(help_text=_("流程范围类型"), max_length=128, required=False)
    scope_value = serializers.CharField(help_text=_("流程范围值"), max_length=128, required=False)
    auto_release = serializers.BooleanField(help_text=_("是否自动发布"), required=False, default=False)

    def validate_a2flow(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(_("a2flow v2 必须是 JSON 对象"))
        version = value.get("version", "2.0")
        normalized_version = "2.0" if version in (None, "", "2", "2.0", 2, 2.0) else str(version)
        if normalized_version not in ("2.0",):
            raise serializers.ValidationError(_("不支持的 a2flow 版本: {}").format(version))
        value["version"] = normalized_version
        if "nodes" not in value:
            raise serializers.ValidationError(_("a2flow v2 缺少 nodes 字段"))
        if not value["nodes"]:
            raise serializers.ValidationError(_("nodes 不能为空"))
        if "name" not in value:
            raise serializers.ValidationError(_("a2flow v2 缺少 name 字段"))
        return value

    def validate(self, attrs):
        scope_type = attrs.get("scope_type")
        scope_value = attrs.get("scope_value")

        if bool(scope_type) != bool(scope_value):
            raise serializers.ValidationError(_("作用域类型和作用域值必须同时填写，或同时不填写"))

        return attrs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/interface/apigw/test_create_template_with_a2flow.py::TestCreateTemplateWithA2FlowV2Serializer -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bkflow/apigw/serializers/a2flow.py tests/interface/apigw/test_create_template_with_a2flow.py
git commit -m "feat(apigw): 添加 a2flow v2 序列化器 --story=133123272"
```

---

### Task 9: Update API View — Version Routing

**Files:**
- Modify: `bkflow/apigw/views/create_template_with_a2flow.py`
- Modify: `tests/interface/apigw/test_create_template_with_a2flow.py` (add v2 view tests)

**Context:** The view needs to detect whether the input is v1 (a2flow is a list) or v2 (a2flow is a dict with version field), then route to the appropriate converter. The view function signature and decorators remain unchanged.

- [ ] **Step 1: Write v2 view tests**

Add to `tests/interface/apigw/test_create_template_with_a2flow.py` (append):

Also update existing imports to include `MagicMock`:

```python
from unittest.mock import MagicMock, patch
```

```python
class TestCreateTemplateWithA2FlowV2View(TestCase):
    """v2 API 视图测试"""

    def create_space(self):
        return Space.objects.create(app_code="test_v2", platform_url="http://test.com", name="space_v2")

    def _mock_component_model(self, mock_cm, codes_versions=None):
        codes_versions = codes_versions or {}

        def filter_side_effect(**kwargs):
            result = MagicMock()
            code = kwargs.get("code") or kwargs.get("code__in", [None])
            if isinstance(code, (list, set)):
                all_versions = []
                for c in code:
                    all_versions.extend(codes_versions.get(c, []))
                result.values_list.return_value = all_versions
            else:
                result.values_list.return_value = codes_versions.get(code, [])
            result.exists.return_value = bool(result.values_list.return_value)
            return result

        mock_cm.objects.filter.side_effect = filter_side_effect

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.BKPlugin")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_v2_create_template_success(self, mock_cm, mock_bkp):
        self._mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False
        space = self.create_space()

        data = {
            "a2flow": {
                "version": "2.0",
                "name": "v2测试流程",
                "nodes": [
                    {"id": "n1", "name": "等待", "code": "sleep_timer", "data": {"bk_timing": 5}, "next": "end"}
                ],
            }
        }
        resp = self.client.post(
            "/apigw/space/{}/create_template_with_a2flow/".format(space.id),
            data=json.dumps(data),
            content_type="application/json",
        )
        result = resp.json()
        self.assertTrue(result.get("result"), result)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.BKPlugin")
    @patch("bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver.ComponentModel")
    def test_v2_missing_version_defaults_to_success(self, mock_cm, mock_bkp):
        self._mock_component_model(mock_cm, {"sleep_timer": ["v1.0.0"]})
        mock_bkp.objects.filter.return_value.exists.return_value = False
        space = self.create_space()

        data = {
            "a2flow": {
                "name": "v2默认版本流程",
                "nodes": [
                    {"id": "n1", "name": "等待", "code": "sleep_timer", "data": {"bk_timing": 5}, "next": "end"}
                ],
            }
        }
        resp = self.client.post(
            "/apigw/space/{}/create_template_with_a2flow/".format(space.id),
            data=json.dumps(data),
            content_type="application/json",
        )
        result = resp.json()
        self.assertTrue(result.get("result"), result)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_v2_validation_error_returns_structured(self):
        space = self.create_space()
        data = {
            "a2flow": {
                "version": "2.0",
                "name": "错误流程",
                "nodes": [{"id": "n1", "name": "x", "code": "y", "next": "nonexistent"}],
            }
        }
        resp = self.client.post(
            "/apigw/space/{}/create_template_with_a2flow/".format(space.id),
            data=json.dumps(data),
            content_type="application/json",
        )
        result = resp.json()
        self.assertFalse(result.get("result"))
        self.assertIn("errors", result)

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_v2_unsupported_version_returns_structured(self):
        space = self.create_space()
        data = {
            "a2flow": {
                "version": "9.9",
                "name": "错误版本",
                "nodes": [{"id": "n1", "name": "x", "code": "y", "next": "end"}],
            }
        }
        resp = self.client.post(
            "/apigw/space/{}/create_template_with_a2flow/".format(space.id),
            data=json.dumps(data),
            content_type="application/json",
        )
        result = resp.json()
        self.assertFalse(result.get("result"))
        self.assertIn("errors", result)
        self.assertEqual(result["errors"][0]["type"], "UNSUPPORTED_VERSION")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/interface/apigw/test_create_template_with_a2flow.py::TestCreateTemplateWithA2FlowV2View -v`
Expected: FAIL

- [ ] **Step 3: Update view with version routing**

Replace the content of `bkflow/apigw/views/create_template_with_a2flow.py` (lines 57-131):

The updated `create_template_with_a2flow` function needs to:
1. Parse request body
2. Route by `a2flow.version` for dict payloads; missing version defaults to `2.0`, reject other unsupported versions with structured `UNSUPPORTED_VERSION`
3. Use appropriate serializer
4. Use appropriate converter
5. Handle Pydantic / converter errors differently for v2 (structured errors)

```python
def create_template_with_a2flow(request, space_id):
    """
    导入简化流程 JSON 并创建模板，支持 v1 / v2 协议自动路由
    """
    data = json.loads(request.body)

    a2flow_raw = data.get("a2flow")
    a2flow_version = a2flow_raw.get("version", "2.0") if isinstance(a2flow_raw, dict) else None
    normalized_version = "2.0" if a2flow_version in (None, "", "2", "2.0", 2, 2.0) else str(a2flow_version)
    is_v2 = isinstance(a2flow_raw, dict) and normalized_version == "2.0"

    if is_v2:
        from bkflow.apigw.serializers.a2flow import (
            CreateTemplateWithA2FlowV2Serializer,
            build_structured_serializer_errors,
        )

        ser = CreateTemplateWithA2FlowV2Serializer(data=data)
        if not ser.is_valid():
            return {
                "result": False,
                "errors": build_structured_serializer_errors(ser.errors, prefix="a2flow"),
                "code": err_code.VALIDATION_ERROR.code,
            }
        validated_data = dict(ser.validated_data)
        a2flow_data = validated_data.pop("a2flow")
        name = a2flow_data.get("name", "")
        desc = a2flow_data.get("desc", "")
        auto_release = validated_data.pop("auto_release", False)

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
            logger.exception("create_template_with_a2flow v2: pydantic validation failed")
            return {
                "result": False,
                "errors": [{"type": "MISSING_REQUIRED_FIELD", "message": str(e)}],
                "code": err_code.VALIDATION_ERROR.code,
            }
        except A2FlowValidationError as e:
            logger.exception("create_template_with_a2flow v2: validation failed")
            response = e.to_response()
            response["code"] = err_code.VALIDATION_ERROR.code
            return response
        except A2FlowConvertError as e:
            logger.exception("create_template_with_a2flow v2: convert error")
            return {"result": False, "errors": [e.to_dict()], "code": err_code.VALIDATION_ERROR.code}
        except Exception as e:
            logger.exception("create_template_with_a2flow v2: unexpected error - {}".format(str(e)))
            return {"result": False, "data": {}, "message": "流程转换失败: {}".format(str(e)),
                    "code": err_code.VALIDATION_ERROR.code}
    elif isinstance(a2flow_raw, dict):
        return {
            "result": False,
            "errors": [
                {
                    "type": "UNSUPPORTED_VERSION",
                    "field": "version",
                    "value": normalized_version,
                    "message": "不支持的 a2flow 版本: '{}'".format(normalized_version),
                    "hint": "当前支持版本: 1.0(数组格式), 2.0(对象格式)",
                }
            ],
            "code": err_code.VALIDATION_ERROR.code,
        }
    else:
        ser = CreateTemplateWithA2FlowSerializer(data=data)
        ser.is_valid(raise_exception=True)
        validated_data = dict(ser.validated_data)
        a2flow = validated_data.pop("a2flow")
        auto_release = validated_data.pop("auto_release", False)
        name = validated_data.pop("name")
        desc = validated_data.pop("desc", "")

        try:
            converter = A2FlowConverter(a2flow)
            pipeline_tree = converter.convert()
        except (KeyError, ValueError) as e:
            logger.exception("create_template_with_a2flow: conversion failed - {}".format(str(e)))
            return {"result": False, "data": {}, "message": "流程转换失败: {}".format(str(e)),
                    "code": err_code.VALIDATION_ERROR.code}

    # 自动排版
    try:
        draw_pipeline(pipeline_tree)
    except Exception as e:
        logger.exception("create_template_with_a2flow: draw_pipeline failed - {}".format(str(e)))
        return {"result": False, "data": {}, "message": "流程自动排版失败: {}".format(str(e)),
                "code": err_code.ERROR.code}

    # 替换节点 ID
    replace_pipeline_tree_node_ids(pipeline_tree, OperateType.CREATE_TEMPLATE.value)

    # 创建模板
    with transaction.atomic():
        username = validated_data.pop("creator", "") or request.user.username
        template_data = {
            "name": name,
            "desc": desc,
            "space_id": space_id,
            "creator": username,
            "updated_by": username,
        }

        scope_type = validated_data.pop("scope_type", None)
        scope_value = validated_data.pop("scope_value", None)
        if scope_type:
            template_data["scope_type"] = scope_type
            template_data["scope_value"] = scope_value

        if SpaceConfig.get_config(space_id=space_id, config_name=FlowVersioning.name) == "true":
            if auto_release:
                snapshot = TemplateSnapshot.create_draft_snapshot(pipeline_tree, username, "1.0.0")
            else:
                snapshot = TemplateSnapshot.create_draft_snapshot(pipeline_tree, username)
        else:
            snapshot = TemplateSnapshot.create_snapshot(pipeline_tree, username, "1.0.0")

        template = Template.objects.create(**template_data, snapshot_id=snapshot.id)
        snapshot.template_id = template.id
        snapshot.save(update_fields=["template_id"])

    return {"result": True, "data": template.to_json(), "code": err_code.SUCCESS.code}
```

Add imports at top of the view file:

```python
from bkflow.pipeline_converter.exceptions import A2FlowConvertError, A2FlowValidationError
from pydantic import ValidationError
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/interface/apigw/test_create_template_with_a2flow.py -v`
Expected: PASS (all tests, both old v1 and new v2)

- [ ] **Step 5: Commit**

```bash
git add bkflow/apigw/views/create_template_with_a2flow.py tests/interface/apigw/test_create_template_with_a2flow.py
git commit -m "feat(apigw): 支持 a2flow v1/v2 协议版本路由 --story=133123272"
```

---

### Task 10: Update API Documentation

**Files:**
- Modify: `bkflow/apigw/docs/zh/create_template_with_a2flow.md`

- [ ] **Step 1: Read current API doc**

Run: `cat bkflow/apigw/docs/zh/create_template_with_a2flow.md`

- [ ] **Step 2: Update API doc to include v2 format**

Add v2 request format description, v2 examples, and structured error response format to the existing doc. Keep v1 section for backward compatibility. Follow the structure of existing API doc files in the same directory.

- [ ] **Step 3: Commit**

```bash
git add bkflow/apigw/docs/zh/create_template_with_a2flow.md
git commit -m "docs(apigw): 更新 a2flow API 文档支持 v2 协议 --story=133123272"
```

---

### Task 11: Run All Tests and Verify

- [ ] **Step 1: Run all new tests**

```bash
pytest tests/interface/pipeline_converter/ -v
```

Expected: All tests PASS

- [ ] **Step 2: Run existing a2flow tests (v1 regression)**

```bash
pytest tests/interface/utils/test_a2flow_converter.py -v
pytest tests/interface/apigw/test_create_template_with_a2flow.py -v
```

Expected: All tests PASS (v1 unchanged)

- [ ] **Step 3: Run linter**

```bash
cd /root/Projects/bk-flow
black --check --line-length 120 bkflow/pipeline_converter/ bkflow/apigw/serializers/a2flow.py bkflow/apigw/views/create_template_with_a2flow.py
flake8 bkflow/pipeline_converter/ bkflow/apigw/serializers/a2flow.py bkflow/apigw/views/create_template_with_a2flow.py --max-line-length 120
```

Expected: No errors (fix any formatting issues)

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -A && git commit -m "style(pipeline_converter): 格式化代码 --story=133123272"
```
