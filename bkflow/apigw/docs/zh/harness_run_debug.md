### Harness P2：执行单步或全局调试

传输参数校验失败统一返回 `SCHEMA_VALIDATION_ERROR`；`path` 仅引用服务端声明字段（无法安全定位时为 `request`），修复动作是 `repair_tool_arguments`，不回显原始参数或未知字段名。业务拒绝的错误分类及治理动作保持不变。

#### 接口说明

`harness_run_debug` 对应 MCP Tool `run_debug`，属于 `BKFlow Workflow Harness MCP` contract `1.2.0`。它以 tagged request 执行单步或全局调试；默认且推荐使用 Mock。

#### 请求方法

POST `/space/{space_id}/harness/run_debug/`

#### 租户边界

开启多租户时，全租户应用必须传 `X-Bk-Tenant-Id` 请求头；单租户应用可省略并使用已认证应用租户。应用本次请求租户、已认证用户租户和路由空间租户必须一致，Body 中的身份字段不能覆盖此边界。关闭多租户时忽略该请求头。

#### 可信字段与不可信字段

平台应用、用户、空间、Scope、环境、策略、当前 Schema 和 TokenLease 都是服务端可信字段。Agent 提交的 mode、node、inputs、mock 结果及 approval receipt 引用是不可信字段，必须经过闭集、大小、秘密检测和会话归属校验；未知字段拒绝。

公共字段为 `session_id`、`expected_plan_hash`、`mode`、`execution_mode`、`idempotency_key`。`step` 分支还接受 `node_id`、`input_overrides`、`mock_result`、`mock_outputs`、`mock_error`，real step 可带服务端可验证的 `approval_receipt_ref`。global 请求只接受 `inputs` 作为分支字段；节点 Mock 决策必须先通过 `control_debug_session` 的 `set_node_mock` 写入当前 Session，`run_debug` 不接受每次运行临时提交的节点 Mock 方案。

#### 执行策略

- Mock 是默认模式；global real 明确禁止，所有可执行节点必须有 Mock 决策。
- real step 同时需要空间 real-step 开关、策略允许、服务端验证通过且 claims 精确匹配的 approval receipt，以及 Token Broker 签发并绑定本会话的 live MOCK TokenLease。缺少任一条件都会在 DebugService 前失败。
- Token 只在 BKFlow 服务端授权域内使用，对 BKAIDev Agent 不可见，也不会作为 SDK 参数、Artifact 或日志字段返回。
- 全局调试采用 fast acknowledgement + poll：Engine 接受后可能立即返回 `RUNNING`，调用方随后使用 `get_debug_session` 收敛状态，不把异步接受误报为完成。

#### 响应 Envelope

Envelope 顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。outputs、global vars、gateway 结果与错误只返回有界深度脱敏投影；超预算时只返回 omission 元数据，不制造不可读取的 Artifact URI。

#### Mock 请求示例

```json
{
  "session_id": "<session_id>",
  "expected_plan_hash": "<plan_hash>",
  "mode": "step",
  "execution_mode": "mock",
  "node_id": "node_a",
  "input_overrides": {},
  "mock_result": "success",
  "mock_outputs": {"result": "ok"},
  "mock_error": "",
  "idempotency_key": "run-step-v1"
}
```

#### 边界

只有与最新校验 Revision 和当前 managed DRAFT 完全一致的 active Session 可运行。`idempotency_key` 的持久派发屏障阻止相同会话因换 key 或跨 control Tool 重复触发外部副作用。
