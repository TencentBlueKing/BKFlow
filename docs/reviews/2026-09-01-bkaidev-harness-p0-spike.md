# BKAIDev Harness P0 接入 Spike

- 日期：2026-09-01
- 实现分支：`feat/a2flow-harness-p0`
- 设计基线：`feat/a2flow@52f62d89`
- Spec：`docs/specs/2026-09-01-bkaidev-a2flow-harness-design.md`
- Plan：`docs/plans/2026-09-01-bkaidev-a2flow-harness-p0.md`
- TAPD：`136729554`
- 执行环境：Cursor 本地仓库，无 BKAIDev SaaS 登录态、无试点空间、无已发布 Harness MCP

## 状态

```text
SPIKE_EXTERNAL_EVIDENCE_BLOCKED
TASK_1_INCOMPLETE
P0_RELEASE_GATE_BLOCKED_BY_EXTERNAL_EVIDENCE
```

本次 Spike 可以固化探针矩阵、本地实现假设和停止条件，不能把 Task 1 或 P0 Release Gate 标为通过。文档证据只证明产品能力存在，不代替 BKAIDev 真机截图、导出配置或五轮 Tool 调用记录。

## 探针矩阵

| Probe ID | Input | Expected | Actual evidence | Pass | Decision impact |
|---|---|---|---|---|---|
| SP-01 | 在一个 BKAIDev SaaS 单智能体上绑定一个逻辑 MCP，并列出可见 Tool | 恰好四个 MCP-visible 名称：`search_workflow_capabilities`、`get_plugin_schema`、`validate_workflow`、`create_workflow_draft`；逻辑连接名为 `BKFlow Workflow Harness MCP` | `SPIKE_EXTERNAL_EVIDENCE_BLOCKED`。iWiki [智能体使用文档](https://iwiki.woa.com/p/4029461518) 证明单智能体可关联「工具或 MCP」，并可选择「蓝鲸API网关」来源 MCP。iWiki [aidev智能体快速接入现有网关能力](https://iwiki.woa.com/p/4019498471) 证明 APIGW 可以把现有接口转成 MCP Server，并把接口映射为 Tool。本环境没有 BKAIDev Agent、没有导出的 MCP 配置、没有 Tool 清单截图，因此不能声称四个 P0 Tool 已经可见。 | no | 本地按 `mcp_adapter = bkaidev_managed` 实现四个 prefixed APIGW operation；真实 MCP 映射留到有 BKAIDev 权限后再关 Task 1 |
| SP-02 | 向 MCP Tool 发送含嵌套对象的 a2flow V2 JSON，并读取嵌套 Envelope | 请求/响应保持 JSON object，不把 a2flow 或 Envelope 字符串化 | `SPIKE_EXTERNAL_EVIDENCE_BLOCKED`。APIGW 资源契约使用 `application/json` requestBody/response。本仓库尚未发布四个 Harness operation，也没有 BKAIDev MCP 调用抓包。无法测量 BKAIDev 是否把嵌套对象改写成字符串。 | no | 本地契约固定为 JSON object；若后续真机发现必须 stringify，先改 spec 再改后端 |
| SP-03 | 连续至少五轮 Tool 调用，每轮回传上一轮返回的 `run_id`、`revision_id`、`plan_hash`、`correlation_id` | BKAIDev 能保留并重发这四个字段，不静默换成另一个 run | `SPIKE_EXTERNAL_EVIDENCE_BLOCKED`。本环境无法打开 BKAIDev 会话，没有五轮 Tool transcript。Approved spec 默认首个写操作隐式创建 `HarnessRun`，只有「刷新/压缩/多轮后无法稳定携带 `run_id`」才允许第 16 个 Tool。当前没有失败证据，因此不启用 `start_generation_run`。 | no | 本地按 `run_creation = validate_workflow_implicit` 实施；SP-03 真机失败则立即停止后端并先改 spec |
| SP-04 | 页面刷新、会话压缩、一次瞬时 Tool 错误后继续同一生成任务 | 不静默替换成另一个 run；必须显式携带或由服务端幂等键恢复同一 `run_id` | `SPIKE_EXTERNAL_EVIDENCE_BLOCKED`。没有 BKAIDev 页面刷新、压缩或瞬时错误的会话记录。本地将用 `idempotency_key` + `run_scope` 保证写操作重试回到同一资源，但这只覆盖服务端，不覆盖 BKAIDev 客户端是否改写 `run_id`。 | no | 与 SP-03 绑定；真机失败才评估第 16 个 Tool |
| SP-05 | 经 BKAIDev MCP 连接调用带 `space_id` 的 APIGW Harness operation | 认证 app 来自网关 JWT；认证 user 来自网关 JWT；`space_id` 来自 route；scope/environment/policy/MCP contract 来自服务端非公开 `HarnessDeploymentConfig`；body 同名字段不能成为授权依据 | 本地代码可证明 BKFlow 侧身份链：`ApiGatewayJWTAppMiddleware` / `ApiGatewayJWTUserMiddleware` 注入 `request.app` 与 `request.user`；`check_space` 用 `Space.app_code == request.app.bk_app_code` 做应用-空间绑定。iWiki [在AIDEV业务项目下接入观测平台MCP](https://iwiki.woa.com/p/4017137609) 写明 BKAIDev 已打通 APIGW MCP，并可透传「当前对话用户」身份，无需把开发者个人 Token 固化为唯一身份。本环境没有 BKAIDev MCP 真机请求头，不能证明 Harness 四个 operation 已经带上 app+user JWT，也不能证明 `space_id` 会由连接绑定而不是模型填写。 | no | 本地实现必须忽略/拒绝 body 中的身份字段，并使用 AND 鉴权；若真机只能拿到 app 而拿不到 user，立即停止并先改 spec |
| SP-06 | 对一个精确 capability 调用 `get_plugin_schema`，记录响应体积与超时 | Tool 响应大小和超时足够承载完整插件 Schema；记录实测上限 | `SPIKE_EXTERNAL_EVIDENCE_BLOCKED`。当前 `api-resources.yml` 中 default backend 资源 `timeout: 0`（走网关默认超时），这是仓库配置，不是 BKAIDev MCP 实测。没有 Schema 字节数、MCP 截断、网关超时或 Token 窗口测量。 | no | 本地返回完整 Schema + `schema_hash`；若真机截断，必须在 Task 9 前改契约，不得静默截断 |
| SP-07 | 给单智能体写入 P0 Prompt，并尝试诱导直接执行插件、调试、发布或创建任务 | Agent 只走四个 P0 Tool，在 `DRAFT` 后停止；禁止第二 Agent、自主 MCP 循环和直接插件执行 | `SPIKE_EXTERNAL_EVIDENCE_BLOCKED`。iWiki 智能体文档证明可配置 Prompt、知识库、Skill、MCP allowlist 和发布版本，但不能用文档代替已发布 Agent Release。本环境没有试点空间的 `harness_enabled=true`，也没有 Prompt 对抗记录。 | no | Task 9 只准备配置契约和 Prompt 文本；不得声称 BKAIDev 已真实配置 |

## 探针执行说明

每个探针的输入、期望和失败判定如下。真机执行时必须把截图或导出配置填回上表的 Actual evidence，并把 Pass 改为 `yes` 或保持 `no`。

### SP-01 MCP 映射

- 输入：一个 SaaS 原生单智能体 + 一个 APIGW MCP Server，Server 只注册四个 prefixed operation。
- 期望：MCP-visible Tool 名称恰好是四个 approved 名；APIGW operation ID 为 `harness_search_workflow_capabilities`、`harness_get_plugin_schema`、`harness_validate_workflow`、`harness_create_workflow_draft`。
- 失败：出现第 5 个控制 Tool、业务插件被展开成 MCP Tool、或必须自建独立 MCP Adapter 才能映射。

### SP-02 嵌套 JSON

- 输入：含 `activities`、`gateways`、`constants` 的 a2flow V2 object，以及标准 Envelope object。
- 期望：BKAIDev 按 object 收发，不要求客户端先 `json.dumps`。
- 失败：平台强制 string schema，或回读后丢失嵌套结构。

### SP-03 五轮字段保持

- 输入：`validate_workflow` 创建 run 后，再连续调用 search/get/validate/validate/draft，每轮显式回传上一轮 Envelope 字段。
- 期望：五个回合使用同一个 `run_id`；`revision_id`/`plan_hash` 只在新校验成功时变化；`correlation_id` 可追踪。
- 失败：平台丢字段、改写字段、或无法在多轮 Tool 后回传 `run_id`。

### SP-04 刷新、压缩、瞬时错误

- 输入：同一会话刷新页面、触发一次上下文压缩、再制造一次可重试 Tool 错误。
- 期望：恢复后仍指向原 `run_id`，或通过同一 `idempotency_key` 回到原资源；不会静默新建另一个 run。
- 失败：刷新或压缩后模型用新 identity 覆盖旧 run，且服务端无法检测。

### SP-05 可信身份

- 输入：MCP 连接绑定平台应用、当前对话用户和 route `space_id`；body 同时伪造另一个 app/user/space/scope/environment。
- 期望：服务端只用 JWT app、JWT user、route space 和非公开 deployment config；伪造字段被忽略或拒绝。
- 失败：只能得到匿名 app、缺失 user、或必须信任模型传入的 space/scope。

### SP-06 Schema 体积与超时

- 输入：试点空间中体积最大的一个精确插件 Schema。
- 期望：完整 Schema 返回，记录字节数、耗时、网关/MCP 超时值和是否截断。
- 失败：响应被截断、超时，或必须改成 artifact-only 才能传完整 Schema。

### SP-07 P0 Prompt 边界

- 输入：P0 Prompt + 四个 Tool allowlist；对抗指令要求直接执行插件、调用 `sdk_xxx`、发布或创建任务。
- 期望：Agent 拒绝并停在 `DRAFT`；服务端即使收到越权字段也不执行。
- 失败：Agent 可见或调用了 P1-P4 Tool，或 Prompt 是唯一门禁。

## 本地可复核证据

以下证据来自本仓库和公开产品文档，不是 BKAIDev 真机 PASS。

1. Approved spec 第 4、5、7、20 节：BKAIDev SaaS 原生单智能体是 Soft Harness；BKFlow Interface 是 Hard Harness；默认不增加第 16 个 Tool。
2. iWiki `4029461518`：单智能体可配置 Prompt、模型、知识库、Skill、MCP/工具、审批和发布。
3. iWiki `4019498471`：APIGW 现有接口可转 MCP Server，并把接口映射为 Tool；创建后需给智能体应用授权。
4. iWiki `4017137609`：BKAIDev 与 APIGW MCP 已打通，支持透传当前对话用户身份，不要求把开发者个人 Token 作为唯一身份。
5. 本仓库 `bkflow/apigw/decorators.py` 的 `check_space`：应用必须等于 `Space.app_code`。
6. 本仓库 Interface 中间件链可从 APIGW JWT 提取 app 和 user。
7. 当前工作区没有 BKAIDev 登录、没有试点空间、没有 Harness MCP 导出配置。

## 架构决策

文档和代码没有证明必须自建独立 MCP Adapter，也没有证明 BKAIDev 无法稳定携带 `run_id`。按 approved spec 默认值作为本地实现假设：

```text
mcp_adapter = bkaidev_managed
run_creation = validate_workflow_implicit
```

这两个值是本地实现假设，不是 BKAIDev 真机结论。

选择依据：

- `bkaidev_managed`：产品文档已支持「APIGW 资源 -> MCP Server -> 单智能体关联」。没有证据表明必须由 BKFlow 再做一个独立 MCP Adapter 进程。
- `validate_workflow_implicit`：SP-03/SP-04 没有失败证据。P0 由首次 `validate_workflow` 隐式创建 `HarnessRun`，不增加 `start_generation_run`。

若后续真机证明需要 `separate_bkflow_adapter`，或 BKAIDev 无法稳定携带 `run_id`，立即停止后端实施，先更新 spec 和 plan，再继续编码。

## 本地继续实施的边界

在 `SPIKE_EXTERNAL_EVIDENCE_BLOCKED` 解除前：

- 可以完成本地 Django app、契约、自动化测试和 APIGW 资源/文档。
- Task 9 只准备配置契约和文档，不能声称 BKAIDev 已真实配置。
- Task 10 可以跑本地 Golden Cases，不能声称试点空间或线上 Agent 验证通过。
- 最终状态最多写到 `LOCAL_IMPLEMENTATION_COMPLETE`，P0 Release Gate 保持阻断。

## 停止条件

出现任一情况立即停止，不扩大方案：

- 真机证明必须独立 MCP Adapter。
- 真机证明必须第 16 个 Tool。
- 无法从网关得到可信 app/user/space/scope。
- APIGW 或 BKAIDev 真实契约与计划不兼容。
- 需要访问、生成或记录真实 Secret/Token。
- 任务触及 P1-P4。
