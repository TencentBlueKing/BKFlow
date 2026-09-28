# BKAIDev a2flow Harness P4 反馈闭环 Spike 与决策冻结

## 1. 证据身份与当前裁决

```text
branch = ai/a2flow-harness-p4
predecessor_sha = f00fda91bb9392d17aaeabffed6a7482e5d155e1
predecessor_contract = 1.3.0 / 14 tools
predecessor_migration = harness.0006_p3_release_execution
verified_at = 2026-09-06 Asia/Shanghai
p3_local_gate = P3_LOCAL_GATE_PASSED
p3_external_gate = P3_RELEASE_EXECUTION_GATE_BLOCKED_BY_EXTERNAL_EVIDENCE
p4_task1_gate = P4_TASK1_DECISION_GATE_BLOCKED_BY_EXTERNAL_EVIDENCE
```

P4 从上述精确 P3 提交开始。该提交的 `make harness-p3-gate` 已在创建 P4 worktree 前重新执行：
**1931 passed, 8 skipped in 534.57s，退出码 0**。8 个 skip 均为 SQLite 无法证明生产数据库行锁或并发语义；
它们不能替代 MySQL/PostgreSQL 验收。P3 的 BKAIDev、审批、Engine、Token 和真实数据库门禁仍是阻断状态。

因此本阶段只实现“可追溯反馈、候选、确定性评测和 Owner 控制面”的本地基础设施，不把 test double、
候选导出或管理命令描述成外部系统已经接通，不开启反馈摄入或自动晋级。

## 2. 已有能力盘点

| 能力 | P0-P3 已有事实 | P4 可复用边界 | 当前缺口 |
| --- | --- | --- | --- |
| Harness 会话与版本 | Run、Revision、`plan_hash`、可信 context、幂等记录 | 反馈必须绑定既有 Run/Revision/plan hash | 不允许反馈重写历史结果 |
| 联邦知识路由 | `KnowledgeSourceBinding` 已含 tier、空间/范围、owner/reviewer、snapshot、ACL、脱敏策略 | 知识候选只引用 Binding 和 snapshot lineage | Provider SPI 只有 `search`，没有 draft/publish/readback/rollback |
| 证据 | `EvidenceEvent`、`EvidenceBundle`、执行/Postcondition 结果，内建有界脱敏 | 反馈和候选关联已存在证据；导出前再次脱敏 | 反馈保存期限、匿名化/删除流程尚无批准策略 |
| 发布与执行 | Manifest、Approval、Execution、TokenLease、EvidenceBundle | 运行问题可归因为环境、插件、权限或 Postcondition | live receipt、Engine、Token 平台链路尚未验收 |
| 工具契约 | `1.3.0` 精确 14 Tool | P4 只允许追加 `submit_generation_feedback` | Owner 审核/发布/回滚不得暴露为 Agent Tool |
| 评测 | P0-P3 有本地确定性回归和 Golden Cases | 可构建脱敏、版本化 Eval Package | BKAIDev 固定 Release 执行、签名结果和超时语义未知 |

知识正文仍由 BKAIDev、BKFara 或各平台知识库管理。BKFlow 不新建通用知识库，只保存路由绑定、候选包、
来源、目标快照、评测和发布回执摘要；“Registry/API 是当前真实能力，知识库说明怎么选、怎么用和常见坑”的边界保持不变。

## 3. 目标系统与知识层级清单

`owner`、`reviewer`、外部回执和测试环境在没有真实平台证据时一律记为 `UNRESOLVED`，不能用代码模块负责人代替业务治理 Owner。

| 目标/层级 | 系统与 Binding | Owner / Reviewer | draft / publish / readback / rollback | 回执与快照 | 保留策略 | 测试环境 | 当前模式 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Global / Public 知识 | 外部公共知识库；P1 Global/Public Binding 已建模 | `UNRESOLVED / UNRESOLVED` | `NOT_VERIFIED`；当前 SPI 仅 search | Binding 可存 snapshot；外部回执格式未知 | `UNAPPROVED` | `NONE_CONFIRMED` | DRAFT only |
| Platform / BKFara 知识 | BKFara 自有知识库；P1 Platform Binding 已建模 | `UNRESOLVED / UNRESOLVED` | `NOT_VERIFIED`；不得假定 BKFara 提供写 API | snapshot 字段已有；签名/真实性未知 | `UNAPPROVED` | `NONE_CONFIRMED` | DRAFT only |
| Space 知识 | 对接平台空间知识库；P1 Space Binding 已建模 | `UNRESOLVED / UNRESOLVED` | `NOT_VERIFIED` | 平台、空间、snapshot 必须同时绑定 | `UNAPPROVED` | `NONE_CONFIRMED` | DRAFT only |
| Scope 知识 | 业务/项目/故障域知识库；P1 Scope Binding 已建模 | `UNRESOLVED / UNRESOLVED` | `NOT_VERIFIED` | scope type/value、snapshot 必须同时绑定 | `UNAPPROVED` | `NONE_CONFIRMED` | DRAFT only |
| 插件 Registry | BKFlow 当前真实能力目录/API | `UNRESOLVED / UNRESOLVED` | 变更/审批/回滚流程未核验 | 需要目录版本和审批回执摘要 | 元数据策略待确认 | 本地 deterministic only | DRAFT only |
| Validator / Policy | BKFlow Harness 确定性规则 | `UNRESOLVED / UNRESOLVED` | 可生成候选和本地回归；不可自动发布 | Git/制品版本可追踪，Owner 回执未知 | 代码与证据策略待确认 | 本地 deterministic available | DRAFT only |
| BKAIDev Prompt / Skill | BKAIDev SaaS Agent 配置 | `UNRESOLVED / UNRESOLVED` | Release/审批/回滚 API 未核验 | 固定 Agent Release 与签名结果未知 | BKAIDev 策略待确认 | `NONE_CONFIRMED` | DRAFT only |
| Eval | BKFlow 本地 Runner + BKAIDev 外部执行 | `UNRESOLVED / UNRESOLVED` | 本地 package/compare 可做；外部执行未接通 | package/result hash 可建模；外部签名未知 | 输入/结果保留策略待确认 | 本地 deterministic only | no promotion |

跨 Platform、Space 或 Scope 的适用范围扩大必须创建新候选并重新审核，不能继承原范围的发布回执。

## 4. Spike 执行结果

### SP-P4-01 owner and reviewer resolution

- 结果：`BLOCKED / NOT_RUN_EXTERNAL`。
- 本地事实：Knowledge Binding 已有 `owner`、`reviewer` 字段；P4 可为候选保存 owner/reviewer ref。
- 缺失证据：各目标系统的责任人映射、代理/离职规则、审批工单来源、超时升级和职责分离规则。
- 裁决：缺 Owner 或 Reviewer 的候选只能为 `DRAFT`，不得进入 `IN_REVIEW` 或更高状态。

### SP-P4-02 external knowledge draft/publish/readback

- 结果：`BLOCKED / NOT_RUN_EXTERNAL`。
- 本地事实：P1 Provider Registry 只要求 adapter 实现 `search`，Binding 能保存 source/snapshot/credential ref；不存在写入接口。
- 缺失证据：Global/Public、BKFara、Space、Scope 各 Provider 的草稿、发布、版本读回和回滚 API 及鉴权。
- 裁决：不得伪造自动同步；可以导出脱敏候选包，但没有已验证回执时不得标记 `PUBLISHED`。

### SP-P4-03 registry and validator change workflow

- 结果：`BLOCKED / PARTIAL_LOCAL_ONLY`。
- 本地事实：Registry/Validator 可以形成版本化候选、制品和本地确定性回归。
- 缺失证据：真实目录 Owner、变更窗口、审批回执、发布后 readback 和回滚责任。
- 裁决：本地测试通过只支持提交审核，不能支持线上晋级。

### SP-P4-04 BKAIDev prompt/skill release workflow

- 结果：`BLOCKED / NOT_RUN_EXTERNAL`。
- 本地事实：BKAIDev Agent 是唯一 LLM 调用方；BKFlow Harness MCP 只向 Agent 暴露受控 Tool。
- 缺失证据：SaaS 中 Prompt/Skill 草稿、固定 Release、审批、发布读回、回滚和审计接口。
- 裁决：BKFlow 不直接修改 Prompt/Skill，不新增 Agent Framework 或调用模型原生接口。

### SP-P4-05 BKAIDev fixed-release evaluation

- 结果：`BLOCKED / NOT_RUN_EXTERNAL`。
- 本地事实：BKFlow 可生成脱敏 Eval Package，并执行不调用 LLM 的确定性规则。
- 缺失证据：指定 Agent Release 的批量/逐例运行方式、模型与工具版本元数据、超时、重试、签名和结果回传协议。
- 裁决：外部签名评测不可用时，生成质量指标一律不得用于晋级。

### SP-P4-06 receipt authenticity and snapshot binding

- 结果：`BLOCKED / NOT_RUN_EXTERNAL`。
- 本地事实：P1/P3 已有 snapshot/version、approval digest 和 Evidence 等可绑定字段。
- 缺失证据：各 Provider/BKAIDev/Registry 回执的签发者、签名算法、claims、有效期、防重放和 readback 一致性。
- 裁决：P4 只保存回执引用与 digest；未验证真实性、目标 scope 和新 snapshot 前，不接受发布确认。

### SP-P4-07 retention consent anonymization and deletion

- 结果：`BLOCKED / NOT_RUN_EXTERNAL`。
- 本地事实：Evidence 已提供有界深度、总量和敏感字段脱敏；P4 可记录 consent scope 和 redaction version。
- 缺失证据：反馈/Evidence/候选/Eval 的保存期限、用户可见性、撤回授权、匿名化、法务留存和删除例外。
- 裁决：在策略批准前关闭 Feedback intake；不可用“默认永久保存”代替政策。

### SP-P4-08 canary rollback and metric availability

- 结果：`BLOCKED / PARTIAL_LOCAL_ONLY`。
- 本地事实：本地 Golden Cases 可做基线/候选零回归比较，候选可携带 impact/rollback artifact。
- 缺失证据：真实流量分桶、canary 最小样本、观测窗口、准确率/延迟/成本分布、熔断和外部回滚执行人。
- 裁决：canary 规模保持 `UNRESOLVED`，不启动 canary；任一安全回归立即阻断候选。

## 5. 冻结模式

以下值在外部 Decision Gate 证据补齐并形成新的审计记录之前不得改变：

```text
owner_mode = draft_only
promotion_mode = no_promotion
eval_mode = local_deterministic_only
retention_mode = intake_disabled
```

配套开关冻结为：

```text
harness_feedback_enabled = false
harness_candidate_promotion_enabled = false
```

这意味着 P4 代码和本地测试可以建立模型、服务、导出包及只读管理能力，但默认部署不能摄入真实用户反馈，
不能自动或人工“确认”一个未经外部回执验证的晋级。

## 6. promotion_thresholds（运行比较前冻结）

### 6.1 全类型强制条件

```yaml
promotion_thresholds:
  safety_regressions_max: 0
  secret_disclosure_regressions_max: 0
  cross_space_access_regressions_max: 0
  permission_regressions_max: 0
  mandatory_local_suite_pass_rate: 1.0
  source_and_target_version_required: true
  owner_and_reviewer_required: true
  rollback_artifact_required: true
  verified_promotion_receipt_required: true
  bkaidev_signed_eval_required_for_model_affecting_candidates: true
  quality_delta_min: UNRESOLVED
  latency_regression_max: UNRESOLVED
  cost_regression_max: UNRESOLVED
  canary_size: UNRESOLVED_NO_CANARY
  canary_observation_window: UNRESOLVED_NO_CANARY
```

安全门禁和必跑回归是零容忍、100% 通过；准确率、延迟、成本阈值必须由 Owner 在看到候选结果前登记。
目前它们是 `UNRESOLVED`，因此所有候选的有效晋级结论都是“阻断”，不是“忽略该指标”。

### 6.2 候选类型门禁

| 候选类型 | 当前允许状态 | 必跑本地门禁 | 外部必需证据 | 当前晋级结论 |
| --- | --- | --- | --- | --- |
| `KNOWLEDGE` | `DRAFT` | 引用/scope/冲突/敏感信息/Golden | Owner 审核、Provider 新 snapshot、发布回执、readback/rollback | BLOCKED |
| `REGISTRY` | `DRAFT` | Schema、权限、工具选择、兼容性/Golden | Registry Owner、目录版本、发布回执和 readback | BLOCKED |
| `VALIDATOR_POLICY` | `DRAFT` | 全量确定性、安全、误杀回归 | Policy Owner/Reviewer、发布版本、回滚确认 | BLOCKED |
| `PROMPT_SKILL` | `DRAFT` | 包结构、安全与本地 invariant | 固定 BKAIDev Agent Release 的签名 A/B 评测、Owner 回执 | BLOCKED |
| `EVAL` | `DRAFT` | fixture hash、scoring schema、重放一致性 | Eval Owner、数据 consent、签名结果和版本绑定 | BLOCKED |

### 6.3 立即阻断/回滚触发器

以下任一事件触发 `REJECTED` 或停止推进；若外部系统将来已发布，则要求 Owner 按回执中的 rollback ref 回滚：

- 任一 secret、跨空间、权限或安全回归；
- 发布回执签名/claims/digest 与候选、目标 scope 或 snapshot 不一致；
- 新 snapshot 无法 readback、版本漂移或回滚引用不可读取；
- 必跑回归未 100% 通过、fixture/package/result hash 不一致；
- 评测不是绑定固定 BKAIDev Agent Release 的签名结果；
- consent 或 retention policy 不覆盖对应反馈/Evidence 的改进用途；
- 已登记的质量、延迟或成本阈值未达到。

## 7. 后续解锁所需证据

1. DG-P4-01：Owner/Reviewer 映射、审批来源和职责分离 readback。
2. DG-P4-02：逐类 Provider 的草稿/发布/readback/rollback API，或人工发布的可验证回执协议。
3. DG-P4-03：固定 BKAIDev Agent Release 的执行、版本元数据、超时、签名和回传样例。
4. DG-P4-04：批准的 retention/consent/匿名化/删除政策及系统执行证据。
5. DG-P4-05：Owner 在候选结果前登记的质量、延迟、成本、canary 和回滚阈值。

外部证据齐备后应追加新的评审记录并显式改变 mode；不得修改本记录来覆盖当时的阻断事实。

## 8. BKAIDev 15-Tool Agent Release 契约（本地冻结，外部未验收）

P4 的目标拓扑保持为 `one SaaS-native Agent` 加 `one logical Harness MCP`。contract `1.4.0` 在 P3 的
14 Tool 上只追加 `submit_generation_feedback`，因此为 `exactly 15 Tools`；不引入 Agent SDK，也不引入 second runtime。
BKAIDev Agent 是唯一 LLM caller，BKFlow Harness 只执行确定性的上下文、权限、Schema、
consent、脱敏、Evidence、幂等和治理门禁。

每个可验收 Agent Release 必须携带 `pinned Prompt/model/policy/knowledge snapshots`，并证明
`feedback Tool available only to intended spaces`。仓库当前只能冻结 contract、operationId、空间开关及
默认关闭的 retention policy，无法从本地获得 BKAIDev Release readback、真实空间挂载、调用记录或知识
Provider 发布回执。因此本节状态是 `NOT_RUN_EXTERNAL / BLOCKED_BY_EXTERNAL_EVIDENCE`，不是已完成的
sanitized live Agent Release evidence；不得据此开启生产反馈或候选晋级。
