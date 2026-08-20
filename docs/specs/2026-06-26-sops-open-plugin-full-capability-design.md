# 标准运维全量插件能力接入 BKFlow 设计（BKFlow 侧）

> **Date:** 2026-06-26
> **Status:** Draft
> **Scope:** 在 `2026-04-20` 集成设计基础上，扩展 `uniform_api v4.0.0` 协议透传业务上下文与 operator，并新增两层空间准入，使选定的「有业务含义的空间」可使用标准运维全部插件。
> **Related:** [标准运维开放插件生态接入 BKFlow 设计](./2026-04-20-sops-open-plugin-integration-design.md) ｜ [BKFlow 设计模式与方案](../../.ai/docs/specs/design-patterns.md) ｜ 标准运维侧设计见 bk-sops 仓库 `docs/specs/2026-06-26-plugin-gateway-full-capability-design.md`
>
> **2026-07-23 修订：** V4 表单改为原生协议透传和按类型加载，新增 BKFlow 内部统一插件详情接口。第一阶段仅 V4 开放插件接入新链路，存量内置、第三方和 V2/V3 API 插件保持原详情、表单和执行逻辑。

## 1. 背景

`2026-04-20-sops-open-plugin-integration-design.md` 选择把标准运维作为一个 `uniform_api` 来源接入，并刻意走保守路线：**不从 BKFlow 透传业务上下文**，标准运维侧用 `default_project_id` 兜 `project`；一期只开放「白名单内、不依赖 `project`、不依赖用户级凭证」的插件；并明确「若 `default_project_id` 覆盖不了，不要临时扩 BKFlow 运行时上下文，先把插件加进不开放白名单」。

本设计是一次方向性升级：**扩展 `uniform_api v4.0.0` 协议**，让 BKFlow 把空间的业务上下文（`scope_type/scope_value`）与真实 operator 透传给标准运维，从而解锁此前被排除的、依赖 `project` 的内置插件，使**选定空间可使用标准运维全部插件（内置 + 第三方）**。

标准运维侧的目录暴露、组件运行壳执行、project/identity 解析见配套的 bk-sops 设计，本文聚焦 BKFlow 侧。

## 2. 目标与非目标

### 2.1 目标

1. 原地扩展 `uniform_api v4.0.0` execute 协议，新增向后兼容的 `context` 对象（不升 wrapper 版本）。
2. 运行时从已有上下文构造并透传 `context`：`scope_type / scope_value / operator / space_id / task_id / node_id / task_name`。
3. 新增**两层空间准入**：平台级「来源准入」+ 已有的空间级 per-plugin 治理。
4. 在查询可用插件 / 保存模板 / 创建任务 / 启动任务四处做服务端强校验。
5. 保持对老 `uniform_api` 来源（v2/v3/v4 不带 context）的完全兼容。
6. 通过内部统一插件详情接口承接原生 `component_js/renderform/jsonschema/api_plugin_json`，恢复标准运维内置和第三方插件的原始表单能力。

### 2.2 非目标

1. 不新增第四种插件类型，继续复用 `uniform_api` 执行壳。
2. 不在 BKFlow 侧解析 sops `project`（解析责任在标准运维侧；BKFlow 只透传 scope）。
3. 不实现用户级凭证透传/代理身份模型（仅透传 operator 供标准运维侧做权限校验）。
4. 不改造引擎或快照体系（沿用现有 v4.0.0 组件与快照治理）。
5. 第一阶段不迁移存量 BKFlow 内置、BKFlow 第三方和 V2/V3 API 插件，不改写其 pipeline tree。

## 3. 协议扩展：`uniform_api v4.0.0` 的 `context`

### 3.1 execute 体新增可选 `context`

`build_open_plugin_execute_payload` 在现有字段（`source_key / plugin_id / plugin_version / client_request_id / callback_url / callback_token / inputs / project_id`）之外，新增可选 `context` 对象：

```json
"context": {
  "scope_type": "biz",
  "scope_value": "2",
  "operator": "zhangsan",
  "space_id": 10,
  "task_id": 123,
  "node_id": "n1",
  "task_name": "..."
}
```

- 字段全部来自 BKFlow 运行时**已有**数据：`task_scope_type / task_scope_value`、operator、space_id、task/node 信息（当前 `_dispatch_schedule_trigger` 已读取 scope 用于取凭证，只是未塞进 execute 体）。
- **向后兼容**：来源不声明 v4 context 能力或老协议不传 `context` 时，标准运维侧按 `default_project_id` 兜底，老来源零改造。
- `detail_meta`、polling / callback 协议不变，仅 execute body 多带一个可选对象，故**不升 wrapper 版本**——这是补齐 `2026-04-20` 集成设计 6.5 中规划但 MVP 未实现的 `context`。

### 3.2 改动位置

`bkflow/pipeline_plugins/components/collections/uniform_api/v4_0_0.py` 的开放插件执行分支：在构造 execute payload 时附加 `context`。

### 3.3 调度模式自适应与回调入口

V4 节点不在流程保存时固化同步、轮询或回调模式，而是以 execute / polling 每次返回的 `status` 决定后续动作：

- `SUCCEEDED / FAILED / CANCELLED` 立即结束，不因 detail 中存在 polling 配置而额外等待一次轮询。
- `CREATED / RUNNING` 继续轮询。
- `WAITING_CALLBACK` 同时接受真实回调并保留轮询兜底；回调投递失败时，节点仍可通过状态查询收敛，不把当前 polling tick 切成 callback tick 后提前结束。

标准运维不持有 BKFlow APIGW 应用凭证，因此 callback URL 复用 BKFlow 已有的节点回调入口（方案 B）：

`/callback/{encrypted_node_token}/`

URL 中的存量 token 用于定位 `space/task/node/version`；入口收到开放插件回调后，再把 `X-Callback-Token` 运行凭证转发至 task 模块。engine 侧继续校验运行 token 的签名、有效期，以及 token 与 task/node/client_request_id/open_plugin_run_id 的绑定关系。只有 engine 返回 `result=True` 时，interface 才返回 2xx，标准运维方才可把本次投递标记为成功。普通存量节点回调不要求 `X-Callback-Token`，行为保持不变。

## 4. 两层空间准入

> **本章第 1 层已于 2026-08-20 移除**，`OpenPluginSpaceGrant` 及其全部校验点、管理命令、迁移均已删除，V4 开放插件只保留第 2 层 `SpaceOpenPluginAvailability` 空间开关。原因与移除后的完整管控链路见 [2026-08-20-open-plugin-remove-space-grant-design.md](./2026-08-20-open-plugin-remove-space-grant-design.md)。本章以下内容保留为历史设计记录。

### 4.1 第 1 层（平台级，新增）：来源准入

平台管理员授权「哪些空间可接入标准运维开放来源」。新增轻量存储与管理 API：

- `OpenPluginSpaceGrant`
  - `space_id`
  - `source_key`
  - `enabled`
  - `operator`
  - `create_time` / `update_time`

未授权空间**连该来源目录都看不到**：`list_space_plugins`、schema 服务、目录同步全部要求存在有效 grant。

展示配置与执行来源分层：`uniform_api.api` 的每个 `api_key` 对应流程编辑器中的一个顶层 API 插件入口；配置项可用可选 `source_key` 指向真实的准入与执行来源，未配置时回退到 `api_key`。因此标准运维内置插件和第三方插件可用两个 `api_key` 分开展示，并通过目录 URL 的固定 `plugin_source` 参数分别过滤，同时共享 `source_key=sops`。目录同步按有效 `source_key` 聚合后一次性刷新，避免两个入口互相把对方插件标记为下架。

### 4.2 第 2 层（空间级，已有）：per-plugin 治理

沿用 `SpaceOpenPluginAvailability`（新来源默认关）+ per-plugin 开关 + 一键全开 + `disable_source`。「一键全开」仅在**已准入**空间内生效。

### 4.3 默认与迁移

- **新空间**：默认无 grant（保守）。
- **存量空间迁移**：对**已配置标准运维 `uniform_api` 来源**的空间默认授予 grant，避免现有第三方插件能力断流。
- per-plugin 默认策略沿用 `2026-04-20` 设计 6.3（新来源默认关，存量空间迁移默认开）。

## 5. 服务端强校验

以下四处必须做服务端校验，而非仅前端隐藏：

1. 查询空间可用插件列表
2. 保存模板
3. 创建任务
4. 启动任务

校验内容：① 空间已准入该来源（grant 有效）；② 该 `plugin_id` 在空间内 `enabled`；③ `plugin_id/version` 仍 `available`；④ 不在标准运维返回的「不开放黑名单」内。

## 6. 上下文构造来源

| context 字段 | BKFlow 来源 |
|---|---|
| `scope_type` | `parent_data.task_scope_type` |
| `scope_value` | `parent_data.task_scope_value` |
| `operator` | 任务执行人（`_load_parent_data` 的 operator） |
| `space_id` | 运行时已有 |
| `task_id / node_id / task_name` | 运行时已有 |

全部来自运行时已有数据，**不需要用户在表单中填写**。

### 6.1 前端节点配置变动（V4.0.0 API 插件）

按最新 `prototype-wireframe` 原型规范，节点使用 API 插件时的前端变动集中在模板编辑的节点配置抽屉中，基线页面为：

- `frontend/src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue`
- `frontend/src/views/template/TemplateEdit/NodeConfig/SelectPanel/apiPlugin.vue`
- `frontend/src/store/modules/template.js`

V4.0.0 不新增插件类型，也不新增独立入口。用户仍按普通 API 插件方式选择来源、分类、插件，只新增和明确以下交互：

1. 节点配置里新增“版本”选择项，默认选 `default_version`，候选项来自 `versions/latest_version/default_version`。
2. 用户切换版本后，前端按所选 `plugin_version` 重新获取 schema 并刷新参数表单。
3. 保存节点时带上用户选择的业务版本；服务端继续校验来源准入、插件开关和版本可用性。

`context` 透传、polling/callback 调度配置、历史版本失效治理不额外增加节点配置 UI。

对应原型与前端说明：

- `prototypes/output/sops-open-plugin-v4-node-api-plugin/README.md`
- `docs/specs/2026-04-20-sops-open-plugin-frontend-interaction-design.md`
- `docs/guide/sops_open_plugin_frontend_contract.md`

### 6.2 内部统一插件详情接口

新增页面内部接口：

```text
POST /api/plugin/detail/
```

静态路由必须注册在 `ComponentModelSetViewSet` 的动态 `/<plugin_code>/` 路由之前，避免 `detail` 被解释为组件 code。请求示例：

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

operator 从当前登录用户读取，不接受前端指定。接口支持 `component / remote_plugin / uniform_api` 三类来源适配器，但第一阶段只有 V4 开放插件由页面实际调用。

响应保持扁平，所有插件类型必须返回相同字段集合，不存在的值使用固定的 `null / "" / [] / {}`：

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

字段含义：

- `plugin_type`：BKFlow 节点类型，固定为 `component / remote_plugin / uniform_api`。
- `source_key`：BKFlow 本地插件固定为 `bkflow`，API 插件使用真实来源。
- `plugin_source`：`builtin / third_party`；V2/V3 来源无法识别时为 `null`。
- `protocol`：`native / plugin_service / uniform_api`。
- `wrapper_version`：仅 Uniform API 有值，其他类型为 `null`。
- `forms.input/output`：原生表单描述；`output` 不存在时固定为 `null`。
- `execution_kind` 与执行字段：本地组件填空值，Uniform API 保留 detail 中的 URL、method、polling、callback 和 credential。

各适配器只负责取数和填充统一字段，不改变提供方的原生表单语义：

| 字段 | `component` | `remote_plugin` | `uniform_api` |
|---|---|---|---|
| `source_key` | `bkflow` | `bkflow` | 配置的真实来源 |
| `plugin_source` | `builtin` | `third_party` | 提供方返回值；无法识别时为 `null` |
| `protocol` | `native` | `plugin_service` | `uniform_api` |
| `wrapper_version` | `null` | `null` | `v2.0.x / v3.0.x / v4.0.0` |
| `name/description` | 组件元数据 | 插件服务详情 | Uniform API detail |
| `inputs/outputs/credentials` | 组件元数据；无值用空数组 | 插件服务详情；无值用空数组 | Uniform API detail；无值用空数组 |
| `forms` | 原生 `component_js` | 原生 `renderform/jsonschema` | V4 使用提供方原生表单；V2/V3 或无原生表单时为 `api_plugin_json` |
| `form_context` | BKFlow 本地上下文 | BKFlow 本地上下文 | V4 合并提供方上下文；V2/V3 使用空对象 |
| `execution_kind` | `component` | `remote_plugin` | `uniform_api` |
| 执行字段 | `url=null, methods=[], response_data_path=null, polling={}, callback={}, credential_key=null` | 同左 | 保留 Uniform API detail 对应值 |

来源适配器只填充统一字段，不转换表单内容。与用户无关的原始详情可按 `source_key + plugin_type + plugin_code + plugin_version` 缓存；operator、scope、Project 和 `form_context` 不得进入共享缓存。

请求中的 `plugin_version` 是精确版本约束。已保存节点必须请求 tree 中记录的版本；来源返回版本不存在或已下架时直接展示版本失效错误，不得回退到 `default_version/latest_version`。只有新选插件、节点尚未保存版本时，前端才能使用目录的 `default_version` 发起第一次详情请求。

### 6.3 原生表单协议

`forms.input` 支持四种类型：

| type | 来源 | 解析方式 |
|---|---|---|
| `component_js` | BKFlow/标准运维内置插件 | 加载 `base`，再按 `is_embedded` 执行 JavaScript 或加载 URL，读取 `$.atoms[key]` |
| `renderform` | BKFlow/标准运维第三方插件 | 执行原始 renderform，读取 `$.atoms[key]` |
| `jsonschema` | 原生提供 JSON Schema 的插件 | 交给现有 `JsonschemaForm` |
| `api_plugin_json` | 无原生表单的 API 插件 | 经现有 `renderFormSchema` 转为 `RenderForm` 配置 |

统一 `PluginFormLoader` 负责协议分发，页面组件不再自行判断 V4 表单类型。只有提供方没有返回 `forms.input` 时，才允许根据 `inputs` 构造 `api_plugin_json`。明确返回的原生表单加载、执行或注册失败时必须展示错误，不得静默退回通用 input。

`component_js/renderform` 执行后必须存在 `$.atoms[forms.input.key]`，否则返回 `FORM_REGISTRATION_FAILED`。错误日志记录插件身份、版本、失败阶段、资源 URL 和 trace ID，但不记录完整 JavaScript、Cookie 或凭证。

### 6.4 `form_context` 装配

BKFlow 调用标准运维 detail 时透传 `scope_type / scope_value`，operator 由后端认证身份产生。标准运维复用执行侧 Project 解析并返回纯数据 `form_context`，BKFlow 不解析标准运维 Project。

`PluginFormLoader` 在加载表单前：

1. 初始化 BKFlow 公共 `$.context`。
2. 合并提供方返回的 `project / biz_cc_id / site_url / component / variable / template / instance / bk_plugin_api_host`。
3. 本地补充 `get/getBkBizId/getProjectId/canSelectBiz/getConstants/getInput/getOutput/getNodeStatus` 等函数。
4. 仅对 `form_context` 声明的标准运维 Origin，通过全局 `jQuery.ajaxPrefilter` 设置 `xhrFields.withCredentials = true`。

标准运维内置插件动态数据继续访问标准运维 `/pipeline/...` 表单辅助接口；标准运维第三方插件动态数据访问 `/plugin_service/data_api/<plugin_code>/<path>`。两者都由浏览器直连标准运维，不新增 BKFlow 数据代理。

### 6.5 全场景 V4 接入

以下页面中的 V4 节点统一调用 `/api/plugin/detail/` 和 `PluginFormLoader`：

- 流程编辑
- 任务详情与侧边任务详情
- 节点重试和参数修改
- Mock 配置与 Mock 执行
- 批量更新
- API 插件变量和全局变量编辑

共享逻辑下沉到 Vuex action 和统一加载器，页面只消费解析结果。`RenderForm` 和 `JsonschemaForm` 继续作为最终渲染器，不复制新的基础 Tag 体系。

### 6.6 存量双轨

第一阶段仅 V4 开放插件切入统一详情链路：

| 节点类型 | 第一阶段逻辑 |
|---|---|
| 存量及新建 BKFlow 内置插件 | 保持 `loadAtomConfig` |
| 存量及新建 BKFlow 第三方插件 | 保持 `loadPluginServiceDetail + eval` |
| Uniform API V2.0.X | 保持原 API JSON 逻辑 |
| Uniform API V3.0.X | 保持原同步/轮询/回调与表单逻辑 |
| Uniform API V4.0.0 开放插件 | 使用统一详情和原生表单加载器 |

V4 节点使用现有 pipeline tree 标识识别：`component.code == uniform_api`，且 `component.api_meta.wrapper_version == v4.0.0`、`source_key/plugin_code` 存在；同时兼容已保存的 `uniform_api_plugin_id / uniform_api_plugin_source_key / uniform_api_plugin_version` 隐藏字段。不得根据 code 形式猜测协议。

不迁移、不批量刷新旧 tree。旧节点打开、保存、创建任务和执行仍使用原 `component.code/version/data/api_meta`；打开后保存也不能自动升级为统一详情协议。统一详情仅参与 V4 的目录选择、表单渲染和配置回显，不改变 Uniform API wrapper 的执行数据。

## 7. 测试与验收（BKFlow 侧）

- execute body 携带 `context`；老来源不带 context 时仍可正常执行（兼容回归）。
- 两层准入：平台 grant + 空间 per-plugin；未准入空间看不到该来源。
- 四处服务端强校验生效。
- 快照与版本治理回归不退化。
- `/api/plugin/detail/` 的三类适配器返回完全相同的字段集合，空值语义固定。
- 已保存节点严格使用 tree 中的插件版本；版本失效时明确报错，不自动升级或回退。
- V4 `component_js/renderform/jsonschema/api_plugin_json` 分别进入正确加载器；原生表单失败不静默降级。
- 流程编辑、任务详情、重试、参数修改、Mock、批量更新和全局变量中的 V4 节点均使用统一加载器。
- BKFlow 内置、第三方和 V2/V3 节点不会调用新接口，旧 pipeline tree 打开再保存后协议语义不变。
- 遵循 TDD：先写失败测试再实现。

### 联调验收（与标准运维侧共同覆盖）

- 正常链路：grant → 开插件 → 存模板 → 建任务 → 执行成功（内置、第三方各一）。
- 异步三模式（同步 / 轮询 / 回调）。
- 业务上下文：biz 空间能跑依赖 `project` 的内置插件（如 JOB 执行作业）。
- 表单上下文：空间 `245` 使用 `scope_type=biz / scope_value=100605 / operator=dannydeng`，JOB 快速执行脚本的代码编辑器、业务、脚本、账号和作业实例动态字段正常。
- 第三方表单：`danny-test-plugi` 的原生 renderform、动态下拉、表格和标准运维 data_api 正常。
- 跨域身份：用户只登录 BKFlow 时，标准运维表单辅助接口仍识别真实用户；非白名单 Origin、未登记接口和黑名单插件被拒绝。
- 存量 API 插件和 SAP 相关节点只验证配置、解析和回显，不执行。
- 身份：operator 无权限被正确拒绝。
- 异常：project 解析失败 / 命中黑名单 / 版本失效 / 回调失败 / 超时兜底。

## 8. 兼容与迁移

- **协议兼容**：不带 `context` 的 v2/v3/v4 老来源继续可用。
- **表单双轨**：第一阶段只切换 V4 开放插件；BKFlow 内置、第三方和 V2/V3 的统一详情迁移另立后续设计。
- **发布顺序**：标准运维先加法返回 `forms/form_context` 并开放有限 CORS；独立验证后发布 BKFlow 统一详情和 V4 加载器；稳定后再删除标准运维旧 `form_schema` 转换。
- **`OpenPluginSpaceGrant` 迁移**：新增表与迁移；存量已配置标准运维来源的空间默认授予 grant。
- **APIGW 同步**：涉及 `bkflow/apigw/` 的改动按规范执行 `apigw_docs` 同步。

## 9. 风险与后续关注点

1. operator 权限依赖：BKFlow 用户需在标准运维对应业务下有权限，否则插件执行被底层系统拒绝；这是产品前提，需在联调与运营中明确。
2. 平台准入与空间自助配置 `uniform_api` 来源的边界需清晰：准入是额外闸门，不替代来源凭证配置。
3. 统计口径需扩展到 `(plugin_source, plugin_code, plugin_version)`，避免来源/版本混淆。
4. 标准运维侧若对某类插件无法由 scope/operator/project 满足上下文，会将其列入不开放黑名单；BKFlow 侧需在校验与 UI 上正确呈现「不可用」。
5. 原生表单继续执行既有 JavaScript。本轮接受与插件原生 SaaS 相同的信任边界，不把该能力扩展给未准入来源或黑名单插件。
6. 跨应用动态表单依赖共享 `bk_token/bk_ticket`；Stage 必须验证 Cookie Domain、SameSite、CORS、CSRF 和 CSP，任一前提不成立时暂停联调，不匿名降级。
