### Harness P2：读取调试会话

传输参数校验失败统一返回 `SCHEMA_VALIDATION_ERROR`；`path` 仅引用服务端声明字段（无法安全定位时为 `request`），修复动作是 `repair_tool_arguments`，不回显原始参数或未知字段名。业务拒绝的错误分类及治理动作保持不变。

#### 接口说明

`harness_get_debug_session` 对应 MCP Tool `get_debug_session`，属于 `BKFlow Workflow Harness MCP` contract `1.2.0`。它读取 BKFlow 持久化的确定性 Session/Evidence，并在调试开关开启时只归并与本 Session `current_task_id` 精确匹配的 Engine 状态。

#### 请求方法

POST `/space/{space_id}/harness/get_debug_session/`

#### 租户边界

开启多租户时，全租户应用必须传 `X-Bk-Tenant-Id` 请求头；单租户应用可省略并使用已认证应用租户。应用本次请求租户、已认证用户租户和路由空间租户必须一致，Body 中的身份字段不能覆盖此边界。关闭多租户时忽略该请求头。

#### 可信字段与不可信字段

APIGW 应用、用户、路径空间、Scope、环境与 Session 归属是可信字段。Body 仅允许 `session_id`、`limit`、`cursor`；Body 身份、Token、任意模板历史或 Engine task ID 都是不可信字段并拒绝。读请求不接受幂等请求头。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| session_id | uuid | 是 | 必须由当前可信上下文拥有。 |
| limit | integer | 否 | 1 至 100，默认 20。 |
| cursor | safe opaque string | 否 | 按 `(occurred_at,id)` 稳定翻页当前 Session 的 Evidence。 |

#### 响应 Envelope

Envelope 顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。上下文、节点状态和 Evidence 均经过有界深度脱敏；历史页还受累计 UTF-8 字节预算限制，`next_cursor` 只指向实际纳入的最后一项。

调试 feature flag 关闭时，本 Tool 仍可读取已持久化的 Session 与 Evidence，但不会解析 capability、访问插件目录、调用 Template DebugService、Engine 或 Token Broker，也不会做终态化或写 Evidence。生命周期清理由服务端 reaper 负责。

#### 请求示例

```json
{
  "session_id": "<session_id>",
  "limit": 20
}
```

#### 边界

BKFlow 维护确定性 Session/Evidence，但不调用 LLM；BKAIDev Agent 直接选择公开 Tool。Token 对 Agent 不可见，响应不会泄露共享模板的其他会话历史或旧 DebugContext 原值。
