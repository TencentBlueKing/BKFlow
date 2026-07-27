# 标准运维全量插件能力接入 BKFlow 设计（BKFlow 侧）

> **Date:** 2026-06-26
> **Status:** Draft
> **Scope:** 在 `2026-04-20` 集成设计基础上，扩展 `uniform_api v4.0.0` 协议透传业务上下文与 operator，并新增两层空间准入，使选定的「有业务含义的空间」可使用标准运维全部插件。
> **Related:** [标准运维开放插件生态接入 BKFlow 设计](./2026-04-20-sops-open-plugin-integration-design.md) ｜ [BKFlow 设计模式与方案](../../.ai/docs/specs/design-patterns.md) ｜ 标准运维侧设计见 bk-sops 仓库 `docs/specs/2026-06-26-plugin-gateway-full-capability-design.md`

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

### 2.2 非目标

1. 不新增第四种插件类型，继续复用 `uniform_api` 执行壳。
2. 不在 BKFlow 侧解析 sops `project`（解析责任在标准运维侧；BKFlow 只透传 scope）。
3. 不实现用户级凭证透传/代理身份模型（仅透传 operator 供标准运维侧做权限校验）。
4. 不改造引擎或快照体系（沿用现有 v4.0.0 组件与快照治理）。

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

### 6.2 声明式表单控件

V4 插件详情可携带可选 `form_schema`。BKFlow 优先使用该 schema；没有 `form_schema` 时继续从 `inputs` 生成兼容表单。无论插件来自标准运维还是 BKFlow，本地最终都转换为现有 `RenderForm` 的数组 schema，并使用同一套 Tag 组件渲染：

```text
BKFlow 内置插件 -------------------+
BKFlow 第三方插件 -----------------+--> RenderForm schema --> RenderForm
标准运维内置插件 ---- V4 适配器 ----+
标准运维第三方插件 -- V4 适配器 ----+
```

这里统一的是前端渲染模型，不强制四类提供方使用相同的原始元数据格式：

- BKFlow 内置插件和存量第三方插件继续提供已有的 `RenderForm` 数组 schema。
- 标准运维内置插件和第三方插件通过 `uniform_api` 提供 JSON 可序列化的 `form_schema` 或兼容 `inputs`。
- `frontend/src/utils/renderFormSchema.js` 是唯一的 V4 协议适配层，负责将两种 uniform API 元数据转换为 `RenderForm` 数组 schema。
- 模板节点配置、任务详情、侧边任务详情和 API 插件变量编辑都调用该适配层，不再为 API 插件维护独立的 `bkui-form` 控件注册表。

`JsonschemaInputParams` 和任务详情中的 `JsonschemaForm` 继续保留给非插件 JSON Schema 场景，避免扩大本次改动范围；四类插件的输入表单不再进入该分支。`RenderForm`、已有 Tag 组件及其注册机制原则上不修改。

本轮标准控件包括：

- `input / textarea / password / codeEditor`
- `select / radio / checkbox / switcher`
- `table`

适配器将上述控件分别映射到现有 `TagInput / TagTextarea / TagPassword / TagCodeEditor / TagSelect / TagRadio / TagCheckbox / TagSwitch / TagDatatable`。`codeEditor` 因此直接复用 `TagCodeEditor` 和 `FullCodeEditor` 的 Monaco 能力，并保留 `language / height / showMiniMap / readOnly` 等声明式属性，不新增 API 插件专用编辑器组件。

适配器同时保留下列协议语义：

- 字段标题、描述、默认值和必填校验。
- `enum/options` 选项及值为 `0`、`false`、空字符串时的精确值语义。
- 对象数组到 `datatable` 的列定义和列级控件。
- 编辑态、只读态和变量勾选所需的字段元数据。

所有跨系统控件配置必须是 JSON 可序列化数据。BKFlow 不获取、不解析、不执行标准运维或开放插件提供方的旧表单 JavaScript；BKFlow 存量第三方插件已有的本地 `renderform` 加载机制本轮保持不变，但其结果同样交给 `RenderForm` 渲染。

未知控件名必须回退到按 JSON Schema 类型推导的基础 Tag，避免渲染空白自定义标签。无效的 `form_schema` 不阻断节点配置：有合法 `inputs` 时回退到 `inputs`，两者均不可用时展示无参数状态并记录错误。`tree / upload / cascader / category / combine` 等依赖动态数据源或动作函数的控件，待统一数据源与动作协议落地后再开放，不在本轮宣称原生等价。

`ui:reactions` 等尚未定义跨系统安全语义的联动配置不转换为可执行函数。后续如需跨来源一致支持，必须先定义有限、声明式、可验证的联动协议，再由适配器映射到 `RenderForm` 能力。

## 7. 测试与验收（BKFlow 侧）

- execute body 携带 `context`；老来源不带 context 时仍可正常执行（兼容回归）。
- 两层准入：平台 grant + 空间 per-plugin；未准入空间看不到该来源。
- 四处服务端强校验生效。
- 快照与版本治理回归不退化。
- 四类插件在模板编辑和任务详情中均进入 `RenderForm`，V4 的代码、多行文本、密码、选项、布尔和表格控件使用已有 Tag 正确渲染。
- V4 `form_schema` 缺失、未知控件及非法结构能按约定回退，不出现空白表单或未注册组件。
- 遵循 TDD：先写失败测试再实现。

### 联调验收（与标准运维侧共同覆盖）

- 正常链路：grant → 开插件 → 存模板 → 建任务 → 执行成功（内置、第三方各一）。
- 异步三模式（同步 / 轮询 / 回调）。
- 业务上下文：biz 空间能跑依赖 `project` 的内置插件（如 JOB 执行作业）。
- 身份：operator 无权限被正确拒绝。
- 异常：project 解析失败 / 命中黑名单 / 版本失效 / 回调失败 / 超时兜底。

## 8. 兼容与迁移

- **协议兼容**：不带 `context` 的 v2/v3/v4 老来源继续可用。
- **`OpenPluginSpaceGrant` 迁移**：新增表与迁移；存量已配置标准运维来源的空间默认授予 grant。
- **APIGW 同步**：涉及 `bkflow/apigw/` 的改动按规范执行 `apigw_docs` 同步。

## 9. 风险与后续关注点

1. operator 权限依赖：BKFlow 用户需在标准运维对应业务下有权限，否则插件执行被底层系统拒绝；这是产品前提，需在联调与运营中明确。
2. 平台准入与空间自助配置 `uniform_api` 来源的边界需清晰：准入是额外闸门，不替代来源凭证配置。
3. 统计口径需扩展到 `(plugin_source, plugin_code, plugin_version)`，避免来源/版本混淆。
4. 标准运维侧若对某类插件无法由 scope/operator/project 满足上下文，会将其列入不开放黑名单；BKFlow 侧需在校验与 UI 上正确呈现「不可用」。
