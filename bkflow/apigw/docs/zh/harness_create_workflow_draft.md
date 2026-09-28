### Harness P0：创建或更新工作流草稿

#### 接口说明

`harness_create_workflow_draft` 是 `BKFlow Workflow Harness MCP` 的 P0 写 Tool。它只将同一 run 的最新成功校验修订写入一个受管理的模板草稿；首次创建与后续修订更新同一模板 ID，永远不会自动发布。

#### 请求方法

POST `/space/{space_id}/harness/create_workflow_draft/`

#### 租户边界

开启多租户时，全租户应用必须传 `X-Bk-Tenant-Id` 请求头；单租户应用可省略并使用已认证应用租户。应用本次请求租户、已认证用户租户和路由空间租户必须一致，Body 中的身份字段不能覆盖此边界。关闭多租户时忽略该请求头。

#### 可信字段与不可信字段

平台应用、真实用户、空间、Scope、环境、风险策略和 MCP contract `1.0.0` 只由认证网关、路由 `{space_id}` 和服务端 Harness 部署绑定决定。Body 不可伪造或覆盖这些字段，也不可提交 `auto_release`、平台身份、策略、MCP、令牌或凭证；未知字段全部拒绝并且不会进入审计或响应。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| run_id | uuid | 是 | 已由可信上下文拥有的 Harness run。 |
| revision_id | uuid | 是 | 待写入的不可变校验修订。 |
| plan_hash | string | 是 | 最长 64，必须等于该修订及最新成功校验结果。 |
| idempotency_key | string | 是 | 最长 255；相同 canonical 请求 exactly-once，相同键不同请求返回冲突。 |

#### 响应 Envelope 与错误

无论成功或失败，顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。成功 Artifact 仅含模板/草稿公开引用与树哈希；每个错误固定包含 `category`、`code`、`message`、`path`、`repairable`、`suggested_action`、`retryable`。分类仅可能为 `USER_INPUT`、`CAPABILITY_NOT_FOUND`、`AMBIGUOUS_CAPABILITY`、`SCHEMA_DRIFT`、`VALIDATION`、`PERMISSION`、`APPROVAL_REQUIRED`、`APPROVAL_INVALID`、`TOKEN_LEASE`、`DEBUG_CONFLICT`、`RUNTIME`、`POSTCONDITION`、`RETRYABLE_INFRA`。

`VALIDATION_STALE`/`SCHEMA_DRIFT` 表示必须重新校验；`RETRYABLE_INFRA` 可用相同 `idempotency_key` 重试。任何失败都不会留下部分模板、快照或 Artifact。

#### 请求示例

```json
{
  "run_id": "<run_id>",
  "revision_id": "<revision_id>",
  "plan_hash": "<plan_hash>",
  "idempotency_key": "draft-restart-v1"
}
```

#### P0 边界

草稿只接受已经由受治理 Schema 读取和 `validate_workflow` 固化的计划；Agent 不得用 raw code、版本或来源字段绕过搜索卡片的 `capability_ref` 与 Schema 哈希门禁。

该接口只产生版本为空的 managed DRAFT，不触发 release、debug、任务创建、执行、SDK 调用或令牌签发。Agent 报告 DRAFT 后必须停止，后续发布与执行仅属于更高阶段的独立 Tool allowlist。
