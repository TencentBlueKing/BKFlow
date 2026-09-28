# BKAIDev a2flow Harness P3 运行时门禁与恢复 Spike

## 1. 结论

```text
branch = ai/a2flow-harness-p3
predecessor_sha = e66c3339c3c834781329080c03d91ed733fd5cf8
predecessor_gate = P2_LOCAL_GATE_PASSED
approval_mode = deny_gated_actions
identity_mode = deny_execution
runtime_authorization_mode = harness_domain_service
publish_mode = extracted_domain_service
execution_recovery_mode = persisted_create_start_saga
readback_mode = task_client_plus_evidence
global_real_mode = deny_global_real
```

以上值分为两类：

- `deny_*` 是当前外部门禁结论，不会因 P3 本地实现自动变成通过；
- `harness_domain_service`、`extracted_domain_service`、`persisted_create_start_saga` 和
  `task_client_plus_evidence` 是 Task 1 时点冻结的 P3 实现选择；该句不描述 Task 10 当前仓库完成度。

截至 Task 10，仓库已经实现相应本地领域服务、恢复状态和 APIGW 契约；但在取得真实 BKAIDev 身份读回、服务端可验证审批回执、
受控 Engine 以及平台应用代用户授权证据前，`publish_workflow`、`start_workflow_execution`、高风险控制和
global real debug 必须 fail closed。

## 2. 基线复验

在 `ai/a2flow-harness-p3`、上述精确 predecessor SHA 上重新执行 P2 全量门禁：

```text
manage.py check = PASS（仅既有 JSONField default 与 naive datetime warning）
makemigrations harness --check --dry-run = No changes detected
apigw-docs.zip integrity = PASS
pytest = 1244 passed, 8 skipped in 131.55s
```

8 个 skip 全部继承自 P2：1 个 public draft 双连接锁、2 个 idempotency 双连接锁、5 个 validator
并发锁测试。SQLite 无法证明这些生产数据库语义；MySQL/PostgreSQL 证据仍为
`NOT_RUN_EXTERNAL / BLOCKED`。Contract `1.2.0` 保持累计 9 Tool，最新 Harness migration 为
`0005_p2_debug_token_broker`。

## 3. Task 1 时点的运行时事实

### 3.1 发布路径

当前 `release_template` 路径是：

```text
APIGW 身份/空间校验
  -> FlowVersioning 开关
  -> TemplateReleaseSerializer
  -> 查询 version 是否已存在
  -> transaction.atomic
       -> Template.release_template(data)
       -> 草稿快照 draft=False + version/operator/desc
       -> Template.snapshot_id = released_snapshot.id
  -> TemplateOperationRecord（事务外）
  -> TEMPLATE_RELEASE Webhook（事务外）
  -> 返回 Template.to_json()
```

静态代码与既有模型测试证明了草稿转发布快照、版本碰撞拒绝和模板当前快照更新；它没有证明：

- 网络响应丢失后的同请求识别；
- “快照已提交、操作记录或 Webhook 未完成”时的自动修复；
- Manifest 与发布版本的一一绑定；
- 同一个 idempotency key 能读回首次发布结果。

版本唯一检查可以阻止第二次创建同版本，但当前重试只得到“版本已存在”，不能区分“我的首次请求已成功”与
“他人占用了版本”。P3 必须把发布领域动作抽为同进程服务，并由持久化记录完成归属和结果读回。

### 3.2 创建、启动和控制路径

当前 APIGW 创建路径组装模板树、scope、通知配置和 Open Plugin 快照，然后调用：

```text
TaskComponentClient.create_task(data)
  -> POST {TASK_MODULE}/task/
```

创建成功后 APIGW 才补充标签并发送 `TASK_CREATE` Webhook。创建不会自动 start。启动和任务控制另走：

```text
TaskComponentClient.operate_task(task_id, "start", {"operator": actor})
  -> POST {TASK_MODULE}/task/{task_id}/operate/start/
```

`BaseComponentClient`/`TaskComponentClient` 当前没有传递 Harness idempotency key，也没有对超时后的远端结果做
反查。现有 Template Debug 全局运行虽已先保存 `active_task_id` 再 start，但 start 失败会尝试删除任务；这不等于
P3 所需的跨 Worker、跨 Tool 重试恢复协议，也不能证明 start 响应丢失时再次 dispatch 安全。

### 3.3 身份、Token 与读回

Harness 的本地可信上下文只从网关认证对象和服务端空间绑定构建：

- `platform_app` 来自 `request.app.bk_app_code`，并要求 `request.app.verified is True`；
- `actor` 来自已认证 `request.user.username`；
- space/scope/environment/policy/contract 来自路由与 `HarnessDeploymentConfig`；
- 请求 body 里的同名字段不能覆盖上述权限维度。

这组本地测试证明了代码边界，但没有真实 BKAIDev -> APIGW 调用的读回证据，所以外部
`identity_mode` 仍为 `deny_execution`。

P2 `TokenLease` 仅绑定 `DebugSession`，资源只有 `TEMPLATE/SCOPE`，权限仅允许 `MOCK`。虽然底层旧 Token 模型
支持 `TASK`，当前 Harness Broker 尚不能为 ExecutionRun 颁发 TASK lease。因此 P3 选择：

- Harness 内部发布/创建编排走抽取后的领域服务，并由 `HarnessPermission + action policy` 授权；
- 不把 `sdk_*` 当作默认发布/执行路径，也不伪造 Token 绕过权限；
- 未来若某个动作必须走 token-protected SDK，则在 ExecutionRun/action digest 绑定、TASK lease、真实平台签发
  与撤销证据齐全前对该动作 `deny_action`。

当前可查询来源包括 `get_task_detail`、`get_task_states`、`get_task_node_detail`、
`render_context_with_node_outputs`，以及按 task id 查询的 Webhook History。`get_task_detail` 会附加
`webhook_delivery_history`；任务完成事件携带输出变量。P3 可以以这些来源实现
`task_client_plus_evidence`，但必须逐项验证 Postcondition，缺少来源时不能猜测成功。

## 4. SP-P3-01 至 SP-P3-08

状态词：`PASS_LOCAL_CHARACTERIZATION` 只表示 Task 1 时点本地代码事实已确认；`NEEDS_IMPLEMENTATION` 表示
对应能力在 Task 1 predecessor 尚未落地，Task 10 当前状态以 6.1 节为准；
`NOT_RUN_EXTERNAL / BLOCKED` 表示缺少真实外部证据。

| Spike | 本地结果 | 外部结果 | 冻结结论与 P3 要求 |
| --- | --- | --- | --- |
| `SP-P3-01` approval receipt verification and expiry | P2 默认 `DebugApprovalVerifier` 无后端并 fail closed；本地 test double 覆盖 claims/digest/expiry 拒绝 | `NOT_RUN_EXTERNAL / BLOCKED`：无真实 issuer、签名/回查、replay、expiry 证据 | `approval_mode = deny_gated_actions`。`prepare_release` 可返回审批需求；publish/start/高风险 control 不得执行 |
| `SP-P3-02` platform application plus real-user identity | `PASS_LOCAL_CHARACTERIZATION`：网关 verified app + authenticated user + 服务端空间绑定，body 伪造无效 | `NOT_RUN_EXTERNAL / BLOCKED`：无 BKAIDev 实际挂载和 app/actor/space/scope/env readback | `identity_mode = deny_execution`；外部门禁通过后才可切为 trusted platform user |
| `SP-P3-03` per-action domain-service versus SDK token path | 发布模型方法、任务组件 client 和 HarnessPermission 已定位；P2 Harness lease 不支持 TASK/ExecutionRun | `NOT_RUN_EXTERNAL / BLOCKED`：无平台应用代用户 TEMPLATE/TASK lease 证据 | `runtime_authorization_mode = harness_domain_service`；抽取同进程发布/创建服务。必须用 SDK 的动作单独 deny，直至 brokered lease 完成 |
| `SP-P3-04` release idempotency and version collision | `PASS_LOCAL_CHARACTERIZATION`：版本碰撞会拒绝；事务只包快照和 template pointer | `NOT_RUN_EXTERNAL / BLOCKED` | `NEEDS_IMPLEMENTATION`：Manifest hash + idempotency record + snapshot/version 归属读回；事务外操作记录/Webhook 需可重放证据 |
| `SP-P3-05` create success followed by response loss | 当前 client 只返回单次 HTTP 结果，无 idempotency header 或远端按 key 查询 | `NOT_RUN_EXTERNAL / BLOCKED` | `NEEDS_IMPLEMENTATION`：create 前持久化 Saga，create 成功后先持久化 task_ref；无法确认结果时不得盲目再次 create |
| `SP-P3-06` start success followed by response loss | create/start 已确认分离；当前 start 无 Harness 恢复 key | `NOT_RUN_EXTERNAL / BLOCKED`：未证明 Engine start 幂等 | `execution_recovery_mode = persisted_create_start_saga`；本地行锁和 START_DISPATCHED 断点提供 at-most-once dispatch，超时后先 readback |
| `SP-P3-07` task/node/output and webhook readback coverage | `PASS_LOCAL_CHARACTERIZATION`：detail/states/node/output-render/Webhook History 来源存在 | `NOT_RUN_EXTERNAL / BLOCKED`：无真实任务全生命周期与输出/回调一致性 trace | `readback_mode = task_client_plus_evidence`；仅支持被适配器和测试证明的固定 Postcondition DSL |
| `SP-P3-08` controlled-environment global real debug | P2 仅 Mock global；real-step 外部门禁仍未通过 | `NOT_RUN_EXTERNAL / BLOCKED` | `global_real_mode = deny_global_real`；须同时满足受控环境白名单、P2 real-step、发布绑定审批和独立开关 |

## 5. 冻结后的 P3 控制流

```text
BKAIDev Agent（唯一 LLM/决策者）
  |
  | prepare_release
  v
Harness：重验 Revision / plan_hash / bindings / draft fingerprint / debug evidence
  |
  +-- 生成不可变 ReleaseManifest 与 action digest
  +-- 缺可信身份或审批后端：只返回门禁，不产生发布/执行副作用
  |
  | publish_workflow（开关 + 身份 + 审批均通过后）
  v
持久化发布记录 --行锁/幂等--> Template release domain service
  |                                  |
  |<----------- snapshot/version ----+
  |
  | start_workflow_execution
  v
ExecutionSaga: NEW -> CREATE_DISPATCHED -> TASK_REF_PERSISTED -> START_DISPATCHED
  |                    |                        |
  |                    +-- response loss -------+--> 先 readback，不盲目重复副作用
  v
TaskComponentClient + EvidenceEvent/Webhook History
  |
  +-- Engine 状态
  +-- 节点状态
  +-- 输出变量
  +-- Webhook 投递历史
  v
固定 Postcondition DSL -> EvidenceBundle -> SUCCEEDED / FAILED / CANCELLED
```

## 6. 实现边界与放行条件

### 6.1 Task 10 APIGW / BKAIDev 契约映射

当前仓库 contract `1.3.0` 在同一个 `BKFlow Workflow Harness MCP` 中定义 `14 cumulative Tools`；P3 新增映射为：

| BKAIDev Tool | APIGW operationId |
| --- | --- |
| `prepare_release` | `harness_prepare_release` |
| `publish_workflow` | `harness_publish_workflow` |
| `start_workflow_execution` | `harness_start_workflow_execution` |
| `get_workflow_execution` | `harness_get_workflow_execution` |
| `control_workflow_execution` | `harness_control_workflow_execution` |

BKAIDev Agent 仍是唯一 LLM caller，并直接从这 14 个 Harness Tool 中选择；BKFlow 不运行第二个 Agent，
也不由 Harness 自主决定下一次 Tool。标准编排是
`prepare → approve → publish → start → poll/control → poll`。`START_UNCERTAIN` 和
`CONTROL_UNCERTAIN` 只能再次调用 `get_workflow_execution` 以可信 readback 恢复，不能靠 Prompt 猜测或重派。

这只是仓库中的 single Harness MCP、APIGW 与文档契约，不是实际 BKAIDev mounting/readback 验收。
生产 `ReleasePolicy` provider、approval verifier/replay guard、平台真实身份、Engine correlation 和 SDK/token path
仍为 `NOT_RUN_EXTERNAL / BLOCKED_BY_EXTERNAL_EVIDENCE`；缺失时发布、启动和控制固定 deny，功能开关保持关闭。

P3 本地实现必须满足：

1. `prepare_release` 永远不发布、不创建任务；
2. publish/create/start/control 每次副作用前重新校验可信上下文、Revision、plan hash、Schema、草稿指纹、
   CapabilityBinding、目标环境和 action-bound approval；
3. publish、create、start、control 分别持久化独立断点和幂等结果；
4. `FINISHED` 只代表 Engine 完成，必须再验证固定 Postcondition；
5. Tool 响应、数据库、Evidence 和日志不得包含 Token、receipt、Credential 或 App Secret 明文；
6. P3 开关默认关闭；关闭写能力后，既有 Execution/Evidence 只读查询仍可用；
7. 外部证据未补齐前，最终结论只能是 `P3_LOCAL_GATE_PASSED` 与
   `P3_PUBLISH_EXECUTION_GATE_BLOCKED_BY_EXTERNAL_EVIDENCE`，不能宣称真实发布执行已可用。

把外部门禁从 deny 切为 allow，至少需要以下独立证据：

- BKAIDev 实际挂载后的 app/actor/space/scope/environment Tool readback；
- 审批系统真实 issuer 的验签或服务端回查、claims、expiry、replay 拒绝 trace；
- 受控空间一次低风险 publish/create/start/readback/control 的关联 trace；
- create 和 start 两个响应丢失窗口的恢复演练，证明不重复产生副作用；
- 平台应用代用户 TASK/TEMPLATE Token 的签发、最小权限、TTL、撤销与零明文证据（仅对必须走 SDK 的动作）；
- MySQL/PostgreSQL 下 migration、唯一约束和行锁/并发恢复测试。
