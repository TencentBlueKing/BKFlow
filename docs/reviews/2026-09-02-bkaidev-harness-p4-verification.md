# BKAIDev a2flow Harness P4 本地验证与外部门禁记录

## 1. 验证对象

```text
branch = ai/a2flow-harness-p4
p3_predecessor_sha = f00fda91bb9392d17aaeabffed6a7482e5d155e1
p4_task9_predecessor_sha = ed631707ec178849fdbb35380394a5e3c88b523f
verified_code_sha = 33194f3431f384dbb1c3ef9c646a1093b2f5c7c9
contract = 1.4.0
agent_visible_tools = 15
verification_database = isolated SQLite
external_systems_called = none
```

`verified_code_sha` 是包含 P4 Task 1–10 代码、42 条 Golden Case 和 `harness-p4-gate` 的精确提交；本记录在其后追加，不改变被验证代码。P4 从精确 P3 基线顺序叠加，未改写 P0–P3 已协商 Tool 集合。

## 2. 本地门禁结果

执行 `make harness-p4-gate`，结果为：

```text
Django system check = passed with 1 pre-existing warning
harness migration drift = none
APIGW documentation archive = valid
pytest = 2124 passed, 8 skipped
git diff --check = passed
duration = 533.31 seconds
verdict = P4_LOCAL_GATE_PASSED
```

8 个跳过项均为 SQLite 无法证明的双连接行锁/并发语义，包括 Harness 幂等与 Validator 并发测试；串行行为仍有覆盖。该结果不等于 MySQL/PostgreSQL 并发验证。Django warning 为既有 `label.Label.label_scope` JSONField default 提示，不属于本次 P4 变更。

定向验证同时得到：

- Task 9 Harness APIGW、feedback 与前序兼容回归：324 passed；
- Task 10 feedback/improvement/eval/APIGW 定向回归：257 passed；
- `feedback_cases.yaml` 精确 42 条，类别计数为 6/5/8/6/6/5/4/2；
- contract `1.4.0` 精确 15 Tool，`1.0.0`–`1.3.0` 的既有有序集合保持不变；
- `harness_submit_generation_feedback` 的 APIGW route、认证设置、请求 Schema、中文文档和压缩包字节一致。

## 3. 已证明的本地闭环

本地确定性测试覆盖五类候选：`KNOWLEDGE`、`REGISTRY`、`VALIDATOR_POLICY`、`PROMPT_SKILL`、`EVAL`。每类至少完成：

```text
consent-bound feedback
  -> immutable Run/Revision provenance
  -> typed Evidence attribution
  -> routed DRAFT with explicit Owner/Reviewer
  -> independent review
  -> sanitized hash-addressed review package
  -> seven mandatory local Eval suites
  -> verified external-evidence requirement or explicit block
```

已验证的关键不变量：

- 反馈 Body 不能指定 Owner、Reviewer、候选状态、目标系统或知识层级；
- 反馈摘要与观测结果先脱敏，凭证型引用拒绝，Run/Revision/Execution/工件都按可信上下文校验归属；
- Tool 调用只保存不可信 Evidence，不直接创建候选，不修改线上知识、Registry、Validator、Prompt 或 Skill；
- 确定性归因只消费类型化 ValidationReport/Evidence code，不从用户自然语言推断规则；
- 知识候选只能路由到同级或更具体的合格 Binding，不允许 Space/Scope 反馈回退到 Public/Global；
- 候选保持 `DRAFT -> IN_REVIEW -> APPROVED/REJECTED`，Owner 不能自审，已批准内容只能创建新修订；
- Eval package 固定 candidate、case hash、contract、Agent Release 与知识 snapshot；必跑 suite 或任一安全指标回归都会阻断；
- P4 敏感信息测试贯穿 feedback、Evidence、candidate package 与 Eval package，原始敏感值未进入响应或持久化投影。

## 4. Contract stub 证明不等于外部验收

测试用显式 `CONTRACT_STUB_ONLY` verifier/readback 走通了一次：

```text
local Eval
  -> test-only signed-result verification
  -> test-only Provider receipt
  -> exact snapshot readback: snapshot-1 -> snapshot-2
  -> verified rollback readback: snapshot-2 -> snapshot-1
```

该链路只证明 BKFlow 的签名结果、回执、digest、版本、readback 和 rollback 校验协议可工作，不证明真实 BKAIDev 或知识 Provider 已签发任何结果。它不能用于填写生产发布验收，也不能触发开关。

## 5. 保持冻结的生产模式

```text
owner_mode = draft_only
promotion_mode = no_promotion
eval_mode = local_deterministic_only
retention_mode = intake_disabled
harness_feedback_enabled = false
harness_candidate_promotion_enabled = false
quality_delta_min = UNRESOLVED
latency_regression_max = UNRESOLVED
cost_regression_max = UNRESOLVED
canary_size = UNRESOLVED_NO_CANARY
canary_observation_window = UNRESOLVED_NO_CANARY
```

代码中的生产 feedback retention policy 默认返回 disabled；即使 contract 和空间 Tool 开关存在，没有经批准的 consent/retention/delete policy 仍不能摄入真实反馈。生产 CandidateEvalGate 使用未解析阈值，因此默认阻断晋级。

## 6. 尚缺的外部证据

| Gate | 缺失证据 | 当前结论 |
| --- | --- | --- |
| DG-P4-01 | 真实目标系统的 Owner/Reviewer 映射、职责分离和 readback | `NOT_RUN_EXTERNAL` |
| DG-P4-02 | Provider 草稿、发布、精确 snapshot readback 与 rollback 回执 | `NOT_RUN_EXTERNAL` |
| DG-P4-03 | 固定 BKAIDev Agent Release 的真实签名评测结果与 verifier 集成 | `NOT_RUN_EXTERNAL` |
| DG-P4-04 | 批准的 consent、retention、匿名化、撤回和删除政策 | `NOT_RUN_EXTERNAL` |
| DG-P4-05 | Owner 预登记的质量、延迟、成本、canary 规模和观测窗口 | `UNRESOLVED` |
| DB-P4-01 | MySQL/PostgreSQL 迁移、行锁和并发幂等验证 | `NOT_RUN_EXTERNAL` |

真实 BKAIDev Agent 的一个 SaaS-native Agent、一个 logical Harness MCP、15 Tool 挂载和目标空间 allowlist 也尚未 readback，不能用仓库契约代替。

## 7. 最终裁决

```text
P4_LOCAL_GATE_PASSED
P4_KNOWLEDGE_CLOSED_LOOP_PASSED = false
P4_BKAIDEV_EVAL_GATE_PASSED = false
P4_CLOSED_LOOP_GATE_BLOCKED_BY_EXTERNAL_EVIDENCE
```

当前可以进入代码 Review 和外部试点准备，但不能开启生产反馈留存、候选晋级、真实知识发布或 canary。解锁必须新增不可覆盖的外部验证记录，并保留本记录所描述的本地通过与外部阻断边界。
