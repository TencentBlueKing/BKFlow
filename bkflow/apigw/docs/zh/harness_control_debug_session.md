### Harness P2：控制调试会话

传输参数校验失败统一返回 `SCHEMA_VALIDATION_ERROR`；`path` 仅引用服务端声明字段（无法安全定位时为 `request`），修复动作是 `repair_tool_arguments`，不回显原始参数或未知字段名。业务拒绝的错误分类及治理动作保持不变。

#### 接口说明

`harness_control_debug_session` 对应 MCP Tool `control_debug_session`，属于 `BKFlow Workflow Harness MCP` contract `1.2.0`。它只接受 `reset`、`terminate`、`set_node_mock`、`set_context_var` 四类 tagged action。

#### 请求方法

POST `/space/{space_id}/harness/control_debug_session/`

#### 租户边界

开启多租户时，全租户应用必须传 `X-Bk-Tenant-Id` 请求头；单租户应用可省略并使用已认证应用租户。应用本次请求租户、已认证用户租户和路由空间租户必须一致，Body 中的身份字段不能覆盖此边界。关闭多租户时忽略该请求头。

#### 可信字段与不可信字段

应用、用户、空间、Scope、环境、策略、Revision、managed DRAFT 与 Session 归属是服务端可信字段。Body action、node/value 是不可信字段，必须经过闭集与安全 JSON 校验；不得提交 Token、SDK task ID、身份或策略覆盖字段。

| action | 额外字段 | 约束 |
|---|---|---|
| reset | node_ids（必填） | 重置显式列出的节点；空数组不重置节点；RUNNING 时拒绝。 |
| terminate | node_id（可选） | ACTIVE 时仅允许缺省并直接关闭 Session；RUNNING 时终止绑定 task 或其指定节点。 |
| set_node_mock | node_id、enabled、mock_result、mock_outputs、mock_error | 更新本 Session 的 Mock 决策。 |
| set_context_var | key、value | 写入有界、非秘密的调试上下文变量。 |

所有分支还必须提供 `session_id`、`expected_plan_hash` 与 `idempotency_key`。相同 key 同请求完整重放，相同 key 异请求冲突；可选请求头只能与 Body key 完全一致。

字段语义以闭集请求为准：reset 的 `node_ids` 必填，空数组不会重置任何节点；需要重置哪些节点就显式列出其 ID。terminate 的 `node_id` 可选：缺省时关闭 ACTIVE Session，或终止 RUNNING Session 绑定的 task；提供时仅适用于 RUNNING Session 的指定节点。set_node_mock 精确要求 `node_id`、`enabled`、`mock_result`、`mock_outputs`、`mock_error`，没有简写字段或隐式默认值。

terminate 的具体行为还取决于 Session 状态：

| Session 状态 | node_id | 服务端语义 |
|---|---|---|
| ACTIVE | 缺省 | 无 Engine task，直接关闭 Session。 |
| ACTIVE | 提供 | 拒绝；当前没有可终止的 active node。 |
| RUNNING | 缺省 | 终止当前 Session 绑定的 task。 |
| RUNNING | 提供 | 终止该 task 的指定节点。 |

因此，`node_id` 缺省不总是表示调用 Engine；ACTIVE Session 没有运行中 task 时会在完成撤权后直接进入终态。RUNNING Session 才会把终止动作限定到 `current_task_id`，不会接受 Agent 自行传入 task ID。

#### 生命周期与撤权

终止请求一旦被 Engine 接受为 `terminating`，就先撤销本 Session 的全部 active TokenLease，再等待 `get_debug_session` 收敛。过期处理同样先撤权；若 Engine 拒绝或 task 映射失败，Session 保持 `RUNNING` 和 `current_task_id` 以供恢复，但不会伪报成功。reset 成功后 Session 回到 active、run 回到 `DRAFT_READY` 所需的受控状态。

#### 响应 Envelope

Envelope 顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。失败只返回稳定错误 code/message 与安全状态，不透传 Engine 原始异常；成功 Artifact 也不会包含 Token。

#### 请求示例

```json
{
  "session_id": "<session_id>",
  "expected_plan_hash": "<plan_hash>",
  "action": "reset",
  "node_ids": ["node_a"],
  "idempotency_key": "reset-debug-v1"
}
```

#### 边界

control 前会重新验证最新 Revision、Schema、模板身份与树指纹。它不发布 managed DRAFT、不把 SDK 接口暴露给 Agent，也不允许 global real 执行。
