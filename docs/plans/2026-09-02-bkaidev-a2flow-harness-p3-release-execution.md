# BKAIDev a2flow Harness P3 Release and Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通调试通过后的复验、审批、发布、应用态执行、受控操作和业务后置条件验证，形成可恢复且可审计的发布执行闭环。

**Architecture:** `prepare_release` 将不可变 Revision、CapabilityBinding、调试 Evidence 和风险策略固化为 `ReleaseManifest`；高风险动作通过服务端可验证的 `ApprovalRequest` 绑定精确 `plan_hash` 和 action digest。发布复用模板领域服务，执行通过 `ExecutionSaga` 分离 create/start 并持久化断点，所有运行状态和 Evidence 保留在 Interface 数据库，Engine 只保存任务执行状态。

**Tech Stack:** Python 3.9.12、Django 3.2.25、Django REST Framework 3.12.4、pytest、BKFlow Template/Task domain services、TaskComponentClient、APIGW。

**Spec:** `docs/specs/2026-09-01-bkaidev-a2flow-harness-design.md`

## Global Constraints

- P3 新增 `prepare_release`、`publish_workflow`、`start_workflow_execution`、`get_workflow_execution`、`control_workflow_execution`，累计 14 Tool。
- BKAIDev Agent 仍是唯一 LLM 调用方；Harness MCP 只暴露稳定控制面，不在 BKFlow 内运行推理循环。
- 发布、执行和控制前必须重新 Resolve 全部 CapabilityBinding，并校验 revision、plan_hash、schema_hash、草稿树指纹和目标环境。
- `prepare_release` 只生成不可变 Manifest 和审批需求，不发布、不创建任务。
- `publish_workflow` 只发布模板快照；`start_workflow_execution` 先创建任务、持久化 task_ref，再单独 start。
- 审批必须由可信服务端校验，并绑定 platform_app、actor、space/scope、plan_hash、action digest、风险和有效期；模型文本不是审批。
- 平台应用代表真实用户执行；App Secret、BKFlow Token、用户票据、Credential 明文和审批凭证明文不得进入 Tool/Persistence/Evidence/Log。
- P3 若复用需要 `sdk_*` BKFlow Token 的接口，必须通过 P2 Token Broker 为平台应用和真实用户签发最小 TEMPLATE/TASK lease；若走本计划抽取的同进程领域服务，则由 HarnessPermission 与 action policy 完成授权，不为绕过检查而伪造无意义 Token。
- Engine `FINISHED` 不等于业务成功；必须按固定 Postcondition DSL 验证，失败分类为 `POSTCONDITION`。
- 页面刷新、Tool 超时或 Worker 重启后，create/start/publish/control 重试不得重复产生副作用。
- P3 contract 为 `1.3.0`；`1.0.0`、`1.1.0`、`1.2.0` 保持兼容。
- P3 发布和执行开关默认关闭；只读查询在开关关闭后仍可读取既有 Execution/Evidence。
- migration 使用 `python manage.py makemigrations harness --name p3_release_execution` 生成。
- APIGW 三件套同步；提交统一使用 `--story=136729554`。

---

## Inherited Contracts

- P0 trusted context、不可变 Revision、plan_hash、CapabilityBinding、ValidationReport、幂等和 managed draft ownership。
- P1 联邦 Knowledge Router 仅提供带来源的建议，不构成发布或执行授权。
- P2 DebugSession、TokenLease、EvidenceEvent、调试树指纹、debug-specific ApprovalVerifier、Mock/Real 门禁和 9-Tool contract。
- 当前 `Template.release_template(data)`、模板快照、版本号检查、TemplateOperationRecord 和发布 Webhook 行为。
- 当前任务 API 的创建逻辑、`TaskComponentClient.create_task/detail/states/operate_task/node_operate`，以及 task/node 现有操作集合。

## Decision Gates

- **DG-P3-01 Approval verifier:** BKAIDev 或平台审批系统必须提供可服务端验签/回查的 receipt。只有用户确认文案而无可验证凭据时，发布、执行和高风险控制 fail-closed。
- **DG-P3-02 Application identity and token path:** 确认 APIGW 注入 platform_app 和真实 actor，平台应用能按空间策略代表该用户调用 BKFlow；逐动作冻结使用领域服务还是 token-protected SDK 路径。SDK 路径必须经 Token Broker，不得回退为开发者个人身份或让 Agent 持有 Token。
- **DG-P3-03 Create/start recovery:** 验证 TaskComponentClient 的 create 成功响应、查询和 start 幂等边界。无法确认 Engine start 幂等时，Saga 必须依靠本地行锁和持久化断点做到 at-most-once dispatch。
- **DG-P3-04 Runtime readback:** 确认任务状态、节点状态、输出和 Webhook Evidence 的可查询来源；缺少某类来源时，对应 Postcondition 不得声明支持。
- **DG-P3-05 Global real debug:** 仅在受控测试环境白名单、P2 real-step 门禁和本阶段审批策略同时成立后开放；否则维持 Mock-only。

## Reconciliation Check

只有 P2 本地 gate 通过且 contract `1.2.0` 稳定后才执行 P3。记录 predecessor SHA，确认 Harness 最新 migration 为 `0005_p2_debug_token_broker`、累计 Tool 为 9，并重新运行 P0/P1/P2 gate。

实施前逐一确认 `Template.release_template(data)`、`bkflow/apigw/views/release_template.py`、`bkflow/apigw/views/create_task.py` 和 `TaskComponentClient` 当前签名及副作用。确认 create 只创建任务，start 由 `operate_task(task_id, "start")` 单独触发；若事实变化，先更新 characterization tests 和本计划。

## File Responsibility Map

```text
bkflow/harness/
├── constants.py
├── contracts.py
├── models.py
└── services/
    ├── approval.py
    ├── evidence.py
    ├── release/
    │   ├── policy.py
    │   ├── prepare.py
    │   ├── publish.py
    │   └── facade.py
    └── execution/
        ├── contracts.py
        ├── adapter.py
        ├── saga.py
        ├── postconditions.py
        ├── control.py
        └── facade.py

bkflow/template/services/release.py
bkflow/task/services/task_creator.py
bkflow/apigw/serializers/harness/release_execution.py
bkflow/apigw/views/harness/release_execution.py
tests/interface/harness/release/
tests/interface/harness/execution/
tests/fixtures/harness/release_execution_cases.yaml
```

### Task 1: Reconcile P2 and Freeze Approval, Runtime, and Recovery Spikes

**Files:**

- Create: `docs/reviews/2026-09-02-bkaidev-harness-p3-runtime-spike.md`
- Reference: `docs/reviews/2026-09-02-bkaidev-harness-p2-verification.md`
- Reference: `bkflow/apigw/views/release_template.py`
- Reference: `bkflow/apigw/views/create_task.py`
- Reference: `bkflow/contrib/api/collections/task.py`

**Interfaces:**

- Consumes: P2 gate, BKAIDev approval behavior, template release and task runtime semantics.
- Produces: `approval_mode`, `identity_mode`, `runtime_authorization_mode`, `publish_mode`, `execution_recovery_mode`, `readback_mode`, `global_real_mode` and predecessor SHA.

- [ ] **Step 1: Re-run predecessor gates and characterize release/runtime**

Run P0 through P2 gates. Add throwaway/manual probes or focused tests that record release side effects, task create response, separate start behavior, task/node state readback and retry outcomes; do not publish or execute in production space.

- [ ] **Step 2: Execute SP-P3-01 through SP-P3-08**

```text
SP-P3-01 approval receipt verification and expiry
SP-P3-02 platform application plus real-user identity
SP-P3-03 per-action domain-service versus SDK token path
SP-P3-04 release idempotency and version collision
SP-P3-05 create success followed by response loss
SP-P3-06 start success followed by response loss
SP-P3-07 task/node/output and webhook readback coverage
SP-P3-08 controlled-environment global real debug
```

- [ ] **Step 3: Freeze decisions**

```text
approval_mode = verifiable_receipt | deny_gated_actions
identity_mode = trusted_platform_user | deny_execution
runtime_authorization_mode = harness_domain_service | brokered_sdk_token | deny_action
publish_mode = extracted_domain_service
execution_recovery_mode = persisted_create_start_saga
readback_mode = task_client_plus_evidence
global_real_mode = allowlisted | deny_global_real
```

Any deny value blocks only the corresponding externally gated capability; it does not turn missing evidence into a pass.

- [ ] **Step 4: Verify and commit**

Run: `rg -n 'SP-P3-0[1-8]|approval_mode =|identity_mode =|runtime_authorization_mode =|publish_mode =|execution_recovery_mode =|readback_mode =|global_real_mode =|predecessor_sha' docs/reviews/2026-09-02-bkaidev-harness-p3-runtime-spike.md`

```bash
git add docs/reviews/2026-09-02-bkaidev-harness-p3-runtime-spike.md
git commit -m "docs(harness): 固化 P3 发布执行门禁 --story=136729554"
```

### Task 2: Add P3 Contract, Feature Flags, States, and Checkpoints

**Files:**

- Modify: `bkflow/harness/services/contract_versions.py`
- Modify: `bkflow/harness/constants.py`
- Modify: `bkflow/space/configs.py`
- Modify: `bkflow/harness/services/debug/policy.py`
- Modify test: `tests/interface/harness/test_contract_versions.py`
- Modify test: `tests/interface/space/test_space_config.py`
- Create test: `tests/interface/harness/release/test_feature_gate.py`
- Modify test: `tests/interface/harness/debug/test_real_step_policy.py`

**Interfaces:**

- Consumes: contract `1.2.0` and current HarnessRun state machine.
- Produces: contract `1.3.0`, publish/execution/global-real flags, release/execution checkpoints and action/risk enums.

- [ ] **Step 1: Write failing compatibility and flag tests**

Assert `1.3.0` appends exactly the five P3 Tools in frozen order, while the previous Toolsets are byte-equivalent. Add `harness_publish_enabled`, `harness_execution_enabled` and the database-safe `harness_global_real_enabled`, all default false; dependent effective values are false when their parent capability is disabled.

- [ ] **Step 2: Write failing state/checkpoint tests**

Cover `DEBUGGING -> RELEASE_READY -> APPROVAL_PENDING/PUBLISHING -> PUBLISHED -> EXECUTING -> SUCCEEDED/FAILED/CANCELLED -> EVIDENCE_FINALIZED`, stale-plan return to `DRAFT_READY`, and ValidationCheckpoint values `PREPARE_RELEASE`, `PUBLISH`, `PRE_EXECUTE`, `POSTCONDITION`.

- [ ] **Step 3: Run tests to verify RED**

Run: `pytest tests/interface/harness/test_contract_versions.py tests/interface/harness/release/test_feature_gate.py tests/interface/harness/debug/test_real_step_policy.py tests/interface/space/test_space_config.py -v --no-cov`

- [ ] **Step 4: Implement phase controls**

Append tools in order prepare, publish, start, get, control. Add states/checkpoints without renaming historical enum values. Global Real requires all of P2 real-step policy, an allowlisted target environment, a release-bound approval decision and the global-real flag.

- [ ] **Step 5: Verify and commit**

```bash
pytest tests/interface/harness/test_contract_versions.py tests/interface/harness/release/test_feature_gate.py tests/interface/harness/debug/test_real_step_policy.py tests/interface/space/test_space_config.py tests/interface/harness/services/test_state.py -v --no-cov
git add bkflow/harness/services/contract_versions.py bkflow/harness/constants.py bkflow/space/configs.py bkflow/harness/services/debug/policy.py tests/interface
git commit -m "feat(harness): 增加 P3 契约状态与执行开关 --story=136729554"
```

### Task 3: Add ApprovalRequest, ReleaseManifest, ReleasePublication, ExecutionRun, and EvidenceBundle

**Files:**

- Modify: `bkflow/harness/models.py`
- Generated: `bkflow/harness/migrations/0006_p3_release_execution.py`
- Create test: `tests/interface/harness/release/test_models.py`
- Create test: `tests/interface/harness/execution/test_models.py`
- Modify test: `tests/interface/harness/debug/test_models.py`

**Interfaces:**

- Consumes: HarnessRun, WorkflowPlanRevision, DebugSession and EvidenceEvent.
- Produces: five persistent P3 aggregate models, generalized action-bound TokenLease metadata and portable uniqueness/ownership constraints.

- [ ] **Step 1: Write failing approval and manifest model tests**

`ApprovalRequest` stores UUID, run/revision, plan_hash, action, action_digest, platform/app/actor/space/scope, normalized risk summary, receipt provider/ref/digest, status, requested/verified/expiry timestamps and verifier version. It has no receipt plaintext.

`ReleaseManifest` is append-only and stores UUID, run/revision, plan_hash, draft template/fingerprint, capability snapshot, validation/debug evidence refs, postcondition spec, risk manifest, required approvals, policy version, manifest hash and created_at. Update/delete are rejected.

`ReleasePublication` is an append-only one-to-one result for the Manifest. It stores the exact published template/snapshot/version, operator and publish idempotency reference so a response-loss retry can read back success without mutating the Manifest or repeating release side effects.

- [ ] **Step 2: Write failing execution and bundle model tests**

`ExecutionRun` stores UUID, manifest, published template/snapshot/version, task_ref, status, create/start/control idempotency refs, trusted actor/app/space/scope, target environment, postcondition status/report, last engine state, heartbeat and terminal timestamps. Enforce one logical execution per `(manifest, start_idempotency_key)`.

`EvidenceBundle` is append-only and stores UUID, run, optional execution, ordered Evidence refs/artifact refs, redaction version, bundle hash, outcome, finalized_at and retention class.

Generalize P2 `TokenLease`: exactly one of DebugSession or ExecutionRun is set, and execution leases additionally store action/action_digest plus TEMPLATE/TASK resource and minimal permission. Existing debug rows and APIs remain compatible; no plaintext field is added.

- [ ] **Step 3: Run tests to verify RED**

Run: `pytest tests/interface/harness/release/test_models.py tests/interface/harness/execution/test_models.py tests/interface/harness/debug/test_models.py -v --no-cov`

- [ ] **Step 4: Implement and generate migration**

```bash
python manage.py makemigrations harness --name p3_release_execution
python manage.py sqlmigrate harness 0006
python manage.py makemigrations harness --check
```

- [ ] **Step 5: Verify and commit**

```bash
pytest tests/interface/harness/release/test_models.py tests/interface/harness/execution/test_models.py tests/interface/harness/debug/test_models.py -v --no-cov
git add bkflow/harness/models.py bkflow/harness/migrations tests/interface/harness/release/test_models.py tests/interface/harness/execution/test_models.py
git commit -m "feat(harness): 新增发布执行审批与证据模型 --story=136729554"
```

### Task 4: Implement Approval Verification, Action Policy, and Evidence Bundles

**Files:**

- Create: `bkflow/harness/services/approval.py`
- Modify: `bkflow/harness/services/debug/approval.py`
- Modify: `bkflow/harness/services/debug/policy.py`
- Modify: `bkflow/harness/services/evidence.py`
- Create: `bkflow/harness/services/release/policy.py`
- Create test: `tests/interface/harness/release/test_approval.py`
- Modify test: `tests/interface/harness/debug/test_real_step_policy.py`
- Create test: `tests/interface/harness/release/test_action_policy.py`
- Create test: `tests/interface/harness/release/test_evidence_bundle.py`

**Interfaces:**

- Consumes: trusted context, receipt reference, immutable plan/action digest, EvidenceEvent and risk policy.
- Produces: `ApprovalVerifier`, `ActionPolicy.evaluate`, `finalize_evidence_bundle` and fail-closed decisions.

- [ ] **Step 1: Write failing approval tests**

Extract the P2 debug-specific contract into `ApprovalVerifier.verify(receipt_ref, expected_claims) -> ApprovalDecision`, leaving a compatibility import in `debug/approval.py`. Test forged, expired, reused, wrong actor/app/space/scope/environment/plan/action, verifier outage and revoked receipt. No configured verifier returns `APPROVAL_REQUIRED`; verifier uncertainty returns `APPROVAL_INVALID` and never falls back to prompt text.

- [ ] **Step 2: Write failing policy and bundle tests**

Policy maps prepare/read to L0, publish/start/pause/resume/revoke to configured L2, and retry/skip/callback/forced_fail/skip_exg/skip_cpg to action-specific L2/L3. Bundle ordering and hash are deterministic; secrets and large payloads are redacted or artifact-referenced.

- [ ] **Step 3: Run tests to verify RED**

Run: `pytest tests/interface/harness/release/test_approval.py tests/interface/harness/release/test_action_policy.py tests/interface/harness/release/test_evidence_bundle.py tests/interface/harness/debug/test_real_step_policy.py -v --no-cov`

- [ ] **Step 4: Implement service abstractions**

Persist only receipt metadata/digest and normalized verifier result. Build action digest from tool, manifest hash, plan hash, target resource, normalized parameters and policy version. Finalize Evidence only after terminal execution plus postconditions; finalized bundles cannot be amended.

- [ ] **Step 5: Verify and commit**

```bash
pytest tests/interface/harness/release/test_approval.py tests/interface/harness/release/test_action_policy.py tests/interface/harness/release/test_evidence_bundle.py tests/interface/harness/debug/test_real_step_policy.py -v --no-cov
git add bkflow/harness/services/approval.py bkflow/harness/services/debug/approval.py bkflow/harness/services/debug/policy.py bkflow/harness/services/evidence.py bkflow/harness/services/release tests/interface/harness/release tests/interface/harness/debug/test_real_step_policy.py
git commit -m "feat(harness): 增加服务端审批策略与证据包 --story=136729554"
```

### Task 5: Implement prepare_release

**Files:**

- Create: `bkflow/harness/services/release/prepare.py`
- Create: `bkflow/harness/services/release/facade.py`
- Create test: `tests/interface/harness/release/test_prepare_release.py`

**Interfaces:**

- Consumes: latest immutable Revision, managed draft, resolver, Validator, Debug Evidence, ActionPolicy and idempotency service.
- Produces: `prepare_release_with_context(context, payload) -> Envelope` containing Manifest and approval summary.

- [ ] **Step 1: Write failing preparation tests**

Require a closed request containing only run_id, revision_id, expected_plan_hash and idempotency_key. Require HarnessRun `RELEASE_READY`, then test trusted ownership, latest revision, schema/version re-resolve, read-only full validation, exact tree fingerprint, required passing GLOBAL debug-session evidence, target environment, server-owned postcondition normalization, risk calculation, same-key replay and different-payload conflict. `DRAFT_READY` or active `DEBUGGING` returns a next action instead of bypassing P2. Same-key replay must first perform a cheap freshness check and cannot replay a successful Manifest after revision, binding, schema, draft-tree, validation or debug-evidence drift.

Plans with unresolved errors return a structured validation summary and no Manifest; release revalidation must not call the write-oriented `validate_workflow` path or create a new Revision/ValidationReport. Postconditions come only from a versioned server-side `ReleasePolicy`; caller-provided postconditions are outside the request schema and an unconfigured policy fails closed.

Prepare stores only canonical approval requirements for known gated actions (`publish` and `start`) in the Manifest. It must not create `ApprovalRequest` rows or placeholder action digests: publish target/version data is finalized in Task 6 and execution target/parameters are finalized in Task 7, so each task creates its own exact action-bound request. A publish approval can never authorize start; control approvals are created on demand after the exact task/node/action payload is known.

- [ ] **Step 2: Run tests to verify RED**

Run: `pytest tests/interface/harness/release/test_prepare_release.py -v --no-cov`

- [ ] **Step 3: Implement deterministic preparation**

Within a transaction, follow the fixed lock order `IdempotencyRecord -> Template -> HarnessRun -> Revision -> TemplateSnapshot -> ValidationReport/CapabilityBinding -> DebugSession/Evidence -> ReleaseManifest`, re-resolve exact bindings, perform read-only validation, compute draft/manifest hashes and persist the immutable ReleaseManifest. Canonically sort every list participating in the Manifest hash and never include newly allocated report IDs. Keep the run `RELEASE_READY` when no approval is required; transition to `APPROVAL_PENDING` only when the Manifest contains approval requirements. Do not call an external artifact writer while holding the database transaction; oversized results require a later durable outbox path or fail closed.

- [ ] **Step 4: Verify and commit**

```bash
pytest tests/interface/harness/release/test_prepare_release.py tests/interface/harness/services/test_validator.py tests/interface/harness/debug/test_get_session.py -v --no-cov
git add bkflow/harness/services/release tests/interface/harness/release/test_prepare_release.py
git commit -m "feat(harness): 生成不可变发布清单与审批请求 --story=136729554"
```

### Task 6: Extract Template Release Service and Implement publish_workflow

**Files:**

- Create: `bkflow/template/services/release.py`
- Modify: `bkflow/apigw/views/release_template.py`
- Modify: `bkflow/apigw/views/update_template.py`
- Modify: `bkflow/template/views/template.py`
- Modify: `bkflow/harness/models.py`
- Create: `bkflow/harness/services/release/publish.py`
- Create test: `tests/interface/template/services/test_release.py`
- Create test: `tests/interface/apigw/test_release_template.py`
- Modify test: `tests/interface/apigw/test_update_template.py`
- Modify test: `tests/interface/template/test_template_views.py`
- Create test: `tests/interface/harness/release/test_publish_workflow.py`

**Interfaces:**

- Consumes: ReleaseManifest, action policy, verified approval decision when required, managed Template and template release domain behavior.
- Produces: `TemplateReleaseService.release(template, release_data, operator, source) -> TemplateSnapshot`, exact append-only ReleasePublication and `publish_workflow_with_context`.

- [ ] **Step 1: Freeze existing release behavior**

Characterization tests cover FlowVersioning, version validation/collision, TemplateSnapshot, snapshot_id update, TemplateOperationRecord, Webhook event and both existing APIGW/UI response contracts. Include the existing `update_template(auto_release=True)` path: it records API source and currently does not emit a release webhook. Extracting the service must not leave this third caller as a direct-model bypass or alter any entry-point permission/response contract.

- [ ] **Step 2: Write failing Harness publish tests**

Test flag and trusted identity, Manifest ownership/hash, latest plan/draft, binding re-resolve, approval-required and no-approval paths, version collision, same-key replay, crash after snapshot creation and response-loss retry. Harness forbids `force=True`. Stale plan or draft invalidates approval and returns the run to `DRAFT_READY`.

For gated publish, use an explicit two-call contract. The first call, without receipt fields, computes the exact action digest and creates/reuses one PENDING `ApprovalRequest`, returning its opaque ID with `APPROVAL_REQUIRED` and zero release side effects. A later call supplies the same action inputs plus `approval_request_id` and `approval_receipt_ref`; the verifier runs outside database locks, after which all release facts are locked and revalidated before the request can transition to VERIFIED. A publish approval cannot authorize start. `ApprovalRequest.expires_at` and `verifier_version` are set-once fields during PENDING-to-VERIFIED rather than immutable-at-creation fields. Missing verifier backend or durable replay guard remains fail-closed and cannot claim publish readiness.

- [ ] **Step 3: Run tests to verify RED**

Run: `pytest tests/interface/template/services/test_release.py tests/interface/apigw/test_release_template.py tests/interface/template/test_template_views.py tests/interface/harness/release/test_publish_workflow.py -v --no-cov`

- [ ] **Step 4: Extract and implement atomically**

Move release domain work out of all three callers while preserving decorators/serialization. The service locks Template, performs the version/collision check under that lock, publishes the exact draft, updates `snapshot_id`, and writes `TemplateOperationRecord` in one transaction. It maps UI/APIGW explicit release to the historical app operation source plus post-commit webhook, maps APIGW auto-release to API source without a release webhook, and maps Harness to API source plus post-commit webhook. Webhook dispatch must not happen inside the database transaction and post-commit broker failure must not turn a committed release into a false failure response.

Harness follows the shared lock order `IdempotencyRecord -> Template -> HarnessRun -> WorkflowPlanRevision -> TemplateSnapshot -> ValidationReport/CapabilityBinding -> ReleaseManifest -> ApprovalRequest -> ReleasePublication`, reevaluates policy and approval, then transitions `RELEASE_READY/APPROVAL_PENDING -> PUBLISHING`, invokes the domain service inside the same outer database transaction, persists the exact `ReleasePublication`, emits Evidence and transitions to `PUBLISHED`. Never infer success only from version text; response-loss recovery must read back and exactly match the Publication plus published snapshot. If the process lost the service response after the former draft snapshot became a matching published snapshot but before a Publication exists, reconcile only the exact Manifest-bound snapshot/version/tree/operator facts; otherwise fail closed.

- [ ] **Step 5: Verify and commit**

```bash
pytest tests/interface/template/services/test_release.py tests/interface/apigw/test_release_template.py tests/interface/apigw/test_update_template.py tests/interface/template/test_template_views.py tests/interface/harness/release/test_publish_workflow.py -v --no-cov
git add bkflow/template/services/release.py bkflow/apigw/views/release_template.py bkflow/apigw/views/update_template.py bkflow/template/views/template.py bkflow/harness/models.py bkflow/harness/services/release/publish.py tests/interface
git commit -m "feat(harness): 幂等发布 Revision 绑定的模板版本 --story=136729554"
```

### Task 7: Extract Task Creation Service and Implement the Create/Start Saga

**Files:**

- Create: `bkflow/task/services/__init__.py`
- Create: `bkflow/task/services/task_creator.py`
- Modify: `bkflow/apigw/views/create_task.py`
- Create: `bkflow/harness/services/execution/contracts.py`
- Create: `bkflow/harness/services/execution/adapter.py`
- Create: `bkflow/harness/services/execution/saga.py`
- Create test: `tests/interface/task/services/test_task_creator.py`
- Modify test: `tests/interface/apigw/test_create_task.py`
- Create test: `tests/interface/harness/execution/test_start_execution.py`

**Interfaces:**

- Consumes: published ReleaseManifest, trusted application/user identity, selected runtime authorization mode, TokenBroker for any SDK path, TaskComponentClient and idempotency.
- Produces: compatibility-preserving `TaskCreator.create_from_current_template`, publication-bound `TaskCreator.create_from_publication`, `ApplicationTaskAdapter`, `ExecutionSaga.start` and `start_workflow_execution_with_context`.

- [ ] **Step 1: Freeze current create-task behavior**

Characterize template lookup, scope propagation, OpenPluginSnapshot preparation, credentials/custom context handling, notification defaults, labels and TASK_CREATE Webhook. Preserve the existing APIGW contract when extracting `TaskCreator`, including its historical creator field and response envelope. The legacy entry point may read the Template's current snapshot; the Harness entry point must require `ReleasePublication.published_snapshot_id` and must never fall back to a later Template current snapshot. Both entry points defensively copy the pipeline tree before Engine preparation mutates it.

- [ ] **Step 2: Write failing Saga tests**

Test the two-call, start-specific approval contract and flags, published snapshot/plan binding, pre-execution re-resolve, platform app plus actor, server-side credential-ref resolution, rejection of credential plaintext in Tool input, action-specific domain-service/SDK authorization mode, mandatory brokered lease on an SDK path, create failure, create success then response loss, persisted task_ref then crash, start success then response loss, Engine rejection, same-key replay and concurrent start calls. A publish approval must not authorize start. The first call creates/reuses only a start-bound PENDING ApprovalRequest and performs no secret resolution, ExecutionRun creation or Engine call; the later approved call verifies outside locks, then re-locks and revalidates all facts before dispatch. `CreateDispatchRejected` and `StartDispatchRejected` are reserved for a future typed adapter contract, and are exercised locally only through explicit test doubles. The current production `TaskComponentClient` folds Engine/HTTP failures into an untyped `result: false` or exception, so those outcomes must always be treated as uncertain rather than as a proven business rejection.

Assert the exact durable sequence:

```text
lock IdempotencyRecord -> Template -> HarnessRun -> Revision -> published Snapshot
  -> ValidationReport/CapabilityBinding -> Manifest -> Approval -> Publication -> ExecutionRun
validate -> CREATE_DISPATCHING -> create once
persist exact task_ref -> CREATED -> START_DISPATCHING -> start once
read back task state -> EXECUTING or terminal -> return
```

The current Engine create API has neither a client request ID/idempotency key nor an exact lookup by Harness execution ID. Therefore, if create may have succeeded but no `task_ref` was received or durably persisted, the only safe result is `CREATE_UNCERTAIN` plus manual-reconciliation Evidence. Do not dispatch create again. Automatic recovery of this window is an external dependency on a future Engine correlation contract, not a local P3 claim.

- [ ] **Step 3: Run tests to verify RED**

Run: `pytest tests/interface/task/services/test_task_creator.py tests/interface/apigw/test_create_task.py tests/interface/harness/execution/test_start_execution.py -v --no-cov`

- [ ] **Step 4: Extract task creation and implement recovery**

The extracted service preserves the existing APIGW credentials/custom-context contract, but the Harness adapter accepts only credential refs from the bound Revision and resolves them server-side for the call. Re-resolve current capability schemas and Credential space/scope grants before dispatch; reject conflicting bindings for one credential key and reject any Tool input containing credential/custom-context/token/secret plaintext. OpenPlugin schema/snapshot preparation and all provider calls happen outside database lock transactions.

The P3 default is the extracted server-side domain-service path under HarnessPermission. The existing TokenBroker has no production execution lease backend or task SDK adapter, so every token-protected SDK mode remains fail-closed until that external evidence exists; a DebugSession token must never be reused as an execution token. The adapter calls `TaskComponentClient.create_task` and `operate_task(task_id, "start")` as separate steps. Persist `task_ref` before dispatching start. A retry with an exact durable `task_ref` first reads the Saga and Engine task state and never creates a second task. A retry without a `task_ref` after a create dispatch cannot prove safety and stays `CREATE_UNCERTAIN`; however, the unique original dispatch may still atomically persist its own late successful receipt when a concurrent retry has only aged that same barrier to `CREATE_UNCERTAIN`, which is recovery of one dispatch rather than a second create. If start-result ambiguity cannot be resolved from readback, return `RETRYABLE_INFRA` with manual-reconciliation evidence instead of re-dispatching blindly. Until the transport exposes a verifiable typed business rejection, production `result: false`, exception and malformed responses remain fail-safe uncertain; typed rejection is an external transport-contract gate, not a local P3 claim.

- [ ] **Step 5: Verify and commit**

```bash
pytest tests/interface/task/services/test_task_creator.py tests/interface/apigw/test_create_task.py tests/interface/harness/execution/test_start_execution.py -v --no-cov
git add bkflow/task/services bkflow/apigw/views/create_task.py bkflow/harness/services/execution tests/interface
git commit -m "feat(harness): 实现应用态任务创建启动 Saga --story=136729554"
```

### Task 8: Implement Execution Readback and Fixed Postconditions

**Files:**

- Create: `bkflow/harness/services/execution/postconditions.py`
- Create: `bkflow/harness/services/execution/read.py`
- Create: `bkflow/harness/services/execution/facade.py`
- Create test: `tests/interface/harness/execution/test_postconditions.py`
- Create test: `tests/interface/harness/execution/test_get_execution.py`

**Interfaces:**

- Consumes: ExecutionRun, `TaskComponentClient.get_task_detail/get_task_states/get_node_id_map/get_task_node_detail(include_data=True)`, bounded webhook history when correlation is available, and correlated Evidence. The current client has no `get_node_outputs`; `render_context_with_node_outputs` performs template evaluation and is forbidden as an equality-evidence source.
- Produces: `PostconditionEvaluator`, `get_workflow_execution_with_context(context, payload) -> Envelope` and finalized EvidenceBundle.

- [ ] **Step 1: Write failing Postcondition DSL tests**

Support exactly these versioned predicates in P3:

```text
TASK_STATE_IN(allowed_states)
OUTPUT_EXISTS(node_id, output_key)
OUTPUT_EQUALS(node_id, output_key, expected_json)
WEBHOOK_DELIVERED(event_type, correlation_id)
```

Reject unknown predicates, unbounded expressions, scripts and template evaluation. Test pending, passed, failed and unavailable-evidence results; compare JSON after canonical normalization so JSON booleans are not equal to integers. The top level and every predicate are closed schemas with bounded counts, depth, strings and total bytes. `WEBHOOK_DELIVERED` is a recognized fail-closed predicate, but the current Webhook History lacks Harness correlation and bounded lookup; it must evaluate `UNAVAILABLE` until execution correlation is propagated end to end. Do not infer delivery from task ID alone or claim all four predicates operational before that external contract exists.

- [ ] **Step 2: Write failing execution read tests**

Test running, paused, succeeded, failed, cancelled, task-not-found, transient read failure, Harness Evidence pagination, bounded handling of non-paginated Engine responses, output redaction and old execution reads with flags disabled. Engine success plus failed Postcondition must produce Harness `FAILED`, error category `POSTCONDITION`, and a finalized failure EvidenceBundle. An Engine `FAILED` projection is recoverable while node retry/skip is still possible and must not be treated as an irreversible Harness terminal state.

When execution is disabled, reads of existing executions remain available but are strictly persistence-only: no Engine/Webhook/provider call, state/deadline mutation, Evidence append, lease revoke or bundle finalization. Return an explicit unavailable refresh reason. Raw detail, state trees, node histories, outputs, `ex_data`, webhook responses and downstream error text must never enter an Envelope, ExecutionRun report, Evidence, idempotency snapshot or Harness log.

- [ ] **Step 3: Run tests to verify RED**

Run: `pytest tests/interface/harness/execution/test_postconditions.py tests/interface/harness/execution/test_get_execution.py -v --no-cov`

- [ ] **Step 4: Implement readback and convergence**

Normalize Engine states without rewriting engine records. Resolve a Manifest-bound template node through `get_node_id_map`, then read only the required output keys from node detail; never expose full histories or use rendered context as source truth. Since Engine read APIs have no pagination, enforce response and collection bounds and fail closed on overflow.

Evaluate postconditions only when their evidence is available. The first observation of Engine `FINISHED` with pending evidence persists immutable `terminal_observed_at` and server-derived absolute `deadline_at` in the bounded postcondition report; later polls cannot extend it. Before the deadline the Harness remains `EXECUTING`; at expiry it fails with evidence-unavailable detail. Finalization is idempotent, occurs only after execution-owned leases are revoked, emits one bounded terminal Evidence event and returns summary plus artifact refs.

One Manifest may have multiple logical executions only through different server-validated `start_idempotency_key` values; the existing `(manifest, start_idempotency_key)` uniqueness remains the exact replay boundary. Readback therefore terminalizes each `ExecutionRun` independently and aggregates `HarnessRun` only after every sibling execution is terminal: any failure wins, otherwise any success wins, otherwise the aggregate is cancelled. While a sibling remains active, the HarnessRun stays `EXECUTING`. A `READY` read from `CREATED`, `START_DISPATCHING` or `START_UNCERTAIN` is projection-only and must not cross the start Saga barrier; `RUNNING` or another conclusive post-start state may recover the persisted start transition.

- [ ] **Step 5: Verify and commit**

```bash
pytest tests/interface/harness/execution/test_postconditions.py tests/interface/harness/execution/test_get_execution.py tests/interface/apigw/test_get_task_detail.py -v --no-cov
git add bkflow/harness/services/execution tests/interface/harness/execution
git commit -m "feat(harness): 增加运行态查询与业务后置条件 --story=136729554"
```

### Task 9: Implement Controlled Task and Node Operations

**Files:**

- Create: `bkflow/harness/services/execution/control.py`
- Modify: `bkflow/harness/services/execution/contracts.py`
- Modify: `bkflow/harness/services/execution/adapter.py`
- Modify: `bkflow/harness/services/execution/facade.py`
- Modify: `bkflow/harness/services/execution/read.py`
- Modify: `bkflow/harness/services/idempotency.py`
- Create test: `tests/interface/harness/execution/test_control_execution.py`

**Interfaces:**

- Consumes: active ExecutionRun, ActionPolicy, ApprovalVerifier, the server-side domain-service runtime mode, TaskComponentClient, append-only control-attempt Evidence and idempotency. Brokered SDK/token execution remains denied in P3 because no production execution TokenBroker or consuming adapter exists.
- Produces: `control_workflow_execution_with_context(context, payload) -> Envelope`.

- [x] **Step 1: Write failing tagged-action tests**

Support task actions `pause`, `resume`, `revoke` and node actions `retry`, `skip`, `callback`, `forced_fail`, `skip_exg`, `skip_cpg` as a closed tagged union. Test exact per-action wire schemas, conservative legal source states, exact task/node ownership, policy/approval claims, same-key replay, concurrent controls, ambiguous Engine results and post-action readback. Caller input cannot contain task refs, runtime IDs, identity, operator, token/credential fields or low-level engine flags. Include the idempotency key as the exact control intent in the approval digest so one approval cannot authorize a second mutation under a new key.

Retry inputs and callback data must be bounded, non-secret and schema-validated; node outputs are readback facts, not control input. P3 has no immutable Manifest-bound retry-input or callback schema, so any retry carrying `inputs` and every generic callback remain fail-closed until that schema exists. Node IDs must exist in the manifest-bound published snapshot and resolve through the server-owned template-node map; arbitrary Engine task/node references are rejected. Gateway skip remains fail-closed until BKFlow preserves an exact template-flow to runtime-flow provenance map; never accept Agent-supplied runtime flow IDs as a substitute.

- [x] **Step 2: Run tests to verify RED**

Run: `pytest tests/interface/harness/execution/test_control_execution.py -v --no-cov`

- [x] **Step 3: Implement action dispatch**

Use `operate_task` only for task actions and `node_operate` only for node actions; always pass the trusted actor as operator. Build approval digest from the normalized action payload. The only enabled P3 adapter is the server-side `TaskComponentClient` domain-service path; SDK/token modes are `deny_action` until an execution-aware broker, issuer, consumer and revocation proof exist.

Before one dispatch, atomically acquire the exact idempotency barrier, block other in-flight controls for the execution, append a bounded `CONTROL_DISPATCHING` Evidence journal entry and move the ExecutionRun to `CONTROL_DISPATCHING`. The event binds idempotency ref, action digest, pre-state, safe template targets and expected readback; cap attempts so the final EvidenceBundle cannot exceed its 100-event limit. Current Client transport collapses network errors, HTTP errors and Engine rejections into the same false result, so `result=False` or exception is always `CONTROL_UNCERTAIN`, never a deterministic rejection. Same or new keys must not blindly redispatch. Task 8 readback reconciles the exact expected state or returns manual reconciliation. Do not treat projected `FAILED`/`NODE_SUSPENDED` as proof of a root task transition.

- [x] **Step 4: Verify and commit**

```bash
pytest tests/interface/harness/execution/test_control_execution.py tests/interface/apigw/test_operate_task.py tests/interface/apigw/test_operate_task_node.py -v --no-cov
git add bkflow/harness/services/execution/control.py bkflow/harness/services/execution/facade.py tests/interface/harness/execution/test_control_execution.py
git commit -m "feat(harness): 增加受控任务与节点操作 --story=136729554"
```

### Task 10: Expose the Five P3 Harness Tools

**Files:**

- Create: `bkflow/apigw/serializers/harness/release_execution.py`
- Create: `bkflow/apigw/views/harness/release_execution.py`
- Modify: `bkflow/apigw/views/harness/common.py`
- Modify: `bkflow/apigw/urls.py`
- Modify: `bkflow/harness/services/facade.py`
- Modify: `bkflow/apigw/management/commands/data/api-resources.yml`
- Create: `bkflow/apigw/docs/zh/harness_prepare_release.md`
- Create: `bkflow/apigw/docs/zh/harness_publish_workflow.md`
- Create: `bkflow/apigw/docs/zh/harness_start_workflow_execution.md`
- Create: `bkflow/apigw/docs/zh/harness_get_workflow_execution.md`
- Create: `bkflow/apigw/docs/zh/harness_control_workflow_execution.md`
- Generated: `bkflow/apigw/docs/apigw-docs.zip`
- Modify: `docs/specs/2026-09-01-bkaidev-a2flow-harness-design.md`
- Modify: `docs/reviews/2026-09-02-bkaidev-harness-p3-runtime-spike.md`
- Create test: `tests/interface/apigw/test_harness_p3.py`
- Modify test: `tests/interface/apigw/test_harness_resource_contract.py`

**Interfaces:**

- Consumes: five P3 facade operations, HarnessPermission, APIGW trusted context and contract gate.
- Produces: five APIGW operations consumed by the existing single Harness MCP Server.

- [x] **Step 1: Write failing API contract tests**

Cover request tags, Envelope, trusted identity, operation-specific approval refs, idempotency, feature flags, error categories and response-size bounds. Assert no raw template/task SDK endpoint, credential or approval plaintext becomes an MCP Tool contract.

- [x] **Step 2: Run tests to verify RED**

Run: `pytest tests/interface/apigw/test_harness_p3.py tests/interface/apigw/test_harness_resource_contract.py tests/interface/harness/test_contract_versions.py -v --no-cov`

- [x] **Step 3: Implement API surface**

Add POST routes `/space/{space_id}/harness/prepare_release/`, `/space/{space_id}/harness/publish_workflow/`, `/space/{space_id}/harness/start_workflow_execution/`, `/space/{space_id}/harness/get_workflow_execution/` and `/space/{space_id}/harness/control_workflow_execution/` with operation IDs `harness_prepare_release`, `harness_publish_workflow`, `harness_start_workflow_execution`, `harness_get_workflow_execution` and `harness_control_workflow_execution`. Views call only Harness facades and use existing APIGW authentication plus HarnessPermission.

- [x] **Step 4: Synchronize APIGW and BKAIDev docs**

Update `api-resources.yml`, add five Chinese operation documents, regenerate `apigw-docs.zip`, and record in the P3 spike that the BKAIDev Agent Release uses contract `1.3.0` with 14 cumulative Tools. Document the prepare/approve/publish/start/poll sequence plus refresh recovery.

- [x] **Step 5: Verify and commit**

```bash
pytest tests/interface/apigw/test_harness_p3.py tests/interface/apigw/test_harness_resource_contract.py tests/interface/harness/test_contract_versions.py -v --no-cov
bash scripts/apigw_docs.sh
unzip -l bkflow/apigw/docs/apigw-docs.zip | rg 'harness_(prepare|publish|start|get|control)'
git diff --check
git add bkflow/apigw bkflow/harness/services/facade.py docs/specs/2026-09-01-bkaidev-a2flow-harness-design.md docs/reviews/2026-09-02-bkaidev-harness-p3-runtime-spike.md tests/interface/apigw/test_harness_p3.py tests/interface/apigw/test_harness_resource_contract.py
git commit -m "feat(harness): 暴露 P3 发布执行 Tool 契约 --story=136729554"
```

### Task 11: Add Release/Execution Golden Cases and the P3 Gate

**Files:**

- Create: `tests/fixtures/harness/release_execution_cases.yaml`
- Create: `tests/interface/harness/release/test_golden_cases.py`
- Create: `tests/interface/harness/execution/test_golden_cases.py`
- Create: `tests/interface/harness/execution/test_secret_non_disclosure.py`
- Create: `docs/reviews/2026-09-02-bkaidev-harness-p3-verification.md`
- Modify: `Makefile`

**Interfaces:**

- Consumes: 14-Tool contract, release/runtime services, approval policy and Evidence.
- Produces: deterministic 48-case regression set, `make harness-p3-gate`, and separate local/external verdicts.

- [x] **Step 1: Define exactly 48 Golden Cases**

```text
prepare_and_manifest             8
approval_binding_and_expiry      6
publish_idempotency_and_drift    6
create_start_recovery            8
execution_readback               5
postcondition_false_success      5
task_controls                    4
node_controls                    4
secret_and_cross_space_denial    2
total                           48
```

- [x] **Step 2: Implement table-driven tests and crash boundaries**

Every case specifies predecessor Revision, trusted context, policy, approval metadata, Engine stub sequence, expected durable state, Evidence and forbidden markers. Inject crashes before/after publish, create, task_ref persistence, start and control; retries must converge without duplicate side effects.

- [x] **Step 3: Add the P3 gate target**

`make harness-p3-gate` runs migration checks, P0–P3 Harness suites, template release/task service characterizations, APIGW consistency, exactly 48 cases, contract count 14, secret scans and `git diff --check`.

- [x] **Step 4: Run local gate and record evidence**

```bash
make harness-p3-gate
python manage.py makemigrations harness --check
git diff --check
```

Record predecessor/current SHA, exact test counts, flags, approval verifier mode, supported Postcondition predicates, external provider/environment coverage and all blocked claims.

- [x] **Step 5: Apply rollout verdict and commit**

`P3_LOCAL_GATE_PASSED` requires all local suites. `P3_EXTERNAL_GATE_PASSED` additionally requires a live BKAIDev receipt, trusted platform/user identity, non-production publish, create/start/readback, one false-success Postcondition, one approved control, refresh recovery and Evidence readback. Otherwise record `P3_RELEASE_EXECUTION_GATE_BLOCKED_BY_EXTERNAL_EVIDENCE` and keep mutation flags disabled.

```bash
git add tests/fixtures/harness/release_execution_cases.yaml tests/interface/harness/release/test_golden_cases.py tests/interface/harness/execution/test_golden_cases.py tests/interface/harness/execution/test_secret_non_disclosure.py docs/reviews/2026-09-02-bkaidev-harness-p3-verification.md Makefile
git commit -m "test(harness): 建立 P3 发布执行验收门禁 --story=136729554"
```

## P3 Completion Evidence

- Contract `1.3.0` exposes exactly 14 cumulative Tools and all earlier contracts remain compatible.
- ReleaseManifest and approval bind the exact immutable plan, draft fingerprint, policy, action and target environment.
- Publish, create, start and control have durable idempotency/recovery boundaries; task creation and start are distinct.
- Platform application plus real-user identity is used without exposing any credential to the Agent.
- Fixed Postconditions can classify Engine success plus business failure as Harness failure.
- Forty-eight Golden Cases pass locally; live approval/runtime evidence is reported as a separate external gate.

## Execution Handoff

After this plan is approved, implement it with one of the following:

1. **Subagent-Driven Development (recommended):** execute tasks in order, use fresh reviewers at service extraction and Saga boundaries, and stop on every Decision Gate failure.
2. **Inline Execution:** use `superpowers:executing-plans` in a separate implementation session, preserving the task commits and running the stated verification after every task.

Do not enable publish/execution flags or begin P4 promotion work until the P3 local gate passes. Do not claim application-state execution readiness until the external gate also passes.
