### Harness P3：控制工作流执行

#### 接口说明

`harness_control_workflow_execution` 对应 MCP Tool `control_workflow_execution`，属于 `BKFlow Workflow Harness MCP` contract `1.3.0`。它接受 `pause`、`resume`、`revoke`、`retry`、`skip`、`callback`、`forced_fail`、`skip_exg`、`skip_cpg` 九种闭合集合动作；每次动作均绑定审批、幂等 barrier 和 Evidence journal。

#### 请求方法

POST `/space/{space_id}/harness/control_workflow_execution/`

#### 可信字段与不可信字段

平台应用、真实用户、空间、Scope、环境、策略、Publication/DRAFT 快照和 contract 是可信字段。Body 中的 task 引用、runtime node、operator、SDK、Token、密钥、低层开关与审批结论是不可信字段，均禁止提交。模板节点由服务端映射到运行时节点。

所有动作必填 `execution_id`、`expected_manifest_hash`、`action`、`idempotency_key`；第二次审批调用再成对增加 `approval_request_id` 和 `approval_receipt_ref`。节点动作使用 `template_node_id`；`retry`/`skip` 还必须提供严格 boolean `loop`；`forced_fail` 只接受服务端枚举 `operator_requested`；gateway 动作仅接受显式 template flow 字段。未知或跨 tag 字段一律拒绝。

#### 响应 Envelope

Envelope 顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。审批申请只作为安全 Artifact 返回，回执、callback_data、inputs、Engine 正文和异常不会回显或写入 Evidence；响应不超过 64 KiB。

#### 风险与恢复

pause/resume/revoke/retry 为 L2；skip/callback/forced_fail/gateway 为 L3，审计按实际 tag 记录，不得降级。当前 callback 缺能力专属 Schema、gateway 缺模板流到运行时流 provenance，固定 deny。Engine ack 仍产生 `CONTROL_UNCERTAIN`，随后只由 `get_workflow_execution` poll/readback 收敛，禁止自动重派。SDK/token path 固定 deny。
