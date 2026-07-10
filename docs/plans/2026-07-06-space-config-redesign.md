# 空间配置改版 · P1 实现计划（元数据框架 + 双栏页 + 通用控件）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让空间管理页的公开配置由后端声明式元数据驱动渲染，7 个简单配置项获得"带说明的开关/单选/输入/成员选择"控件，并搭好通用验证接口骨架；4 个复杂项本期用 JSON 编辑器兜底，不发生功能回退。

**Architecture:** 后端在 `BaseSpaceConfig` 上新增可选声明字段（`group`/`help`/`ui`/`verifiable`）并由 `to_dict()` → `config_meta` 下发；新增 `POST verify/` 接口按配置分发验证（P1 仅骨架，默认"不支持"）。前端把 `Space/SpaceConfig/index.vue` 改为双栏 master-detail 页，通过"控件注册表"按 `ui.control` 动态渲染表单，未声明 `ui` 的配置回退到 JSON 编辑器。存储结构与既有读写接口不变。

**Tech Stack:** Django + DRF（pytest 全量 TDD）；Vue 2.7 + bk-magic-vue 2.5.8 + Vuex（前端无单测框架，验证用 `eslint` + 浏览器手测）。

---

## 范围说明

- **本计划 = P1**，覆盖 7 个简单配置项：`token_expiration`、`token_auto_renewal`、`allow_multiple_triggers`、`flow_versioning`、`gateway_expression`、`canvas_mode`、`superusers`。
- 4 个复杂项（`uniform_api`、`api_gateway_credential_name`、`space_plugin_config`、`engine_space_config`）本期在新页面中**自动回退到 JSON 编辑器**（等价于旧交互，无回退），其结构化控件与验证在 **P2/P3 单独成文**。
- 设计依据：`docs/specs/2026-07-06-space-config-redesign-design.md`。

## 文件结构

**后端**
- 修改 `bkflow/space/configs.py`：`BaseSpaceConfig` 增 `group/help/ui/verifiable` + `to_dict()` 扩展 + `verify()` 默认实现 + `SpaceConfigVerifyNotSupported` 异常；为 7 个 P1 配置类补 `group/help/ui`。
- 修改 `bkflow/space/serializers.py`：新增 `SpaceConfigVerifySerializer`。
- 修改 `bkflow/space/views.py`：`SpaceConfigAdminViewSet` 新增 `verify` action。
- 新增测试 `tests/interface/space/test_config_metadata.py`：元数据 `to_dict` + 各配置声明。
- 修改测试 `tests/interface/space/test_space_views.py`：`verify` 接口。

**前端**
- 新增 `frontend/src/views/admin/Space/SpaceConfig/controls/`：`index.js`（注册表）、`BoolSwitch.vue`、`OptionRadio.vue`、`TextInput.vue`、`MemberSelectorControl.vue`、`JsonEditorControl.vue`。
- 新增 `frontend/src/views/admin/Space/SpaceConfig/ConfigDetail.vue`（右栏详情）。
- 重写 `frontend/src/views/admin/Space/SpaceConfig/index.vue`（左栏分组列表 + 右栏详情）。
- 修改 `frontend/src/store/modules/spaceConfig.js`：新增 `verifySpaceConfig` action。
- 修改 `frontend/src/config/i18n/cn.js`、`frontend/src/config/i18n/en.js`：新增文案键。

---

## Task 1: 后端 —— `BaseSpaceConfig` 元数据框架

**Files:**
- Modify: `bkflow/space/configs.py`
- Test: `tests/interface/space/test_config_metadata.py`

- [ ] **Step 1: 写失败测试**

新建 `tests/interface/space/test_config_metadata.py`：

```python
"""空间配置声明式元数据测试"""
import pytest

from bkflow.space.configs import (
    BaseSpaceConfig,
    CanvasModeConfig,
    SpaceConfigVerifyNotSupported,
)


class TestBaseSpaceConfigMetadata:
    def test_to_dict_contains_new_metadata_keys(self):
        """to_dict 应包含 group/help/ui/verifiable 四个新键"""
        data = CanvasModeConfig.to_dict()
        for key in ("group", "help", "ui", "verifiable"):
            assert key in data

    def test_base_defaults_are_none_or_false(self):
        """基类默认值：group/help/ui 为 None，verifiable 为 False"""
        assert BaseSpaceConfig.group is None
        assert BaseSpaceConfig.help is None
        assert BaseSpaceConfig.ui is None
        assert BaseSpaceConfig.verifiable is False

    def test_verify_default_raises_not_supported(self):
        """未实现 verify 的配置调用 verify 抛 SpaceConfigVerifyNotSupported"""
        with pytest.raises(SpaceConfigVerifyNotSupported):
            CanvasModeConfig.verify(space_id=1, value="horizontal")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign && pytest tests/interface/space/test_config_metadata.py -v`
Expected: FAIL —— `ImportError: cannot import name 'SpaceConfigVerifyNotSupported'` / `AttributeError: group`。

- [ ] **Step 3: 实现最小代码**

在 `bkflow/space/configs.py` 顶部（`SpaceConfigValueType` 之后）新增异常类：

```python
class SpaceConfigVerifyNotSupported(Exception):
    """配置项不支持验证"""

    pass
```

修改 `BaseSpaceConfig`，在 `is_mix_type = False` 之后新增声明字段，并扩展 `to_dict`、新增 `verify`：

```python
class BaseSpaceConfig(metaclass=SpaceConfigMeta):
    """
    SpaceConfig 基类，该类及其子类无需被实例化即可使用
    """

    name = None  # 配置名称（唯一），需要定义
    desc = None  # 描述，需要定义
    is_public = True  # 是否公开
    value_type = SpaceConfigValueType.TEXT.value  # 配置值类型
    default_value = None  # 默认值
    choices = None  # 配置值可选项列表，适用于 TEXT 类型
    example = None  # 配置值示例
    is_mix_type = False
    group = None  # 分组 key：access_security / flow_canvas / api_integration
    help = None  # {"summary": 用途, "effect": 影响, "media": [{type, src, caption}], "doc_link": url}
    ui = None  # 控件描述，见设计文档 §5.2
    verifiable = False  # 是否支持"测试/验证"

    @classmethod
    def to_dict(cls):
        return {
            "name": cls.name,
            "desc": cls.desc,
            "is_public": cls.is_public,
            "value_type": cls.value_type,
            "default_value": cls.default_value,
            "choices": cls.choices,
            "example": cls.example,
            "is_mix_type": cls.is_mix_type,
            "group": cls.group,
            "help": cls.help,
            "ui": cls.ui,
            "verifiable": cls.verifiable,
        }

    @classmethod
    def validate(cls, value):
        return True

    @classmethod
    def verify(cls, space_id, value, **params):
        """验证配置（真实连通性/预览）。默认不支持。"""
        raise SpaceConfigVerifyNotSupported(f"config '{cls.name}' does not support verify")

    @classmethod
    def get_value(cls, config, *args, **kwrags):
        # 默认的父类方法
        return config.text_value if config.value_type == SpaceConfigValueType.TEXT.value else config.json_value
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign && pytest tests/interface/space/test_config_metadata.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 5: 提交**

```bash
git add bkflow/space/configs.py tests/interface/space/test_config_metadata.py
git commit -m "feat(space): 空间配置基类支持声明式元数据与验证骨架 --story=<TAPD_ID>"
```

---

## Task 2: 后端 —— 为 7 个简单配置项补充元数据声明

**Files:**
- Modify: `bkflow/space/configs.py`
- Test: `tests/interface/space/test_config_metadata.py`

- [ ] **Step 1: 追加失败测试**

在 `tests/interface/space/test_config_metadata.py` 追加：

```python
from bkflow.space.configs import (  # noqa: E402  追加到已有 import
    CanvasModeConfig,
    FlowVersioning,
    GatewayExpressionConfig,
    SuperusersConfig,
    TemplateTriggerConfig,
    TokenAutoRenewalConfig,
    TokenExpirationConfig,
)


class TestP1ConfigDeclarations:
    def test_switch_configs(self):
        """开关型配置：control=switch，声明 group"""
        for cfg in (TokenAutoRenewalConfig, TemplateTriggerConfig, FlowVersioning):
            data = cfg.to_dict()
            assert data["ui"]["control"] == "switch"
            assert data["group"] in ("access_security", "flow_canvas")

    def test_radio_configs_options_have_desc(self):
        """单选型配置：control=radio，每个选项含 value/label/desc"""
        for cfg in (GatewayExpressionConfig, CanvasModeConfig):
            options = cfg.to_dict()["ui"]["options"]
            assert len(options) == len(cfg.choices)
            for opt in options:
                assert set(("value", "label", "desc")) <= set(opt.keys())
            assert {o["value"] for o in options} == set(cfg.choices)

    def test_token_expiration_is_input(self):
        assert TokenExpirationConfig.to_dict()["ui"]["control"] == "input"

    def test_superusers_is_member_selector(self):
        data = SuperusersConfig.to_dict()
        assert data["ui"]["control"] == "member_selector"
        assert data["group"] == "access_security"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign && pytest tests/interface/space/test_config_metadata.py::TestP1ConfigDeclarations -v`
Expected: FAIL —— `TypeError: 'NoneType' object is not subscriptable`（`ui` 仍为 None）。

- [ ] **Step 3: 实现最小代码**

在 `bkflow/space/configs.py` 对应的 7 个配置类内新增 `group`/`help`/`ui` 类属性（放在各类已有 `desc`/`default_value`/`choices` 之后、`validate` 之前）。逐个如下：

`TokenExpirationConfig`：

```python
    group = "access_security"
    help = {
        "summary": _("访问 Token 的有效期"),
        "effect": _("过期后需重新获取 Token；最短 1 小时"),
        "media": [],
        "doc_link": "",
    }
    ui = {
        "control": "input",
        "label": _("过期时间"),
        "help": _("格式：[n]m / [n]h / [n]d，如 2h、7d；不少于 1h"),
        "placeholder": "1h",
        "validation": {"type": "duration", "min": "1h"},
    }
```

`TokenAutoRenewalConfig`：

```python
    group = "access_security"
    help = {
        "summary": _("Token 临近过期时是否自动续期"),
        "effect": _("开启：使用中的 Token 自动延长有效期，减少中断；关闭：到期即失效需重新获取"),
        "media": [],
        "doc_link": "",
    }
    ui = {"control": "switch", "label": _("自动续期"), "true_value": "true", "false_value": "false"}
```

`TemplateTriggerConfig`：

```python
    group = "flow_canvas"
    help = {
        "summary": _("单个流程是否允许配置多个触发器"),
        "effect": _("开启：一个流程可挂多个触发器（定时/事件）同时生效；关闭：仅允许一个"),
        "media": [],
        "doc_link": "",
    }
    ui = {"control": "switch", "label": _("允许多触发器"), "true_value": "true", "false_value": "false"}
```

`CanvasModeConfig`：

```python
    group = "flow_canvas"
    help = {
        "summary": _("流程画布的默认排布方向"),
        "effect": _("影响新建/打开流程时画布的默认排布方向"),
        "media": [{"type": "gif", "src": "", "caption": _("横向 vs 纵向 排布示意")}],
        "doc_link": "",
    }
    ui = {
        "control": "radio",
        "label": _("画布模式"),
        "options": [
            {"value": "horizontal", "label": _("横向"), "desc": _("节点从左到右排布，适合较线性的流程")},
            {"value": "vertical", "label": _("纵向"), "desc": _("节点从上到下排布，适合分支多、层级清晰的流程")},
        ],
    }
```

`GatewayExpressionConfig`：

```python
    group = "flow_canvas"
    help = {
        "summary": _("分支网关条件使用的表达式语言"),
        "effect": _("影响分支网关条件的书写与求值方式；修改仅影响此后新建/编辑的条件"),
        "media": [],
        "doc_link": "",
    }
    ui = {
        "control": "radio",
        "label": _("表达式类型"),
        "options": [
            {"value": "boolrule", "label": _("Boolrule（默认）"), "desc": _("简单布尔规则，可视化友好，适合常规条件")},
            {"value": "FEEL", "label": "FEEL", "desc": _("DMN 标准表达式，功能强，适合复杂决策")},
            {"value": "MAKO", "label": "MAKO", "desc": _("Python 模板表达式，最灵活但需谨慎")},
        ],
    }
```

`SuperusersConfig`（在 `default_value = []` 之后）：

```python
    group = "access_security"
    help = {
        "summary": _("空间的超级管理员"),
        "effect": _("加入的成员拥有本空间的全部管理权限（配置、凭证、全部流程与任务）"),
        "media": [],
        "doc_link": "",
    }
    ui = {"control": "member_selector", "label": _("空间管理员"), "placeholder": _("请选择成员")}
```

`FlowVersioning`：

```python
    group = "flow_canvas"
    help = {
        "summary": _("是否开启流程版本管理"),
        "effect": _("开启：流程保存产生版本、可回溯与回滚；关闭：仅保留最新版本"),
        "media": [],
        "doc_link": "",
    }
    ui = {"control": "switch", "label": _("版本控制"), "true_value": "true", "false_value": "false"}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign && pytest tests/interface/space/test_config_metadata.py -v`
Expected: PASS（全部通过）。

- [ ] **Step 5: 回归 config_meta 未破坏**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign && pytest tests/interface/space/test_space_views.py::TestSpaceConfigAdminViewSet::test_config_meta -v`
Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add bkflow/space/configs.py tests/interface/space/test_config_metadata.py
git commit -m "feat(space): 为 7 个简单空间配置补充分组/说明/控件元数据 --story=<TAPD_ID>"
```

---

## Task 3: 后端 —— 验证接口 `POST verify/`

**Files:**
- Modify: `bkflow/space/serializers.py`
- Modify: `bkflow/space/views.py`
- Test: `tests/interface/space/test_space_views.py`

- [ ] **Step 1: 写失败测试**

在 `tests/interface/space/test_space_views.py` 的 `TestSpaceConfigAdminViewSet` 类中追加：

```python
    def test_verify_not_supported_config(self):
        """验证不支持验证的配置项：返回 ok=False 且 not_supported=True"""
        view = SpaceConfigAdminViewSet.as_view({"post": "verify"})
        data = {"space_id": self.space.id, "name": "canvas_mode", "value": "horizontal"}
        request = self.factory.post("/space_configs/verify/", data, format="json")
        force_authenticate(request, user=self.superuser)

        response = view(request)

        assert response.status_code == 200
        payload = response.data.get("data", {})
        assert payload.get("ok") is False
        assert payload.get("error", {}).get("not_supported") is True

    def test_verify_unknown_config(self):
        """验证不存在的配置项：返回 ok=False"""
        view = SpaceConfigAdminViewSet.as_view({"post": "verify"})
        data = {"space_id": self.space.id, "name": "not_exist_config", "value": "x"}
        request = self.factory.post("/space_configs/verify/", data, format="json")
        force_authenticate(request, user=self.superuser)

        response = view(request)

        assert response.status_code == 200
        assert response.data.get("data", {}).get("ok") is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign && pytest tests/interface/space/test_space_views.py::TestSpaceConfigAdminViewSet::test_verify_not_supported_config -v`
Expected: FAIL —— action `verify` 不存在（404 / AttributeError）。

- [ ] **Step 3: 新增序列化器**

在 `bkflow/space/serializers.py` 末尾新增：

```python
class SpaceConfigVerifySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    name = serializers.CharField(help_text=_("配置项名称"))
    value = serializers.JSONField(help_text=_("待验证的配置值"), required=False)
    params = serializers.DictField(help_text=_("验证参数"), required=False, default=dict)
```

- [ ] **Step 4: 新增 view action**

在 `bkflow/space/views.py`：确认顶部已从 `bkflow.space.configs` 导入 `SpaceConfigHandler`（已在用），追加导入 `SpaceConfigVerifyNotSupported`，并从 `bkflow.space.serializers` 追加导入 `SpaceConfigVerifySerializer`。在 `SpaceConfigAdminViewSet` 内（`get_all_space_configs` 之后）新增：

```python
    @swagger_auto_schema(
        method="post",
        operation_summary="验证空间配置",
        request_body=SpaceConfigVerifySerializer,
    )
    @action(detail=False, methods=["POST"])
    def verify(self, request, *args, **kwargs):
        ser = SpaceConfigVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        try:
            config_cls = SpaceConfigHandler.get_config(data["name"])
        except Exception as e:
            return Response({"ok": False, "error": {"message": str(e)}})
        try:
            preview = config_cls.verify(
                space_id=data["space_id"], value=data.get("value"), **data.get("params", {})
            )
            return Response({"ok": True, "preview": preview})
        except SpaceConfigVerifyNotSupported as e:
            return Response({"ok": False, "error": {"message": str(e), "not_supported": True}})
        except Exception as e:
            logger.error(f"[space_config verify] name={data['name']} error: {e}")
            return Response({"ok": False, "error": {"message": str(e)}})
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign && pytest tests/interface/space/test_space_views.py::TestSpaceConfigAdminViewSet -v`
Expected: PASS（含新增 2 条 verify 测试与既有测试）。

- [ ] **Step 6: 提交**

```bash
git add bkflow/space/serializers.py bkflow/space/views.py tests/interface/space/test_space_views.py
git commit -m "feat(space): 新增空间配置验证接口骨架 --story=<TAPD_ID>"
```

---

## Task 4: 前端 —— store 新增 `verifySpaceConfig`

**Files:**
- Modify: `frontend/src/store/modules/spaceConfig.js`

- [ ] **Step 1: 新增 action**

在 `frontend/src/store/modules/spaceConfig.js` 的 `actions` 中，`getSpaceConfigMeta` 之后新增：

```javascript
    verifySpaceConfig({}, data) {
      return axios.post('api/space/admin/space_config/verify/', data).then(response => response.data);
    },
```

- [ ] **Step 2: 校验**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign/frontend && npx eslint src/store/modules/spaceConfig.js`
Expected: 无 error。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/store/modules/spaceConfig.js
git commit -m "feat(space): 前端新增空间配置验证 action --story=<TAPD_ID>"
```

---

## Task 5: 前端 —— 通用控件与注册表

**Files:**
- Create: `frontend/src/views/admin/Space/SpaceConfig/controls/BoolSwitch.vue`
- Create: `frontend/src/views/admin/Space/SpaceConfig/controls/OptionRadio.vue`
- Create: `frontend/src/views/admin/Space/SpaceConfig/controls/TextInput.vue`
- Create: `frontend/src/views/admin/Space/SpaceConfig/controls/MemberSelectorControl.vue`
- Create: `frontend/src/views/admin/Space/SpaceConfig/controls/JsonEditorControl.vue`
- Create: `frontend/src/views/admin/Space/SpaceConfig/controls/index.js`

所有控件统一约定：`model` 为 `{ prop: 'value', event: 'change' }`；props 含 `value` 与 `schema`(即后端 `ui` 对象)。

- [ ] **Step 1: `BoolSwitch.vue`**

```vue
<template>
  <bk-switcher :value="isOn" theme="primary" @change="handleChange" />
</template>
<script>
  export default {
    name: 'BoolSwitch',
    model: { prop: 'value', event: 'change' },
    props: {
      value: { type: [String, Boolean], default: '' },
      schema: { type: Object, default: () => ({}) },
    },
    computed: {
      trueValue() { return this.schema.true_value || 'true'; },
      falseValue() { return this.schema.false_value || 'false'; },
      isOn() { return this.value === this.trueValue || this.value === true; },
    },
    methods: {
      handleChange(val) { this.$emit('change', val ? this.trueValue : this.falseValue); },
    },
  };
</script>
```

- [ ] **Step 2: `OptionRadio.vue`**

```vue
<template>
  <bk-radio-group
    class="option-radio"
    :value="value"
    @change="val => $emit('change', val)">
    <bk-radio
      v-for="opt in options"
      :key="opt.value"
      :value="opt.value"
      class="option-item">
      <span class="option-label">{{ opt.label }}</span>
      <span
        v-if="opt.desc"
        class="option-desc">{{ opt.desc }}</span>
    </bk-radio>
  </bk-radio-group>
</template>
<script>
  export default {
    name: 'OptionRadio',
    model: { prop: 'value', event: 'change' },
    props: {
      value: { type: [String, Number, Boolean], default: '' },
      schema: { type: Object, default: () => ({}) },
    },
    computed: {
      options() { return this.schema.options || []; },
    },
  };
</script>
<style lang="scss" scoped>
  .option-radio {
    display: flex;
    flex-direction: column;
  }
  .option-item {
    display: flex;
    align-items: baseline;
    margin-bottom: 12px;
  }
  .option-label { font-weight: 500; }
  .option-desc {
    margin-left: 8px;
    color: #979ba5;
    font-size: 12px;
  }
</style>
```

- [ ] **Step 3: `TextInput.vue`**

```vue
<template>
  <bk-input
    :value="value"
    :placeholder="schema.placeholder || ''"
    @change="val => $emit('change', val)" />
</template>
<script>
  export default {
    name: 'TextInput',
    model: { prop: 'value', event: 'change' },
    props: {
      value: { type: [String, Number], default: '' },
      schema: { type: Object, default: () => ({}) },
    },
  };
</script>
```

- [ ] **Step 4: `MemberSelectorControl.vue`**

```vue
<template>
  <MemberSelect
    :value="normalizedValue"
    :placeholder="schema.placeholder || ''"
    @change="val => $emit('change', val)" />
</template>
<script>
  import MemberSelect from '@/components/common/Individualization/MemberSelect.vue';

  export default {
    name: 'MemberSelectorControl',
    components: { MemberSelect },
    model: { prop: 'value', event: 'change' },
    props: {
      value: { type: Array, default: () => [] },
      schema: { type: Object, default: () => ({}) },
    },
    computed: {
      normalizedValue() { return Array.isArray(this.value) ? this.value : []; },
    },
  };
</script>
```

- [ ] **Step 5: `JsonEditorControl.vue`（兜底，复用 FullCodeEditor）**

```vue
<template>
  <div class="json-editor-control">
    <FullCodeEditor
      ref="editor"
      :value="text"
      :options="{ language: 'json', placeholder: placeholder }"
      @input="onInput" />
  </div>
</template>
<script>
  import FullCodeEditor from '@/components/common/FullCodeEditor.vue';

  export default {
    name: 'JsonEditorControl',
    components: { FullCodeEditor },
    model: { prop: 'value', event: 'change' },
    props: {
      value: { type: [Object, Array, String, Number, Boolean], default: '' },
      schema: { type: Object, default: () => ({}) },
    },
    computed: {
      placeholder() {
        const ex = this.schema.example;
        if (ex === undefined || ex === null) return '';
        return typeof ex === 'string' ? ex : JSON.stringify(ex, null, 2);
      },
      text() {
        if (typeof this.value === 'string') return this.value;
        return JSON.stringify(this.value, null, 4);
      },
    },
    methods: {
      onInput(val) { this.$emit('change', val); },
    },
    mounted() {
      this.$nextTick(() => {
        const editor = this.$refs.editor;
        if (editor && editor.layoutCodeEditorInstance) editor.layoutCodeEditorInstance();
      });
    },
  };
</script>
<style lang="scss" scoped>
  .json-editor-control { height: 300px; position: relative; }
</style>
```

> 注：`FullCodeEditor` 的对外事件名以现有用法为准（现有 `SpaceConfig/index.vue` 用的是 `v-model`）。实现时先打开 `frontend/src/components/common/FullCodeEditor.vue` 确认其 `model`/事件；若为 `v-model`（prop `value` + event `input`），上面 `@input` 即正确；若不同，按其真实事件名对接。

- [ ] **Step 6: `index.js` 注册表**

```javascript
import BoolSwitch from './BoolSwitch.vue';
import OptionRadio from './OptionRadio.vue';
import TextInput from './TextInput.vue';
import MemberSelectorControl from './MemberSelectorControl.vue';
import JsonEditorControl from './JsonEditorControl.vue';

const registry = {
  switch: BoolSwitch,
  radio: OptionRadio,
  select: OptionRadio,
  input: TextInput,
  member_selector: MemberSelectorControl,
  json: JsonEditorControl,
};

// 未声明或未知 control 一律回退到 JSON 编辑器，保证复杂/未改造配置不回退
export function getControlComponent(control) {
  return registry[control] || JsonEditorControl;
}

export default registry;
```

- [ ] **Step 7: 校验**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign/frontend && npx eslint src/views/admin/Space/SpaceConfig/controls/`
Expected: 无 error。

- [ ] **Step 8: 提交**

```bash
git add frontend/src/views/admin/Space/SpaceConfig/controls/
git commit -m "feat(space): 空间配置通用控件与控件注册表 --story=<TAPD_ID>"
```

---

## Task 6: 前端 —— 右栏详情组件 `ConfigDetail.vue`

**Files:**
- Create: `frontend/src/views/admin/Space/SpaceConfig/ConfigDetail.vue`

职责：接收"合并后的配置对象"（meta + 当前存储值），渲染 说明区 + 动态控件表单 + 验证区 + 底部按钮；把控件值与存储值互转；向父组件 `emit('save', payload)` 与 `emit('reset', row)`。

- [ ] **Step 1: 创建组件**

```vue
<template>
  <div
    v-if="config"
    class="config-detail">
    <div class="detail-header">
      <span class="detail-title">{{ config.ui && config.ui.label || config.desc || config.name }}</span>
      <span :class="['detail-status', config.isDefault ? 'is-default' : 'is-custom']">
        {{ config.isDefault ? $t('默认值') : $t('已配置') }}
      </span>
      <bk-button
        text
        theme="primary"
        :disabled="config.isDefault"
        @click="$emit('reset', config)">
        {{ $t('恢复默认值') }}
      </bk-button>
    </div>

    <div
      v-if="config.help"
      class="detail-help">
      <p
        v-if="config.help.summary"
        class="help-summary">{{ config.help.summary }}</p>
      <p
        v-if="config.help.effect"
        class="help-effect">{{ config.help.effect }}</p>
      <div
        v-if="hasMedia"
        class="help-media">
        <div
          v-for="(m, idx) in config.help.media"
          :key="idx"
          class="media-item">
          <img
            v-if="m.src"
            :src="m.src"
            :alt="m.caption">
          <div
            v-else
            class="media-placeholder">{{ m.caption || $t('示意图待补充') }}</div>
        </div>
      </div>
      <a
        v-if="config.help.doc_link"
        :href="config.help.doc_link"
        target="_blank"
        class="help-doc">{{ $t('查看文档') }}</a>
    </div>

    <div class="detail-form">
      <component
        :is="controlComponent"
        v-model="formValue"
        :schema="config.ui || {}" />
    </div>

    <div
      v-if="config.verifiable"
      class="detail-verify">
      <bk-button
        :loading="verifying"
        @click="handleVerify">
        {{ $t('测试') }}
      </bk-button>
      <span
        v-if="verifyResult"
        :class="['verify-result', verifyResult.ok ? 'is-ok' : 'is-fail']">
        {{ verifyResult.ok ? $t('验证通过') : (verifyResult.error && verifyResult.error.message) }}
      </span>
    </div>

    <div class="detail-footer">
      <bk-button
        theme="primary"
        :loading="saving"
        @click="handleSave">
        {{ $t('保存') }}
      </bk-button>
    </div>
  </div>
</template>
<script>
  import { getControlComponent } from './controls/index.js';
  import tools from '@/utils/tools.js';

  export default {
    name: 'ConfigDetail',
    props: {
      config: { type: Object, default: null },
      spaceId: { type: [String, Number], default: '' },
      saving: { type: Boolean, default: false },
      verifying: { type: Boolean, default: false },
      verifyResult: { type: Object, default: null },
    },
    data() {
      return {
        formValue: this.readValue(this.config),
      };
    },
    computed: {
      controlComponent() {
        const control = this.config && this.config.ui ? this.config.ui.control : null;
        return getControlComponent(control);
      },
      hasMedia() {
        return this.config && this.config.help && Array.isArray(this.config.help.media)
          && this.config.help.media.length > 0;
      },
      isJsonControl() {
        const control = this.config && this.config.ui ? this.config.ui.control : null;
        return !control || !['switch', 'radio', 'select', 'input', 'member_selector'].includes(control);
      },
    },
    watch: {
      config: {
        handler(val) {
          this.formValue = this.readValue(val);
        },
      },
    },
    methods: {
      // 存储值 -> 控件值
      readValue(config) {
        if (!config) return '';
        if (config.isDefault) {
          return config.default_value === null || config.default_value === undefined ? '' : config.default_value;
        }
        return config.value_type === 'TEXT' ? config.value : config.json_value;
      },
      // 控件值 -> 存储 payload
      buildPayload() {
        const { id, name, value_type: valueType, is_mix_type: isMixType } = this.config;
        const payload = { id, name, space_id: this.spaceId, value_type: valueType };
        if (this.isJsonControl) {
          // 兜底 JSON 编辑器产出的是字符串，需解析
          const raw = this.formValue;
          const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
          if (valueType === 'TEXT' && !isMixType) {
            payload.text_value = typeof raw === 'string' ? raw : JSON.stringify(raw);
          } else {
            payload.value_type = isMixType ? 'JSON' : valueType;
            payload.json_value = parsed;
          }
        } else if (valueType === 'TEXT') {
          payload.text_value = this.formValue;
        } else {
          payload.json_value = this.formValue;
        }
        return payload;
      },
      handleSave() {
        if (this.isJsonControl && typeof this.formValue === 'string' && !tools.checkIsJSON(this.formValue)) {
          this.$bkMessage({ message: this.$t('数据格式不正确，应为JSON格式'), theme: 'error' });
          return;
        }
        this.$emit('save', this.buildPayload());
      },
      handleVerify() {
        this.$emit('verify', { space_id: this.spaceId, name: this.config.name, value: this.formValue });
      },
    },
  };
</script>
<style lang="scss" scoped>
  .config-detail { padding: 16px 24px; }
  .detail-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
    .detail-title { font-size: 16px; font-weight: 700; }
    .detail-status {
      font-size: 12px; padding: 0 8px; border-radius: 2px;
      &.is-custom { color: #14a568; background: #e4faf0; }
      &.is-default { color: #979ba5; background: #f0f1f5; }
    }
  }
  .detail-help {
    background: #f5f7fa; border-radius: 2px; padding: 12px 16px; margin-bottom: 16px;
    .help-summary { font-weight: 500; margin-bottom: 4px; }
    .help-effect { color: #63656e; font-size: 13px; }
    .media-placeholder {
      margin-top: 8px; height: 120px; display: flex; align-items: center; justify-content: center;
      border: 1px dashed #c4c6cc; color: #979ba5; border-radius: 2px;
    }
    .help-doc { display: inline-block; margin-top: 8px; color: #3a84ff; }
  }
  .detail-form { margin-bottom: 16px; }
  .detail-verify {
    margin-bottom: 16px;
    .verify-result { margin-left: 12px; font-size: 13px;
      &.is-ok { color: #14a568; } &.is-fail { color: #ea3636; } }
  }
</style>
```

- [ ] **Step 2: 校验**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign/frontend && npx eslint src/views/admin/Space/SpaceConfig/ConfigDetail.vue`
Expected: 无 error。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/admin/Space/SpaceConfig/ConfigDetail.vue
git commit -m "feat(space): 空间配置详情组件（说明/表单/验证） --story=<TAPD_ID>"
```

---

## Task 7: 前端 —— 双栏主页面 `index.vue` 重写

**Files:**
- Modify: `frontend/src/views/admin/Space/SpaceConfig/index.vue`

- [ ] **Step 1: 重写组件**

保留 `spaceId`/`hasAlertNotice` props 与数据加载（复用 `getSpaceConfigData` + `getSpaceConfigMeta`），改为左栏分组列表 + 右栏 `ConfigDetail`。

```vue
<template>
  <div class="space-config-center">
    <div class="config-sidebar">
      <bk-input
        v-model="keyword"
        class="config-search"
        :placeholder="$t('搜索配置')"
        right-icon="bk-icon icon-search" />
      <div
        v-bkloading="{ isLoading: listLoading }"
        class="config-groups">
        <div
          v-for="group in filteredGroups"
          :key="group.key"
          class="config-group">
          <div class="group-title">{{ group.title }}</div>
          <div
            v-for="item in group.items"
            :key="item.name"
            :class="['group-item', { active: selectedName === item.name }]"
            @click="selectItem(item)">
            <span class="item-label">{{ (item.ui && item.ui.label) || item.desc || item.name }}</span>
            <span :class="['item-badge', item.isDefault ? 'is-default' : 'is-custom']">
              {{ item.isDefault ? $t('默认') : $t('已配置') }}
            </span>
          </div>
        </div>
      </div>
    </div>
    <div class="config-content">
      <ConfigDetail
        :key="selectedName"
        :config="selectedConfig"
        :space-id="spaceId"
        :saving="saving"
        :verifying="verifying"
        :verify-result="verifyResult"
        @save="handleSave"
        @reset="handleReset"
        @verify="handleVerify" />
    </div>
  </div>
</template>
<script>
  import { mapActions } from 'vuex';
  import ConfigDetail from './ConfigDetail.vue';
  import i18n from '@/config/i18n/index.js';

  const GROUP_DEFS = [
    { key: 'access_security', title: i18n.t('权限与安全') },
    { key: 'flow_canvas', title: i18n.t('流程与画布行为') },
    { key: 'api_integration', title: i18n.t('API 与插件集成') },
    { key: 'other', title: i18n.t('其他') },
  ];

  export default {
    name: 'SpaceConfigCenter',
    components: { ConfigDetail },
    props: {
      spaceId: { type: [String, Number], default: '' },
      hasAlertNotice: { type: Boolean, default: false },
    },
    data() {
      return {
        listLoading: false,
        saving: false,
        verifying: false,
        verifyResult: null,
        configList: [],
        selectedName: '',
        keyword: '',
      };
    },
    computed: {
      publicList() {
        return this.configList.filter(item => item.is_public);
      },
      filteredGroups() {
        const kw = this.keyword.trim().toLowerCase();
        return GROUP_DEFS.map((g) => {
          const items = this.publicList.filter((item) => {
            const groupKey = item.group || 'other';
            if (groupKey !== g.key) return false;
            if (!kw) return true;
            const label = ((item.ui && item.ui.label) || item.desc || item.name).toLowerCase();
            return label.includes(kw) || item.name.toLowerCase().includes(kw);
          });
          return { ...g, items };
        }).filter(g => g.items.length > 0);
      },
      selectedConfig() {
        return this.publicList.find(item => item.name === this.selectedName) || null;
      },
    },
    watch: {
      spaceId: { handler() { this.loadConfigs(); }, immediate: true },
    },
    methods: {
      ...mapActions('spaceConfig/', [
        'getSpaceConfigData',
        'updateSpaceConfig',
        'deleteSpaceConfig',
        'getSpaceConfigMeta',
        'verifySpaceConfig',
      ]),
      async loadConfigs() {
        if (!this.spaceId) return;
        try {
          this.listLoading = true;
          const [dataResp, metaResp] = await Promise.all([
            this.getSpaceConfigData({ space_id: this.spaceId }),
            this.getSpaceConfigMeta({ space_id: this.spaceId }),
          ]);
          const stored = dataResp.data || [];
          this.configList = Object.values(metaResp.data).map((meta) => {
            const cur = stored.find(item => item.name === meta.name);
            if (cur) {
              return { ...meta, ...cur, isDefault: false };
            }
            return { ...meta, value: meta.default_value, json_value: meta.default_value, isDefault: true };
          });
          if (!this.selectedName && this.filteredGroups.length) {
            this.selectedName = this.filteredGroups[0].items[0].name;
          }
        } catch (error) {
          console.warn(error);
        } finally {
          this.listLoading = false;
        }
      },
      selectItem(item) {
        this.selectedName = item.name;
        this.verifyResult = null;
      },
      async handleSave(payload) {
        try {
          this.saving = true;
          const resp = await this.updateSpaceConfig(payload);
          if (resp.result === false) return;
          this.$bkMessage({ message: this.$t('修改成功！'), theme: 'success' });
          this.loadConfigs();
        } catch (error) {
          console.warn(error);
        } finally {
          this.saving = false;
        }
      },
      handleReset(row) {
        this.$bkInfo({
          title: this.$t('确认恢复默认值？'),
          maskClose: false,
          confirmLoading: true,
          confirmFn: async () => {
            const resp = await this.deleteSpaceConfig({ id: row.id });
            if (resp.result === false) return;
            this.$bkMessage({ message: this.$t('已恢复默认值'), theme: 'success' });
            this.loadConfigs();
          },
        });
      },
      async handleVerify(payload) {
        try {
          this.verifying = true;
          this.verifyResult = null;
          const resp = await this.verifySpaceConfig(payload);
          this.verifyResult = resp.data || resp;
        } catch (error) {
          this.verifyResult = { ok: false, error: { message: String(error) } };
        } finally {
          this.verifying = false;
        }
      },
    },
  };
</script>
<style lang="scss" scoped>
  .space-config-center {
    display: flex;
    height: 100%;
    background: #fff;
  }
  .config-sidebar {
    width: 280px;
    border-right: 1px solid #dcdee5;
    display: flex;
    flex-direction: column;
    .config-search { margin: 12px; width: calc(100% - 24px); }
    .config-groups { flex: 1; overflow-y: auto; }
    .group-title { padding: 8px 16px; color: #979ba5; font-size: 12px; }
    .group-item {
      display: flex; align-items: center; justify-content: space-between;
      padding: 8px 16px; cursor: pointer;
      &:hover { background: #f5f7fa; }
      &.active { background: #e1ecff; color: #3a84ff; }
      .item-badge {
        font-size: 12px; transform: scale(0.9);
        &.is-custom { color: #14a568; } &.is-default { color: #c4c6cc; }
      }
    }
  }
  .config-content { flex: 1; overflow-y: auto; }
</style>
```

- [ ] **Step 2: 校验 lint**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign/frontend && npx eslint src/views/admin/Space/SpaceConfig/index.vue`
Expected: 无 error。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/admin/Space/SpaceConfig/index.vue
git commit -m "feat(space): 空间配置改为双栏配置中心页 --story=<TAPD_ID>"
```

---

## Task 8: 前端 —— i18n 文案与整体校验

**Files:**
- Modify: `frontend/src/config/i18n/cn.js`
- Modify: `frontend/src/config/i18n/en.js`

- [ ] **Step 1: 补充文案键**

在 `cn.js`、`en.js` 中补齐本次新增的中文键（若已存在则跳过）：`'搜索配置'`、`'权限与安全'`、`'流程与画布行为'`、`'API 与插件集成'`、`'其他'`、`'默认值'`、`'已配置'`、`'查看文档'`、`'示意图待补充'`、`'测试'`、`'验证通过'`、`'保存'`、`'已恢复默认值'`、`'确认恢复默认值？'`。`cn.js` 中键值一致（如 `'搜索配置': '搜索配置'`）；`en.js` 给英文翻译。参照文件现有格式追加。

- [ ] **Step 2: 全量前端 lint**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign/frontend && npm run lint`
Expected: 无 error（warning 可接受，与仓库现状一致）。

- [ ] **Step 3: 浏览器手测（验收）**

启动前端联调环境后，进入某空间 → 管理 → 配置（`activeTab=config`），验证：
1. 左栏出现 3 组，7 个简单项显示带说明的控件；4 个复杂项显示 JSON 编辑器（不报错）。
2. 修改 `canvas_mode`（单选带说明）→ 保存 → 徽标变"已配置"。
3. 对 `token_auto_renewal` 用开关切换 → 保存成功。
4. `superusers` 用成员选择器增删人员 → 保存成功。
5. "恢复默认值"可用并生效。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/config/i18n/cn.js frontend/src/config/i18n/en.js
git commit -m "feat(space): 补充空间配置中心 i18n 文案 --story=<TAPD_ID>"
```

---

## 后端整体回归

- [ ] 运行空间模块相关测试：

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign && pytest tests/interface/space/ -v`
Expected: 全部 PASS。

---

## 后续计划（已单独成文）

- **P2/P3 实现计划见**：`docs/plans/2026-07-10-space-config-redesign-p2-p3.md`。
- **P2**：`credential_map`（`api_gateway_credential_name` 与凭证管理完整联动：默认+作用域覆盖、就近新建、跳转管理、引用完整性、作用域校验）+ `api_plugin_config`（`uniform_api` 结构化编辑 + 复用 `UniformAPIClient` 的实时预览验证，在 `UniformApiConfig.verify` 中实现）。
- **P3**：`plugin_scope`（`space_plugin_config`）、`engine_kv`（`engine_space_config`）、复合控件的"结构化 ↔ JSON 源码"切换、`canvas_mode`/`gateway_expression` 媒体素材补图。

---

## Self-Review

- **Spec 覆盖**：设计 §4 分组 → Task 7 `GROUP_DEFS`；§5 后端元数据 → Task 1/2；§5.3 验证接口 → Task 3；§6 前端双栏+注册表+兜底 → Task 5/6/7；§8 的 7 个简单项 → Task 2；复杂项兜底不回退 → Task 5 `getControlComponent` 默认 `JsonEditorControl` + Task 7 全量展示 public 配置。§7 凭证联动 / §12 验证的真实实现属 P2，已在"后续计划"标注。
- **占位符扫描**：无 TBD/TODO；`FullCodeEditor` 事件名一处给出"实现时确认"的明确指令（非占位，是核对动作）。媒体 `src` 为空是设计既定的占位位，非计划占位。
- **类型/命名一致**：控件 `model` 统一 `{prop:'value',event:'change'}`；注册表键 `switch/radio/select/input/member_selector/json` 与后端 `ui.control` 取值一致；`verify` 接口返回 `{ok, preview|error}` 在后端 Task 3 与前端 Task 6/7 `verifyResult` 使用一致；`getControlComponent` 命名前后一致。
- **TAPD**：所有 commit 的 `--story=<TAPD_ID>` 为占位，实现前需经 tapd-workitem-sync 取得单据号并统一替换。
