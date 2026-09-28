### Harness P3：查询工作流执行

#### 接口说明

`harness_get_workflow_execution` 对应 MCP Tool `get_workflow_execution`，属于 `BKFlow Workflow Harness MCP` contract `1.3.0`。它查询服务端持久化状态，并在执行开关开启时从 Engine 进行有界、安全的状态与后置条件读回；开关关闭时保持 persistence-only，零 Engine/provider 调用和零写入。

#### 请求方法

POST `/space/{space_id}/harness/get_workflow_execution/`

#### 租户边界

开启多租户时，全租户应用必须传 `X-Bk-Tenant-Id` 请求头；单租户应用可省略并使用已认证应用租户。应用本次请求租户、已认证用户租户和路由空间租户必须一致，Body 中的身份字段不能覆盖此边界。关闭多租户时忽略该请求头。

#### 可信字段与不可信字段

平台应用、真实用户、空间、Scope、环境、策略和 contract 是可信字段。Body 中的身份、空间、task 引用、节点输出、SDK、Token 和密钥是不可信字段；调用方只能提交 Harness 分配的 execution_id。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| execution_id | uuid | 是 | 当前可信上下文拥有的执行。 |
| limit | integer | 否 | Evidence 页大小，1–100，默认 20。 |
| cursor | string | 否 | 最长 512 的不透明游标。 |

#### 响应 Envelope

Envelope 顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。输出只投影发布快照声明的节点、状态、后置条件摘要与 Evidence，不返回原始 detail/history/ex_data，响应不超过 64 KiB。

#### 恢复语义

`START_UNCERTAIN` 与 `CONTROL_UNCERTAIN` 都只能经本 Tool 的可信 readback 收敛或进入人工核对，不能由 Agent 猜测成功后重派。Webhook 缺少可信 correlation 时固定 `UNAVAILABLE`，不会按 task id 猜测。
