# V4 开放插件原生表单接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增内部统一插件详情接口与统一表单加载器，让 Uniform API V4 开放插件在流程编辑、任务查看与修改、Mock、批量更新和变量编辑中原样使用提供方的 `component_js/renderform/jsonschema`，同时保证 BKFlow 内置、BKFlow 第三方和 Uniform API V2/V3 完整保留原链路。

**Architecture:** 后端 `/api/plugin/detail/` 通过 `component/remote_plugin/uniform_api` 三个适配器输出固定字段集合；V4 uniform adapter 通过已同步目录、两层准入和精确版本定位提供方 detail，并把用户与 scope 传给标准运维。前端只在明确识别为 V4 开放插件时调用新接口，由 `PluginFormLoader` 装配 `$.context` 并把原生表单交给现有 `RenderForm/JsonschemaForm`。旧节点不迁移、不刷新、不自动升级。

**Tech Stack:** Django 3.2, Django REST Framework, Vue 2, Vuex, Axios, jQuery, existing RenderForm/JsonschemaForm, Jest-style Node tests, pytest

**Spec:** `docs/specs/2026-06-26-sops-open-plugin-full-capability-design.md` 第 6.2-6.6、7、8 节

**Provider Dependency:** bk-sops `docs/plans/2026-07-23-plugin-gateway-native-form-passthrough.md` Tasks 1-4

## Global Constraints

1. 本计划继续使用当前分支 `fix/open-plugin-unified-render-form`，在现有未合入 PR 上修正实现，不 rebase `develop`。
2. 第一阶段只有 Uniform API V4 开放插件调用 `/api/plugin/detail/`。BKFlow 内置、BKFlow 第三方、Uniform API V2/V3 的页面调用必须保持原样。
3. 已保存 V4 节点严格使用 pipeline tree 中的 `source_key/plugin_id/plugin_version`；版本不存在或下架时展示错误，不得回退到 default/latest。
4. 新选择且尚未保存的节点才可以把目录 `default_version` 作为第一次详情请求的显式版本。
5. operator 只能取 `request.user.username`，不接受前端传入。
6. `form_context` 不进入跨用户共享缓存。本轮不新增完整 detail 响应缓存，避免 scope/operator/Project 混用。
7. 原生 `forms.input` 存在但加载、执行或注册失败时明确报错；只有 `forms.input` 不存在时使用 `api_plugin_json` 兜底。
8. 标准运维表单静态资源、`/pipeline/` 辅助接口和 `plugin_service/data_api` 由浏览器直连提供方，不新增 BKFlow 代理。
9. 不新建一套表单控件。最终仍由现有 `RenderForm` 或 `JsonschemaForm` 渲染。
10. 不迁移、不批量刷新旧 pipeline tree。打开后保存也不得改变旧节点的 wrapper、版本或执行字段。
11. 不修改 `bkflow/apigw/`；`/api/plugin/detail/` 是页面内部接口，不需要运行 `scripts/apigw_docs.sh`。
12. 所有提交使用 `<type>(<scope>): <subject> --story=133649781`。
13. Stage 验收使用空间 `245`、`scope_type=biz`、`scope_value=100605`、operator `dannydeng`。SAP 存量插件只做配置、解析、回显，禁止执行。

---

## Unified Contract

Request:

```json
{
  "space_id": "245",
  "template_id": "2329",
  "plugin_type": "uniform_api",
  "plugin_code": "builtin__job_fast_execute_script",
  "plugin_version": "v2.0",
  "source_key": "sops",
  "scope_type": "biz",
  "scope_value": "100605"
}
```

Success response:

```json
{
  "result": true,
  "message": "",
  "data": {
    "plugin_type": "uniform_api",
    "plugin_code": "builtin__job_fast_execute_script",
    "plugin_version": "v2.0",
    "source_key": "sops",
    "plugin_source": "builtin",
    "protocol": "uniform_api",
    "wrapper_version": "v4.0.0",
    "name": "快速执行脚本",
    "description": "",
    "inputs": [],
    "outputs": [],
    "credentials": [],
    "forms": {
      "input": {
        "type": "component_js",
        "key": "job_fast_execute_script",
        "data": "https://bksops.example.com/static/components/atoms/job/fast_execute_script/v2_0.js",
        "is_embedded": false,
        "base": null
      },
      "output": null
    },
    "form_context": {},
    "execution_kind": "uniform_api",
    "url": "https://bk-sops.example.com/plugin-gateway/runs/",
    "methods": ["POST"],
    "response_data_path": null,
    "polling": {},
    "callback": {},
    "credential_key": null
  }
}
```

`data` 内不再按 plugin type 增加一层。三个 adapter 必须返回完全相同的 key 集合，空值固定为 `None/""/[]/{}`。

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `bkflow/plugin/serializers/plugin_detail.py` | Create | 统一详情 POST 请求校验 |
| `bkflow/plugin/services/plugin_detail.py` | Create | 固定响应字段与三类来源 adapter |
| `bkflow/plugin/views/plugin.py` | Modify | 新增 `PluginDetailView`，operator 取认证用户 |
| `bkflow/plugin/urls.py` | Modify | 在动态 router 前注册 `/detail/` |
| `bkflow/plugin/permissions.py` | Modify | POST body 中的 `space_id` 兼容现有页面权限 |
| `bkflow/pipeline_plugins/query/uniform_api/utils.py` | Modify | 校验 V4 `forms/form_context` 响应类型 |
| `tests/interface/plugin/services/test_plugin_detail.py` | Create | 三类 adapter、固定空值、精确版本测试 |
| `tests/interface/plugin/test_plugin_detail_view.py` | Create | URL、权限、operator、错误响应测试 |
| `frontend/src/utils/pluginFormLoader.js` | Create | 原生表单加载、注册校验与通用兜底 |
| `frontend/src/utils/uniformApi.js` | Modify | V4 识别、保存版本解析、统一请求构造 |
| `frontend/src/config/setting.js` | Modify | 合并纯数据 context、本地补函数、限定凭证 AJAX |
| `frontend/src/store/modules/atomForm.js` | Modify | 新增 V4 统一详情与表单加载 action；旧 action 不改语义 |
| `frontend/tests/pluginFormLoader.test.js` | Create | 四种表单类型、错误与 context 单元测试 |
| `frontend/tests/uniformApi.test.mjs` | Modify | V4 识别与精确版本测试 |
| `frontend/package.json` | Modify | 新增可直接运行的表单专项测试脚本 |
| `frontend/src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue` | Modify | 流程编辑 V4 分支 |
| `frontend/src/views/template/TemplateEdit/NodeConfig/InputParams.vue` | Modify | 只消费 loader 返回的 Array/Object，不新增 renderer |
| `frontend/src/views/task/TaskExecute/ExecuteInfo.vue` | Modify | 任务详情 V4 分支 |
| `frontend/src/views/task/TaskExecute/SideDrawerExecuteInfo.vue` | Modify | 侧边任务详情 V4 分支 |
| `frontend/src/views/task/TaskExecute/RetryNode.vue` | Modify | 节点重试 V4 分支 |
| `frontend/src/views/task/TaskParamEdit.vue` | Modify | 任务参数修改 V4 分支 |
| `frontend/src/views/template/TemplateMock/MockSetting/index.vue` | Modify | Mock 配置 V4 分支 |
| `frontend/src/views/template/TemplateMock/MockExecute/components/TaskParamEdit.vue` | Modify | Mock 执行参数 V4 分支 |
| `frontend/src/views/template/TemplateEdit/BatchUpdateDialog.vue` | Modify | 批量更新 V4 分支 |
| `frontend/src/views/template/TemplateEdit/TemplateSetting/TabGlobalVariables/VariableEdit.vue` | Modify | V4 来源变量表单项提取 |
| `tests/plugins/uniform_api/test_api_plugin_vue.py` | Modify | 全场景静态接入与双轨守卫 |
| `docs/guide/sops_open_plugin_frontend_contract.md` | Modify | 内部详情、表单类型、存量双轨说明 |

Files deliberately preserved:

- `bkflow/plugin/views/plugin.py::UniformPluginViewSet`
- `bkflow/plugin/handlers.py`
- `frontend/src/store/modules/atomForm.js::loadAtomConfig`
- `frontend/src/store/modules/atomForm.js::loadPluginServiceDetail`
- `frontend/src/store/modules/template.js::loadUniformApiMeta`
- Uniform API V2/V3 components and existing pipeline tree parser

---

### Task 1: 建立固定详情契约与本地插件 adapters

**Files:**
- Create: `bkflow/plugin/serializers/plugin_detail.py`
- Create: `bkflow/plugin/services/plugin_detail.py`
- Create: `tests/interface/plugin/services/test_plugin_detail.py`

- [ ] **Step 1: 写固定字段与请求校验失败测试**

`test_plugin_detail.py` 先定义期望 key：

```python
EXPECTED_DETAIL_KEYS = {
    "plugin_type",
    "plugin_code",
    "plugin_version",
    "source_key",
    "plugin_source",
    "protocol",
    "wrapper_version",
    "name",
    "description",
    "inputs",
    "outputs",
    "credentials",
    "forms",
    "form_context",
    "execution_kind",
    "url",
    "methods",
    "response_data_path",
    "polling",
    "callback",
    "credential_key",
}


def assert_contract(detail):
    assert set(detail) == EXPECTED_DETAIL_KEYS
    assert set(detail["forms"]) == {"input", "output"}
```

请求 serializer 覆盖：

```python
def test_request_rejects_unknown_plugin_type():
    serializer = PluginDetailRequestSerializer(
        data={
            "space_id": "245",
            "template_id": "2329",
            "plugin_type": "unknown",
            "plugin_code": "x",
            "plugin_version": "1.0",
        }
    )
    assert serializer.is_valid() is False


def test_uniform_api_requires_source_key():
    serializer = PluginDetailRequestSerializer(data=uniform_request(source_key=""))
    assert serializer.is_valid() is False
```

- [ ] **Step 2: 写 component 精确版本失败测试**

```python
@patch("bkflow.plugin.services.plugin_detail.ComponentLibrary.get_component_class")
def test_component_adapter_returns_native_component_js(component_class, component_model):
    component_class.return_value = FakeComponent
    detail = PluginDetailService(
        space_id="245",
        template_id="2329",
        operator="dannydeng",
        scope_type="biz",
        scope_value="100605",
    ).get_detail(
        plugin_type="component",
        plugin_code="job_fast_execute_script",
        plugin_version="v2.0",
    )
    assert_contract(detail)
    assert detail["source_key"] == "bkflow"
    assert detail["protocol"] == "native"
    assert detail["forms"]["input"]["type"] == "component_js"
    assert detail["forms"]["input"]["key"] == "job_fast_execute_script"
    component_class.assert_called_once_with("job_fast_execute_script", "v2.0")
```

另加不存在版本测试：数据库只有 `v2.0`，请求 `v2.1` 必须失败，`ComponentLibrary` 不得被调用。

- [ ] **Step 3: 写 remote plugin 精确版本和授权失败测试**

```python
@patch("bkflow.plugin.services.plugin_detail.PluginServiceApiClient")
def test_remote_adapter_preserves_renderform(client_cls, authorized_remote_plugin):
    client_cls.return_value.get_meta.return_value = {
        "result": True,
        "data": {"versions": ["1.1.0", "1.0.0"]},
    }
    client_cls.return_value.get_detail.return_value = {
        "result": True,
        "data": {
            "version": "1.0.0",
            "inputs": {"type": "object", "properties": {}},
            "outputs": {"type": "object", "properties": {}},
            "credentials": [],
            "forms": {
                "renderform": "window.$.atoms.demo = [{tag_code: 'x', type: 'input'}]",
            },
        },
    }

    detail = service().get_detail(
        plugin_type="remote_plugin",
        plugin_code="demo",
        plugin_version="1.0.0",
    )

    assert_contract(detail)
    assert detail["forms"]["input"]["type"] == "renderform"
    assert detail["forms"]["input"]["data"].startswith("window.$.atoms.demo")
    client_cls.return_value.get_detail.assert_called_once_with("1.0.0")
```

覆盖：

- 插件未授权给空间时 `PermissionDenied`。
- 请求版本不在 meta versions 中时失败且不请求 detail。
- 无 `forms.renderform` 时 `forms.input.type == "jsonschema"`，`data` 保留原始 inputs schema。

- [ ] **Step 4: 运行失败测试**

Run:

```bash
pytest tests/interface/plugin/services/test_plugin_detail.py -v
```

Expected: FAIL，新 serializer/service 不存在。

- [ ] **Step 5: 实现请求 serializer**

`plugin_detail.py`：

```python
from rest_framework import serializers


class PluginDetailRequestSerializer(serializers.Serializer):
    space_id = serializers.CharField()
    template_id = serializers.CharField()
    plugin_type = serializers.ChoiceField(
        choices=("component", "remote_plugin", "uniform_api")
    )
    plugin_code = serializers.CharField()
    plugin_version = serializers.CharField()
    source_key = serializers.CharField(required=False, allow_blank=True, default="")
    scope_type = serializers.CharField(required=False, allow_blank=True, default="")
    scope_value = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["plugin_type"] == "uniform_api" and not attrs["source_key"]:
            raise serializers.ValidationError(
                {"source_key": "uniform_api plugin requires source_key"}
            )
        return attrs
```

不要增加 operator 字段。

- [ ] **Step 6: 实现固定空值和 dispatch**

`services/plugin_detail.py`：

```python
DETAIL_DEFAULTS = {
    "plugin_type": "",
    "plugin_code": "",
    "plugin_version": "",
    "source_key": "",
    "plugin_source": None,
    "protocol": "",
    "wrapper_version": None,
    "name": "",
    "description": "",
    "inputs": [],
    "outputs": [],
    "credentials": [],
    "forms": {"input": None, "output": None},
    "form_context": {},
    "execution_kind": "",
    "url": None,
    "methods": [],
    "response_data_path": None,
    "polling": {},
    "callback": {},
    "credential_key": None,
}


def build_detail(**values):
    detail = deepcopy(DETAIL_DEFAULTS)
    detail.update(values)
    detail["forms"] = {
        "input": (detail.get("forms") or {}).get("input"),
        "output": (detail.get("forms") or {}).get("output"),
    }
    return detail


class PluginDetailService:
    ADAPTERS = {
        "component": "_get_component_detail",
        "remote_plugin": "_get_remote_plugin_detail",
        "uniform_api": "_get_uniform_api_detail",
    }

    def __init__(
        self,
        space_id,
        template_id,
        operator,
        scope_type="",
        scope_value="",
    ):
        self.space_id = str(space_id)
        self.template_id = str(template_id)
        self.operator = operator
        self.scope_type = scope_type
        self.scope_value = scope_value

    def get_detail(
        self,
        plugin_type,
        plugin_code,
        plugin_version,
        source_key="",
    ):
        method = getattr(self, self.ADAPTERS[plugin_type])
        return method(plugin_code, plugin_version, source_key)
```

用独立 helper 处理 lazy translation、组件 callable 属性、IO normalize 和 forms descriptor；不能在 adapter 之间返回不同 key。

本地 adapters 的 `form_context` 使用同一固定结构：

```python
{
    "project": None,
    "biz_cc_id": int(self.scope_value)
    if self.scope_type in ("biz", "cmdb_biz") and self.scope_value
    else None,
    "site_url": settings.SITE_URL,
    "component": None,
    "variable": None,
    "template": None,
    "instance": None,
    "bk_plugin_api_host": {},
}
```

第一阶段页面不会调用这两个 adapters，但接口契约不能因此返回缺字段的临时结构。

- [ ] **Step 7: 实现 component 和 remote adapters**

Component 必须先按 `code/version/status=True` 查 `ComponentModel`，再用相同版本取组件类：

```python
component_model = ComponentModel.objects.filter(
    code=plugin_code,
    version=plugin_version,
    status=True,
).first()
if component_model is None:
    raise NotFound("插件版本不存在或已下架")
component_cls = ComponentLibrary.get_component_class(plugin_code, plugin_version)
```

Remote 必须使用 `BKPluginAuthorization.objects.get_codes_by_space_id(str(self.space_id))` 校验空间授权，调用 `get_meta()` 验证版本，再调用 `get_detail(plugin_version)`。`renderform` 原值放入 descriptor；没有 renderform 时把原始 inputs schema 放入 `jsonschema` descriptor。统一 `inputs/outputs` 字段仍用 `PluginSchemaService._normalize_io_fields` 的相同规则转换为列表。

- [ ] **Step 8: 运行测试至通过**

Run:

```bash
pytest tests/interface/plugin/services/test_plugin_detail.py -v
```

Expected: PASS；component/remote key 集合相同，精确版本和授权均生效。

- [ ] **Step 9: Commit**

```bash
git add bkflow/plugin/serializers/plugin_detail.py \
  bkflow/plugin/services/plugin_detail.py \
  tests/interface/plugin/services/test_plugin_detail.py
git commit -m "feat(open-plugin): 建立统一插件详情契约 --story=133649781"
```

---

### Task 2: 接入 V4 uniform adapter 与内部 POST 路由

**Files:**
- Modify: `bkflow/plugin/services/plugin_detail.py`
- Modify: `bkflow/plugin/views/plugin.py`
- Modify: `bkflow/plugin/urls.py`
- Modify: `bkflow/plugin/permissions.py`
- Modify: `bkflow/pipeline_plugins/query/uniform_api/utils.py`
- Modify: `tests/interface/plugin/services/test_plugin_detail.py`
- Create: `tests/interface/plugin/test_plugin_detail_view.py`
- Modify: `tests/plugins/uniform_api/test_uniform_api_client.py`

- [ ] **Step 1: 写 V4 adapter 失败测试**

用已经同步的 `OpenPluginCatalogIndex`、grant 和 availability 构造可用插件：

```python
@patch("bkflow.plugin.services.plugin_detail._get_api_credential")
@patch("bkflow.plugin.services.plugin_detail.UniformAPIClient")
def test_uniform_adapter_forwards_scope_and_operator(
    client_cls,
    get_credential,
    available_open_plugin,
):
    get_credential.return_value = {
        "bk_app_code": "bkflow",
        "bk_app_secret": "secret",
    }
    client_cls.return_value.request.return_value = uniform_result(
        data={
            "id": "builtin__job_fast_execute_script",
            "plugin_code": "job_fast_execute_script",
            "plugin_version": "v2.0",
            "plugin_source": "builtin",
            "wrapper_version": "v4.0.0",
            "name": "快速执行脚本",
            "inputs": [],
            "outputs": [],
            "forms": {
                "input": {
                    "type": "component_js",
                    "key": "job_fast_execute_script",
                    "data": "https://bksops.example.com/static/job.js",
                    "is_embedded": False,
                    "base": None,
                },
                "output": None,
            },
            "form_context": {"biz_cc_id": 100605},
            "url": "https://bksops.example.com/runs/",
            "methods": ["POST"],
            "polling": {},
        }
    )

    detail = service().get_detail(
        plugin_type="uniform_api",
        plugin_code="builtin__job_fast_execute_script",
        plugin_version="v2.0",
        source_key="sops",
    )

    assert_contract(detail)
    assert detail["form_context"]["biz_cc_id"] == 100605
    request_kwargs = client_cls.return_value.request.call_args.kwargs
    assert request_kwargs["username"] == "dannydeng"
    assert request_kwargs["data"] == {
        "source_key": "sops",
        "scope_type": "biz",
        "scope_value": "100605",
    }
```

覆盖：

- source 未 grant。
- plugin availability 关闭。
- catalog status unavailable。
- 请求版本不在 `versions`。
- 已保存版本失效时不使用 `latest_version`。
- provider 返回 `result=false` 或违反 detail schema 时明确失败。
- `form_context` 不写缓存。

- [ ] **Step 2: 写静态路由和 operator 失败测试**

`test_plugin_detail_view.py`：

```python
@patch("bkflow.plugin.views.plugin.PluginDetailService")
def test_detail_route_uses_authenticated_operator(service_cls, api_client, user):
    service_cls.return_value.get_detail.return_value = build_detail(
        plugin_type="uniform_api"
    )
    api_client.force_authenticate(user)
    response = api_client.post("/api/plugin/detail/", uniform_request(), format="json")
    assert response.status_code == 200
    assert response.data["result"] is True
    assert set(response.data["data"]) == EXPECTED_DETAIL_KEYS
    assert service_cls.call_args.kwargs["operator"] == user.username
```

路由解析测试：

```python
match = resolve("/api/plugin/detail/")
assert match.func.view_class is PluginDetailView
```

这条测试保证 `detail` 不会落入 `ComponentModelSetViewSet` 的动态 `/<code>/`。

另覆盖：

- body 中伪造 `operator` 被 serializer 拒绝或忽略，service 始终收到登录用户。
- space admin、token 权限能从 POST body 读取 `space_id`。
- 无权限 403。
- serializer 错误 400。
- adapter 的 NotFound/PermissionDenied/APIResponseError 保留明确错误。

- [ ] **Step 3: 运行失败测试**

Run:

```bash
pytest \
  tests/interface/plugin/services/test_plugin_detail.py \
  tests/interface/plugin/test_plugin_detail_view.py \
  tests/plugins/uniform_api/test_uniform_api_client.py -v
```

Expected: FAIL，uniform adapter、view、静态路由和 schema 扩展尚不存在。

- [ ] **Step 4: 实现 catalog 驱动的 V4 adapter**

使用 `PluginSchemaService` 现有准入与精确版本入口定位 `api_item`：

```python
schema_service = PluginSchemaService(
    space_id=self.space_id,
    username=self.operator,
    scope_type=self.scope_type,
    scope_id=self.scope_value,
)
api_item = schema_service._get_single_by_type(
    plugin_code,
    "uniform_api",
    version=plugin_version,
)
if api_item.get("source_key") != source_key:
    raise PermissionDenied("插件来源与请求不一致")
meta_url = schema_service._build_uniform_api_meta_url(api_item, plugin_version)
```

用现有 `_get_api_credential(space_id, template_id)` 取当前模板凭证，再发请求：

```python
credential = _get_api_credential(
    space_id=self.space_id,
    template_id=self.template_id,
)
client = UniformAPIClient()
headers = client.gen_default_apigw_header(
    app_code=credential["bk_app_code"],
    app_secret=credential["bk_app_secret"],
    username=self.operator,
)
result = client.request(
    url=meta_url,
    method="GET",
    data={
        "source_key": source_key,
        "scope_type": self.scope_type,
        "scope_value": self.scope_value,
    },
    headers=headers,
    username=self.operator,
)
```

检查 `result.result`、`json_resp.result` 并调用 `validate_response_data`。把 provider 的 `forms/form_context/url/methods/response_data_path/polling/callback/credential_key` 原样填入统一字段，不使用旧 `form_schema` 转换。统一响应的 `plugin_code` 保持请求中的目录插件 ID（例如 `builtin__job_fast_execute_script`），不得被 provider 内部组件 code 覆盖；执行所需的 provider 元数据继续保留在节点原有 `api_meta` 和隐藏字段中。

- [ ] **Step 5: 扩展 Uniform API meta schema**

在 `UNIFORM_API_META_RESPONSE_DATA_SCHEMA.properties` 增加：

```python
"forms": {
    "type": "object",
    "required": ["input", "output"],
    "properties": {
        "input": {"type": ["object", "null"]},
        "output": {"type": ["object", "null"]},
    },
},
"form_context": {"type": "object"},
```

不要把 `forms` 设为 required，以兼容 Uniform API V2/V3 和尚未升级的 V4 提供方；新 V4 loader 会在缺失时走 `api_plugin_json`。

- [ ] **Step 6: 让现有空间权限兼容 POST body**

在 `plugin/permissions.py` 增加：

```python
def get_request_space_id(request):
    return request.query_params.get("space_id") or request.data.get("space_id")
```

`PluginTokenPermissions` 和 `PluginSpaceSuperuserPermission` 都使用该 helper。原 GET query 行为不变，补充现有权限类回归测试。

- [ ] **Step 7: 实现 view 与静态 URL**

`PluginDetailView`：

```python
class PluginDetailView(APIView):
    permission_classes = [
        AdminPermission | PluginSpaceSuperuserPermission | PluginTokenPermissions
    ]

    def post(self, request):
        serializer = PluginDetailRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        service = PluginDetailService(
            space_id=data["space_id"],
            template_id=data["template_id"],
            operator=request.user.username,
            scope_type=data["scope_type"],
            scope_value=data["scope_value"],
        )
        detail = service.get_detail(
            plugin_type=data["plugin_type"],
            plugin_code=data["plugin_code"],
            plugin_version=data["plugin_version"],
            source_key=data["source_key"],
        )
        return Response({"result": True, "message": "", "data": detail})
```

`plugin/urls.py` 必须按以下顺序：

```python
urlpatterns = [
    url(r"^detail/$", PluginDetailView.as_view(), name="plugin_detail"),
    url(r"^", include(router.urls)),
]
```

不要删除旧 `uniform_plugin_query/get_plugin_detail/`。

- [ ] **Step 8: 运行后端测试至通过**

Run:

```bash
pytest \
  tests/interface/plugin/services/test_plugin_detail.py \
  tests/interface/plugin/test_plugin_detail_view.py \
  tests/interface/plugin/services/test_plugin_schema_service.py \
  tests/plugins/uniform_api/test_uniform_api_client.py -v
```

Expected: PASS；POST 返回统一 envelope，operator、grant、availability、source 和版本均受校验。

- [ ] **Step 9: Commit**

```bash
git add bkflow/plugin/services/plugin_detail.py \
  bkflow/plugin/views/plugin.py \
  bkflow/plugin/urls.py \
  bkflow/plugin/permissions.py \
  bkflow/pipeline_plugins/query/uniform_api/utils.py \
  tests/interface/plugin/services/test_plugin_detail.py \
  tests/interface/plugin/test_plugin_detail_view.py \
  tests/plugins/uniform_api/test_uniform_api_client.py
git commit -m "feat(open-plugin): 新增 V4 统一插件详情接口 --story=133649781"
```

---

### Task 3: 建立 V4 识别、表单 loader 与 context 装配

**Files:**
- Create: `frontend/src/utils/pluginFormLoader.js`
- Modify: `frontend/src/utils/uniformApi.js`
- Modify: `frontend/src/config/setting.js`
- Modify: `frontend/src/store/modules/atomForm.js`
- Create: `frontend/tests/pluginFormLoader.test.js`
- Modify: `frontend/tests/uniformApi.test.mjs`
- Modify: `frontend/package.json`

- [ ] **Step 1: 写 V4 识别和精确版本失败测试**

在 `uniformApi.test.mjs` 覆盖：

```javascript
assert.equal(isV4OpenPlugin({
  code: 'uniform_api',
  version: 'v4.0.0',
  api_meta: {
    wrapper_version: 'v4.0.0',
    source_key: 'sops',
    id: 'builtin__job_fast_execute_script',
  },
  data: {
    uniform_api_plugin_version: { value: 'v2.0' },
  },
}), true);

assert.equal(isV4OpenPlugin({
  code: 'uniform_api',
  version: 'v3.0.0',
  api_meta: { source_key: 'sops' },
}), false);

assert.equal(resolveV4OpenPluginVersion(savedComponent), 'v2.0');
assert.throws(
  () => buildV4PluginDetailRequest({ component: missingSavedVersion }),
  /plugin version is required/,
);
```

明确断言不能把 `component.version == v4.0.0` 当作子插件版本。

- [ ] **Step 2: 写四种表单和错误失败测试**

`pluginFormLoader.test.js` 覆盖：

```javascript
const component = await loadPluginForms(componentDetail, { readOnly: false });
assert.deepStrictEqual(component.input, translatedAtoms.job_fast_execute_script);
assert.deepStrictEqual(scriptCalls, [
  'https://bksops.example.com/static/base.js',
  'https://bksops.example.com/static/job.js',
]);

const renderform = await loadPluginForms(renderformDetail);
assert.deepStrictEqual(renderform.input, globalAtoms.demo);

const jsonschema = await loadPluginForms(jsonschemaDetail);
assert.deepStrictEqual(jsonschema.input, jsonschemaDetail.forms.input.data);

const fallback = await loadPluginForms(noNativeFormDetail);
assert.equal(Array.isArray(fallback.input), true);
assert.equal(fallback.inputType, 'api_plugin_json');
```

错误测试：

```javascript
await assert.rejects(
  () => loadPluginForms(detailWhoseScriptDoesNotRegister),
  error => error.code === 'FORM_REGISTRATION_FAILED',
);

await assert.rejects(
  () => loadPluginForms(detailWhoseNativeScriptThrows),
  error => error.code === 'FORM_LOAD_FAILED',
);
```

两条错误都不得调用 `renderFormSchema`。

再覆盖对象 scheme 的公共判定：

```javascript
assert.equal(hasPluginFormFields([{ tag_code: 'x' }]), true);
assert.equal(hasPluginFormFields({ properties: { x: { type: 'string' } } }), true);
assert.equal(hasPluginFormFields({ properties: {} }), false);
```

- [ ] **Step 3: 写 context 与凭证 AJAX 失败测试**

覆盖：

- `project/biz_cc_id/site_url/component/variable/template/instance/bk_plugin_api_host` 被合并。
- `getBkBizId()` 返回 `biz_cc_id`。
- `getProjectId()` 返回 `project.id`。
- `getInput()` 对 `0/false/""` 使用 `hasOwnProperty`，不误判为空。
- 只有 `form_context.site_url` 和 `bk_plugin_api_host` 声明的 Origin 获得 `xhrFields.withCredentials=true`。
- 其他跨域 URL 不修改。

- [ ] **Step 4: 运行失败测试**

先在 `package.json` 临时通过命令行直接执行现有与新测试：

```bash
node frontend/tests/renderFormSchema.test.js
node frontend/tests/pluginFormLoader.test.js
node frontend/tests/uniformApi.test.mjs
```

Expected: 新测试 FAIL，loader/context/V4 helper 不存在；旧 renderFormSchema 测试仍 PASS。

- [ ] **Step 5: 实现 V4 识别和请求构造**

`uniformApi.js` 增加：

```javascript
export const isV4OpenPlugin = (component = {}) => {
  const apiMeta = component.api_meta || {};
  const data = component.data || {};
  const sourceKey = getComponentDataValue(data, 'uniform_api_plugin_source_key')
    || apiMeta.source_key;
  const pluginId = getComponentDataValue(data, 'uniform_api_plugin_id')
    || apiMeta.id
    || apiMeta.plugin_id;
  const wrapperVersion = apiMeta.wrapper_version || component.version;
  return component.code === 'uniform_api'
    && wrapperVersion === 'v4.0.0'
    && Boolean(sourceKey)
    && Boolean(pluginId);
};

export const resolveV4OpenPluginVersion = (component = {}) => (
  getComponentDataValue(component.data || {}, 'uniform_api_plugin_version')
  || (component.api_meta || {}).plugin_version
  || ''
);
```

`buildV4PluginDetailRequest` 接收 `component/spaceId/templateId/scopeType/scopeValue/selectedVersion`，保存节点只读隐藏字段；`selectedVersion` 只用于未保存新节点。版本为空时抛错，不读 `default/latest`。

- [ ] **Step 6: 实现统一 loader**

核心返回值固定为：

```javascript
{
  detail,
  input,
  output,
  inputType,
  outputType,
  isRenderOutputForm,
}
```

关键实现：

```javascript
export class PluginFormLoadError extends Error {
  constructor(code, message, cause = null) {
    super(message);
    this.code = code;
    this.cause = cause;
  }
}

const getGlobalAtoms = () => (
  (window.$ && window.$.atoms)
  || (window.jQuery && window.jQuery.atoms)
  || $.atoms
);

const loadJavaScriptForm = async (descriptor, transformComponent) => {
  if (descriptor.base) {
    await loadScript(descriptor.base);
  }
  if (descriptor.is_embedded) {
    (0, eval)(descriptor.data); // eslint-disable-line no-eval
  } else {
    await loadScript(descriptor.data);
  }
  const atoms = getGlobalAtoms();
  if (!Object.prototype.hasOwnProperty.call(atoms, descriptor.key)) {
    throw new PluginFormLoadError(
      'FORM_REGISTRATION_FAILED',
      `form ${descriptor.key} was not registered`,
    );
  }
  return transformComponent
    ? transAtom(atoms, descriptor.key)
    : atoms[descriptor.key];
};
```

dispatch：

- `component_js` 调 `loadJavaScriptForm(descriptor, true)`。
- `renderform` 为字符串时执行并读取 `$.atoms[key]`；为 Array/Object 时直接作为 RenderForm scheme，兼容原始提供方数据。
- `jsonschema` 返回原始 object。
- `api_plugin_json` 调 `renderFormSchema(detail, { readOnly })`。
- `forms.input == null` 才合成 `api_plugin_json`。
- 已声明 descriptor 但 type/data/key 无效时抛 `FORM_PROTOCOL_INVALID`。

输出表单使用同一 dispatch，不复制加载逻辑。

同时导出：

```javascript
export const hasPluginFormFields = scheme => (
  Array.isArray(scheme)
    ? scheme.length > 0
    : Boolean(
      scheme
      && scheme.properties
      && Object.keys(scheme.properties).length > 0
    )
);
```

所有页面使用这个 helper 判断空表单，不能继续对可能为 Object 的 scheme 直接读取 `.length`。

- [ ] **Step 7: 装配纯数据 context 和限定凭证 AJAX**

在 `setting.js` 保留 `setConfigContext`，新增：

```javascript
const pluginFormCredentialOrigins = new Set();

export const applyPluginFormContext = (formContext = {}, runtime = {}) => {
  setConfigContext(formContext.site_url || window.SITE_URL, formContext.project);
  const allowedKeys = [
    'biz_cc_id',
    'component',
    'variable',
    'template',
    'instance',
    'bk_plugin_api_host',
  ];
  allowedKeys.forEach((key) => {
    if (Object.prototype.hasOwnProperty.call(formContext, key)) {
      $.context[key] = formContext[key];
    }
  });
  $.context.input_form.inputs = runtime.inputs;
  $.context.output_form.outputs = runtime.outputs;
  $.context.output_form.state = runtime.state;
  $.context.getBkBizId = () => $.context.biz_cc_id;
  $.context.getProjectId = () => $.context.project && $.context.project.id;
  registerPluginFormCredentialOrigins(formContext);
};
```

修正现有 `getInput` 为 `hasOwnProperty` 判断。`setJqueryAjaxConfig()` 中只注册一次 prefilter：

```javascript
$.ajaxPrefilter((options) => {
  const origin = new URL(options.url, window.location.href).origin;
  if (pluginFormCredentialOrigins.has(origin)) {
    options.xhrFields = {
      ...(options.xhrFields || {}),
      withCredentials: true,
    };
  }
});
```

不把所有跨域请求统一设为凭证请求。

- [ ] **Step 8: 新增 Vuex action**

`atomForm.js` 新增但不修改旧 actions：

```javascript
async loadV4OpenPluginForm({}, payload) {
  const response = await axios.post('/api/plugin/detail/', payload.request);
  if (!response.data.result) {
    throw new Error(response.data.message || 'load plugin detail failed');
  }
  const detail = response.data.data;
  applyPluginFormContext(detail.form_context, payload.runtimeContext);
  return loadPluginForms(detail, { readOnly: payload.readOnly });
},
```

- [ ] **Step 9: 增加专项测试脚本并运行**

`package.json`：

```json
"test:plugin-form": "node tests/renderFormSchema.test.js && node tests/pluginFormLoader.test.js && node tests/uniformApi.test.mjs"
```

Run:

```bash
cd frontend
npm run test:plugin-form
```

Expected:

```text
renderFormSchema tests passed
pluginFormLoader tests passed
uniformApi tests passed
```

- [ ] **Step 10: Commit**

```bash
git add frontend/src/utils/pluginFormLoader.js \
  frontend/src/utils/uniformApi.js \
  frontend/src/config/setting.js \
  frontend/src/store/modules/atomForm.js \
  frontend/tests/pluginFormLoader.test.js \
  frontend/tests/uniformApi.test.mjs \
  frontend/package.json
git commit -m "feat(open-plugin): 支持 V4 原生插件表单加载 --story=133649781"
```

---

### Task 4: 流程编辑只让 V4 走统一 loader

**Files:**
- Modify: `frontend/src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue`
- Modify: `frontend/src/views/template/TemplateEdit/NodeConfig/InputParams.vue`
- Modify: `tests/plugins/uniform_api/test_api_plugin_vue.py`

- [ ] **Step 1: 写流程编辑双轨失败测试**

替换当前“所有 Uniform API 都走 `renderFormSchema`”断言：

```python
def test_template_editor_routes_only_v4_open_plugin_to_unified_loader():
    source = node_config_source()
    assert "isV4OpenPlugin(this.nodeConfig.component)" in source
    assert "'loadV4OpenPluginForm'" in source
    assert "buildV4PluginDetailRequest" in source
    assert "loadUniformApiMeta" in source
    assert "loadAtomConfig" in source
    assert "loadPluginServiceDetail" in source
```

用 utility 单测证明 V2/V3 返回 false；静态测试只保证组件保留三条旧 action，不把源码字符串当完整行为证明。

- [ ] **Step 2: 运行失败测试**

Run:

```bash
pytest tests/plugins/uniform_api/test_api_plugin_vue.py -v
```

Expected: FAIL，NodeConfig 尚未接入新 action。

- [ ] **Step 3: 在现有 API plugin 分支最前增加 V4 分流**

`getAtomConfig` 中 API plugin 逻辑顺序固定为：

```javascript
if (this.isApiPlugin && isV4OpenPlugin(this.nodeConfig.component)) {
  const result = await this.loadV4OpenPluginForm({
    request: buildV4PluginDetailRequest({
      component: this.nodeConfig.component,
      selectedVersion: this.basicInfo.version,
      spaceId: this.spaceId,
      templateId: this.$route.params.templateId,
      scopeType: this.scopeInfo.scope_type,
      scopeValue: this.scopeInfo.scope_value,
    }),
    readOnly: this.isViewMode,
    runtimeContext: {
      inputs: this.inputsParamValue,
      outputs: this.outputs,
    },
  });
  this.apiInputs = result.detail.inputs;
  this.uniformOutputs = result.detail.outputs;
  this.outputs = result.detail.outputs;
  this.updateBasicInfo({
    version: result.detail.plugin_version,
    uniform_api_plugin_version: result.detail.plugin_version,
    wrapperVersion: result.detail.wrapper_version,
    methodList: result.detail.methods,
    polling: result.detail.polling,
    callback: result.detail.callback,
    credentialKey: result.detail.credential_key,
  });
  return result.input;
}
```

后面的现有 `loadUniformApiMeta + renderFormSchema` 分支保留给 V2/V3。现有 `loadAtomConfig` 与 `loadPluginServiceDetail + eval` 分支保持。

- [ ] **Step 4: 复用现有 renderer**

`InputParams.vue` 继续通过 `Array.isArray(scheme)` 选择：

- Array → `RenderForm`
- Object → `JsonschemaInputParams`

仅补充 loader 返回空值和 form load error 的显示，不增加新的表单组件。不要把 `component_js/renderform` 类型传进 Tag 层。

- [ ] **Step 5: 运行前端和静态测试**

Run:

```bash
cd frontend
npm run test:plugin-form
npm run lint
cd ..
pytest tests/plugins/uniform_api/test_api_plugin_vue.py -v
```

Expected: PASS；V4 utility、NodeConfig 接线和 lint 均通过。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue \
  frontend/src/views/template/TemplateEdit/NodeConfig/InputParams.vue \
  tests/plugins/uniform_api/test_api_plugin_vue.py
git commit -m "fix(open-plugin): 流程编辑接入 V4 原生表单 --story=133649781"
```

---

### Task 5: 任务详情、侧栏、重试和参数修改接入 V4

**Files:**
- Modify: `frontend/src/views/task/TaskExecute/ExecuteInfo.vue`
- Modify: `frontend/src/views/task/TaskExecute/SideDrawerExecuteInfo.vue`
- Modify: `frontend/src/views/task/TaskExecute/RetryNode.vue`
- Modify: `frontend/src/views/task/TaskParamEdit.vue`
- Modify: `frontend/src/views/task/TaskExecute/ExecuteInfo/ExecuteInfoForm.vue`
- Modify: `frontend/src/views/task/TaskExecute/ExecuteInfoCompoment/ExecuteInfoForm.vue`
- Modify: `tests/plugins/uniform_api/test_api_plugin_vue.py`

- [ ] **Step 1: 写四个任务场景失败测试**

扩展静态测试：

```python
TASK_V4_SOURCES = [
    "frontend/src/views/task/TaskExecute/ExecuteInfo.vue",
    "frontend/src/views/task/TaskExecute/SideDrawerExecuteInfo.vue",
    "frontend/src/views/task/TaskExecute/RetryNode.vue",
    "frontend/src/views/task/TaskParamEdit.vue",
]


def test_task_scenes_route_v4_to_unified_loader_and_keep_legacy_actions():
    for path in TASK_V4_SOURCES:
        source = read(path)
        assert "isV4OpenPlugin" in source
        assert "loadV4OpenPluginForm" in source
        assert "loadAtomConfig" in source
```

详情与侧栏额外保留 `loadPluginServiceDetail`，保证 BKFlow 第三方旧节点没有被统一接口替换。

- [ ] **Step 2: 运行失败测试**

Run:

```bash
pytest tests/plugins/uniform_api/test_api_plugin_vue.py -v
```

Expected: FAIL，四个页面缺少 V4 分支。

- [ ] **Step 3: 详情和侧栏在旧 Uniform 分支前增加 V4 分流**

两个 `getNodeConfig` 使用同一个请求构造规则：

```javascript
if (this.pluginCode === 'uniform_api'
  && isV4OpenPlugin(this.nodeActivity.component)) {
  const result = await this.loadV4OpenPluginForm({
    request: buildV4PluginDetailRequest({
      component: this.nodeActivity.component,
      spaceId: this.spaceId,
      templateId: this.templateId,
      scopeType: this.scopeInfo.scope_type,
      scopeValue: this.scopeInfo.scope_value,
    }),
    readOnly: true,
    runtimeContext: {
      inputs: this.nodeDetail.inputs,
      outputs: this.nodeDetail.outputs,
      state: this.nodeDetail.state,
    },
  });
  this.renderConfig = result.input;
  this.outputRenderConfig = result.output || [];
  this.outputs = result.detail.outputs;
  this.isRenderOutputForm = result.isRenderOutputForm;
  return;
}
```

随后保留现有 V2/V3 `loadUniformApiMeta`，以及内置/第三方旧逻辑。

- [ ] **Step 4: 重试和 TaskParamEdit 使用同一 action**

从节点 activity/component 生成请求，传当前输入值到 `runtimeContext`。表单值仍从原 node data 读取；loader 只负责 scheme，不改保存格式。错误显示包含 `error.code` 和插件版本，不打印脚本内容。

`RetryNode.vue` 原先只支持 Array scheme，本任务必须改为复用现有两个 renderer：

```vue
<RenderForm
  v-if="Array.isArray(renderConfig)"
  ref="renderForm"
  v-model="renderData"
  :scheme="renderConfig"
  :form-option="renderOption" />
<JsonschemaInputParams
  v-else
  ref="renderForm"
  :form-data="renderData"
  :schema="renderConfig"
  :is-view-mode="false"
  @update="renderData = $event" />
```

空态使用 `hasPluginFormFields(renderConfig)`，不能读取 `renderConfig.length`。

`TaskParamEdit.vue` 可能同时展示来自不同插件的变量。把当前单一 `renderConfig` 聚合改为 `formSections`：

- RenderForm 字段仍合并为一个 Array section。
- JSON Schema 字段按 `properties/required` 合并为一个 Object section。
- template 使用 `v-for`，每个 section 分别交给现有 `RenderForm` 或 `JsonschemaInputParams`。
- 两个 section 都写回同一个 `renderData`，提交格式不变。
- V2/V3 和存量变量仍进入原 Array section。

- [ ] **Step 5: 两套详情表单组件只消费 Array/Object**

`ExecuteInfoForm.vue` 两个版本继续：

- Array → RenderForm
- Object → JsonschemaInputParams

删除当前无条件 `renderFormSchema(resp.data)`，但保留 V2/V3 原分支需要的转换。不要调用 `setFormsSchema` 去二次改写 loader 已返回的原生 scheme。

- [ ] **Step 6: 运行测试**

Run:

```bash
cd frontend
npm run test:plugin-form
npm run lint
cd ..
pytest tests/plugins/uniform_api/test_api_plugin_vue.py -v
```

Expected: PASS；任务详情、侧栏、重试、参数修改均有 V4 分支，旧 action 仍存在。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/task/TaskExecute/ExecuteInfo.vue \
  frontend/src/views/task/TaskExecute/SideDrawerExecuteInfo.vue \
  frontend/src/views/task/TaskExecute/RetryNode.vue \
  frontend/src/views/task/TaskParamEdit.vue \
  frontend/src/views/task/TaskExecute/ExecuteInfo/ExecuteInfoForm.vue \
  frontend/src/views/task/TaskExecute/ExecuteInfoCompoment/ExecuteInfoForm.vue \
  tests/plugins/uniform_api/test_api_plugin_vue.py
git commit -m "fix(open-plugin): 任务场景接入 V4 原生表单 --story=133649781"
```

---

### Task 6: Mock、批量更新和变量编辑接入 V4

**Files:**
- Modify: `frontend/src/utils/pluginFormLoader.js`
- Modify: `frontend/src/views/template/TemplateMock/MockSetting/index.vue`
- Modify: `frontend/src/views/template/TemplateMock/MockExecute/components/TaskParamEdit.vue`
- Modify: `frontend/src/views/template/TemplateEdit/BatchUpdateDialog.vue`
- Modify: `frontend/src/views/template/TemplateEdit/TemplateSetting/TabGlobalVariables/VariableEdit.vue`
- Modify: `frontend/tests/pluginFormLoader.test.js`
- Modify: `tests/plugins/uniform_api/test_api_plugin_vue.py`

- [ ] **Step 1: 写表单项提取失败测试**

变量编辑和 Mock 参数编辑只需要单个字段，loader 增加不改变 scheme 的 helper：

```javascript
assert.deepStrictEqual(
  selectPluginFormField(renderFormArray, 'job_content'),
  renderFormArray.find(item => item.tag_code === 'job_content'),
);
assert.deepStrictEqual(
  selectPluginFormField(jsonSchemaObject, 'job_content'),
  {
    type: 'object',
    properties: {
      job_content: jsonSchemaObject.properties.job_content,
    },
    required: ['job_content'],
  },
);
```

字段不存在时抛 `FORM_FIELD_NOT_FOUND`，不得生成普通 input。

同时断言 `hasPluginFormFields` 可用于批量更新页面的 Array/Object 空态，避免 `inputsConfig.length` 把合法 JSON Schema 判成无数据。

- [ ] **Step 2: 写全场景静态失败测试**

```python
V4_AUXILIARY_SOURCES = [
    "frontend/src/views/template/TemplateMock/MockSetting/index.vue",
    "frontend/src/views/template/TemplateMock/MockExecute/components/TaskParamEdit.vue",
    "frontend/src/views/template/TemplateEdit/BatchUpdateDialog.vue",
    "frontend/src/views/template/TemplateEdit/TemplateSetting/TabGlobalVariables/VariableEdit.vue",
]


def test_auxiliary_scenes_use_v4_loader_without_replacing_legacy_paths():
    for path in V4_AUXILIARY_SOURCES:
        source = read(path)
        assert "isV4OpenPlugin" in source
        assert "loadV4OpenPluginForm" in source
        assert "loadAtomConfig" in source
```

- [ ] **Step 3: 运行失败测试**

Run:

```bash
cd frontend
npm run test:plugin-form
cd ..
pytest tests/plugins/uniform_api/test_api_plugin_vue.py -v
```

Expected: FAIL，field helper 和四个页面接线未实现。

- [ ] **Step 4: 实现 Array/Object 字段提取**

`selectPluginFormField`：

```javascript
export const selectPluginFormField = (scheme, fieldKey) => {
  if (Array.isArray(scheme)) {
    const field = scheme.find(item => (
      item.tag_code === fieldKey || (item.attrs && item.attrs.name === fieldKey)
    ));
    if (!field) throw fieldNotFound(fieldKey);
    return field;
  }
  if (scheme && scheme.properties && scheme.properties[fieldKey]) {
    return {
      ...scheme,
      properties: { [fieldKey]: scheme.properties[fieldKey] },
      required: (scheme.required || []).filter(key => key === fieldKey),
    };
  }
  throw fieldNotFound(fieldKey);
};
```

- [ ] **Step 5: 四个场景都先判断 V4**

统一规则：

1. `isV4OpenPlugin(component)` 为 true → `loadV4OpenPluginForm`。
2. Mock/批量更新使用完整 `result.input/result.detail.outputs`。
3. 变量编辑和 Mock 单字段编辑调用 `selectPluginFormField`。
4. false → 完整保留当前 `loadUniformApiMeta/loadAtomConfig/loadPluginServiceDetail`。

批量更新不得按 plugin code 聚合不同版本的表单；缓存键至少包含 `source_key/plugin_id/plugin_version`。

`BatchUpdateDialog.vue` 的 `v-if="inputsConfig.length > 0"` 改为 `hasPluginFormFields(inputsConfig)`；继续复用 `InputParams.vue` 对 Array/Object 的既有分流。Mock 页面若直接渲染 scheme，也使用相同 helper 和现有两个 renderer。

- [ ] **Step 6: 运行专项、lint 与静态测试**

Run:

```bash
cd frontend
npm run test:plugin-form
npm run lint
cd ..
pytest tests/plugins/uniform_api/test_api_plugin_vue.py -v
```

Expected: PASS；所有辅助场景接入，单字段提取同时支持 Array/Object。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/utils/pluginFormLoader.js \
  frontend/src/views/template/TemplateMock/MockSetting/index.vue \
  frontend/src/views/template/TemplateMock/MockExecute/components/TaskParamEdit.vue \
  frontend/src/views/template/TemplateEdit/BatchUpdateDialog.vue \
  frontend/src/views/template/TemplateEdit/TemplateSetting/TabGlobalVariables/VariableEdit.vue \
  frontend/tests/pluginFormLoader.test.js \
  tests/plugins/uniform_api/test_api_plugin_vue.py
git commit -m "fix(open-plugin): 补齐 V4 表单全场景接入 --story=133649781"
```

---

### Task 7: 双轨回归、构建与 Stage 联调

**Files:**
- Modify: `tests/plugins/uniform_api/test_api_plugin_vue.py`
- Modify: `docs/guide/sops_open_plugin_frontend_contract.md`

- [ ] **Step 1: 增加存量节点双轨守卫**

utility 测试覆盖以下 fixture：

```javascript
assert.equal(isV4OpenPlugin(bkflowBuiltinComponent), false);
assert.equal(isV4OpenPlugin(bkflowRemotePluginComponent), false);
assert.equal(isV4OpenPlugin(uniformApiV2Component), false);
assert.equal(isV4OpenPlugin(uniformApiV3Component), false);
assert.equal(isV4OpenPlugin(uniformApiV4WithoutSourceKey), false);
assert.equal(isV4OpenPlugin(savedUniformApiV4OpenPlugin), true);
```

pipeline tree Python fixture 断言：

- 打开再保存 V2/V3 节点后 `component.code/version/data/api_meta` 不变。
- V4 节点的 `uniform_api_plugin_id/source_key/version` 隐藏字段不变。
- 详情加载不改执行 URL、method、polling、callback、credential 字段的保存结构。

- [ ] **Step 2: 更新前端契约文档**

记录：

- `/api/plugin/detail/` 的请求/响应。
- V4 识别条件和版本来源优先级。
- 四种 forms type。
- 原生失败不降级。
- 浏览器直连标准运维与凭证 Origin 限制。
- 第一阶段双轨表。
- Stage 认证失败停止规则。

- [ ] **Step 3: 运行后端目标测试**

Run:

```bash
pytest \
  tests/interface/plugin/services/test_plugin_detail.py \
  tests/interface/plugin/test_plugin_detail_view.py \
  tests/interface/plugin/services/test_plugin_schema_service.py \
  tests/plugins/uniform_api/test_uniform_api_client.py \
  tests/plugins/uniform_api/test_api_plugin_vue.py -v
```

Expected: PASS。

- [ ] **Step 4: 运行开放插件既有回归**

Run:

```bash
pytest \
  tests/interface/plugin/services/test_open_plugin_catalog.py \
  tests/interface/plugin/services/test_open_plugin_grant.py \
  tests/interface/plugin/services/test_open_plugin_snapshot.py \
  tests/plugins/components/collections/uniform_api_test/test_v4_0_0.py -v
```

Expected: PASS；目录、准入、快照、执行 context 不回归。

- [ ] **Step 5: 运行前端测试、lint 和生产构建**

Run:

```bash
cd frontend
npm run test:plugin-form
npm run lint
npm run build:production
```

Expected: 三条命令退出 0；构建日志无 module resolution、ESLint 或 asset emission 错误。

- [ ] **Step 6: 静态检查**

Run:

```bash
git diff --check
python -m compileall \
  bkflow/plugin \
  bkflow/pipeline_plugins/query/uniform_api
```

Expected: 均退出 0。

- [ ] **Step 7: Commit**

```bash
git add tests/plugins/uniform_api/test_api_plugin_vue.py \
  docs/guide/sops_open_plugin_frontend_contract.md
git commit -m "test(open-plugin): 补齐原生表单双轨回归 --story=133649781"
```

---

## Stage Acceptance Gate

先确认 bk-sops 加法版本、有限 CORS 和 BKFlow 本计划版本均已发布；任一未发布或配置缺失立即停止。

1. `POST /api/plugin/detail/` 在空间 `245`、`scope_type=biz`、`scope_value=100605` 下返回 operator `dannydeng` 对应的标准运维表单上下文。
2. JOB 快速执行脚本选择精确版本后显示原代码编辑器、脚本来源、脚本类型、业务、账号和目标选择控件。
3. JOB 表单动态请求直接访问标准运维域，携带登录态，并由标准运维识别为 `dannydeng`。
4. `danny-test-plugi` 原始 renderform、动态下拉和表格在侧栏内不越界，data_api 直接访问标准运维域。
5. 模板编辑、任务详情、侧栏详情、节点重试、参数修改、Mock 配置、Mock 执行、批量更新、变量编辑逐一抽查。
6. 保存 V4 节点后重新打开，仍请求保存的子插件版本；切换到另一个明确版本后才改变。
7. 模拟已保存版本下架，页面显示版本不可用，不能自动显示最新版本表单。
8. 抽查一个 BKFlow 内置插件、一个 BKFlow 第三方插件、一个 Uniform API V2、一个 Uniform API V3，Network 中都没有 `/api/plugin/detail/`。
9. 存量 pipeline tree 打开并保存后字段不变；SAP 节点只验证配置、解析和回显，不执行。
10. 最后执行一个允许的 V4 同步插件、一个轮询插件和一个回调插件，确认表单变更没有影响运行协议。

## Spec Coverage Map

| Spec Requirement | Plan Coverage |
|---|---|
| §6.2 固定字段统一详情接口与三类 adapters | Tasks 1-2 |
| §6.2 认证 operator、scope、精确版本、无 context 缓存 | Task 2 |
| §6.3 四种表单协议与明确失败 | Task 3 |
| §6.4 纯数据 context、本地函数、限定凭证 AJAX | Task 3 |
| §6.5 流程编辑 | Task 4 |
| §6.5 任务详情、侧栏、重试、参数修改 | Task 5 |
| §6.5 Mock、批量更新、变量编辑 | Task 6 |
| §6.6 BKFlow 内置/第三方和 Uniform API V2/V3 双轨 | Global Constraints + Task 7 |
| §7 自动测试与联合验收 | Tasks 1-7 + Stage Acceptance Gate |
| §8 发布顺序与 provider 清理 | Global Constraints + Provider Cleanup Gate |

## Provider Cleanup Gate

上述 Stage 验收稳定后，才能在 bk-sops 独立变更中删除过渡 `form_schema`。BKFlow 的 `renderFormSchema` 仍需保留，因为它继续承担无原生表单的 `api_plugin_json` 兜底和 Uniform API V2/V3 存量逻辑。
