# 空间配置改版 · P2/P3 实现计划（复合控件 + 实时验证 + JSON 兜底 + 媒体）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 P1 元数据框架与双栏配置中心的基础上，落地 4 个复杂配置项的结构化复合控件（`credential_map`、`api_plugin_config`、`plugin_scope`、`engine_kv`），为 `uniform_api` 提供复用 `UniformAPIClient` 的一键实时预览验证，并补齐"结构化 ↔ JSON 源码"逃生通道与 `canvas_mode` 图示素材。

**Architecture:** 后端为 4 个复杂配置类补 `group/help/ui`（具名复合控件）声明，`uniform_api` 实现 `verify()`（拉取 meta 列表回显预览，凭证默认取空间默认网关凭证），`verify` 接口（P1 已建骨架）注入操作人。前端在 P1 控件注册表新增 4 个复合控件组件；`ConfigDetail` 扩展 `is_mix_type` 存储路由、复合控件验证透传与"结构化 ↔ JSON 源码"切换。存储结构与既有读写接口完全不变，旧值兼容。

**Tech Stack:** Django + DRF（pytest 全量 TDD，`mock` 打桩 `UniformAPIClient`）；Vue 2.7 + bk-magic-vue 2.5.8 + Vuex（前端无单测框架，验证用 `eslint` + 浏览器手测）。

---

## 范围说明

- **本计划 = P2 + P3**，覆盖 4 个复杂配置项与配套能力：
  - **P2**：`api_gateway_credential_name` → `credential_map`（凭证管理完整联动）；`uniform_api` → `api_plugin_config`（结构化编辑 + 实时预览验证）。
  - **P3**：`space_plugin_config` → `plugin_scope`；`engine_space_config` → `engine_kv`；复合控件"结构化 ↔ JSON 源码"切换；`canvas_mode` 媒体图示补图。
- 设计依据：`docs/specs/2026-07-06-space-config-redesign-design.md`（§5.2 控件描述、§5.3 验证接口、§6.2 控件注册表、§6.3 JSON 兜底、§7 凭证联动、§8 各配置项目标形态、§9 兼容性）。

## 前置依赖（P1 已完成）

本计划直接构建在 P1（`docs/plans/2026-07-06-space-config-redesign.md`）交付物之上，实现前请确认以下 P1 产物已合入当前分支：

1. `bkflow/space/configs.py`：`BaseSpaceConfig` 已有 `group/help/ui/verifiable` 声明字段、`to_dict()` 已输出这些字段、`verify()` 默认抛 `SpaceConfigVerifyNotSupported`。
2. `bkflow/space/views.py`：`SpaceConfigAdminViewSet.verify` action 已存在（按 `name` 分发到 `config_cls.verify`，返回 `{ok, preview|error}`）。
3. `bkflow/space/serializers.py`：`SpaceConfigVerifySerializer`（`space_id/name/value/params`）已存在。
4. 前端 `frontend/src/views/admin/Space/SpaceConfig/controls/`（`index.js` 注册表 + `BoolSwitch/OptionRadio/TextInput/MemberSelectorControl/JsonEditorControl`）、`ConfigDetail.vue`、双栏 `index.vue`，`store/modules/spaceConfig.js` 的 `verifySpaceConfig` action 均已存在。

> 若 P1 尚未合入，先完成 P1 再执行本计划。

## 文件结构

**后端**
- 修改 `bkflow/space/configs.py`：为 `UniformApiConfig` 补 `group/help/ui(api_plugin_config)/verifiable=True` + 实现 `verify()`；为 `ApiGatewayCredentialConfig`（`credential_map`）、`SpacePluginConfig`（`plugin_scope`）、`SpaceEngineConfig`（`engine_kv`）补 `group/help/ui`。
- 修改 `bkflow/space/views.py`：`SpaceConfigAdminViewSet.verify` 注入 `operator=request.user.username`。
- 修改 `tests/interface/space/test_config_metadata.py`：新增 4 个复杂项元数据声明断言。
- 修改 `tests/interface/space/test_space_views.py`：`uniform_api` verify 成功/失败测试（mock `UniformAPIClient`）。

**前端**
- 新增控件：`controls/CredentialMap.vue`、`controls/ApiPluginConfig.vue`、`controls/PluginScope.vue`、`controls/EngineKv.vue`。
- 修改 `controls/index.js`：注册 4 个复合控件。
- 修改 `ConfigDetail.vue`：`is_mix_type` 存储路由、复合控件验证透传、结构化 ↔ JSON 源码切换。
- 修改 `store/modules/atomForm.js` —— 无需改动（复用 `loadSingleAtomList`、`loadPluginServiceList`）；`store/modules/credentialConfig.js` —— 无需改动（复用 `loadCredentialList`/`createCredential`）。
- 修改 `frontend/src/config/i18n/cn.js`、`en.js`：新增文案键。
- 新增素材：`frontend/src/assets/images/space-config/canvas-horizontal.svg`、`canvas-vertical.svg`。

---

## Task 1: 后端 —— `uniform_api` 元数据声明 + `verify()` 实时预览

**Files:**
- Modify: `bkflow/space/configs.py`（`UniformApiConfig`）
- Modify: `bkflow/space/views.py`（`SpaceConfigAdminViewSet.verify` 注入 operator）
- Test: `tests/interface/space/test_config_metadata.py`、`tests/interface/space/test_space_views.py`

- [ ] **Step 1: 写失败测试（元数据声明）**

在 `tests/interface/space/test_config_metadata.py` 追加（import 段补 `UniformApiConfig`）：

```python
from bkflow.space.configs import UniformApiConfig  # noqa: E402  追加到已有 import


class TestComplexConfigDeclarations:
    def test_uniform_api_is_api_plugin_config_and_verifiable(self):
        """uniform_api：control=api_plugin_config，group=api_integration，可验证"""
        data = UniformApiConfig.to_dict()
        assert data["ui"]["control"] == "api_plugin_config"
        assert data["group"] == "api_integration"
        assert data["verifiable"] is True
        assert data["help"]["summary"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign && pytest tests/interface/space/test_config_metadata.py::TestComplexConfigDeclarations::test_uniform_api_is_api_plugin_config_and_verifiable -v`
Expected: FAIL —— `TypeError: 'NoneType' object is not subscriptable`（`ui` 仍为 None）。

- [ ] **Step 3: 实现元数据 + verify**

在 `bkflow/space/configs.py` 的 `UniformApiConfig` 类内（`desc` 之后、`Keys` 之前）新增 `group/help/ui/verifiable`：

```python
    group = "api_integration"
    verifiable = True
    help = {
        "summary": _("接入统一 API 平台，把外部 API 暴露为可编排的 API 插件"),
        "effect": _("按 api_key 配置 meta/分类接口；更改配置可能对已存在数据产生不兼容影响，请谨慎操作"),
        "media": [],
        "doc_link": "",
    }
    ui = {
        "control": "api_plugin_config",
        "label": _("API 插件"),
        "help": _("每个 api_key 配置 display_name / meta_apis(apigw URL) / api_categories(可选) / headers"),
        "validation": {"type": "apigw_url"},
    }
```

在 `UniformApiConfig` 类末尾（`validate` 之后）新增 `verify` 类方法。它复用 `UniformAPIClient` 拉取 meta 列表并回显预览，凭证默认取空间默认网关凭证：

```python
    @classmethod
    def verify(cls, space_id, value=None, api_key=None, credential_name=None, operator=None, **kwargs):
        """一键测试：用当前（未保存）配置拉取 meta 列表，回显数量与样例。

        :param value: 待测的 uniform_api 配置（表单当前值；为空则回退到已存配置）
        :param api_key: 待测 api_key，默认 default
        :param credential_name: 用于鉴权的凭证名，默认取空间默认网关凭证
        :param operator: 操作人用户名，用于 apigw 请求头
        """
        from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
        from bkflow.space.models import Credential, SpaceConfig

        if not value:
            value = SpaceConfig.get_config(space_id=space_id, config_name=cls.name) or {}
        try:
            model = UniformAPIConfigHandler(value).handle()
        except Exception as e:
            raise ValidationError(f"[uniform_api verify] 配置解析失败: {e}")

        api_key = api_key or cls.Keys.DEFAULT_API_KEY.value
        api_obj = model.api.get(api_key)
        if not api_obj:
            raise ValidationError(f"[uniform_api verify] 未找到 api_key={api_key} 的配置")
        meta_url = api_obj.get(cls.Keys.META_APIS.value)
        if not meta_url:
            raise ValidationError(f"[uniform_api verify] api_key={api_key} 未配置 meta_apis")

        if not credential_name:
            credential_name = SpaceConfig.get_config(
                space_id=space_id, config_name=ApiGatewayCredentialConfig.name, scope=None
            )
        if not credential_name:
            raise ValidationError("[uniform_api verify] 空间未配置默认网关凭证，无法测试")
        credential = Credential.objects.filter(space_id=space_id, name=credential_name).first()
        if credential is None:
            raise ValidationError(f"[uniform_api verify] 凭证 {credential_name} 不存在")
        content = credential.content or {}
        if not content.get("bk_app_code") or not content.get("bk_app_secret"):
            raise ValidationError(f"[uniform_api verify] 凭证 {credential_name} 缺少 bk_app_code/bk_app_secret")

        client = UniformAPIClient()
        headers = client.gen_default_apigw_header(
            app_code=content["bk_app_code"], app_secret=content["bk_app_secret"], username=operator or "admin"
        )
        request_result = client.request(
            url=meta_url, method="GET", data={}, headers=headers, username=operator or "admin"
        )
        if not request_result.result:
            raise ValidationError(f"[uniform_api verify] 请求失败: {request_result.message}")
        resp_data = request_result.json_resp.get("data", {})
        client.validate_response_data(resp_data, client.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA)
        apis = resp_data.get("apis", [])
        return {
            "api_key": api_key,
            "credential_name": credential_name,
            "total": resp_data.get("total", len(apis)),
            "sample": [a.get("name") for a in apis[:5]],
        }
```

- [ ] **Step 4: verify 接口注入 operator**

在 `bkflow/space/views.py` 的 `SpaceConfigAdminViewSet.verify` 中，把调用 `config_cls.verify` 前的参数组装改为注入操作人（在 P1 已有实现基础上微调）：

```python
        params = dict(data.get("params", {}))
        params.setdefault("operator", request.user.username)
        try:
            preview = config_cls.verify(space_id=data["space_id"], value=data.get("value"), **params)
            return Response({"ok": True, "preview": preview})
        except SpaceConfigVerifyNotSupported as e:
            return Response({"ok": False, "error": {"message": str(e), "not_supported": True}})
        except Exception as e:
            logger.error(f"[space_config verify] name={data['name']} error: {e}")
            return Response({"ok": False, "error": {"message": str(e)}})
```

- [ ] **Step 5: 写失败测试（verify 成功/失败）**

在 `tests/interface/space/test_space_views.py` 的 `TestSpaceConfigAdminViewSet` 类中追加（顶部 import 补 `from unittest import mock` 已存在；`Credential/CredentialType` 从 `bkflow.space.models` 导入已存在）：

```python
    def _uniform_api_value(self):
        return {
            "api": {
                "default": {
                    "meta_apis": "http://bkapi.example.com/api/meta/",
                    "api_categories": "http://bkapi.example.com/api/category/",
                    "display_name": "演示 API",
                }
            }
        }

    def test_uniform_api_verify_success(self):
        """uniform_api verify 成功：回显 total 与 sample"""
        Credential.objects.create(
            space_id=self.space.id,
            name="default_cred",
            type=CredentialType.BK_APP.value,
            content={"bk_app_code": "code", "bk_app_secret": "secret"},
        )
        fake_result = mock.MagicMock()
        fake_result.result = True
        fake_result.json_resp = {"data": {"total": 2, "apis": [{"id": "1", "meta_url": "u", "name": "A"},
                                                               {"id": "2", "meta_url": "u", "name": "B"}]}}
        with mock.patch(
            "bkflow.pipeline_plugins.query.uniform_api.utils.UniformAPIClient.request", return_value=fake_result
        ), mock.patch(
            "bkflow.pipeline_plugins.query.uniform_api.utils.UniformAPIClient.check_url_from_apigw", return_value=True
        ):
            view = SpaceConfigAdminViewSet.as_view({"post": "verify"})
            data = {
                "space_id": self.space.id,
                "name": "uniform_api",
                "value": self._uniform_api_value(),
                "params": {"api_key": "default", "credential_name": "default_cred"},
            }
            request = self.factory.post("/space_configs/verify/", data, format="json")
            force_authenticate(request, user=self.superuser)
            response = view(request)

        assert response.status_code == 200
        payload = response.data.get("data", {})
        assert payload["ok"] is True
        assert payload["preview"]["total"] == 2
        assert payload["preview"]["sample"] == ["A", "B"]

    def test_uniform_api_verify_missing_credential(self):
        """uniform_api verify 凭证不存在：ok=False 且回显错误"""
        view = SpaceConfigAdminViewSet.as_view({"post": "verify"})
        data = {
            "space_id": self.space.id,
            "name": "uniform_api",
            "value": self._uniform_api_value(),
            "params": {"api_key": "default", "credential_name": "not_exist"},
        }
        request = self.factory.post("/space_configs/verify/", data, format="json")
        force_authenticate(request, user=self.superuser)
        response = view(request)

        assert response.status_code == 200
        payload = response.data.get("data", {})
        assert payload["ok"] is False
        assert "not_exist" in payload["error"]["message"]
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign && pytest tests/interface/space/test_config_metadata.py::TestComplexConfigDeclarations tests/interface/space/test_space_views.py::TestSpaceConfigAdminViewSet -v`
Expected: PASS（含元数据与 verify 成功/失败测试）。

- [ ] **Step 7: 提交**

```bash
git add bkflow/space/configs.py bkflow/space/views.py tests/interface/space/test_config_metadata.py tests/interface/space/test_space_views.py
git commit -m "feat(space): uniform_api 元数据声明与实时预览验证 --story=136012988"
```

---

## Task 2: 后端 —— `api_gateway_credential_name` 元数据声明（credential_map）

**Files:**
- Modify: `bkflow/space/configs.py`（`ApiGatewayCredentialConfig`）
- Test: `tests/interface/space/test_config_metadata.py`

- [ ] **Step 1: 追加失败测试**

在 `tests/interface/space/test_config_metadata.py` 的 `TestComplexConfigDeclarations` 追加（import 段补 `ApiGatewayCredentialConfig`）：

```python
    def test_api_gateway_credential_is_credential_map(self):
        """api_gateway_credential_name：control=credential_map，data_source 指向 BK_APP 凭证"""
        data = ApiGatewayCredentialConfig.to_dict()
        assert data["ui"]["control"] == "credential_map"
        assert data["group"] == "access_security"
        assert data["ui"]["data_source"] == {"type": "credential", "credential_type": "BK_APP"}
        assert data["is_mix_type"] is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign && pytest tests/interface/space/test_config_metadata.py::TestComplexConfigDeclarations::test_api_gateway_credential_is_credential_map -v`
Expected: FAIL —— `TypeError: 'NoneType' object is not subscriptable`。

- [ ] **Step 3: 实现元数据**

在 `bkflow/space/configs.py` 的 `ApiGatewayCredentialConfig` 类内（`is_mix_type = True` 之后、`SCHEMA` 之前）新增：

```python
    group = "access_security"
    help = {
        "summary": _("网关调用使用哪个凭证（引用凭证管理里的 BK_APP 凭证）"),
        "effect": _("支持一个默认凭证 + 按作用域覆盖；调用外部 API 时据此选择鉴权凭证"),
        "media": [],
        "doc_link": "",
    }
    ui = {
        "control": "credential_map",
        "label": _("网关凭证"),
        "help": _("默认凭证必选；可按作用域（scope_type_scope_value）追加覆盖"),
        "data_source": {"type": "credential", "credential_type": "BK_APP"},
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign && pytest tests/interface/space/test_config_metadata.py::TestComplexConfigDeclarations -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add bkflow/space/configs.py tests/interface/space/test_config_metadata.py
git commit -m "feat(space): api_gateway_credential_name 补充 credential_map 控件元数据 --story=136012988"
```

---

## Task 3: 前端 —— `ConfigDetail.vue` 支持复合控件（混合存储 + 验证透传 + JSON 切换）

**Files:**
- Modify: `frontend/src/views/admin/Space/SpaceConfig/ConfigDetail.vue`

本任务在 P1 的 `ConfigDetail.vue` 上做三处增强，均为复合控件（P2/P3）服务，对 P1 简单控件零影响：

1. 向动态控件透传 `space-id / verifying / verify-result` 并监听控件自身的 `@verify`（`api_plugin_config` 按 api_key 自测）。
2. `is_mix_type` 配置（`credential_map`）按值类型落 `text_value`(字符串) / `json_value`(对象)。
3. 复合控件支持"结构化 ↔ JSON 源码"切换（复用 `JsonEditorControl`）。

- [ ] **Step 1: 顶部 import 与常量**

在 `<script>` 顶部，`import tools` 之后新增 `JsonEditorControl` 直接引用与控件分类常量：

```javascript
  import JsonEditorControl from './controls/JsonEditorControl.vue';

  // 结构化复合控件（可切换 JSON 源码；is_mix_type 之外的对象型存储）
  const COMPOSITE_CONTROLS = ['credential_map', 'api_plugin_config', 'plugin_scope', 'engine_kv'];
  // 所有"非 JSON 兜底"的已知控件（buildPayload 不做 JSON.parse）
  const KNOWN_CONTROLS = [
    'switch', 'radio', 'select', 'input', 'number', 'url', 'string_list', 'member_selector',
    ...COMPOSITE_CONTROLS,
  ];
  // 控件自带验证 UI（不再显示 ConfigDetail 顶部统一"测试"按钮）
  const SELF_VERIFY_CONTROLS = ['api_plugin_config'];
```

- [ ] **Step 2: data 增 sourceMode**

在 `data()` 返回对象中新增：

```javascript
        sourceMode: false,
```

- [ ] **Step 3: 模板 —— 动态控件绑定与 JSON 切换按钮**

将 `detail-header` 中 `恢复默认值` 按钮之后，新增"切换 JSON 源码"按钮（仅复合控件可见）：

```html
      <bk-button
        v-if="isCompositeControl"
        text
        theme="primary"
        class="source-toggle"
        @click="toggleSourceMode">
        {{ sourceMode ? $t('切换结构化编辑') : $t('切换 JSON 源码') }}
      </bk-button>
```

将 `detail-form` 中的 `<component>` 替换为（透传 space-id / 验证状态，监听控件 `@verify`，`sourceMode` 时切到 JSON 编辑器）：

```html
    <div class="detail-form">
      <component
        :is="sourceMode ? jsonControl : controlComponent"
        v-model="formValue"
        :schema="config.ui || {}"
        :space-id="spaceId"
        :verifying="verifying"
        :verify-result="verifyResult"
        @verify="onControlVerify" />
    </div>
```

将 `detail-verify` 区的显隐条件改为排除自带验证的控件：

```html
    <div
      v-if="config.verifiable && !controlOwnsVerify"
      class="detail-verify">
```

- [ ] **Step 4: computed 扩展**

在 `computed` 中新增/替换以下项（`controlComponent`、`hasMedia` 保留 P1 实现）：

```javascript
      jsonControl() { return JsonEditorControl; },
      currentControl() {
        return this.config && this.config.ui ? this.config.ui.control : null;
      },
      isCompositeControl() {
        return COMPOSITE_CONTROLS.includes(this.currentControl);
      },
      controlOwnsVerify() {
        return SELF_VERIFY_CONTROLS.includes(this.currentControl);
      },
      isJsonControl() {
        // 源码模式或未知/未声明控件都走 JSON 兜底
        if (this.sourceMode) return true;
        return !KNOWN_CONTROLS.includes(this.currentControl);
      },
```

> 删除 P1 中旧的 `isJsonControl`（基于 `['switch','radio','select','input','member_selector']` 的判断），用上面版本替换。

- [ ] **Step 5: methods 扩展**

在 `methods` 中新增 `onControlVerify`、`toggleSourceMode`，并用下方版本替换 P1 的 `buildPayload`（增加 `is_mix_type` 分支）：

```javascript
      onControlVerify(payload) {
        // 复合控件（如 api_plugin_config）自带 api_key 等参数，合并当前表单值后上抛
        this.$emit('verify', {
          space_id: this.spaceId,
          name: this.config.name,
          value: this.formValue,
          ...(payload || {}),
        });
      },
      toggleSourceMode() {
        if (this.sourceMode) {
          // JSON -> 结构化：把源码字符串解析回对象
          if (typeof this.formValue === 'string') {
            if (!tools.checkIsJSON(this.formValue)) {
              this.$bkMessage({ message: this.$t('数据格式不正确，应为JSON格式'), theme: 'error' });
              return;
            }
            this.formValue = JSON.parse(this.formValue);
          }
        }
        this.sourceMode = !this.sourceMode;
      },
      buildPayload() {
        const { id, name, value_type: valueType, is_mix_type: isMixType } = this.config;
        const payload = { id, name, space_id: this.spaceId, value_type: valueType };
        const v = this.formValue;
        if (this.isJsonControl) {
          const parsed = typeof v === 'string' ? JSON.parse(v) : v;
          if (valueType === 'TEXT' && !isMixType) {
            payload.text_value = typeof v === 'string' ? v : JSON.stringify(v);
          } else {
            payload.value_type = isMixType ? 'JSON' : valueType;
            payload.json_value = parsed;
          }
        } else if (isMixType) {
          // credential_map：对象落 json_value(JSON)，字符串落 text_value(TEXT)
          if (v && typeof v === 'object') {
            payload.value_type = 'JSON';
            payload.json_value = v;
          } else {
            payload.value_type = 'TEXT';
            payload.text_value = v || '';
          }
        } else if (valueType === 'TEXT') {
          payload.text_value = v;
        } else {
          payload.json_value = v;
        }
        return payload;
      },
```

同时在 `watch.config.handler` 内、重置 `formValue` 之后追加复位源码模式：

```javascript
          this.sourceMode = false;
```

- [ ] **Step 6: 校验**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign/frontend && npx eslint src/views/admin/Space/SpaceConfig/ConfigDetail.vue`
Expected: 无 error。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/views/admin/Space/SpaceConfig/ConfigDetail.vue
git commit -m "feat(space): 配置详情支持复合控件混合存储/验证透传/JSON 切换 --story=136012988"
```

---

## Task 4: 前端 —— `credential_map` 复合控件 `CredentialMap.vue`

**Files:**
- Create: `frontend/src/views/admin/Space/SpaceConfig/controls/CredentialMap.vue`
- Modify: `frontend/src/views/admin/Space/SpaceConfig/controls/index.js`

职责：默认凭证下拉（本空间 BK_APP 凭证）+ 按作用域覆盖行（scope_type + scope_value + 凭证）+ 就近新建/管理凭证（复用 `CredentialSlider`）+ 悬空引用标红。存储：无覆盖 → 字符串（默认名）；有覆盖 → `{ default, "<type>_<value>": name }`。

- [ ] **Step 1: 创建组件**

```vue
<template>
  <div class="credential-map">
    <div class="cm-row">
      <label class="cm-label">{{ $t('默认凭证') }}<span class="cm-required">*</span></label>
      <bk-select
        v-model="defaultCred"
        searchable
        :loading="loading"
        :placeholder="$t('请选择 BK_APP 凭证')"
        class="cm-select"
        @change="emitValue">
        <bk-option
          v-for="c in credentialList"
          :key="c.name"
          :id="c.name"
          :name="c.name">
          <span>{{ c.name }}</span>
          <span class="cm-opt-desc">{{ c.scope_level }}{{ c.desc ? ' · ' + c.desc : '' }}</span>
        </bk-option>
        <div
          slot="extension"
          class="cm-create"
          @click="openCreate">
          <i class="bk-icon icon-plus-circle" /> {{ $t('新建凭证') }}
        </div>
      </bk-select>
      <span
        v-if="defaultCred && !credExists(defaultCred)"
        class="cm-dangling">{{ $t('凭证不存在，请重选') }}</span>
    </div>

    <div class="cm-overrides">
      <div class="cm-sub-title">{{ $t('按作用域覆盖') }}</div>
      <div
        v-for="(row, idx) in overrides"
        :key="idx"
        class="cm-override-row">
        <bk-input
          v-model="row.scope_type"
          :placeholder="$t('作用域类型')"
          class="cm-scope-input"
          @change="emitValue" />
        <bk-input
          v-model="row.scope_value"
          :placeholder="$t('作用域值')"
          class="cm-scope-input"
          @change="emitValue" />
        <bk-select
          v-model="row.name"
          searchable
          :placeholder="$t('请选择凭证')"
          class="cm-select"
          @change="emitValue">
          <bk-option
            v-for="c in credentialList"
            :key="c.name"
            :id="c.name"
            :name="c.name" />
        </bk-select>
        <i
          class="bk-icon icon-close-circle cm-del"
          @click="removeOverride(idx)" />
        <span
          v-if="row.name && !credExists(row.name)"
          class="cm-dangling">{{ $t('凭证不存在，请重选') }}</span>
      </div>
      <bk-button
        text
        theme="primary"
        @click="addOverride">
        <i class="bk-icon icon-plus-circle" /> {{ $t('添加覆盖') }}
      </bk-button>
    </div>

    <CredentialSlider
      :is-show.sync="sliderShow"
      :detail="{}"
      :space-id="spaceId"
      @confirm="onCredentialCreated" />
  </div>
</template>
<script>
  import { mapActions } from 'vuex';
  import CredentialSlider from '@/views/admin/Space/Credential/components/CredentialSlider.vue';

  export default {
    name: 'CredentialMap',
    components: { CredentialSlider },
    model: { prop: 'value', event: 'change' },
    props: {
      value: { type: [String, Object], default: '' },
      schema: { type: Object, default: () => ({}) },
      spaceId: { type: [String, Number], default: '' },
    },
    data() {
      return {
        loading: false,
        credentialList: [],
        defaultCred: '',
        overrides: [],
        sliderShow: false,
      };
    },
    watch: {
      value: { handler(val) { this.parseValue(val); }, immediate: true },
      spaceId: { handler() { this.loadList(); }, immediate: true },
    },
    methods: {
      ...mapActions('credentialConfig', ['loadCredentialList']),
      async loadList() {
        if (!this.spaceId) return;
        try {
          this.loading = true;
          const resp = await this.loadCredentialList({ space_id: this.spaceId, type: 'BK_APP', limit: 500 });
          this.credentialList = (resp.data && resp.data.results) || [];
        } catch (e) {
          this.credentialList = [];
        } finally {
          this.loading = false;
        }
      },
      parseValue(val) {
        if (val && typeof val === 'object') {
          this.defaultCred = val.default || '';
          this.overrides = Object.keys(val)
            .filter(k => k !== 'default')
            .map((k) => {
              const i = k.indexOf('_');
              return { scope_type: i > -1 ? k.slice(0, i) : k, scope_value: i > -1 ? k.slice(i + 1) : '', name: val[k] };
            });
        } else {
          this.defaultCred = val || '';
          this.overrides = [];
        }
      },
      credExists(name) {
        return this.credentialList.some(c => c.name === name);
      },
      addOverride() {
        this.overrides.push({ scope_type: '', scope_value: '', name: '' });
      },
      removeOverride(idx) {
        this.overrides.splice(idx, 1);
        this.emitValue();
      },
      emitValue() {
        const valid = this.overrides.filter(o => o.scope_type && o.scope_value && o.name);
        if (!valid.length) {
          this.$emit('change', this.defaultCred || '');
          return;
        }
        const obj = { default: this.defaultCred };
        valid.forEach((o) => { obj[`${o.scope_type}_${o.scope_value}`] = o.name; });
        this.$emit('change', obj);
      },
      openCreate() {
        this.sliderShow = true;
      },
      async onCredentialCreated() {
        await this.loadList();
      },
    },
  };
</script>
<style lang="scss" scoped>
  .credential-map { font-size: 12px; }
  .cm-row { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
  .cm-label { width: 72px; color: #63656e; }
  .cm-required { color: #ea3636; margin-left: 2px; }
  .cm-select { flex: 1; max-width: 360px; }
  .cm-opt-desc { margin-left: 8px; color: #979ba5; }
  .cm-create { padding: 0 12px; line-height: 38px; color: #3a84ff; cursor: pointer; }
  .cm-dangling { color: #ea3636; margin-left: 8px; }
  .cm-sub-title { color: #979ba5; margin: 8px 0; }
  .cm-override-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
  .cm-scope-input { width: 140px; }
  .cm-del { color: #c4c6cc; cursor: pointer; &:hover { color: #ea3636; } }
</style>
```

- [ ] **Step 2: 注册控件**

在 `controls/index.js` 顶部追加 import，并在 `registry` 中登记（`getControlComponent` 保持不变）：

```javascript
import CredentialMap from './CredentialMap.vue';
// registry 中新增：
  credential_map: CredentialMap,
```

- [ ] **Step 3: 校验**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign/frontend && npx eslint src/views/admin/Space/SpaceConfig/controls/CredentialMap.vue src/views/admin/Space/SpaceConfig/controls/index.js`
Expected: 无 error。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/admin/Space/SpaceConfig/controls/CredentialMap.vue frontend/src/views/admin/Space/SpaceConfig/controls/index.js
git commit -m "feat(space): credential_map 凭证联动复合控件 --story=136012988"
```

---

## Task 5: 前端 —— `api_plugin_config` 复合控件 `ApiPluginConfig.vue`

**Files:**
- Create: `frontend/src/views/admin/Space/SpaceConfig/controls/ApiPluginConfig.vue`
- Modify: `frontend/src/views/admin/Space/SpaceConfig/controls/index.js`

职责：按 `api_key` 结构化编辑 `display_name / meta_apis / api_categories / headers`，每个 api_key 一个"测试"按钮（向父级发 `verify`，params 带 `api_key`），从 `verify-result` 回显预览/报错。旧值无 `api` 结构时给出提示，引导用户用顶部"切换 JSON 源码"。

- [ ] **Step 1: 创建组件**

```vue
<template>
  <div class="api-plugin-config">
    <div
      v-if="!hasApiStructure"
      class="apc-legacy-tip">
      {{ $t('当前值不是标准 API 结构，请使用右上角"切换 JSON 源码"编辑') }}
    </div>
    <div
      v-for="(item, idx) in apiList"
      :key="item._id"
      class="apc-card">
      <div class="apc-card-head">
        <bk-input
          v-model="item.apiKey"
          :placeholder="$t('api_key，如 default')"
          class="apc-key"
          @change="emitValue" />
        <bk-button
          :loading="verifying && testingKey === item.apiKey"
          size="small"
          @click="test(item.apiKey)">
          {{ $t('测试') }}
        </bk-button>
        <i
          class="bk-icon icon-close-circle apc-del"
          @click="removeApi(idx)" />
      </div>
      <bk-form
        form-type="vertical"
        class="apc-form">
        <bk-form-item :label="$t('显示名称')">
          <bk-input
            v-model="item.display_name"
            @change="emitValue" />
        </bk-form-item>
        <bk-form-item
          label="meta_apis"
          :desc="$t('接口列表 apigw URL')">
          <bk-input
            v-model="item.meta_apis"
            @change="emitValue" />
        </bk-form-item>
        <bk-form-item
          label="api_categories"
          :desc="$t('分类接口 apigw URL，可选')">
          <bk-input
            v-model="item.api_categories"
            @change="emitValue" />
        </bk-form-item>
        <bk-form-item label="headers">
          <div
            v-for="(h, hIdx) in item.headers"
            :key="hIdx"
            class="apc-header-row">
            <bk-input
              v-model="h.key"
              placeholder="Header"
              class="apc-h-input"
              @change="emitValue" />
            <bk-input
              v-model="h.value"
              placeholder="Value"
              class="apc-h-input"
              @change="emitValue" />
            <i
              class="bk-icon icon-close-circle apc-del"
              @click="removeHeader(item, hIdx)" />
          </div>
          <bk-button
            text
            theme="primary"
            @click="addHeader(item)">
            <i class="bk-icon icon-plus-circle" /> {{ $t('添加请求头') }}
          </bk-button>
        </bk-form-item>
      </bk-form>
      <div
        v-if="testingKey === item.apiKey && verifyResult"
        :class="['apc-result', verifyResult.ok ? 'is-ok' : 'is-fail']">
        <template v-if="verifyResult.ok">
          {{ $t('测试通过，共 {0} 个 API', [verifyResult.preview.total]) }}
          <span v-if="verifyResult.preview.sample && verifyResult.preview.sample.length">
            ：{{ verifyResult.preview.sample.join('、') }}
          </span>
        </template>
        <template v-else>{{ verifyResult.error && verifyResult.error.message }}</template>
      </div>
    </div>
    <bk-button
      text
      theme="primary"
      @click="addApi">
      <i class="bk-icon icon-plus-circle" /> {{ $t('添加 API') }}
    </bk-button>
  </div>
</template>
<script>
  let uid = 0;

  export default {
    name: 'ApiPluginConfig',
    model: { prop: 'value', event: 'change' },
    props: {
      value: { type: [Object, String], default: () => ({}) },
      schema: { type: Object, default: () => ({}) },
      spaceId: { type: [String, Number], default: '' },
      verifying: { type: Boolean, default: false },
      verifyResult: { type: Object, default: null },
    },
    data() {
      return {
        apiList: [],
        testingKey: '',
      };
    },
    computed: {
      hasApiStructure() {
        return !this.value || (typeof this.value === 'object' && !!this.value.api);
      },
    },
    watch: {
      value: { handler(val) { this.parseValue(val); }, immediate: true },
    },
    methods: {
      parseValue(val) {
        const api = (val && typeof val === 'object' && val.api) || {};
        this.apiList = Object.keys(api).map((key) => {
          const o = api[key] || {};
          return {
            _id: uid++,
            apiKey: key,
            display_name: o.display_name || '',
            meta_apis: o.meta_apis || '',
            api_categories: o.api_categories || '',
            headers: Object.entries(o.headers || {}).map(([k, v]) => ({ key: k, value: v })),
          };
        });
      },
      addApi() {
        this.apiList.push({ _id: uid++, apiKey: '', display_name: '', meta_apis: '', api_categories: '', headers: [] });
      },
      removeApi(idx) {
        this.apiList.splice(idx, 1);
        this.emitValue();
      },
      addHeader(item) { item.headers.push({ key: '', value: '' }); },
      removeHeader(item, hIdx) { item.headers.splice(hIdx, 1); this.emitValue(); },
      emitValue() {
        const api = {};
        this.apiList.forEach((item) => {
          if (!item.apiKey) return;
          const entry = { display_name: item.display_name, meta_apis: item.meta_apis };
          if (item.api_categories) entry.api_categories = item.api_categories;
          const headers = {};
          item.headers.forEach((h) => { if (h.key) headers[h.key] = h.value; });
          if (Object.keys(headers).length) entry.headers = headers;
          api[item.apiKey] = entry;
        });
        const next = { ...(this.value && typeof this.value === 'object' ? this.value : {}), api };
        this.$emit('change', next);
      },
      test(apiKey) {
        this.testingKey = apiKey;
        this.$emit('verify', { params: { api_key: apiKey } });
      },
    },
  };
</script>
<style lang="scss" scoped>
  .api-plugin-config { font-size: 12px; }
  .apc-legacy-tip {
    padding: 8px 12px; margin-bottom: 12px; background: #fdf4e8; color: #ff9c01; border-radius: 2px;
  }
  .apc-card { border: 1px solid #dcdee5; border-radius: 2px; padding: 12px; margin-bottom: 12px; }
  .apc-card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
  .apc-key { width: 200px; }
  .apc-del { color: #c4c6cc; cursor: pointer; &:hover { color: #ea3636; } }
  .apc-header-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
  .apc-h-input { width: 200px; }
  .apc-result { margin-top: 8px; font-size: 13px;
    &.is-ok { color: #14a568; } &.is-fail { color: #ea3636; } }
</style>
```

> 说明：`verify-result` 结构为后端 `verify` 接口返回体（`{ ok, preview }` 或 `{ ok:false, error }`）。父级 `index.vue` 的 `handleVerify` 已把 `resp.data || resp` 存入 `verifyResult`，本控件直接读取。

- [ ] **Step 2: 注册控件**

在 `controls/index.js` 追加：

```javascript
import ApiPluginConfig from './ApiPluginConfig.vue';
// registry 中新增：
  api_plugin_config: ApiPluginConfig,
```

- [ ] **Step 3: 校验**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign/frontend && npx eslint src/views/admin/Space/SpaceConfig/controls/ApiPluginConfig.vue src/views/admin/Space/SpaceConfig/controls/index.js`
Expected: 无 error。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/admin/Space/SpaceConfig/controls/ApiPluginConfig.vue frontend/src/views/admin/Space/SpaceConfig/controls/index.js
git commit -m "feat(space): api_plugin_config 结构化编辑与实时预览控件 --story=136012988"
```

> **P2 阶段小结**：Task 1–5 完成后，`api_gateway_credential_name` 与 `uniform_api` 已具备结构化控件、凭证联动与一键验证；`ConfigDetail` 的"结构化 ↔ JSON 源码"切换（Task 3）同时惠及后续 P3 复合控件。建议在此处做一次 P2 浏览器手测（见文末验收）后再进入 P3。

---

# P3

## Task 6: 后端 —— `space_plugin_config` / `engine_space_config` 元数据声明

**Files:**
- Modify: `bkflow/space/configs.py`（`SpacePluginConfig`、`SpaceEngineConfig`）
- Test: `tests/interface/space/test_config_metadata.py`

- [ ] **Step 1: 追加失败测试**

在 `TestComplexConfigDeclarations` 追加（import 段补 `SpacePluginConfig`、`SpaceEngineConfig`）：

```python
    def test_space_plugin_config_is_plugin_scope(self):
        data = SpacePluginConfig.to_dict()
        assert data["ui"]["control"] == "plugin_scope"
        assert data["group"] == "api_integration"

    def test_engine_space_config_is_engine_kv(self):
        data = SpaceEngineConfig.to_dict()
        assert data["ui"]["control"] == "engine_kv"
        assert data["group"] == "api_integration"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign && pytest tests/interface/space/test_config_metadata.py::TestComplexConfigDeclarations -k "plugin_scope or engine_kv" -v`
Expected: FAIL —— `TypeError: 'NoneType' object is not subscriptable`。

- [ ] **Step 3: 实现元数据**

在 `SpacePluginConfig` 类内（`example` 之后、`validate` 之前）新增：

```python
    group = "api_integration"
    help = {
        "summary": _("控制本空间可用的插件范围"),
        "effect": _("allow_list 仅允许所列插件，deny_list 屏蔽所列插件；影响流程编辑时可选插件"),
        "media": [],
        "doc_link": "",
    }
    ui = {
        "control": "plugin_scope",
        "label": _("空间插件"),
        "help": _("选择模式并配置插件 code 列表"),
    }
```

在 `SpaceEngineConfig` 类内（`SCHEMA` 之前，`example` 之后）新增：

```python
    group = "api_integration"
    help = {
        "summary": _("下发给引擎的运行参数（高级）"),
        "effect": _("space 为空间级键值，scope 为按作用域覆盖的键值；影响引擎运行行为，请谨慎修改"),
        "media": [],
        "doc_link": "",
    }
    ui = {
        "control": "engine_kv",
        "label": _("引擎模块配置"),
        "help": _("键值仅支持字符串/数字/布尔"),
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign && pytest tests/interface/space/test_config_metadata.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add bkflow/space/configs.py tests/interface/space/test_config_metadata.py
git commit -m "feat(space): space_plugin_config/engine_space_config 补充控件元数据 --story=136012988"
```

---

## Task 7: 前端 —— `plugin_scope` 复合控件 `PluginScope.vue`

**Files:**
- Create: `frontend/src/views/admin/Space/SpaceConfig/controls/PluginScope.vue`
- Modify: `frontend/src/views/admin/Space/SpaceConfig/controls/index.js`

职责：模式单选（allow_list / deny_list，带说明）+ 插件多选（`bk-select` 可搜索、允许自定义 code 以覆盖远程/统一 API 插件）。存储：`{ default: { mode, plugin_codes } }`。候选插件复用 `atomForm/loadSingleAtomList`。

- [ ] **Step 1: 创建组件**

```vue
<template>
  <div class="plugin-scope">
    <bk-radio-group
      v-model="mode"
      class="ps-mode"
      @change="emitValue">
      <bk-radio value="allow_list" class="ps-radio">
        <span class="ps-label">{{ $t('允许名单') }}</span>
        <span class="ps-desc">{{ $t('仅所列插件可用') }}</span>
      </bk-radio>
      <bk-radio value="deny_list" class="ps-radio">
        <span class="ps-label">{{ $t('屏蔽名单') }}</span>
        <span class="ps-desc">{{ $t('屏蔽所列插件，其余可用') }}</span>
      </bk-radio>
    </bk-radio-group>
    <bk-select
      v-model="pluginCodes"
      multiple
      searchable
      display-tag
      allow-create
      :loading="loading"
      :placeholder="$t('选择或输入插件 code')"
      class="ps-select"
      @change="emitValue">
      <bk-option
        v-for="p in candidates"
        :key="p.id"
        :id="p.id"
        :name="p.name" />
    </bk-select>
  </div>
</template>
<script>
  import { mapActions } from 'vuex';

  export default {
    name: 'PluginScope',
    model: { prop: 'value', event: 'change' },
    props: {
      value: { type: [Object, String], default: () => ({}) },
      schema: { type: Object, default: () => ({}) },
      spaceId: { type: [String, Number], default: '' },
    },
    data() {
      return {
        mode: 'allow_list',
        pluginCodes: [],
        candidates: [],
        loading: false,
      };
    },
    watch: {
      value: { handler(val) { this.parseValue(val); }, immediate: true },
      spaceId: { handler() { this.loadCandidates(); }, immediate: true },
    },
    methods: {
      ...mapActions('atomForm', ['loadSingleAtomList']),
      parseValue(val) {
        const def = (val && typeof val === 'object' && val.default) || {};
        this.mode = def.mode || 'allow_list';
        this.pluginCodes = Array.isArray(def.plugin_codes) ? [...def.plugin_codes] : [];
      },
      async loadCandidates() {
        if (!this.spaceId) return;
        try {
          this.loading = true;
          const list = await this.loadSingleAtomList({ space_id: this.spaceId });
          this.candidates = (list || []).map(p => ({ id: p.code || p.tag_code, name: p.name || p.code }));
        } catch (e) {
          this.candidates = [];
        } finally {
          this.loading = false;
        }
      },
      emitValue() {
        this.$emit('change', { default: { mode: this.mode, plugin_codes: this.pluginCodes } });
      },
    },
  };
</script>
<style lang="scss" scoped>
  .plugin-scope { font-size: 12px; }
  .ps-mode { display: flex; flex-direction: column; margin-bottom: 12px; }
  .ps-radio { margin-bottom: 8px; }
  .ps-label { font-weight: 500; }
  .ps-desc { margin-left: 8px; color: #979ba5; font-size: 12px; }
  .ps-select { max-width: 480px; }
</style>
```

- [ ] **Step 2: 注册控件**

在 `controls/index.js` 追加：

```javascript
import PluginScope from './PluginScope.vue';
// registry 中新增：
  plugin_scope: PluginScope,
```

- [ ] **Step 3: 校验**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign/frontend && npx eslint src/views/admin/Space/SpaceConfig/controls/PluginScope.vue src/views/admin/Space/SpaceConfig/controls/index.js`
Expected: 无 error。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/admin/Space/SpaceConfig/controls/PluginScope.vue frontend/src/views/admin/Space/SpaceConfig/controls/index.js
git commit -m "feat(space): plugin_scope 空间插件范围控件 --story=136012988"
```

---

## Task 8: 前端 —— `engine_kv` 复合控件 `EngineKv.vue`

**Files:**
- Create: `frontend/src/views/admin/Space/SpaceConfig/controls/EngineKv.vue`
- Modify: `frontend/src/views/admin/Space/SpaceConfig/controls/index.js`

职责：两级键值编辑 —— `space`（空间级键值）+ `scope`（按 `scope_type_scope_value` 覆盖的键值块）。存储：`{ space: {k:v}, scope: { "<type>_<value>": {k:v} } }`（值为字符串）。

- [ ] **Step 1: 创建组件**

```vue
<template>
  <div class="engine-kv">
    <div class="ek-section">
      <div class="ek-title">{{ $t('空间级') }}</div>
      <div
        v-for="(row, idx) in spaceRows"
        :key="idx"
        class="ek-row">
        <bk-input v-model="row.key" :placeholder="$t('键')" class="ek-input" @change="emitValue" />
        <bk-input v-model="row.value" :placeholder="$t('值')" class="ek-input" @change="emitValue" />
        <i class="bk-icon icon-close-circle ek-del" @click="removeSpaceRow(idx)" />
      </div>
      <bk-button text theme="primary" @click="addSpaceRow">
        <i class="bk-icon icon-plus-circle" /> {{ $t('添加') }}
      </bk-button>
    </div>

    <div class="ek-section">
      <div class="ek-title">{{ $t('按作用域') }}</div>
      <div
        v-for="(blk, bIdx) in scopeBlocks"
        :key="bIdx"
        class="ek-scope-block">
        <div class="ek-scope-head">
          <bk-input v-model="blk.scope_type" :placeholder="$t('作用域类型')" class="ek-scope-input" @change="emitValue" />
          <bk-input v-model="blk.scope_value" :placeholder="$t('作用域值')" class="ek-scope-input" @change="emitValue" />
          <i class="bk-icon icon-close-circle ek-del" @click="removeBlock(bIdx)" />
        </div>
        <div
          v-for="(row, idx) in blk.rows"
          :key="idx"
          class="ek-row">
          <bk-input v-model="row.key" :placeholder="$t('键')" class="ek-input" @change="emitValue" />
          <bk-input v-model="row.value" :placeholder="$t('值')" class="ek-input" @change="emitValue" />
          <i class="bk-icon icon-close-circle ek-del" @click="removeScopeRow(blk, idx)" />
        </div>
        <bk-button text theme="primary" @click="addScopeRow(blk)">
          <i class="bk-icon icon-plus-circle" /> {{ $t('添加') }}
        </bk-button>
      </div>
      <bk-button text theme="primary" @click="addBlock">
        <i class="bk-icon icon-plus-circle" /> {{ $t('添加作用域') }}
      </bk-button>
    </div>
  </div>
</template>
<script>
  export default {
    name: 'EngineKv',
    model: { prop: 'value', event: 'change' },
    props: {
      value: { type: [Object, String], default: () => ({}) },
      schema: { type: Object, default: () => ({}) },
    },
    data() {
      return { spaceRows: [], scopeBlocks: [] };
    },
    watch: {
      value: { handler(val) { this.parseValue(val); }, immediate: true },
    },
    methods: {
      toRows(obj) {
        return Object.entries(obj || {}).map(([key, value]) => ({ key, value: String(value) }));
      },
      parseValue(val) {
        const v = (val && typeof val === 'object') ? val : {};
        this.spaceRows = this.toRows(v.space);
        this.scopeBlocks = Object.entries(v.scope || {}).map(([k, kv]) => {
          const i = k.indexOf('_');
          return {
            scope_type: i > -1 ? k.slice(0, i) : k,
            scope_value: i > -1 ? k.slice(i + 1) : '',
            rows: this.toRows(kv),
          };
        });
      },
      addSpaceRow() { this.spaceRows.push({ key: '', value: '' }); },
      removeSpaceRow(idx) { this.spaceRows.splice(idx, 1); this.emitValue(); },
      addBlock() { this.scopeBlocks.push({ scope_type: '', scope_value: '', rows: [] }); },
      removeBlock(idx) { this.scopeBlocks.splice(idx, 1); this.emitValue(); },
      addScopeRow(blk) { blk.rows.push({ key: '', value: '' }); },
      removeScopeRow(blk, idx) { blk.rows.splice(idx, 1); this.emitValue(); },
      rowsToObj(rows) {
        const obj = {};
        rows.forEach((r) => { if (r.key) obj[r.key] = r.value; });
        return obj;
      },
      emitValue() {
        const result = {};
        const space = this.rowsToObj(this.spaceRows);
        if (Object.keys(space).length) result.space = space;
        const scope = {};
        this.scopeBlocks.forEach((blk) => {
          if (!blk.scope_type || !blk.scope_value) return;
          const kv = this.rowsToObj(blk.rows);
          if (Object.keys(kv).length) scope[`${blk.scope_type}_${blk.scope_value}`] = kv;
        });
        if (Object.keys(scope).length) result.scope = scope;
        this.$emit('change', result);
      },
    },
  };
</script>
<style lang="scss" scoped>
  .engine-kv { font-size: 12px; }
  .ek-section { margin-bottom: 16px; }
  .ek-title { color: #313238; font-weight: 500; margin-bottom: 8px; }
  .ek-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
  .ek-input { width: 200px; }
  .ek-scope-block { border: 1px solid #dcdee5; border-radius: 2px; padding: 12px; margin-bottom: 8px; }
  .ek-scope-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
  .ek-scope-input { width: 160px; }
  .ek-del { color: #c4c6cc; cursor: pointer; &:hover { color: #ea3636; } }
</style>
```

- [ ] **Step 2: 注册控件**

在 `controls/index.js` 追加：

```javascript
import EngineKv from './EngineKv.vue';
// registry 中新增：
  engine_kv: EngineKv,
```

- [ ] **Step 3: 校验**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign/frontend && npx eslint src/views/admin/Space/SpaceConfig/controls/EngineKv.vue src/views/admin/Space/SpaceConfig/controls/index.js`
Expected: 无 error。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/admin/Space/SpaceConfig/controls/EngineKv.vue frontend/src/views/admin/Space/SpaceConfig/controls/index.js
git commit -m "feat(space): engine_kv 引擎两级键值控件 --story=136012988"
```

> **结构化 ↔ JSON 源码切换**：设计 §6.3 要求的复合控件源码逃生通道已在 **Task 3** 的 `ConfigDetail` 中统一实现（`isCompositeControl` → 顶部"切换 JSON 源码"按钮），`credential_map / api_plugin_config / plugin_scope / engine_kv` 均自动获得，无需在各控件内重复实现。

## Task 9: 媒体素材 —— `canvas_mode` 横/纵向图示补图

**Files:**
- Create: `frontend/src/assets/images/space-config/canvas-horizontal.svg`
- Create: `frontend/src/assets/images/space-config/canvas-vertical.svg`
- Create: `frontend/src/views/admin/Space/SpaceConfig/controls/mediaAssets.js`
- Modify: `frontend/src/views/admin/Space/SpaceConfig/ConfigDetail.vue`（媒体渲染改用 `resolveMedia`）
- Modify: `bkflow/space/configs.py`（`CanvasModeConfig.help.media` 指向 asset）

约定：后端 `help.media[].src` 支持 `asset:<name>` 方案（前端本地素材），普通 URL 原样使用。前端用一个 asset 注册表解析，避免依赖部署态静态资源路径。

- [ ] **Step 1: 创建横向示意 SVG**

`frontend/src/assets/images/space-config/canvas-horizontal.svg`：

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 120" width="360" height="120">
  <rect x="16" y="46" width="72" height="36" rx="4" fill="#e1ecff" stroke="#3a84ff"/>
  <rect x="144" y="46" width="72" height="36" rx="4" fill="#e1ecff" stroke="#3a84ff"/>
  <rect x="272" y="46" width="72" height="36" rx="4" fill="#e1ecff" stroke="#3a84ff"/>
  <line x1="88" y1="64" x2="144" y2="64" stroke="#979ba5" stroke-width="2" marker-end="url(#ah)"/>
  <line x1="216" y1="64" x2="272" y2="64" stroke="#979ba5" stroke-width="2" marker-end="url(#ah)"/>
  <defs>
    <marker id="ah" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#979ba5"/>
    </marker>
  </defs>
</svg>
```

- [ ] **Step 2: 创建纵向示意 SVG**

`frontend/src/assets/images/space-config/canvas-vertical.svg`：

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 240" width="160" height="240">
  <rect x="44" y="12" width="72" height="36" rx="4" fill="#e1ecff" stroke="#3a84ff"/>
  <rect x="44" y="102" width="72" height="36" rx="4" fill="#e1ecff" stroke="#3a84ff"/>
  <rect x="44" y="192" width="72" height="36" rx="4" fill="#e1ecff" stroke="#3a84ff"/>
  <line x1="80" y1="48" x2="80" y2="102" stroke="#979ba5" stroke-width="2" marker-end="url(#av)"/>
  <line x1="80" y1="138" x2="80" y2="192" stroke="#979ba5" stroke-width="2" marker-end="url(#av)"/>
  <defs>
    <marker id="av" markerWidth="8" markerHeight="8" refX="3" refY="6" orient="auto">
      <path d="M0,0 L6,0 L3,6 Z" fill="#979ba5"/>
    </marker>
  </defs>
</svg>
```

- [ ] **Step 3: 素材注册表**

`frontend/src/views/admin/Space/SpaceConfig/controls/mediaAssets.js`：

```javascript
const assets = {
  'canvas-horizontal': require('@/assets/images/space-config/canvas-horizontal.svg'),
  'canvas-vertical': require('@/assets/images/space-config/canvas-vertical.svg'),
};

// 后端 help.media[].src 支持 asset:<name> 方案；普通 URL 原样返回
export function resolveMediaSrc(src) {
  if (!src) return '';
  if (src.indexOf('asset:') === 0) return assets[src.slice(6)] || '';
  return src;
}

export default assets;
```

- [ ] **Step 4: ConfigDetail 媒体渲染改用 resolveMediaSrc**

在 `ConfigDetail.vue` 顶部 import：

```javascript
  import { resolveMediaSrc } from './controls/mediaAssets.js';
```

在 `methods` 增加：

```javascript
      resolveMedia(src) { return resolveMediaSrc(src); },
```

将 P1 媒体渲染 `<img v-if="m.src" :src="m.src" :alt="m.caption">` 改为：

```html
          <img
            v-if="resolveMedia(m.src)"
            :src="resolveMedia(m.src)"
            :alt="m.caption">
```

- [ ] **Step 5: 后端 canvas_mode 指向素材**

在 `bkflow/space/configs.py` 把 `CanvasModeConfig.help.media` 改为（替换 P1 的空 gif 占位）：

```python
        "media": [
            {"type": "image", "src": "asset:canvas-horizontal", "caption": _("横向排布")},
            {"type": "image", "src": "asset:canvas-vertical", "caption": _("纵向排布")},
        ],
```

> `gateway_expression` 的对比图示较复杂，本期保留文字说明 + `doc_link` 占位，图示素材待产品补充（符合设计 §非目标"仅预留位"）。

- [ ] **Step 6: 校验**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign/frontend && npx eslint src/views/admin/Space/SpaceConfig/controls/mediaAssets.js src/views/admin/Space/SpaceConfig/ConfigDetail.vue`
Expected: 无 error。

> 若 webpack 未配置 `.svg` 为可 `require` 的资源模块，`svg-url-loader`/`file-loader` 通常已在 bk-magic-vue 脚手架内置；如遇 require 报错，改用 `import` 静态引入或确认 `vue.config.js` 的 svg 规则。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/assets/images/space-config/ frontend/src/views/admin/Space/SpaceConfig/controls/mediaAssets.js frontend/src/views/admin/Space/SpaceConfig/ConfigDetail.vue bkflow/space/configs.py
git commit -m "feat(space): canvas_mode 横纵向图示补图 --story=136012988"
```

---

## Task 10: i18n 文案、整体校验与验收

**Files:**
- Modify: `frontend/src/config/i18n/cn.js`、`frontend/src/config/i18n/en.js`

- [ ] **Step 1: 补充文案键**

在 `cn.js`、`en.js` 补齐本次新增中文键（已存在则跳过）：

`'切换 JSON 源码'`、`'切换结构化编辑'`、`'默认凭证'`、`'请选择 BK_APP 凭证'`、`'新建凭证'`、`'凭证不存在，请重选'`、`'按作用域覆盖'`、`'作用域类型'`、`'作用域值'`、`'请选择凭证'`、`'添加覆盖'`、`'当前值不是标准 API 结构，请使用右上角"切换 JSON 源码"编辑'`、`'api_key，如 default'`、`'显示名称'`、`'接口列表 apigw URL'`、`'分类接口 apigw URL，可选'`、`'添加请求头'`、`'测试通过，共 {0} 个 API'`、`'添加 API'`、`'允许名单'`、`'仅所列插件可用'`、`'屏蔽名单'`、`'屏蔽所列插件，其余可用'`、`'选择或输入插件 code'`、`'空间级'`、`'按作用域'`、`'键'`、`'值'`、`'添加'`、`'添加作用域'`。

`cn.js` 键值一致（如 `'默认凭证': '默认凭证'`）；`en.js` 给英文翻译（带占位符的如 `'测试通过，共 {0} 个 API': 'Passed, {0} APIs in total'`）。

- [ ] **Step 2: 全量前端 lint**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign/frontend && npm run lint`
Expected: 无 error（warning 与仓库现状一致可接受）。

- [ ] **Step 3: 后端整体回归**

Run: `cd /Users/dengyh/Projects/bk-flow/.worktrees/space-config-redesign && pytest tests/interface/space/ -v`
Expected: 全部 PASS。

- [ ] **Step 4: 浏览器手测（验收）**

进入某空间 → 管理 → 配置：

**P2 验收**
1. `网关凭证`：默认凭证下拉列出本空间 BK_APP 凭证；"+ 新建凭证"打开侧滑，建完自动回填；改凭证名到不存在值应标红"凭证不存在，请重选"；无覆盖保存为字符串、加覆盖保存为 dict（对照 `get_all_space_configs` 返回）。
2. `API 插件`：按 api_key 结构化编辑；点"测试"回显"测试通过，共 N 个 API"或失败错误（需空间已配默认网关凭证 + 可达 apigw）；顶部"切换 JSON 源码"可与结构化互转。
3. 旧 V1 `uniform_api`（顶层 meta_apis）值：展示"非标准结构"提示，可切 JSON 源码编辑不报错。

**P3 验收**
4. `空间插件`：allow_list/deny_list 单选 + 插件多选（含自定义 code）；保存为 `{default:{mode,plugin_codes}}`。
5. `引擎模块配置`：空间级 + 作用域两级键值编辑；保存为 `{space,scope}`。
6. `画布模式`：右侧说明区显示横向/纵向 SVG 图示。
7. 所有复合控件"切换 JSON 源码"往返一致、保存成功。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/config/i18n/cn.js frontend/src/config/i18n/en.js
git commit -m "feat(space): 补充复合控件 i18n 文案 --story=136012988"
```

---

## Self-Review

- **Spec 覆盖**：
  - §7 凭证联动（默认+作用域覆盖、就近新建、悬空引用标红、管理）→ Task 2 + Task 4 `CredentialMap.vue`。
  - §8 `uniform_api` 结构化 + 实时预览 → Task 1（`verify()`）+ Task 5 `ApiPluginConfig.vue`；`space_plugin_config` → Task 6 + Task 7；`engine_space_config` → Task 6 + Task 8。
  - §5.3 验证接口用"表单当前值"、凭证默认取空间默认 → Task 1 `verify(value, credential_name 默认空间默认)`。
  - §6.3 结构化 ↔ JSON 源码兜底 → Task 3（`ConfigDetail` 统一实现）。
  - §9 兼容性：旧字符串凭证=仅默认（Task 4 parseValue）、旧 V1 uniform_api 归一化/落 JSON 源码（Task 5 `hasApiStructure` 提示 + Task 3 切换）→ 覆盖。
  - §8 媒体位（canvas_mode 最该补图）→ Task 9。
- **占位符扫描**：无 TBD/TODO。所有 commit 统一关联 TAPD 单据 `--story=136012988`（[空间配置改版｜P2·P3 复合控件与实时验证实现](https://tapd.woa.com/70120217/prong/stories/view/136012988)）。`gateway_expression` 图示为设计既定"仅预留位"，非计划占位。Task 9 Step 6 的 svg require 注记为核对动作（非占位）。
- **类型/命名一致**：
  - 控件 `model` 统一 `{prop:'value',event:'change'}`；注册表键 `credential_map/api_plugin_config/plugin_scope/engine_kv` 与后端 `ui.control` 完全一致。
  - `verify` 返回 `{ok, preview:{api_key,credential_name,total,sample} | error:{message}}`：后端 Task 1、前端 Task 5 读取 `verifyResult.preview.total/sample` 与 `verifyResult.error.message` 一致；`ConfigDetail.onControlVerify` 透传 `{params:{api_key}}` 与后端 `verify(api_key=...)` 形参一致。
  - `is_mix_type` 存储：`ApiGatewayCredentialConfig.is_mix_type=True`（Task 2 断言）与前端 `buildPayload` 的 `isMixType` 分支（Task 3）一致；字符串→`text_value`(TEXT)、对象→`json_value`(JSON)。
  - `COMPOSITE_CONTROLS`/`KNOWN_CONTROLS`/`SELF_VERIFY_CONTROLS`（Task 3）与各控件注册键一致。
- **依赖复用核对**：`UniformAPIClient.request/gen_default_apigw_header/validate_response_data` 与 `UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA`（`bkflow/pipeline_plugins/query/uniform_api/utils.py`）、`UniformAPIConfigHandler`（configs.py）、`Credential.content`（`bkflow/space/models.py`）、`credentialConfig/loadCredentialList`、`atomForm/loadSingleAtomList`、`CredentialSlider`（`is-show.sync/detail/space-id/@confirm`）、`FullCodeEditor`（`value` + `@input`）均为现有实现，签名已核对。

---

## 后续/超出本计划

- `gateway_expression` 图示、`api_gateway_credential_name`/`uniform_api` 的文档 `doc_link` 待产品/文档补充。
- `credential_map` 的"作用域校验（scope_level=none/不匹配置灰）"为增强项，本期以悬空引用标红为主，可在后续迭代补充。
- 前端组件单测：仓库当前无前端单测框架，控件以 `eslint` + 浏览器手测保障；后续若引入 vitest/jest 可补充控件级用例（设计 §12）。

