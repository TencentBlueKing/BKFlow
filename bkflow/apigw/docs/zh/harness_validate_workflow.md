### Harness P0：校验受治理的工作流

#### 接口说明

`harness_validate_workflow` 是 `BKFlow Workflow Harness MCP` 的 P0 写 Tool。它先按可信上下文重新解析所有绑定，再校验、转换并持久化不可变修订与 ValidationReport；它不发布、调试或执行流程。

#### 请求方法

POST `/space/{space_id}/harness/validate_workflow/`

#### 租户边界

开启多租户时，全租户应用必须传 `X-Bk-Tenant-Id` 请求头；单租户应用可省略并使用已认证应用租户。应用本次请求租户、已认证用户租户和路由空间租户必须一致，Body 中的身份字段不能覆盖此边界。关闭多租户时忽略该请求头。

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

以下仅展示外层结构；空 `nodes` 会被拒绝，不是成功校验样例。实际调用须先检索能力、获取精确 Schema，构建 Activity 与一一对应的 binding。

```json
{
  "intent_spec": {"goal": "restart safely"},
  "a2flow": {"version": "2.0", "name": "restart", "nodes": []},
  "bindings": [],
  "idempotency_key": "validate-restart-v1"
}
```

#### P0 边界

网关 Tool Schema 明确声明 `bindings` 为至多 100 项的闭合对象数组。每项必须包含 `node_id`、`capability_ref`、64 位小写 `schema_hash`、`credential_ref` 四个键；不需要凭证时显式传 `credential_ref: null`。非空值只能使用服务端已有的受治理凭证引用，格式以 Tool Schema 为准，不得放入密钥或令牌，引用本身也不构成授权。

Activity 可以省略 `code` 和 `plugin_type`：服务端以该节点的精确 `capability_ref` binding 重新校验目录授权、版本和 Schema 后补齐并持久化身份；无需客户端解码引用或猜测插件 code。若显式传入，必须与解析后的身份一致，否则仍返回 `SCHEMA_DRIFT`。缺失 binding、未授权或 Schema 漂移仍然拒绝。

传输参数校验失败的 `path` 仅引用已声明字段（否则为 `request`），`suggested_action` / `next_actions` 为 `repair_tool_arguments`；业务流程校验失败仍使用对应领域修复动作。内部异常只在服务端保留有界代码坐标和 `correlation_id`，不记录原始请求、异常文案或局部变量。

能力 Binding 的 `capability_ref` 必须来自受治理搜索卡片；精确 Schema 读取只向 `get_plugin_schema` 传递该卡片的 `capability_ref` 与 `schema_hash`，不得使用 raw code、版本或来源字段重建身份。

校验成功不等于模板发布或执行成功。只有同一 run 的最新成功校验、匹配的 `plan_hash` 和新写幂等键可进入 `create_workflow_draft`；结果为 DRAFT 后停止。
