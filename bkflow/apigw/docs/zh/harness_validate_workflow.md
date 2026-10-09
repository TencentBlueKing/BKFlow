### Harness P0：校验受治理的工作流

#### 接口说明

`harness_validate_workflow` 是 `BKFlow Workflow Harness MCP` 的 P0 写 Tool。它先按可信上下文重新解析所有绑定，再校验、转换并持久化不可变修订与 ValidationReport；它不发布、调试或执行流程。

#### 请求方法

POST `/space/{space_id}/harness/validate_workflow/`

#### 租户边界

开启多租户时，全租户应用必须传 `X-Bk-Tenant-Id` 请求头；单租户应用可省略并使用已认证应用租户。应用本次请求租户、已认证用户租户和路由空间租户必须一致，Body 中的身份字段不能覆盖此边界。关闭多租户时忽略该请求头。

#### 可信字段与不可信字段

认证网关、路由 `{space_id}` 与服务端 Harness 部署绑定拥有平台应用、真实用户、空间、Scope、环境、风险策略和 MCP contract `1.0.0`。Body 不得提供 `platform`、`app`、`user`、`space`、`scope`、`environment`、`policy`、`mcp` 或任何令牌/凭证字段；未知字段会被拒绝，服务端不会回显敏感信息。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| intent_spec | object | 是 | 有界的意图与约束 DTO。 |
| a2flow | object | 是 | 网关 Schema 已展开 v2 的 nodes/next/inputs、变量与失败策略；不是底层 pipeline_tree 或画布 JSON。 |
| bindings | array | 是 | 闭合的能力绑定 DTO。 |
| idempotency_key | string | 是 | 最长 255；相同键与相同 canonical 请求仅返回同一结果。 |
| run_id | uuid | 否 | 后续修订指定既有 run；首次可由本操作隐式创建。 |
| expected_plan_hash | string | 否 | 最长 64；断言本次计算出的计划哈希。没有预期值时省略，不传 null。 |
| client_context | object | 否 | 仅可含非敏感 `conversation_ref` 与 `agent_release`。 |

#### 响应 Envelope 与错误

无论成功或失败，顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。每个错误固定包含 `category`、`code`、`message`、`path`、`repairable`、`suggested_action`、`retryable`，分类仅可能为 `USER_INPUT`、`CAPABILITY_NOT_FOUND`、`AMBIGUOUS_CAPABILITY`、`SCHEMA_DRIFT`、`VALIDATION`、`PERMISSION`、`APPROVAL_REQUIRED`、`APPROVAL_INVALID`、`TOKEN_LEASE`、`DEBUG_CONFLICT`、`RUNTIME`、`POSTCONDITION`、`RETRYABLE_INFRA`。

`SCHEMA_DRIFT` 表示精确版本、来源或 Schema 已变化；`RETRYABLE_INFRA` 才允许以相同 `idempotency_key` 重试。修复必须以新的 revision 再次校验，不能覆盖已验证修订。

#### 请求示例

以下是合法的编排结构示例（两个串行暂停节点）。先检索暂停能力，再获取精确插件 Schema；替换示例 binding 的引用和哈希，并按实时 Schema 核对 `description`。占位引用不是可直接调用的能力或授权。

```json
{
  "intent_spec": {"goal": "生成两个串行暂停节点，只创建草稿"},
  "a2flow": {
    "version": "2.0",
    "name": "串行暂停示例",
    "nodes": [
      {"id": "check_1", "type": "Activity", "name": "检查一", "inputs": {"description": "检查一"}, "next": "check_2"},
      {"id": "check_2", "type": "Activity", "name": "检查二", "inputs": {"description": "检查二"}, "next": "end"}
    ]
  },
  "bindings": [
    {"node_id": "check_1", "capability_ref": "<search 返回的引用>", "schema_hash": "<get_plugin_schema 确认的 64 位哈希>", "credential_ref": null},
    {"node_id": "check_2", "capability_ref": "<search 返回的引用>", "schema_hash": "<get_plugin_schema 确认的 64 位哈希>", "credential_ref": null}
  ],
  "idempotency_key": "validate-pause-v1"
}
```

`type` 是编排类型，不是 `pause_node` 等插件 code，也不是引擎内部的 `ServiceActivity`。默认类型为 `Activity`，也支持 `SubProcess`、`StartEvent`、`EndEvent`、四类网关。普通节点通过 `next` 连线，末节点指向 `end`；开始和结束事件可自动补齐。不要发送 `edges`、`config`、`position` 或 `label`；节点参数用 `inputs`，名称用 `name`，布局由服务端生成。

编排协议与按需检索的插件输入 Schema 是两层契约，都不依赖业务知识库。知识库提供案例或领域经验，不应作为获取基本协议的唯一途径。当前仍为 15 个 Harness Tool，本次未增加独立的协议 Tool。

#### P0 边界

网关 Tool Schema 明确声明 `bindings` 为至多 100 项的闭合对象数组。每项必须包含 `node_id`、`capability_ref`、64 位小写 `schema_hash`、`credential_ref` 四个键；不需要凭证时显式传 `credential_ref: null`。非空值只能使用服务端已有的受治理凭证引用，格式以 Tool Schema 为准，不得放入密钥或令牌，引用本身也不构成授权。

Activity 可以省略 `code` 和 `plugin_type`：服务端以该节点的精确 `capability_ref` binding 重新校验目录授权、版本和 Schema 后补齐并持久化身份；无需客户端解码引用或猜测插件 code。若显式传入，必须与解析后的身份一致，否则仍返回 `SCHEMA_DRIFT`。缺失 binding、未授权或 Schema 漂移仍然拒绝。

传输参数校验失败的 `path` 仅引用已声明字段（否则为 `request`），`suggested_action` / `next_actions` 为 `repair_tool_arguments`；业务流程校验失败仍使用对应领域修复动作。内部异常只在服务端保留有界代码坐标和 `correlation_id`，不记录原始请求、异常文案或局部变量。

能力 Binding 的 `capability_ref` 必须来自受治理搜索卡片；精确 Schema 读取只向 `get_plugin_schema` 传递该卡片的 `capability_ref` 与 `schema_hash`，不得使用 raw code、版本或来源字段重建身份。

校验成功不等于模板发布或执行成功。只有同一 run 的最新成功校验、匹配的 `plan_hash` 和新写幂等键可进入 `create_workflow_draft`；结果为 DRAFT 后停止。

#### HTTP 公开 Header 输入边界

仅当精确 binding 重新授权为内置 `component / bk_http_request`，且字段符合实时 Schema 时，允许在节点的 `inputs`（或兼容字段 `data`）中传入 `bk_http_request_header`。其他插件、意图、全局变量及任意嵌套位置不享受该例外。

Header 必须是闭合的 `{name, value}` 对象数组；也支持 `{hook: false, value: [...]}` 包装，`need_render` 可选且必须是布尔值。名称大小写不敏感，仅允许：`Accept`、`Accept-Language`、`Content-Type`、`Content-Language`、`Cache-Control`、`X-Test-Case`、`X-Request-Id`、`X-Correlation-Id`。值必须是公开的字面字符串；拒绝控制字符、动态变量/模板、敏感文本及额外字段，原有深度、项数和总字节数上限不变。

```json
{"bk_http_request_header": [{"name": "Content-Type", "value": "application/json"}]}
```

不开放任意 `X-*` 名称。`Authorization`、`Cookie`、网关认证头、自定义密钥头及令牌不得随模型输入传入；需经服务端受治理的凭证机制处理。本例外不会自动给 HTTP 插件增加凭证注入能力，也不允许执行请求。

#### 可修复规则与画布证据

| 错误码 | 修复方式 |
|---|---|
| A2FLOW_NODE_TYPE_INVALID | 按 `path` 定位节点，改用 `Activity` 等编排类型；插件身份通过 binding 指定。 |
| BINDING_FIELD_REQUIRED | 补齐指出的必填字段；无需凭证时保留 `credential_ref: null`。 |
| BINDING_NODE_MISMATCH | 每个 Activity 恰好对应一个 binding，其他类型不得绑定；检查 node_id 与节点 id。 |
| BINDING_NODE_DUPLICATE | 删除路径所指的重复 binding，保留每个 Activity 的唯一绑定。 |
| FAILURE_STRATEGY_CONFLICT | 自动跳过、自动重试、超时控制至多启用一项。 |
| FAILURE_STRATEGY_INVALID_COMBO | 自动跳过时关闭手动重试/跳过；自动重试时关闭手动重试。 |
| SUBPROCESS_DRAFT_NOT_ALLOWED | 选择同空间、同 Scope 的已发布子流程；不得为了修复候选流程而自动发布草稿。 |
| HOOK_REFERENCE_INVALID | `hook=true` 的表达式只使用已声明的纯变量引用，如 `${variable}`；不支持与字面文本混合。 |

上述错误仅返回服务端白名单文案和安全字段路径，不回显转换器异常、输入值或内部细节。修复后使用新幂等键再次校验。

受治理转换结果包含完整 `location`、`line`，与逻辑节点、边一起参与 `pipeline_tree_hash`；`plan_hash` 仍描述 canonical a2flow、能力绑定和可信策略。布局实现版本计入转换器指纹。升级前的校验不能直接作为新布局的验收证据：遇到 `VALIDATION_STALE`，须重新校验，而不是绕过哈希检查。
