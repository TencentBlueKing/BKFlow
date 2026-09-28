### Harness P4：提交生成反馈

#### 接口说明

`harness_submit_generation_feedback` 对应 `BKFlow Workflow Harness MCP` contract `1.4.0` 的第 15 个 Tool `submit_generation_feedback`，累计恰好 `15 Tools`。它把用户对既有 Run/Revision 的评价记录为不可信 Evidence，不自动学习，不直接修改线上知识、Registry、Validator、Prompt 或 Skill，也不会直接生成或晋级候选。

#### 请求方法

POST `/space/{space_id}/harness/submit_generation_feedback/`

#### 可信字段与不可信字段

平台应用、真实用户、空间、Scope、环境、策略和 contract 都来自 APIGW 认证、路径及服务端部署，是可信字段。Body 只表达反馈观察；其中摘要、评分、观测结果、纠正工件引用和 consent 用途均是不可信字段，入库前要经过归属校验、大小限制和强制脱敏。Body 不能指定身份、Owner、Reviewer、候选状态、目标系统、目标知识层级、发布或回滚结果，未知字段一律拒绝。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| run_id | uuid | 是 | 当前可信上下文拥有的 Harness Run。 |
| revision_id | uuid | 是 | Run 内已存在的不可变 Revision。 |
| expected_plan_hash | 64 位小写十六进制 | 是 | 调用方看到的计划版本。 |
| feedback_type | enum | 是 | `ACCEPTED`、`REJECTED`、`CORRECTION`、`RUNTIME_ISSUE` 或 `BUSINESS_OUTCOME`。 |
| consent_scope | string | 是 | 最长 64；必须被服务端已批准的 retention/consent 策略覆盖。 |
| idempotency_key | string | 是 | 最长 255；同键同请求重放，同键异请求冲突。 |
| rating | integer | 否 | 1 到 5。 |
| summary | string | 否 | 最长 4096 字符；敏感片段脱敏后保存。 |
| correction_artifact_ref | opaque ref | 否 | 必须属于该 Run；凭证 URI 与未拥有引用拒绝。 |
| execution_id | uuid | 否 | 必须属于同一 Run 与 Revision。 |
| observed_outcome | JSON | 否 | 有界 JSON；敏感键和值强制脱敏。 |

可选请求头 `X-Idempotency-Key` 如存在，必须与 Body `idempotency_key` 完全一致。

#### 响应 Envelope

成功与失败的 Envelope 顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。成功只返回反馈和 Evidence 的安全引用，不回显反馈正文或敏感值；完整响应最多 64 KiB。

#### 闭环与门禁

反馈保存不等于候选成立。确定性归因、候选 DRAFT、Owner/Reviewer 审核、Eval、外部发布回执、精确 readback 与 rollback 都在 Owner 控制面闭环，不是 Agent Tool。当前生产 retention 策略默认关闭；只有目标空间同时启用 `harness_feedback_enabled`，且 consent、保存期限和删除政策已被批准时才允许摄入。外部知识发布和 BKAIDev 固定 Release 评测证据未完成时保持阻断。
