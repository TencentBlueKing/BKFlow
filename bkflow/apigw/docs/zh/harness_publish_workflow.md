### Harness P3：发布工作流

#### 接口说明

`harness_publish_workflow` 对应 MCP Tool `publish_workflow`，属于 `BKFlow Workflow Harness MCP` contract `1.3.0`。它以两次调用完成审批绑定：首次不带审批字段时只创建待审批申请；第二次携带对应申请与 opaque receipt 后，服务端重新复验 Manifest 和 DRAFT 快照，再原子发布。

#### 请求方法

POST `/space/{space_id}/harness/publish_workflow/`

#### 租户边界

开启多租户时，全租户应用必须传 `X-Bk-Tenant-Id` 请求头；单租户应用可省略并使用已认证应用租户。应用本次请求租户、已认证用户租户和路由空间租户必须一致，Body 中的身份字段不能覆盖此边界。关闭多租户时忽略该请求头。

#### 可信字段与不可信字段

平台应用、真实用户、空间、Scope、环境、策略和 contract 是可信字段，只从 APIGW 与服务端配置取得。Body 中的用户身份、模板 ID、审批结论、SDK、Token、密钥和策略文本是不可信字段；未知字段及不完整审批字段对一律拒绝。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| run_id / manifest_id | uuid | 是 | 精确 run 和 Manifest。 |
| manifest_hash | 64 位小写十六进制 | 是 | 防止调用方基于过期 Manifest 发布。 |
| version / description | string | 是 | 版本最长 32，描述最长 255。 |
| idempotency_key | string | 是 | 最长 255；可选请求头只能与 Body 完全一致。 |
| approval_request_id / approval_receipt_ref | uuid / opaque ref | 第二次调用必填 | 只能成对出现；回执原文不会返回或落入 Evidence。 |

#### 响应 Envelope

Envelope 顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。待审批时，严格 UUID 的申请标识只投影为 `approval_request` Artifact，不新增第 11 个顶层键；回执明文不会回显。响应上限为 64 KiB。

#### 边界

发布只接受服务端绑定的 Manifest、唯一 DRAFT 快照和当前能力事实，Harness 禁止 force。生产审批 verifier、durable replay guard、`ReleasePolicy` 与发布回调的真实联调仍未验证，缺失时固定 deny。
