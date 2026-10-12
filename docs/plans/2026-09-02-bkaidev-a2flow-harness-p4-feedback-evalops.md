# BKAIDev a2flow Harness P4 Feedback and EvalOps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将用户反馈和真实运行 Evidence 转化为可追溯、需 Owner 审核、可回归验证且可回滚的知识/Registry/Validator/Prompt/Skill/Eval 改进候选，完成 Harness 持续改进闭环。

**Architecture:** `submit_generation_feedback` 只接收关联既有 Run/Revision/Evidence 的脱敏反馈。确定性归因器生成 `ImprovementCandidate`，知识类候选再绑定 P1 的 `KnowledgeSourceBinding`。BKFlow 保存治理元数据、候选包、评测和发布回执，不自建通用知识库、不直接修改线上知识或 BKAIDev Prompt；外部 Owner 审核发布后，BKFlow 验证新快照并通过本地回归加 BKAIDev 外部评测完成晋级。

**Tech Stack:** Python 3.9.12、Django 3.2.25、Django REST Framework 3.12.4、pytest、BKFlow Harness models/services、management commands、Django Admin、APIGW。

**Spec:** `docs/specs/2026-09-01-bkaidev-a2flow-harness-design.md`

## Global Constraints

- P4 只新增 `submit_generation_feedback`，累计 15 Tool；候选审核、发布确认和回滚是 Owner 控制面，不暴露为 Agent Tool。
- BKAIDev Agent 是唯一 LLM 调用方；BKFlow 不新增 Agent Framework，也不在评测 Runner 内直接调用模型原生接口。
- Feedback 是用户观测，不自动成为事实；必须关联 run/revision/plan_hash 和可用 Evidence，保留来源与置信度。
- 反馈文本、Evidence、候选内容在持久化和导出前脱敏；敏感原文不进入 Prompt、候选包、普通日志或测试 Fixture。
- Knowledge/Registry/Validator/Policy/Prompt/Skill 候选不得自动写入线上；必须有明确 Owner、Reviewer、回归用例、影响范围、发布回执和回滚引用。
- 知识正文继续存放在 BKAIDev、BKFara 或平台知识库；BKFlow 复用 P1 Binding/Provider，只保存候选、来源、目标绑定、快照和闭环状态。
- Global/Public、Platform、Space、Scope 候选按目标 KnowledgeSourceBinding 路由；跨平台或跨空间扩大适用范围必须重新审核。
- 高风险失败优先转化为 Validator/Policy 阻断规则和回归用例，禁止未经验证地自动学习为推荐知识。
- BKAIDev 生成效果评测采用版本化导出/导入：BKFlow 生成脱敏 Eval Package，BKAIDev 固定 Agent Release 执行，结果带签名/回执回传。
- P4 contract 为 `1.4.0`；`1.0.0` 至 `1.3.0` 保持兼容。
- Feedback Tool 默认关闭；关闭后仍允许 Owner 读取既有候选、Eval 和 Evidence。
- migration 使用 `python manage.py makemigrations harness --name p4_feedback_evalops` 生成。
- APIGW 三件套同步；提交统一使用 `--story=136729554`。

---

## Inherited Contracts

- P0 trusted context、Revision、plan_hash、CapabilityBinding、ValidationReport、Artifact、幂等和稳定 Envelope。
- P1 KnowledgeSourceBinding、Provider SPI、ACL-before-retrieval、KnowledgeHit 来源/快照和审计。
- P2 EvidenceEvent、DebugSession 和调试结果。
- P3 ApprovalRequest、ReleaseManifest、ExecutionRun、EvidenceBundle、Postcondition 结果和 14-Tool contract。
- 已有 Django Admin、management command、APIGW resource/doc 生成机制。

## Decision Gates

- **DG-P4-01 Owner system:** 确认 Knowledge、Registry、Validator/Policy、BKAIDev Prompt/Skill、Eval 各自的 Owner/Reviewer 与工单或审批回执来源；缺 Owner 的候选只能停留在 DRAFT。
- **DG-P4-02 Provider writeback:** 确认每类知识库能否创建草稿、发布、读取 snapshot/version 和回滚。没有写 API 时使用脱敏候选包加人工发布回执，不伪造自动同步。
- **DG-P4-03 BKAIDev evaluation:** 确认固定 Agent Release 的批量评测或逐例执行、结果签名、版本元数据和超时语义；不可用时只运行 BKFlow 本地确定性回归，并阻断生成质量晋级。
- **DG-P4-04 Retention and consent:** 确认反馈/Evidence 的保存期限、用户可见性、删除/匿名化流程和可用于改进的 consent scope。
- **DG-P4-05 Promotion thresholds:** 在看到基线分布前冻结安全零回归条件；准确率、延迟和成本阈值必须由 Owner 预先登记，不能在结果出来后调整。

## Reconciliation Check

只有 P3 本地 gate 通过且 contract `1.3.0` 稳定后才执行 P4。记录 predecessor SHA，确认 Harness 最新 migration 为 `0006_p3_release_execution`、累计 Tool 为 14，重新运行 P0–P3 gate，并记录 P3 外部门禁是通过还是阻断。

开始前检查 P1 Knowledge Provider/Binding、P3 EvidenceBundle/Postcondition 的真实字段和服务签名。P4 不得把 predecessor 尚未交付的 provider write API 或 BKAIDev Eval API 当成已存在；所有外部能力均由 Decision Gate 产出显式 mode。

## File Responsibility Map

```text
bkflow/harness/
├── admin.py
├── constants.py
├── contracts.py
├── models.py
├── management/commands/
│   ├── export_harness_candidates.py
│   ├── acknowledge_harness_promotion.py
│   ├── export_harness_eval_package.py
│   └── import_harness_eval_result.py
└── services/
    ├── feedback/
    │   ├── contracts.py
    │   ├── intake.py
    │   ├── attribution.py
    │   └── facade.py
    ├── improvement/
    │   ├── routing.py
    │   ├── package.py
    │   ├── governance.py
    │   └── promotion.py
    └── eval/
        ├── fixtures.py
        ├── runner.py
        └── gate.py

bkflow/apigw/serializers/harness/feedback.py
bkflow/apigw/views/harness/feedback.py
tests/interface/harness/feedback/
tests/interface/harness/improvement/
tests/interface/harness/eval/
tests/fixtures/harness/feedback_cases.yaml
```

### Task 1: Reconcile P3 and Freeze Ownership, Provider, Eval, and Retention Spikes

**Files:**

- Create: `docs/reviews/2026-09-02-bkaidev-harness-p4-feedback-spike.md`
- Reference: `docs/reviews/2026-09-02-bkaidev-harness-p3-verification.md`
- Reference: `bkflow/harness/services/knowledge/providers.py`
- Reference: `bkflow/harness/services/evidence.py`

**Interfaces:**

- Consumes: P3 gate, external knowledge systems, BKAIDev evaluation facility, governance owners and retention policy.
- Produces: `owner_mode`, `promotion_mode`, `eval_mode`, `retention_mode`, promotion thresholds and predecessor SHA.

- [x] **Step 1: Re-run predecessor gates and inventory destinations**

Run P0–P3 gates. Build a table for each destination type and tier: system, owner, reviewer, source binding, draft/publish/readback/rollback capability, receipt format, retention class and test environment. Include Global/Public, platform such as BKFara, Space and Scope.

- [x] **Step 2: Execute SP-P4-01 through SP-P4-08**

```text
SP-P4-01 owner and reviewer resolution
SP-P4-02 external knowledge draft/publish/readback
SP-P4-03 registry and validator change workflow
SP-P4-04 BKAIDev prompt/skill release workflow
SP-P4-05 BKAIDev fixed-release evaluation
SP-P4-06 receipt authenticity and snapshot binding
SP-P4-07 retention consent anonymization and deletion
SP-P4-08 canary rollback and metric availability
```

- [x] **Step 3: Freeze modes and thresholds before candidate promotion**

```text
owner_mode = resolved_owner_map | draft_only
promotion_mode = provider_draft_api | artifact_plus_verified_receipt | no_promotion
eval_mode = signed_bkaidev_eval | local_deterministic_only
retention_mode = approved_policy | intake_disabled
```

Record per-candidate-type thresholds, mandatory zero-regression suites, canary size and rollback trigger before running candidate comparisons.

- [x] **Step 4: Verify and commit**

Run: `rg -n 'SP-P4-0[1-8]|owner_mode =|promotion_mode =|eval_mode =|retention_mode =|predecessor_sha|promotion_thresholds' docs/reviews/2026-09-02-bkaidev-harness-p4-feedback-spike.md`

```bash
git add docs/reviews/2026-09-02-bkaidev-harness-p4-feedback-spike.md
git commit -m "docs(harness): 固化 P4 反馈闭环门禁 --story=136729554"
```

### Task 2: Add P4 Contract, Flags, Taxonomy, and Checkpoints

**Files:**

- Modify: `bkflow/harness/services/contract_versions.py`
- Modify: `bkflow/harness/constants.py`
- Modify: `bkflow/space/configs.py`
- Modify test: `tests/interface/harness/test_contract_versions.py`
- Modify test: `tests/interface/space/test_space_config.py`
- Create test: `tests/interface/harness/feedback/test_feature_gate.py`

**Interfaces:**

- Consumes: contract `1.3.0` and existing Harness enums.
- Produces: contract `1.4.0`, feedback/promotion flags, feedback/attribution/candidate/eval enums and checkpoints.

- [x] **Step 1: Write failing compatibility tests**

Assert `1.4.0` appends only `submit_generation_feedback`, yielding exactly 15 Tools; all earlier sets remain byte-equivalent. Add `harness_feedback_enabled` and owner-only `harness_candidate_promotion_enabled`, both default false.

- [x] **Step 2: Write taxonomy tests**

Freeze feedback types `ACCEPTED`, `REJECTED`, `CORRECTION`, `RUNTIME_ISSUE`, `BUSINESS_OUTCOME`; attribution categories `REQUIREMENT`, `KNOWLEDGE`, `PROMPT`, `SCHEMA`, `RESOLVER`, `VALIDATOR`, `PERMISSION`, `PLUGIN`, `ENVIRONMENT`, `POSTCONDITION`; candidate types `KNOWLEDGE`, `REGISTRY`, `VALIDATOR_POLICY`, `PROMPT_SKILL`, `EVAL`; lifecycle `DRAFT`, `IN_REVIEW`, `APPROVED`, `REJECTED`, `PUBLISHED`, `RETIRED`. Add checkpoints `FEEDBACK_INTAKE` and `PROMOTION_EVAL`.

- [x] **Step 3: Run tests to verify RED**

Run: `pytest tests/interface/harness/test_contract_versions.py tests/interface/harness/feedback/test_feature_gate.py tests/interface/space/test_space_config.py -v --no-cov`

- [x] **Step 4: Implement without altering terminal run outcomes**

Feedback and candidate lifecycles are separate from HarnessRun execution status. `EVIDENCE_FINALIZED` remains terminal; submitting feedback never rewrites historical execution outcome.

- [x] **Step 5: Verify and commit**

```bash
pytest tests/interface/harness/test_contract_versions.py tests/interface/harness/feedback/test_feature_gate.py tests/interface/space/test_space_config.py tests/interface/harness/services/test_state.py -v --no-cov
git add bkflow/harness/services/contract_versions.py bkflow/harness/constants.py bkflow/space/configs.py tests/interface
git commit -m "feat(harness): 增加 P4 反馈评测契约 --story=136729554"
```

### Task 3: Add Feedback, Candidate, and Eval Models

**Files:**

- Modify: `bkflow/harness/models.py`
- Generated: `bkflow/harness/migrations/0007_p4_feedback_evalops.py`
- Create test: `tests/interface/harness/feedback/test_models.py`
- Create test: `tests/interface/harness/improvement/test_models.py`
- Create test: `tests/interface/harness/eval/test_models.py`

**Interfaces:**

- Consumes: HarnessRun, Revision, EvidenceBundle and KnowledgeSourceBinding.
- Produces: `GenerationFeedback`, `ImprovementCandidate`, `KnowledgeCandidate`, `HarnessEvalCase`, `HarnessEvalRun`.

- [x] **Step 1: Write failing feedback and candidate tests**

`GenerationFeedback` stores UUID, run/revision/plan_hash, optional execution/evidence bundle, trusted platform/app/actor/space/scope, feedback type, rating, redacted summary, correction artifact ref, observed outcome, consent scope, idempotency digest, redaction version and timestamps.

`ImprovementCandidate` stores UUID, source feedback/Evidence, candidate type, attribution, sanitized proposal artifact, owner/reviewer refs, target system/tier/scope, status, risk, confidence, regression case refs, impact/rollback artifacts, source/current/target version, promotion receipt digest and timestamps.

`KnowledgeCandidate` has a one-to-one ImprovementCandidate, target KnowledgeSourceBinding, target source ref, proposed snapshot lineage, citation refs and conflict set. It contains no provider credential or unrestricted raw document.

- [x] **Step 2: Write failing Eval model tests**

`HarnessEvalCase` is immutable and stores case ID/version, source candidate, tier/scope, sanitized input artifact, expected invariants, scoring schema, safety tags and fixture hash. `HarnessEvalRun` stores candidate, base/candidate release versions, runner mode, package/result hashes, signed result ref/digest, aggregate metrics, safety result, threshold snapshot, status and timestamps.

- [x] **Step 3: Run tests to verify RED**

Run: `pytest tests/interface/harness/feedback/test_models.py tests/interface/harness/improvement/test_models.py tests/interface/harness/eval/test_models.py -v --no-cov`

- [x] **Step 4: Implement and generate migration**

```bash
python manage.py makemigrations harness --name p4_feedback_evalops
python manage.py sqlmigrate harness 0007
python manage.py makemigrations harness --check
```

- [x] **Step 5: Verify and commit**

```bash
pytest tests/interface/harness/feedback/test_models.py tests/interface/harness/improvement/test_models.py tests/interface/harness/eval/test_models.py tests/interface/harness/release/test_models.py -v --no-cov
git add bkflow/harness/models.py bkflow/harness/migrations tests/interface/harness
git commit -m "feat(harness): 新增反馈候选与评测模型 --story=136729554"
```

### Task 4: Implement Feedback Intake, Provenance, and Redaction

**Files:**

- Create: `bkflow/harness/services/feedback/contracts.py`
- Create: `bkflow/harness/services/feedback/intake.py`
- Create: `bkflow/harness/services/feedback/facade.py`
- Modify: `bkflow/harness/services/evidence.py`
- Create test: `tests/interface/harness/feedback/test_intake.py`
- Create test: `tests/interface/harness/feedback/test_redaction.py`

**Interfaces:**

- Consumes: trusted context, existing Run/Revision/Execution/Evidence, user feedback and consent policy.
- Produces: `submit_generation_feedback_with_context(context, payload) -> Envelope` and immutable feedback provenance.

- [x] **Step 1: Write failing intake tests**

Request requires run_id, revision_id, expected_plan_hash, feedback_type, consent_scope and idempotency_key; optional fields are rating, summary, correction_artifact_ref, execution_id and observed_outcome. Test ownership, plan binding, evidence reference, consent/retention, repeated feedback, conflicting idempotency payload, cross-space refs and feedback on validation/debug/runtime failures.

- [x] **Step 2: Write adversarial redaction tests**

Cover credentials, tokens, user tickets, approval receipts, embedded log payloads, prompt injection and attempts to set owner/status/target tier. Only trusted context sets identity; user content is stored as untrusted data and cannot choose promotion state.

- [x] **Step 3: Run tests to verify RED**

Run: `pytest tests/interface/harness/feedback/test_intake.py tests/interface/harness/feedback/test_redaction.py -v --no-cov`

- [x] **Step 4: Implement bounded intake**

Resolve and authorize all references before reading artifacts. Redact before persistence, cap inline summary, store oversized sanitized content as an Artifact, emit Evidence and return a feedback ref plus `next_actions=[]`. Intake does not build or publish a candidate inside the request transaction.

- [x] **Step 5: Verify and commit**

```bash
pytest tests/interface/harness/feedback/test_intake.py tests/interface/harness/feedback/test_redaction.py tests/interface/harness/release/test_evidence_bundle.py -v --no-cov
git add bkflow/harness/services/feedback bkflow/harness/services/evidence.py tests/interface/harness/feedback
git commit -m "feat(harness): 接收脱敏且可追溯的生成反馈 --story=136729554"
```

### Task 5: Implement Deterministic Failure Attribution

**Files:**

- Create: `bkflow/harness/services/feedback/attribution.py`
- Create: `bkflow/harness/data/attribution_rules.yaml`
- Create test: `tests/interface/harness/feedback/test_attribution.py`
- Create test: `tests/interface/harness/feedback/test_attribution_rules.py`

**Interfaces:**

- Consumes: GenerationFeedback, ValidationReport, Evidence events, debug/runtime/postcondition errors and versioned rules.
- Produces: ordered `AttributionResult` values with category, evidence refs, confidence, ambiguity and recommended candidate types.

- [x] **Step 1: Write failing attribution table tests**

Cover all ten categories with positive, competing and insufficient-evidence cases. Security/permission/schema drift/validator/postcondition codes take precedence over text similarity. Plugin and environment attribution requires concrete runtime Evidence; missing proof yields ambiguity, not a confident label.

- [x] **Step 2: Write poisoning and determinism tests**

The same normalized Evidence plus rule version must produce the same ordered result/hash. Feedback text cannot override hard Evidence, inject a new rule or broaden target scope. Confidence below the frozen threshold routes to human triage and creates no auto-drafted content.

- [x] **Step 3: Run tests to verify RED**

Run: `pytest tests/interface/harness/feedback/test_attribution.py tests/interface/harness/feedback/test_attribution_rules.py -v --no-cov`

- [x] **Step 4: Implement versioned rules**

Rules reference typed error/event/postcondition codes and required Evidence fields, never executable expressions. Persist rule version and evidence refs with each result. High-risk failures always recommend `VALIDATOR_POLICY` plus `EVAL`, even when a knowledge candidate is also useful.

- [x] **Step 5: Verify and commit**

```bash
pytest tests/interface/harness/feedback/test_attribution.py tests/interface/harness/feedback/test_attribution_rules.py -v --no-cov
git add bkflow/harness/services/feedback/attribution.py bkflow/harness/data/attribution_rules.yaml tests/interface/harness/feedback
git commit -m "feat(harness): 增加基于证据的失败归因 --story=136729554"
```

### Task 6: Build and Route Governed Improvement Candidate Packages

**Files:**

- Create: `bkflow/harness/services/improvement/routing.py`
- Create: `bkflow/harness/services/improvement/package.py`
- Create: `bkflow/harness/management/commands/export_harness_candidates.py`
- Create test: `tests/interface/harness/improvement/test_routing.py`
- Create test: `tests/interface/harness/improvement/test_package.py`
- Create test: `tests/interface/harness/improvement/test_export_command.py`

**Interfaces:**

- Consumes: attribution, trusted source context, P1 KnowledgeSourceBinding and Owner map.
- Produces: typed candidates and a sanitized, hash-addressed review package.

- [ ] **Step 1: Write failing routing tests**

Route `KNOWLEDGE` to the most specific eligible target Binding without broadening tier; `REGISTRY` to capability owner; `VALIDATOR_POLICY` to BKFlow owner; `PROMPT_SKILL` to BKAIDev Agent Release owner; `EVAL` to Harness Eval owner. Missing or ambiguous Owner leaves candidate DRAFT with an explicit reason.

- [ ] **Step 2: Write failing package tests**

Each package contains candidate/provenance refs, sanitized proposal, evidence citations, current and proposed version/snapshot, applicability and exclusions, risk/blast radius, regression cases, evaluation requirements and rollback steps. It excludes raw user content, secrets and unbounded logs.

- [ ] **Step 3: Write command safety tests**

`export_harness_candidates --candidate-id <uuid> --output <dir>` exports only an approved-for-review package after path and ownership validation. Batch filters require explicit type/status/space and default to dry-run. The command never changes candidate status.

- [ ] **Step 4: Run tests to verify RED**

Run: `pytest tests/interface/harness/improvement/test_routing.py tests/interface/harness/improvement/test_package.py tests/interface/harness/improvement/test_export_command.py -v --no-cov`

- [ ] **Step 5: Implement, verify, and commit**

```bash
pytest tests/interface/harness/improvement/test_routing.py tests/interface/harness/improvement/test_package.py tests/interface/harness/improvement/test_export_command.py -v --no-cov
git add bkflow/harness/services/improvement bkflow/harness/management/commands/export_harness_candidates.py tests/interface/harness/improvement
git commit -m "feat(harness): 生成分层归属的改进候选包 --story=136729554"
```

### Task 7: Implement Owner Review, Publication Acknowledgment, and Rollback Governance

**Files:**

- Create: `bkflow/harness/services/improvement/governance.py`
- Create: `bkflow/harness/services/improvement/promotion.py`
- Create: `bkflow/harness/admin.py`
- Create: `bkflow/harness/management/commands/acknowledge_harness_promotion.py`
- Create test: `tests/interface/harness/improvement/test_governance.py`
- Create test: `tests/interface/harness/improvement/test_promotion.py`
- Create test: `tests/interface/harness/improvement/test_acknowledge_command.py`

**Interfaces:**

- Consumes: candidate package, Owner/Reviewer decisions, external receipt/snapshot and promotion policy.
- Produces: legal lifecycle transitions, verified publication acknowledgment and rollback state.

- [ ] **Step 1: Write failing lifecycle tests**

Allow DRAFT -> IN_REVIEW -> APPROVED -> PUBLISHED -> RETIRED and IN_REVIEW -> REJECTED. Submitter cannot self-approve where policy requires separation. Any proposal, tier, scope, source snapshot or regression change after approval creates a new candidate revision and invalidates approval.

- [ ] **Step 2: Write failing knowledge closed-loop tests**

For provider draft API mode, approved candidates may create an external draft but never auto-publish. For artifact mode, Owner publishes externally. `acknowledge_harness_promotion` verifies receipt, reads back the exact source/version/snapshot through the P1 Provider, updates Binding snapshot metadata and records previous snapshot for rollback. A mismatched or unreadable snapshot is rejected.

- [ ] **Step 3: Write failing non-knowledge governance tests**

Registry/Validator/Prompt/Skill acknowledgments require the destination release/version and immutable change reference. They cannot be marked PUBLISHED until their mandatory regression/Eval gate passes. Rollback records target version, reason, operator and verified readback.

- [ ] **Step 4: Run tests to verify RED**

Run: `pytest tests/interface/harness/improvement/test_governance.py tests/interface/harness/improvement/test_promotion.py tests/interface/harness/improvement/test_acknowledge_command.py -v --no-cov`

- [ ] **Step 5: Implement owner-only controls and commit**

Use Django permissions plus Owner map for Admin actions; keep them out of MCP dispatch. All command mutation requires `--apply`, a candidate ID, receipt ref and expected target version. Persist receipt digests, never receipt plaintext.

```bash
pytest tests/interface/harness/improvement/test_governance.py tests/interface/harness/improvement/test_promotion.py tests/interface/harness/improvement/test_acknowledge_command.py -v --no-cov
git add bkflow/harness/services/improvement bkflow/harness/admin.py bkflow/harness/management/commands/acknowledge_harness_promotion.py tests/interface/harness/improvement
git commit -m "feat(harness): 建立候选审核发布与回滚治理 --story=136729554"
```

### Task 8: Implement Local Eval Packages and Signed BKAIDev Result Import

**Files:**

- Create: `bkflow/harness/services/eval/fixtures.py`
- Create: `bkflow/harness/services/eval/runner.py`
- Create: `bkflow/harness/services/eval/gate.py`
- Create: `bkflow/harness/management/commands/export_harness_eval_package.py`
- Create: `bkflow/harness/management/commands/import_harness_eval_result.py`
- Create test: `tests/interface/harness/eval/test_fixtures.py`
- Create test: `tests/interface/harness/eval/test_runner.py`
- Create test: `tests/interface/harness/eval/test_gate.py`
- Create test: `tests/interface/harness/eval/test_commands.py`

**Interfaces:**

- Consumes: candidate, versioned Eval cases, frozen thresholds, local Harness services and optional signed BKAIDev results.
- Produces: deterministic local EvalRun, export package, verified external EvalRun and promotion decision.

- [ ] **Step 1: Write failing fixture and local-runner tests**

Derive immutable regression cases from sanitized feedback/Evidence only after Owner review. Local runner covers resolver, schema, validation, ACL, policy, postcondition and security invariants without calling an LLM. Fixture hashes and base/candidate versions make runs reproducible.

- [ ] **Step 2: Write failing export/import tests**

Export contains sanitized cases, expected invariants, scoring schema, fixed BKAIDev Agent Release, MCP contract and knowledge snapshots. Import verifies signer/receipt, exact package hash, release/config versions, complete case set and metric schema; partial or unsigned results cannot pass.

- [ ] **Step 3: Write failing promotion-gate tests**

Gate requires all mandatory local safety suites, pre-registered type-specific thresholds, zero cross-space/permission/secret regressions, and signed BKAIDev generation results for Prompt/Skill/Knowledge changes that affect model behavior. Metric improvement cannot offset a safety regression.

- [ ] **Step 4: Run tests to verify RED**

Run: `pytest tests/interface/harness/eval/test_fixtures.py tests/interface/harness/eval/test_runner.py tests/interface/harness/eval/test_gate.py tests/interface/harness/eval/test_commands.py -v --no-cov`

- [ ] **Step 5: Implement, verify, and commit**

```bash
pytest tests/interface/harness/eval/test_fixtures.py tests/interface/harness/eval/test_runner.py tests/interface/harness/eval/test_gate.py tests/interface/harness/eval/test_commands.py -v --no-cov
git add bkflow/harness/services/eval bkflow/harness/management/commands/export_harness_eval_package.py bkflow/harness/management/commands/import_harness_eval_result.py tests/interface/harness/eval
git commit -m "feat(harness): 增加版本化评测与晋级门禁 --story=136729554"
```

### Task 9: Expose submit_generation_feedback and Synchronize APIGW

**Files:**

- Create: `bkflow/apigw/serializers/harness/feedback.py`
- Create: `bkflow/apigw/views/harness/feedback.py`
- Modify: `bkflow/apigw/views/harness/common.py`
- Modify: `bkflow/apigw/urls.py`
- Modify: `bkflow/harness/services/facade.py`
- Modify: `bkflow/apigw/management/commands/data/api-resources.yml`
- Create: `bkflow/apigw/docs/zh/harness_submit_generation_feedback.md`
- Generated: `bkflow/apigw/docs/apigw-docs.zip`
- Modify: `docs/specs/2026-09-01-bkaidev-a2flow-harness-design.md`
- Modify: `docs/reviews/2026-09-02-bkaidev-harness-p4-feedback-spike.md`
- Create test: `tests/interface/apigw/test_harness_p4.py`
- Modify test: `tests/interface/apigw/test_harness_resource_contract.py`

**Interfaces:**

- Consumes: feedback facade, contract `1.4.0`, HarnessPermission and trusted APIGW context.
- Produces: operation `harness_submit_generation_feedback` mapped to the fifteenth MCP-visible Tool.

- [ ] **Step 1: Write failing API and resource tests**

Test request/Envelope schema, trusted identity, run ownership, contract version, flag, idempotency, input bounds, secret rejection, earlier-contract rejection and exact APIGW auth settings. Assert candidate owner/status/target fields are absent from the public serializer.

- [ ] **Step 2: Run tests to verify RED**

Run: `pytest tests/interface/apigw/test_harness_p4.py tests/interface/apigw/test_harness_resource_contract.py tests/interface/harness/test_contract_versions.py -v --no-cov`

- [ ] **Step 3: Add facade, endpoint and APIGW docs**

Route POST `/space/{space_id}/harness/submit_generation_feedback/`, operation ID `harness_submit_generation_feedback`. Document feedback consent/provenance, untrusted-data treatment, no auto-learning guarantee and the Owner-controlled closure path.

- [ ] **Step 4: Record the BKAIDev 15-Tool release contract**

Update the P4 spike with sanitized Agent Release evidence: one SaaS-native Agent, one logical Harness MCP, contract `1.4.0`, exactly 15 Tools, pinned Prompt/model/policy/knowledge snapshots, and feedback Tool available only to intended spaces. No Agent SDK or second runtime is introduced.

- [ ] **Step 5: Synchronize and commit**

```bash
bash scripts/apigw_docs.sh
pytest tests/interface/apigw/test_harness_p4.py tests/interface/apigw/test_harness_resource_contract.py tests/interface/harness/test_contract_versions.py -v --no-cov
unzip -l bkflow/apigw/docs/apigw-docs.zip | rg 'harness_submit_generation_feedback'
git diff --check
git add bkflow/apigw bkflow/harness/services/facade.py docs/specs/2026-09-01-bkaidev-a2flow-harness-design.md docs/reviews/2026-09-02-bkaidev-harness-p4-feedback-spike.md tests/interface/apigw
git commit -m "feat(harness): 暴露 P4 生成反馈 Tool --story=136729554"
```

### Task 10: Add Closed-Loop Golden Cases and the P4 Gate

**Files:**

- Create: `tests/fixtures/harness/feedback_cases.yaml`
- Create: `tests/interface/harness/feedback/test_golden_cases.py`
- Create: `tests/interface/harness/improvement/test_closed_loop.py`
- Create: `tests/interface/harness/eval/test_promotion_regression.py`
- Create: `tests/interface/harness/feedback/test_secret_non_disclosure.py`
- Create: `docs/reviews/2026-09-02-bkaidev-harness-p4-verification.md`
- Modify: `Makefile`

**Interfaces:**

- Consumes: 15-Tool contract, feedback/candidate/governance/Eval services and external modes.
- Produces: deterministic 42-case suite, `make harness-p4-gate`, and final local/external closure verdict.

- [ ] **Step 1: Define exactly 42 Golden Cases**

```text
feedback_validation_redaction      6
idempotency_and_provenance         5
evidence_based_attribution         8
candidate_owner_and_tier_routing   6
review_publish_rollback            6
eval_and_promotion_regression      5
cross_space_and_poisoning_denial   4
external_receipt_and_readback      2
total                             42
```

- [ ] **Step 2: Implement end-to-end closure assertions**

At least one case per candidate type must traverse feedback -> attribution -> DRAFT -> review -> approved package -> eval -> verified publication or explicit external block -> readback/rollback reference. Assert no case directly changes production knowledge, Registry, Validator, Prompt or Skill from a Tool call.

- [ ] **Step 3: Add the P4 gate target**

`make harness-p4-gate` runs migration checks, P0–P4 suites, exactly 42 cases, contract count 15, attribution determinism, cross-space negatives, secret scans, APIGW consistency and `git diff --check`.

- [ ] **Step 4: Run local verification and record evidence**

```bash
make harness-p4-gate
python manage.py makemigrations harness --check
git diff --check
```

Record predecessor/current SHA, exact case/test counts, external modes, frozen thresholds, owner coverage, published snapshots, rollback proof and every missing piece. Separate local deterministic checks from BKAIDev model evaluation and provider publication evidence.

- [ ] **Step 5: Apply verdict and commit**

`P4_LOCAL_GATE_PASSED` requires all local suites. `P4_KNOWLEDGE_CLOSED_LOOP_PASSED` requires one non-production provider candidate with Owner approval, eval, publication receipt, exact snapshot readback and rollback proof. `P4_BKAIDEV_EVAL_GATE_PASSED` requires signed fixed-release results. Otherwise use `P4_CLOSED_LOOP_GATE_BLOCKED_BY_EXTERNAL_EVIDENCE`; never promote by relabeling missing evidence.

```bash
git add tests/fixtures/harness/feedback_cases.yaml tests/interface/harness/feedback/test_golden_cases.py tests/interface/harness/improvement/test_closed_loop.py tests/interface/harness/eval/test_promotion_regression.py tests/interface/harness/feedback/test_secret_non_disclosure.py docs/reviews/2026-09-02-bkaidev-harness-p4-verification.md Makefile
git commit -m "test(harness): 建立 P4 反馈闭环验收门禁 --story=136729554"
```

## P4 Completion Evidence

- Contract `1.4.0` exposes exactly 15 cumulative Tools and earlier contracts remain compatible.
- Feedback is redacted, consent-aware, idempotent and bound to immutable run/revision/evidence provenance.
- Candidate routing preserves Global/Public/Platform/Space/Scope ownership and never broadens applicability automatically.
- Knowledge remains in platform repositories; BKFlow governs candidate, snapshot, Eval, receipt and rollback metadata.
- No Tool call directly updates online Knowledge/Registry/Validator/Prompt/Skill content.
- Forty-two Golden Cases pass locally; knowledge publication and BKAIDev generation evaluation retain separate external gates.

## Execution Handoff

After this plan is approved, implement it with one of the following:

1. **Subagent-Driven Development (recommended):** execute each task with independent implementation/review passes, especially for redaction, ownership, external receipt verification and promotion gates.
2. **Inline Execution:** use `superpowers:executing-plans` in a separate implementation session and stop whenever a Decision Gate lacks evidence or a safety regression appears.

P4 local completion does not authorize production promotion. Enable candidate promotion only for destinations with resolved Owner, verified receipts, passing frozen gates and tested rollback.
