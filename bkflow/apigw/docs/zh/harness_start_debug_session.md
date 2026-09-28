### Harness P2：建立调试会话

#### 接口说明

`harness_start_debug_session` 对应 MCP Tool `start_debug_session`，属于 `BKFlow Workflow Harness MCP` contract `1.2.0`。它把已校验的最新 Revision、managed DRAFT 与画布树指纹绑定成一个服务端 `DebugSession`，但不执行节点、不创建 Engine task。

#### 请求方法

POST `/space/{space_id}/harness/start_debug_session/`

#### 租户边界

开启多租户时，全租户应用必须传 `X-Bk-Tenant-Id` 请求头；单租户应用可省略并使用已认证应用租户。应用本次请求租户、已认证用户租户和路由空间租户必须一致，Body 中的身份字段不能覆盖此边界。关闭多租户时忽略该请求头。

#### 可信字段与不可信字段

平台应用、真实用户、空间、Scope、环境、策略版本与 contract 只来自 APIGW 身份、路径 `{space_id}` 和服务端部署配置。Body 中的身份、空间、插件 Schema、SDK Token、策略字段均是不可信字段，未知字段一律拒绝。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| run_id | uuid | 是 | 可信上下文拥有的 Harness run。 |
| revision_id | uuid | 是 | 必须是 run 的最新成功校验 Revision。 |
| expected_plan_hash | 64 位小写十六进制 | 是 | 必须与 Revision、ValidationReport 和 DRAFT 一致。 |
| mode | step / global | 是 | 固化会话意图，不启动执行。 |
| idempotency_key | string | 是 | 最长 255；同键同请求完整重放，同键异请求冲突。可选请求头只能与其完全一致。 |

服务端会重新解析当前 capability/schema binding，核对 managed DRAFT 的 template、revision、plan hash 和实际树指纹，并建立干净的调试上下文，避免复用旧会话的 global vars、节点输出或用户级 mock。

#### 响应 Envelope

成功与失败的 Envelope 顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。成功 Artifact 仅返回会话 ID、输入 Schema、节点 readiness、树指纹及安全引用；Token 不会出现在 Agent 请求、响应、Evidence 或日志中。

#### 请求示例

```json
{
  "run_id": "<run_id>",
  "revision_id": "<revision_id>",
  "expected_plan_hash": "<plan_hash>",
  "mode": "step",
  "idempotency_key": "start-debug-v1"
}
```

#### 边界

仅 `DRAFT_READY` 且归属、Revision、Schema 和树事实全部一致时可进入 `DEBUGGING`。本 Tool 不让 BKAIDev Agent 直接调用画布 SDK，也不触发真实插件执行。
