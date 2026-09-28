### Harness P0：校验受治理的工作流

#### 接口说明

`harness_validate_workflow` 是 `BKFlow Workflow Harness MCP` 的 P0 写 Tool。它先按可信上下文重新解析所有绑定，再校验、转换并持久化不可变修订与 ValidationReport；它不发布、调试或执行流程。

#### 请求方法

POST `/space/{space_id}/harness/validate_workflow/`

#### 可信字段与不可信字段

认证网关、路由 `{space_id}` 与服务端 Harness 部署绑定拥有平台应用、真实用户、空间、Scope、环境、风险策略和 MCP contract `1.0.0`。Body 不得提供 `platform`、`app`、`user`、`space`、`scope`、`environment`、`policy`、`mcp` 或任何令牌/凭证字段；未知字段会被拒绝，服务端不会回显敏感信息。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| intent_spec | object | 是 | 有界的意图与约束 DTO。 |
| a2flow | object | 是 | 有界的候选 a2flow；不是底层 pipeline_tree。 |
| bindings | array | 是 | 闭合的能力绑定 DTO。 |
| idempotency_key | string | 是 | 最长 255；相同键与相同 canonical 请求仅返回同一结果。 |
| run_id | uuid | 否 | 后续修订指定既有 run；首次可由本操作隐式创建。 |
| expected_plan_hash | string | 否 | 最长 64；用于防止在已知计划上静默覆盖。 |
| client_context | object | 否 | 仅可含非敏感 `conversation_ref` 与 `agent_release`。 |

#### 响应 Envelope 与错误

无论成功或失败，顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。每个错误固定包含 `category`、`code`、`message`、`path`、`repairable`、`suggested_action`、`retryable`，分类仅可能为 `USER_INPUT`、`CAPABILITY_NOT_FOUND`、`AMBIGUOUS_CAPABILITY`、`SCHEMA_DRIFT`、`VALIDATION`、`PERMISSION`、`APPROVAL_REQUIRED`、`APPROVAL_INVALID`、`TOKEN_LEASE`、`DEBUG_CONFLICT`、`RUNTIME`、`POSTCONDITION`、`RETRYABLE_INFRA`。

`SCHEMA_DRIFT` 表示精确版本、来源或 Schema 已变化；`RETRYABLE_INFRA` 才允许以相同 `idempotency_key` 重试。修复必须以新的 revision 再次校验，不能覆盖已验证修订。

#### 请求示例

```json
{
  "intent_spec": {"goal": "restart safely"},
  "a2flow": {"version": "2.0", "name": "restart", "nodes": []},
  "bindings": [],
  "idempotency_key": "validate-restart-v1"
}
```

#### P0 边界

能力 Binding 的 `capability_ref` 必须来自受治理搜索卡片；精确 Schema 读取只向 `get_plugin_schema` 传递该卡片的 `capability_ref` 与 `schema_hash`，不得使用 raw code、版本或来源字段重建身份。

校验成功不等于模板发布或执行成功。只有同一 run 的最新成功校验、匹配的 `plan_hash` 和新写幂等键可进入 `create_workflow_draft`；结果为 DRAFT 后停止。
