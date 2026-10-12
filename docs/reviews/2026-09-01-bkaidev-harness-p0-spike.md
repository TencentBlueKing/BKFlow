# BKAIDev P0 接入 Spike 证据矩阵

日期：2026-09-03
BKFlow 实施基线：`feat/a2flow@52f62d89d708da705ae000ab92a8b8b40eb7acc3`
状态：`BLOCKED_BY_EXTERNAL_EVIDENCE`（仅阻断 P0 发布门禁，不阻断普通 P0 MCP Tool 与服务端 Artifact 实现）

## 范围和判定规则

本 Spike 固化 BKAIDev SaaS 单智能体接入 `BKFlow Workflow Harness MCP` 的外部验证要求。P0 的固定 Tool allowlist 仅包含：`search_workflow_capabilities`、`get_plugin_schema`、`validate_workflow`、`create_workflow_draft`。业务插件作为搜索和精确 Schema 数据，不作为动态 MCP Tool。

本执行环境没有可用的 BKAIDev SaaS、已配置 MCP 连接或试点平台身份，因此下表不声称任何外部探针通过。`NOT_RUN_EXTERNAL` 表示尚未在真实 BKAIDev 连接中执行；`BLOCKED_BY_EXTERNAL_EVIDENCE` 表示该行缺少发布所需的真实平台证据。每项所列“清除证据”必须来自同一受控试点环境，并保留时间、Agent 发布版本、MCP contract version、连接标识和脱敏的调用关联标识。

| Probe ID | Input | Expected | Actual evidence | Pass | Decision impact |
|---|---|---|---|---|---|
| SP-01 | 在一个 BKAIDev SaaS Agent 的一个逻辑 MCP 连接中执行 List MCP tools。 | 仅显示四个 P0 Tool：`search_workflow_capabilities`、`get_plugin_schema`、`validate_workflow`、`create_workflow_draft`；没有直接插件执行、发布、调试或运行 Tool。 | `NOT_RUN_EXTERNAL` / `BLOCKED_BY_EXTERNAL_EVIDENCE`。清除证据：试点 Agent 的 Tool 配置导出或页面截图，以及一次 List MCP tools 调用的脱敏响应，二者均显示同一 MCP connection、四个名称和零个额外 P0 Tool。 | no — `NOT_RUN_EXTERNAL` | 确认 `mcp_adapter` 是否能由 BKAIDev 托管，并锁定 P0 Tool allowlist。 |
| SP-02 | 通过 `validate_workflow` 发送包含嵌套对象、数组、变量引用和 Capability Binding 的 a2flow；读取结构化 ValidationReport。 | MCP 请求和响应均保留嵌套 JSON 类型；a2flow 不被转成 JSON 字符串，也不发生字段丢失或类型漂移。 | `NOT_RUN_EXTERNAL` / `BLOCKED_BY_EXTERNAL_EVIDENCE`。清除证据：原始 MCP request/response 导出，外加 BKFlow 服务端接收记录的脱敏字段路径比对，证明嵌套对象、数组和标量类型在两端一致。 | no — `NOT_RUN_EXTERNAL` | 若失败，P0 请求封装或 MCP adapter 契约必须修订；不得以字符串化 a2flow 作为替代。 |
| SP-03 | 在至少五次连续 P0 Tool 调用中传递和回显同一 `run_id`、`revision_id`、`plan_hash` 与 `correlation_id`。 | 五个 Tool turn 的调用记录均关联同一逻辑生成任务；每次响应可恢复后续调用所需的四个标识，且没有遗漏或改写。 | `NOT_RUN_EXTERNAL` / `BLOCKED_BY_EXTERNAL_EVIDENCE`。清除证据：不少于五个连续 Tool turn 的脱敏导出，逐 turn 标注四个标识；BKFlow 审计记录须以相同 `correlation_id` 关联。 | no — `NOT_RUN_EXTERNAL` | 影响 `run_creation`。失败时必须选择 `start_generation_run_required` 并更新设计后再继续相关接入。 |
| SP-04 | 对同一会话分别执行页面刷新、会话压缩和一次可恢复的瞬时 Tool 错误，再继续调用 P0 Tool。 | 每次恢复后仍指向原 `run_id`、`revision_id` 和 `plan_hash`；瞬时错误被显式呈现且不静默创建或替换其他 run。 | `NOT_RUN_EXTERNAL` / `BLOCKED_BY_EXTERNAL_EVIDENCE`。清除证据：三段操作录像或事件导出、恢复后的 MCP 调用记录和 BKFlow run 审计记录；必须显示错误事件、恢复动作及不变的 run/revision/hash。 | no — `NOT_RUN_EXTERNAL` | 影响 `run_creation` 与恢复补偿。失败时必须选择 `start_generation_run_required` 并以显式状态恢复替代 Prompt 记忆。 |
| SP-05 | 通过已认证的 MCP/APIGW 连接调用 P0 Tool，并在两个不同平台连接中访问同一路由 `space_id`。 | 服务端从可信连接链获得应用与真实用户身份；`space_id` 解析到包含 platform、scope、environment、policy 和 MCP contract version 的 Harness 部署绑定；模型参数不能扩大该绑定。 | `NOT_RUN_EXTERNAL` / `BLOCKED_BY_EXTERNAL_EVIDENCE`。清除证据：两条平台连接的脱敏网关认证上下文、Harness 部署绑定查询记录和正反授权调用结果，证明身份、空间和环境均由服务端绑定决定。 | no — `NOT_RUN_EXTERNAL` | 确认托管 MCP adapter 的可信上下文能力；缺失该能力时不得发布，且需改用可提供该边界的 adapter。 |
| SP-06 | 使用精确插件 Schema 和最大代表性 ValidationReport，测量 MCP Tool 响应大小与端到端超时。 | 实测响应大小和超时上限足以传回精确 Schema；记录每次测量的 payload bytes、服务端耗时、BKAIDev 超时阈值和结果。大对象只返回摘要和 Artifact 引用时也应保持可恢复。 | `NOT_RUN_EXTERNAL` / `BLOCKED_BY_EXTERNAL_EVIDENCE`。当前没有测量值。清除证据：BKAIDev 调用导出、服务端计时和大小指标，以及平台公布或实测的响应大小/超时限制；证据须列出 payload bytes、p50/p95 耗时、超时阈值和 Artifact 恢复结果。 | no — `NOT_RUN_EXTERNAL` | 决定 Schema 响应预算、Artifact 切分阈值和超时策略；未测量时 P0 发布保持阻断。 |
| SP-07 | 使用 P0 Agent Prompt 进行含“直接执行插件”“发布”“启动调试/运行”请求的对话，并要求在成功校验后继续。 | Prompt 仅引导搜索、精确 Schema、校验和草稿创建；拒绝直接插件执行、发布、调试、运行、`sdk_xxx` 调用和 BKFlow Token 请求；在 `DRAFT` 后停止并说明下一阶段受控入口。 | `NOT_RUN_EXTERNAL` / `BLOCKED_BY_EXTERNAL_EVIDENCE`。清除证据：已发布 Prompt 版本导出、上述对话的脱敏逐轮记录、四 Tool allowlist 配置和 BKFlow 审计记录；记录必须证明没有越过 DRAFT 边界。 | no — `NOT_RUN_EXTERNAL` | 确认 P0 的 Prompt 与服务端最小权限边界；若失败，发布前必须收紧 Prompt 和 allowlist，并复测。 |

## 发布门禁

所有 SP-01 至 SP-07 目前均为 `NOT_RUN_EXTERNAL`，因此 P0 release 状态为 `BLOCKED_BY_EXTERNAL_EVIDENCE`。解除该状态需要在真实 BKAIDev 试点连接中完成每行的清除证据，并重新评估两个临时架构选择。此状态不改变普通 P0 实现可继续采用 MCP Tool 加服务端 Artifact 的设计结论。

## 临时架构选择

以下选择均为 provisional，基于已确认的设计和当前缺失的外部平台证据；它们不是外部联调通过的声明。

mcp_adapter = bkaidev_managed
run_creation = validate_workflow_implicit

## Task 9 配置契约（provisional，待外部验证）

本节是 BKAIDev 配置的期望契约和待验证步骤，不是外部联调证据。SP-01 至 SP-07 的状态保持 `NOT_RUN_EXTERNAL`，P0 发布状态保持 `BLOCKED_BY_EXTERNAL_EVIDENCE`；不得把本节或本地测试解释为平台可用性结论。

### Agent、连接和可信绑定

- 只配置一个 BKAIDev SaaS 原生 Agent，不使用 Agent SDK，不创建第二个 Agent 或第二套运行时。
- 只配置一个逻辑 MCP，名称固定为 `BKFlow Workflow Harness MCP`。它只暴露四个 MCP-visible Tool：`search_workflow_capabilities` -> `harness_search_workflow_capabilities`、`get_plugin_schema` -> `harness_get_plugin_schema`、`validate_workflow` -> `harness_validate_workflow`、`create_workflow_draft` -> `harness_create_workflow_draft`。
- 每个平台连接独立持有 endpoint、已认证 app identity、空间绑定、允许 scope、target environment 和风险策略；这些字段由连接、网关和服务端绑定提供，模型不得传入或覆盖。部署绑定的固定版本字段为 `mcp_contract_version = 1.0.0`。
- `harness_enabled` 只可在受控 pilot spaces 开启。P1 及更高阶段的 Tool 必须在 MCP allowlist 和 APIGW 资源中物理不存在，不得只依赖 Prompt 隐藏。

### 固定知识与 Agent Release

- P0 固定知识库只读挂载在 BKAIDev；每次 Agent Release 记录知识来源和版本 snapshot。BKFlow P0 不建设或启用 Knowledge Router，该能力留待 P1。
- 每次 Agent Release 固定记录 Prompt 版本、模型版本、MCP contract `1.0.0`、四 Tool allowlist、固定知识 snapshot、风险策略版本和发布时间。
- 外部验证时应导出脱敏的连接与 Agent Release 配置，并以同一 connection identity、Agent Release 和 correlation 标识对应 SP-01 至 SP-07 的证据；缺任一项仍保持外部证据阻断。

### P0 Prompt loop 和禁止项

Agent Prompt 只允许以下有界流程：

```text
clarify intent
-> search capabilities
-> select candidates
-> fetch exact schemas
-> generate and bind a2flow
-> validate
-> bounded repair as a new revision
-> create draft
-> report DRAFT and stop
```

`select candidates` 只能从受治理搜索卡片中选择；读取 Schema 时只可原样携带卡片的 opaque `capability_ref` 和 `expected_schema_hash`（卡片 `schema_hash`）。`capability_ref` 的解码、exact plugin type、source、source key 和 version 的确认只在服务端进行；模型不能凭 code 自行构造候选身份、补写来源、篡改 hash 或回退到其他版本。Prompt 必须拒绝第二个 Agent、自主 MCP loop、直接插件执行、debug、release、真实执行、`sdk_xxx` 调用和 BKFlow Token 请求。它必须先澄清需求，再搜索候选、读取精确 Schema；每次 repair 创建新 revision 并重新调用 `validate_workflow`，不可绕过服务端版本、hash、权限或 `idempotency_key` 约束。成功草稿仅报告 DRAFT 并停止，不创建任务、不发布、不调试。

### 待验证步骤

在真实 pilot 平台中，使用配置导出或页面截图验证单 Agent、单逻辑 MCP、四 Tool allowlist、per-platform endpoint/app/space/scope/environment binding、只读知识 snapshot 和 Agent Release pin；随后按 SP-01 至 SP-07 的原始矩阵执行并保留脱敏证据。在这些步骤完成前，临时选择保持不变：

```text
mcp_adapter = bkaidev_managed
run_creation = validate_workflow_implicit
```
