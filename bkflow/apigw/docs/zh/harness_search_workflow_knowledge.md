### Harness P1：检索联邦流程知识

传输参数校验失败统一返回 `SCHEMA_VALIDATION_ERROR`；`path` 仅引用服务端声明字段（无法安全定位时为 `request`），修复动作是 `repair_tool_arguments`，不回显原始参数或未知字段名。业务拒绝的错误分类及治理动作保持不变。

#### 接口说明

`harness_search_workflow_knowledge` 是 `BKFlow Workflow Harness MCP` 在 contract `1.1.0` 增加的第 5 个只读 Tool。它按照可信平台、空间和 Scope 选择已经启用的外部知识源，返回带来源、快照、信任等级和 citation 的流程经验；BKFlow 只维护路由绑定与审计，不保存完整知识正文或向量索引。

#### 请求方法

POST `/space/{space_id}/harness/search_workflow_knowledge/`

#### 租户边界

开启多租户时，全租户应用必须传 `X-Bk-Tenant-Id` 请求头；单租户应用可省略并使用已认证应用租户。应用本次请求租户、已认证用户租户和路由空间租户必须一致，Body 中的身份字段不能覆盖此边界。关闭多租户时忽略该请求头。

#### 可信字段与不可信字段

应用、真实用户、路由空间、平台、Scope、环境、策略、关联 ID 和 MCP contract 只能由认证网关、路径 `{space_id}` 与服务端部署绑定生成。接口要求应用认证、用户认证和 APIGW 资源授权同时通过，并且总开关、contract `1.1.0` 与 P1 知识开关均已启用。

Body 仅接受下列查询数据。任何 `actor`、`platform`、`app`、`space`、`scope`、`environment`、`policy`、`contract`、`correlation`、令牌或凭证字段都会作为不可信字段被拒绝，不能改变路由和访问控制。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| query | string | 是 | 非空查询，最多 2000 字符，并受请求总字节数限制。 |
| top_k | integer | 否 | 1–20，默认 10；每个知识源还能设置更小的上限。 |
| run_id | uuid | 否 | 仅关联当前完整可信上下文拥有的 Harness run；跨空间、Scope、用户或 contract 的 run 会被拒绝。 |
| data_classification | string | 否 | 最多 64，默认 `internal`；用于检索前的数据分级门禁。 |
| client_context | object | 否 | 只允许非敏感的 `conversation_ref` 与 `agent_release`，不参与身份和 ACL 决策。 |

#### ACL-before-retrieval 与知识治理

Provider 调用前先按状态、信任、有效期、环境、应用、用户、数据分级和完整可信上下文过滤绑定，禁止先跨库搜索再过滤结果。有效层级为 Global、Public、Platform、Space、Scope；业务建议的优先级为 `Scope > Space > Platform > Public`，Global 硬规则仍必须由 Validator/Policy 代码落实。

知识命中始终带 `policy_effect=ADVISORY`。知识内容、恶意指令或高分结果都不能修改 Tool allowlist、可信身份、插件 Schema、Validator、Policy 或执行权限。每个命中返回脱敏摘要、source、snapshot、trust、适用范围和稳定 citation；同主题冲突返回非执行性的冲突标注。

#### 响应 Envelope、64 KiB 与错误

无论成功或失败，顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。命中、冲突标注、外置结果引用与告警位于 `artifact_refs` 的 `knowledge_search` 工件内，工件及命中均明确为 `ADVISORY`。

最终十字段 JSON Envelope 在 HTTP 返回前按当前请求协商出的 DRF renderer 实际输出字节复检，最大 64 KiB；JSON 转义与 `indent` 等媒体类型参数均计入预算，无法安全预渲染时按失败关闭。若内联命中过大，优先保留由服务端可信 Artifact Writer 产生的引用；否则返回明确的截断告警，不生成不可解析或悬空引用。检索审计在结果裁剪前独立落库，不会因响应压缩而丢失。

成功但无命中仍返回 `ok=true` 和空命中，不应当作基础设施错误重试。部分知识源失败时保留可用命中并返回有界告警；所有可用知识源都失败时返回规范化 `RETRYABLE_INFRA`，不反射 Provider 地址、异常、配置、正文或敏感值。contract `1.0.0`、P1 开关关闭、伪造身份和跨上下文 run 均在检索前拒绝。

#### 请求示例

```json
{
  "query": "服务重启流程有哪些前置检查",
  "top_k": 5,
  "data_classification": "internal",
  "client_context": {
    "conversation_ref": "conversation-opaque-ref",
    "agent_release": "bkaidev-harness-1.1"
  }
}
```

#### P1 边界

本 Tool 只返回辅助流程生成的业务知识，不搜索 MCP Tool Definition，不返回实时插件能力事实，也不执行插件、调试、发布、启动任务、签发 BKFlow Token 或写回知识。插件当前版本、Schema、权限和生命周期仍以 `search_workflow_capabilities`、`get_plugin_schema` 与后续 Validator 的实时结果为准。
