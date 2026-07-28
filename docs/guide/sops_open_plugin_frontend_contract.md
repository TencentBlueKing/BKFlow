# 标准运维开放插件前后端对接协议

## 场景范围

本协议只覆盖以下三组页面的前端消费需求：

- 空间开放插件管理页
- 模板编辑中的插件选择与版本展示页
- 任务页中的插件异常提示页

这份文档只保留前端必需字段、状态和展示规则，不重复后端主 spec 中的完整协议设计。

## 页面到接口映射

### 1. 空间开放插件管理页

前端至少依赖以下能力：

- 空间开放插件列表接口  
  用于获取当前空间下的来源、插件、开启状态、目录可用状态、最近同步时间
- 单个插件开关接口  
  用于切换 `enabled`
- 当前可见插件一键全开接口  
  用于对当前已发现插件执行批量开启
- 按来源批量关闭接口  
  作为增强态的来源级 kill switch

### 2. 模板编辑插件选择与版本展示页

前端至少依赖以下能力：

- `list_plugins`  
  用于展示开放插件来源、来源别名、插件类型和列表项
- `get_plugin_schema`  
  用于按 `plugin_id + plugin_version` 获取当前版本 schema
- 模板保存接口  
  用于保存节点当前绑定的插件引用和版本

V4.0.0 节点使用 API 插件时，前端只需要额外完成三件事：

- 在节点配置面板中展示“版本”选择项
- 切换版本后按 `plugin_version` 重新获取 schema
- 保存节点时带上用户选择的业务版本

### 3. 任务页异常提示

前端至少依赖以下能力：

- 创建任务 / 启动任务接口  
  用于得到任务运行结果或异常状态
- 任务详情接口  
  用于获取任务当前异常说明、插件快照和建议动作提示所需字段

## 核心展示实体

### 1. 开放插件来源

前端只关心以下最小字段：

- `source_key`
- `display_name`
- `status`
- `last_sync_at`
- `plugin_total`
- `enabled_plugin_total`

### 2. 开放插件

前端最小字段：

- `plugin_id`
- `plugin_code`
- `plugin_source`
- `display_name`
- `plugin_type`
- `enabled`
- `availability_status`
- `default_version`
- `latest_version`
- `last_sync_at`

### 3. 插件版本

前端最小字段：

- `plugin_version`
- `status`
- `version_note`
- `is_default`
- `is_latest`

### 4. 任务异常信息

前端最小字段：

- `error_type`
- `error_title`
- `error_message`
- `plugin_id`
- `plugin_source`
- `plugin_version`
- `template_id`
- `space_id`
- `suggested_actions`
- `is_history_snapshot`

## 页面字段清单

### 空间开放插件管理页

表格建议至少消费：

- `display_name`
- `source_display_name`
- `plugin_type`
- `enabled`
- `availability_status`
- `default_version`
- `latest_version`
- `last_sync_at`

### 模板编辑页

插件选择和摘要区至少消费：

- `plugin_id`
- `plugin_source`
- `plugin_code`
- `display_name`
- `plugin_type`
- `plugin_version`
- `default_version`
- `latest_version`
- `versions`
- `availability_status`

参数区至少消费：

- `inputs`
- `schema_protocol_version`

节点保存时至少需要写入：

- `component.code = "uniform_api"`
- `component.data.uniform_api_plugin_version`

`context` 不属于节点表单字段，前端不保存；运行时由 BKFlow 根据任务上下文构造。

### 任务异常页

错误卡片至少消费：

- `error_type`
- `error_title`
- `error_message`
- `plugin_source`
- `plugin_id`
- `plugin_version`
- `impact_scope`
- `suggested_actions`
- `is_history_snapshot`

## 状态枚举

建议前端统一按以下状态命名消费：

### 插件开放状态

- `enabled`
- `disabled`

### 插件可用状态

- `available`
- `unavailable`

### 来源状态

- `ready`
- `sync_failed`
- `temporarily_unreachable`

### 任务异常类型

- `plugin_not_enabled`
- `plugin_version_unavailable`
- `plugin_removed`
- `source_unreachable`

如果后端需要扩展更多错误类型，应优先在 `error_type` 层扩展，而不是让前端自行解析错误文本。

## 展示规则

### 空间开放插件管理页

- `enabled=false` 时默认展示为未开启，可执行单个开启动作
- `availability_status=unavailable` 时，展示为历史记录或不可用记录，不允许继续开启
- 来源异常时，应保留列表，但页面顶部给出来源异常提示

### 模板编辑页

- `plugin_version` 始终显式展示
- API 插件业务版本选择器展示的是 `plugin_version`，不是 `uniform_api` 包装器版本
- 当 `availability_status=available` 时允许正常编辑和保存
- 当版本不可用但存在历史快照时，允许回看，但页面需提示不能继续新用
- 仅当后端返回可选新版本时，前端才展示“切换到可用版本”的引导
- 切换 `plugin_version` 后必须重新获取 schema
- 切换版本不自动保存，不自动升级历史模板
- 不额外设计 `context`、polling/callback、版本差异对比 UI

### 任务异常页

- `error_type` 决定错误卡片标题、说明和建议动作
- 任务页默认不提供原地修复能力
- `is_history_snapshot=true` 时，页面需补充“当前展示的是历史快照，不代表该版本仍可新建任务”的说明

## 错误态与建议动作映射

| error_type | 页面标题建议 | 建议动作 |
| --- | --- | --- |
| `plugin_not_enabled` | 插件未在当前空间开放 | 去空间开放插件管理页检查插件状态 |
| `plugin_version_unavailable` | 插件版本不可用 | 返回模板切换到可用版本 |
| `plugin_removed` | 插件已从来源目录下线 | 联系管理员或维护人确认替代方案 |
| `source_unreachable` | 插件来源暂时不可达 | 稍后重试，或联系管理员检查来源状态 |

前端不需要自己生成复杂动作逻辑，但应保证不同错误类型下的按钮文案和引导方向一致。

## 跳转与回退规则

建议页面按以下规则组织跳转：

- 空间管理页 ←→ 模板编辑页  
  不直接强耦合，主要通过“建议动作”或上下文提示关联
- 模板编辑页 → 任务页  
  正常启动后统一进入任务页
- 任务页 → 模板编辑页  
  仅通过“回模板切换版本”这类引导动作返回
- 任务页 → 空间开放插件管理页  
  仅在错误类型与空间治理有关时引导跳转

回退规则上，前端不承担数据恢复逻辑，只负责把用户带回合适的配置入口。

## 增强态预留字段

为后续增强态预留的字段建议集中在以下几类：

- `version_diff_summary`  
  用于展示版本切换时的高层差异说明
- `source_status_detail`  
  用于解释来源异常的更细粒度原因
- `action_target`  
  用于更明确地指导按钮跳向模板页、空间页或其他位置
- `history_snapshot_note`  
  用于细化历史任务的只读说明

这些字段在一期可以为空或缺省，前端不应把它们作为 MVP 的强依赖。

## Internal Native-Form Detail Contract

The template editor and task pages use the same internal endpoint for V4 open plugins:

```text
POST /api/plugin/detail/
Content-Type: application/json
```

The endpoint is an internal BKFlow page API. The authenticated BKFlow user is the
operator; `operator` is not accepted from the request body.

### Request

The request body is strict. Unknown fields are rejected rather than ignored.

| Field | Required | Meaning |
| --- | --- | --- |
| `space_id` | yes | BKFlow space identifier |
| `template_id` | yes | Current template identifier |
| `plugin_type` | yes | `component`, `remote_plugin`, or `uniform_api` |
| `plugin_code` | yes | Plugin code or open-plugin id |
| `plugin_version` | yes | Exact wrapper/plugin version requested |
| `source_key` | no | Required and non-empty for `uniform_api` |
| `scope_type` | no | Task scope type, for example `biz` |
| `scope_value` | no | Task scope value; must be an integer for `biz`/`cmdb_biz` when present |

Example:

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

The service uses `space_id`, `template_id`, `scope_type`, and `scope_value` to
perform the space, scope, credential, and provider-detail lookup. `scope` is
execution/display context passed through from the template or task state; it
is not a business permission granted by BKFlow through this endpoint. The
provider and underlying system must authorize the real authenticated operator
(`request.user.username`) together with that scope before returning or
performing business data. BKFlow does not parse or replace that authorization
decision, and the browser cannot impersonate another operator.

### Response

A successful response is the standard BKFlow envelope:

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
    "forms": {"input": null, "output": null},
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

`data` always contains the same keys for `component`, `remote_plugin`, and
`uniform_api`. Empty values use `null`, an empty string, an empty list, or an
empty object according to the field above. A form descriptor has this fixed
shape:

```json
{
  "type": "component_js",
  "key": "job_fast_execute_script",
  "data": "https://bk-sops.example.com/static/components/atoms/job/fast_execute_script/v2_0.js",
  "is_embedded": false,
  "base": null
}
```

The component adapter returns `component_js`; the remote-plugin adapter returns
native `renderform` when supplied, otherwise `jsonschema`; the uniform-api
adapter passes through the provider's `forms` and `form_context` after schema
validation. Execution fields (`url`, `methods`, `response_data_path`,
`polling`, `callback`, and `credential_key`) are meaningful for `uniform_api`
and remain empty for the local component/remote-plugin adapters.

## V4 Identity And Version Rules

`isV4OpenPlugin(component)` is true only when all of the following are true:

1. `component.code == "uniform_api"`.
2. The wrapper version is `api_meta.wrapper_version`, or `component.version`
   when the metadata value is absent, and equals `v4.0.0`.
3. An open-plugin source key exists.
4. An open-plugin id exists.

For saved pipeline nodes, identity fields are read with this priority:

| Value | First choice | Fallback |
| --- | --- | --- |
| source key | `data.uniform_api_plugin_source_key.value` | `api_meta.source_key` |
| plugin id | `data.uniform_api_plugin_id.value` | `api_meta.id`, then `api_meta.plugin_id` |
| plugin version | `data.uniform_api_plugin_version.value` | `api_meta.plugin_version` |

For a new, unsaved node only, the catalog-selected version may be used after
the saved fields are absent. The wrapper version (`v4.0.0`) is never treated as
the business plugin version. A saved node with a missing saved version fails
the detail request instead of falling back to `selectedVersion`,
`default_version`, or `latest_version`. Re-opening a saved V4 node therefore
requests the exact version stored in its pipeline tree; a user-selected
version changes only after an explicit version switch.

## Four Form Types

The frontend `PluginFormLoader` dispatches the descriptor without changing the
provider's native form semantics:

| `forms.*.type` | Loading behavior |
| --- | --- |
| `component_js` | Load `base` when present, then execute/load the form JavaScript and read `$.atoms[key]`. |
| `renderform` | Execute the original renderform and read `$.atoms[key]`; structured array/object renderform data is consumed directly. |
| `jsonschema` | Pass the object schema to the existing JSON Schema renderer. |
| `api_plugin_json` | Convert the detail's legacy `inputs` through the existing `renderFormSchema` path. |

If `forms.input` is absent or `null`, the loader may construct the
`api_plugin_json` fallback from `inputs`. If a provider explicitly returns a
native descriptor, any protocol, script-loading, execution, or registration
failure is shown as a failure. It must never silently downgrade to
`api_plugin_json`.

The relevant frontend failure codes are:

- `FORM_PROTOCOL_INVALID`: missing/invalid descriptor or unsupported type
- `FORM_REGISTRATION_FAILED`: JavaScript ran but `$.atoms[key]` was not registered
- `FORM_LOAD_FAILED`: resource, execution, or post-load failure
- `FORM_LOAD_STALE`: the response belongs to an obsolete request and must not update the page
- `FORM_FIELD_NOT_FOUND`: a variable/mock field is absent from the native scheme

These errors are scoped to the current request. They do not authorize a
fallback to another plugin version or to a different renderer.

## Browser Direct Requests And Credential Origins

The browser calls BKFlow's `/api/plugin/detail/` endpoint through the normal
same-origin frontend API. Native form JavaScript and its dynamic data requests
then call the standard-ops domain directly; BKFlow does not proxy these form
requests or rewrite their URLs.

Credentialed cross-origin requests are restricted to origins declared by the
detail response: `form_context.site_url` and the values in
`form_context.bk_plugin_api_host`. BKFlow registers those exact origins and
sets `xhrFields.withCredentials = true` only when the request URL resolves to
one of them. It does not enable credentials for arbitrary URLs.

The standard-ops side must therefore allow the exact BKFlow Origin, credentials,
CSRF/Cookie policy, and the requested resource. A wildcard `Access-Control-Allow-Origin`
cannot be used with credentials. A non-allowlisted Origin, missing credential
cookie, failed CSRF/CORS check, or denied operator permission is a real failure;
the browser must not retry anonymously or route the request through an
unrestricted BKFlow proxy.

## Phase-One Dual Track

Only V4 open plugins use the internal detail endpoint and the native
`PluginFormLoader` in phase one. Existing nodes are not migrated or batch
rewritten:

| Node | Detail/form path | Pipeline-tree rule |
| --- | --- | --- |
| BKFlow built-in component | `loadAtomConfig` and the existing component form | `component.code`, `version`, `data`, and `api_meta` stay unchanged when opened and saved without user edits |
| BKFlow remote plugin | `loadPluginServiceDetail` and the existing renderform/eval path | Keep the existing component data and metadata shape |
| Uniform API V2 | Existing API JSON path | Do not add V4 identity fields or call `/api/plugin/detail/` |
| Uniform API V3 | Existing API JSON and sync/polling/callback path | Do not add V4 identity fields or call `/api/plugin/detail/` |
| Uniform API V4 open plugin | `/api/plugin/detail/` and `PluginFormLoader` | Preserve `uniform_api_plugin_id/source_key/version` and the execution URL/method/polling/callback/credential fields |

The save guard is semantic, not based on a plugin-code naming convention:
`component`, `remote_plugin`, V2, V3, and V4-without-complete-identity remain
on the legacy track. V4 identity hidden fields are written only for a
recognized V4 open plugin. URL, method, polling, callback, response-path, and
credential execution fields continue to be saved for every API plugin using
the existing structure; the additional guard applies only to V4 hidden
identity/version fields. Opening and saving a legacy node must not upgrade it
to V4.

## Stage Stop Gate

Stage is an external acceptance gate, not a local unit-test claim. Before any
joint test, confirm that the BK-SOPS additive `forms/form_context` change,
limited credential CORS configuration, and this BKFlow plan revision are all
published and configured. If any one is missing, stop the Stage test immediately.

The Stage checklist is:

1. In space `245`, with `scope_type=biz`, `scope_value=100605`, the detail
   request returns the standard-ops form context for authenticated operator
   `dannydeng`.
2. The JOB fast-execute-script form displays its code editor, script source and
   type, business, credential, and target selectors after an exact version is
   selected.
3. The form's dynamic requests go directly to the standard-ops domain with
   login state, and standard ops identifies `dannydeng`.
4. `danny-test-plugi` renderform, dynamic dropdown, and table stay inside the
   side panel; its `data_api` calls go directly to standard ops.
5. Check template editing, task detail, side detail, retry, parameter edit,
   Mock setting, Mock execute, batch update, and variable editing.
6. Re-opening a saved V4 node requests its saved plugin version; only an
   explicit version switch changes it.
7. A withdrawn saved version is displayed as unavailable and is not replaced
   by the latest version automatically.
8. Network inspection confirms that built-in, third-party, Uniform API V2, and
   Uniform API V3 nodes do not call `/api/plugin/detail/`.
9. Open/save a legacy pipeline tree and compare the component fields; SAP nodes
   are configuration/parse/echo checks only and are not executed.
10. Execute one permitted synchronous, one polling, and one callback V4 plugin
    to confirm that form changes did not alter the execution protocol.

This document records the gate only. It does not claim that Stage credentials,
published versions, cross-domain cookies, or the above live executions have
been verified locally.

## Accepted `$.context` Risk

The current form runtime uses the existing global `$.context` object because
native component scripts expect that contract. Each loader call reapplies the
current `form_context` and runtime inputs/outputs, and request-generation
guards prevent stale responses from applying another request's context.

The remaining accepted risk is that two native forms rendered concurrently in
one browser page share global `$.context`; a script that retains the global
object asynchronously could observe another form's context. Phase one accepts
this existing native-form trust boundary and does not introduce a second
context cache or a new renderer. Do not broaden this risk to untrusted sources:
source grants, plugin availability, exact versions, Origin allowlists, and
operator authorization remain mandatory gates. Multi-instance context isolation
is a follow-up design item.
