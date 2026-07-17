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

`bkflow/pipeline_plugins/components/collections/uniform_api/v4_0_0.py` 的开放插件执行分支：在构造 execute payload 时附加 `context`。其余执行 / 轮询 / 回调逻辑不变。

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

## 7. 测试与验收（BKFlow 侧）

- execute body 携带 `context`；老来源不带 context 时仍可正常执行（兼容回归）。
- 两层准入：平台 grant + 空间 per-plugin；未准入空间看不到该来源。
- 四处服务端强校验生效。
- 快照与版本治理回归不退化。
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
