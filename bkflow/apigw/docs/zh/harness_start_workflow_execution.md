### Harness P3：启动工作流执行

#### 接口说明

`harness_start_workflow_execution` 对应 MCP Tool `start_workflow_execution`，属于 `BKFlow Workflow Harness MCP` contract `1.3.0`。它只从已发布 Publication 的不可变 DRAFT 来源快照创建并启动一个执行，采用可恢复的 create/start saga；创建与启动不会合并为一次不可恢复调用。

#### 请求方法

POST `/space/{space_id}/harness/start_workflow_execution/`

#### 可信字段与不可信字段

平台应用、真实用户、空间、Scope、环境、策略和 contract 是可信字段。Body 中的 task 引用、运行时节点、operator、SDK endpoint、Token、密钥和审批结论是不可信字段；服务端始终使用可信 actor，并重新解析当前能力及所需凭据。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| run_id / manifest_id / publication_id | uuid | 是 | 精确绑定发布事实。 |
| expected_plan_hash | 64 位小写十六进制 | 是 | 防止从过期计划启动。 |
| name | string | 是 | 最长 128。 |
| constants | object | 是 | 经过非秘密、有界校验的业务输入。 |
| idempotency_key | string | 是 | 最长 128；绑定一次逻辑执行。 |
| approval_request_id / approval_receipt_ref | uuid / opaque ref | 第二次调用必填 | 必须成对出现并绑定 start action digest。 |

#### 响应 Envelope

Envelope 顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。只返回 execution、Publication 和状态等安全引用；不返回 Engine 原始正文、Token、密钥或审批回执，响应不超过 64 KiB。

#### 恢复与门禁

`START_UNCERTAIN` 绝不盲目重派，BKAIDev Agent 必须调用 `get_workflow_execution` 刷新恢复。唯一生产路径是服务端 domain service；SDK/token path 固定 deny，直至 execution-aware issuer、consumer、撤销与真实 Engine correlation 证据齐备。
