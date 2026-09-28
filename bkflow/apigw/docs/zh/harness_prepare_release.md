### Harness P3：准备发布清单

#### 接口说明

`harness_prepare_release` 对应 MCP Tool `prepare_release`，属于 `BKFlow Workflow Harness MCP` contract `1.3.0`。它只读重转并复验已完成全局调试的 DRAFT，生成绑定 Revision、能力版本、树指纹、风险和后置条件的不可变 Manifest，不发布流程。

#### 请求方法

POST `/space/{space_id}/harness/prepare_release/`

#### 可信字段与不可信字段

平台应用、真实用户、空间、Scope、环境、策略和 contract 都来自 APIGW 认证、路径和服务端部署。Body 中的身份、空间、模板、策略、SDK、Token 和原始能力配置均是不可信字段；未知字段一律拒绝。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| run_id | uuid | 是 | 当前可信上下文拥有的 Harness run。 |
| revision_id | uuid | 是 | run 的最新成功校验 Revision。 |
| expected_plan_hash | 64 位小写十六进制 | 是 | 调用方看到的计划版本。 |
| idempotency_key | string | 是 | 最长 255；同键同请求重放，同键异请求冲突。 |

#### 响应 Envelope

成功与失败的 Envelope 顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。Artifact 只含 Manifest 等安全引用，不含流程树、密钥、审批回执或 SDK 参数；完整响应最多 64 KiB。

#### 调用顺序与门禁

标准链路是 `prepare → approve → publish → start → poll/control → poll`。当前仓库没有可验证的生产 `ReleasePolicy` provider；未配置可信策略时本 Tool fail closed。真实 BKAIDev 挂载、审批和 Engine 联调仍属于外部门禁，功能开关默认不启用。
