### Harness P0：获取精确插件 Schema

#### 接口说明

`harness_get_plugin_schema` 是 `BKFlow Workflow Harness MCP` 的 P0 只读 Tool。它只接受受治理搜索卡片的 opaque `capability_ref` 与卡片上的 Schema 哈希，服务端重新按 exact source、类型和版本获取已授权能力的完整 Schema；同 code 的 legacy 与 V4 来源不会互相通配。Schema 是生成数据，不是执行许可。

#### 请求方法

POST `/space/{space_id}/harness/get_plugin_schema/`

#### 可信字段与不可信字段

平台应用、真实用户、空间、Scope、环境、风险策略与 MCP contract `1.0.0` 仅从认证网关、路由 `{space_id}` 和服务端部署绑定取得。Body 只能转交搜索卡片，Agent 不得解码、构造或修改 `capability_ref`。不能传入或伪造平台、应用、用户、空间、Scope、环境、策略、MCP、令牌、凭证或 raw `code`、`version`、`plugin_type`、`source_key` 身份字段；未知字段一律拒绝。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| capability_ref | string | 是 | `search_workflow_capabilities` 卡片原样返回的 opaque 引用，最长 1799。 |
| expected_schema_hash | string | 是 | 同一搜索卡片的 64 位小写 SHA-256 Schema 哈希。 |

#### 响应 Envelope

无论成功或失败，顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。成功 Schema 位于 `artifact_refs`，只包含生成所需的公开输入输出与身份事实；服务器内部转换元数据不会返回。

每个错误固定包含 `category`、`code`、`message`、`path`、`repairable`、`suggested_action`、`retryable`。分类仅可能为 `USER_INPUT`、`CAPABILITY_NOT_FOUND`、`AMBIGUOUS_CAPABILITY`、`SCHEMA_DRIFT`、`VALIDATION`、`PERMISSION`、`APPROVAL_REQUIRED`、`APPROVAL_INVALID`、`TOKEN_LEASE`、`DEBUG_CONFLICT`、`RUNTIME`、`POSTCONDITION`、`RETRYABLE_INFRA`。

#### 请求示例

```json
{
  "capability_ref": "cap_v1_eyJjb2RlIjoicmVzdGFydCIsInBsdWdpbl90eXBlIjoiY29tcG9uZW50Iiwic291cmNlX2tleSI6bnVsbCwidmVyc2lvbiI6IjEuMC4wIn0",
  "expected_schema_hash": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}
```

#### P0 边界

本 Tool 不创建 run，不接受 `idempotency_key` 或计划哈希，也不执行、调试、发布或运行插件。服务端每次读取都重新验证卡片引用的当前目录、ACL、生命周期、精确版本和 `expected_schema_hash`；调用方必须把返回的精确版本和 Schema 绑定到 a2flow，并由 `validate_workflow` 重新治理；草稿创建后仅报告 DRAFT 并停止。
