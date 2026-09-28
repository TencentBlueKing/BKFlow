### Harness P0：搜索流程能力

#### 接口说明

`harness_search_workflow_capabilities` 是 `BKFlow Workflow Harness MCP` 的 P0 只读 Tool，按当前可信空间、用户、Scope 和环境返回已授权能力的受治理摘要。业务插件是搜索数据，不会动态变成 MCP Tool，也不会被本接口执行。

#### 请求方法

POST `/space/{space_id}/harness/search_workflow_capabilities/`

#### 租户边界

开启多租户时，全租户应用必须传 `X-Bk-Tenant-Id` 请求头；单租户应用可省略并使用已认证应用租户。应用本次请求租户、已认证用户租户和路由空间租户必须一致，Body 中的身份字段不能覆盖此边界。关闭多租户时忽略该请求头。

#### 可信字段与不可信字段

网关认证、路由 `{space_id}` 和服务端 Harness 部署绑定共同决定平台应用、真实用户、空间、允许 Scope、目标环境、风险策略和 MCP contract `1.0.0`；这些是可信字段，调用方不得在 body 中提供或覆盖。

Body 仅接受下表字段，未知字段和任何伪造的 `platform`、`app`、`user`、`space`、`scope`、`environment`、`policy`、`mcp` 身份字段都会被拒绝。请求和响应均不会返回令牌、密钥、凭证引用或 Provider 原始错误。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| query | string | 是 | 长度不超过 256 的能力查询词。 |
| top_k | integer | 否 | 1–20，默认 10。 |
| plugin_source | string | 否 | 仅用于受治理的 Uniform API 来源过滤，长度不超过 64。 |

#### 响应 Envelope

无论成功或失败，顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。搜索成功的 `artifact_refs` 只携带能力摘要；`required_credentials` 是公开的凭证种类列表，不包含任何凭证值。

每个错误固定包含 `category`、`code`、`message`、`path`、`repairable`、`suggested_action`、`retryable`。分类仅可能为 `USER_INPUT`、`CAPABILITY_NOT_FOUND`、`AMBIGUOUS_CAPABILITY`、`SCHEMA_DRIFT`、`VALIDATION`、`PERMISSION`、`APPROVAL_REQUIRED`、`APPROVAL_INVALID`、`TOKEN_LEASE`、`DEBUG_CONFLICT`、`RUNTIME`、`POSTCONDITION`、`RETRYABLE_INFRA`。

#### 请求示例

```json
{
  "query": "restart service",
  "top_k": 3
}
```

#### P0 边界

本 Tool 不创建 run、不会执行插件，也不接受 `idempotency_key`、版本或计划哈希作为授权条件。选择候选时只能原样保留卡片的 `capability_ref` 和 `schema_hash` 并交给 `get_plugin_schema`；模型不得解码引用或凭 code、source、version 自行构造 Schema 请求。后续只有将精确 Schema 绑定到 a2flow 并通过 `validate_workflow` 后，才可携带服务器返回的版本、哈希和幂等键进入草稿流程；最终只报告 DRAFT 状态并停止。
