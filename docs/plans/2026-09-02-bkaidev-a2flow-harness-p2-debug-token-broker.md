# BKAIDev a2flow Harness P2 Debug and Token Broker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 BKFlow 已有单步与全局调试底座封装为 4 个可恢复、可审计的 Harness Tool，并通过服务端 Token Broker 为真实调试提供最小权限、短时授权且不向 Agent 暴露 Token。

**Architecture:** `DebugSession` 绑定不可变 Revision、`plan_hash`、模板草稿和树指纹；Harness Debug Adapter 复用 `DebugService`，不把 `sdk_debug_*` 直接暴露给 Agent。Token Broker 在可信平台应用和用户授权成立后签发/复用短时 MOCK Token，明文只在服务端调用栈内存在，Agent 仅得到 `TokenLease` 引用和脱敏 Evidence。

**Tech Stack:** Python 3.9.12、Django 3.2.25、Django REST Framework 3.12.4、pytest、BKFlow DebugService、TaskComponentClient、BKFlow Token。

**Spec:** `docs/specs/2026-09-01-bkaidev-a2flow-harness-design.md`

## Global Constraints

- P2 新增 `start_debug_session`、`run_debug`、`get_debug_session`、`control_debug_session`，累计 9 Tool。
- BKAIDev Agent 是唯一 LLM 调用方；调试 Tool 被动响应，不实现 Agent Runtime。
- `sdk_debug_*` 是画布 SDK 接口，不直接进入 MCP allowlist；Harness 通过 service/adapter 复用其底层行为。
- DebugSession 必须绑定 revision、plan_hash、template、tree_fingerprint 和 trusted context；草稿变化后旧 Session 失效。
- 开始 Session 和每次 run 前重新 Resolve 所有 CapabilityBinding 并校验精确版本和 schema_hash。
- 默认 `mock`；真实单步要求 `harness_real_step_enabled=true`、有效审批证明和 Token Broker；全局真实调试在 P2 默认禁止。
- Token 明文不得进入数据库可读字段、Prompt、Tool 输入输出、Evidence、普通日志、异常或测试 Fixture。
- 同一模板最多一个 active Harness DebugSession；必须复用 DebugContext 的共享锁并支持陈旧锁回收。
- P2 contract 为 `1.2.0`；`1.0.0` 和 `1.1.0` Tool 集合保持兼容。
- P2 开关关闭不能影响 P0/P1 读、校验和草稿；只读 `get_debug_session` 在总开关关闭后仍可读取既有 Evidence。
- migration 使用 `python manage.py makemigrations harness --name p2_debug_token_broker` 生成。
- APIGW 三件套同步；提交统一使用 `--story=136729554`。

---

## Inherited Contracts

- P0 trusted context、HarnessPermission、Envelope、幂等、不可变 Revision、CapabilityBinding、ValidationReport 和草稿所有权。
- P1 `CONTRACT_TOOLSETS` 和 `require_tool_enabled`；P2 只追加 4 个 Tool。
- P1 KnowledgeHit 只作为解释上下文，不作为调试权限、输入真值或执行批准。
- 已有 `DebugService` 的 context/input_schema/history/global_run/reset/terminate/reset_impact/step_run/node_mock/context_var 行为。
- 已有 `Token`、`PermissionType.MOCK`、`apply_token`、`revoke_token` 和 `BaseMockTokenPermission` 语义。

## Decision Gates

- **DG-P2-01 Approval receipt:** 验证 BKAIDev Tool 审批能否产生服务端可验证、绑定 actor/app/space/plan_hash/action/expiry 的 receipt。不能验证时 `real` 永久 fail-closed。
- **DG-P2-02 Token issuer:** 确认平台应用经 APIGW 身份链为当前用户和模板/Scope 颁发 MOCK Token；不得使用开发者个人 Token。
- **DG-P2-03 Async recovery:** 验证 BKAIDev 对 running Tool 的刷新、断线和轮询恢复；不能保持长调用时，`run_debug` 必须快速返回并由 `get_debug_session` 轮询。
- **DG-P2-04 Global policy:** P2 只开放全局 Mock。任何全局 Real 白名单必须等 P3 Policy/Approval 完成。

## Reconciliation Check

只有 P1 本地 gate 通过且 contract `1.1.0` 已稳定后才执行 P2。开始前记录 P1 predecessor SHA，确认 Harness 最新 migration 为 `0004_p1_knowledge_router`、P1 Tool 总数为 5，并重新运行 P0/P1 全量聚焦测试。

同时核对 `DebugService.step_run(node_id, operator, mode, input_overrides, mock_result, mock_outputs, mock_error)`、`global_run(inputs, operator)`、`build_context_view()`、`history()`、`reset()`、`terminate()`、`reset_impact()`、`node_mock()`、`set_context_var()` 的当前签名。签名变化必须先更新 Adapter 契约测试。

## File Responsibility Map

```text
bkflow/harness/
├── constants.py
├── contracts.py
├── models.py
└── services/
    ├── token_broker.py
    ├── evidence.py
    └── debug/
        ├── contracts.py
        ├── adapter.py
        ├── approval.py
        ├── policy.py
        ├── session.py
        └── facade.py

bkflow/permission/services/token_issuer.py
bkflow/apigw/serializers/harness/debug.py
bkflow/apigw/views/harness/debug.py
tests/interface/harness/debug/
tests/fixtures/harness/debug_cases.yaml
```

### Task 1: Reconcile P1 and Freeze Debug, Approval, and Token Spikes

**Files:**

- Create: `docs/reviews/2026-09-02-bkaidev-harness-p2-debug-spike.md`
- Reference: `docs/reviews/2026-09-02-bkaidev-harness-p1-verification.md`
- Reference: `bkflow/template/debug/service.py`
- Reference: `bkflow/permission/models.py`

**Interfaces:**

- Consumes: P1 gate, BKAIDev approval/recovery behavior, existing DebugService and Token APIs.
- Produces: `approval_mode`, `debug_call_mode`, `token_issue_mode`, `async_mode` and predecessor SHA.

- [ ] **Step 1: Re-run predecessor suites and characterize DebugService**

Run P0/P1 Harness suites plus all `tests/interface/template/debug` tests. Record current pass counts and inspect real DebugService return shapes for step mock, step real, global, history, terminate and reset.

- [ ] **Step 2: Execute SP-P2-01 through SP-P2-07**

```text
SP-P2-01 approval receipt authenticity and binding
SP-P2-02 current-user identity through BKAIDev MCP
SP-P2-03 platform application token issuance
SP-P2-04 token expiry, renewal and revoke
SP-P2-05 running Tool refresh and polling recovery
SP-P2-06 DebugContext lock conflict and stale reclaim
SP-P2-07 maximum history/Evidence response size
```

- [ ] **Step 3: Freeze decisions**

```text
approval_mode = verifiable_receipt | deny_real
debug_call_mode = in_process_debug_service
token_issue_mode = trusted_apply_token_service | deny_real
async_mode = fast_ack_and_poll | bounded_sync_then_poll
```

Any `deny_real` value still permits Mock P2 implementation but blocks real-step rollout.

- [ ] **Step 4: Verify and commit**

Run: `rg -n 'SP-P2-0[1-7]|approval_mode =|debug_call_mode =|token_issue_mode =|async_mode =|predecessor_sha' docs/reviews/2026-09-02-bkaidev-harness-p2-debug-spike.md`

```bash
git add docs/reviews/2026-09-02-bkaidev-harness-p2-debug-spike.md
git commit -m "docs(harness): 固化 P2 调试与 Token 门禁 --story=136729554"
```

### Task 2: Add P2 Contract, Flags, States, and Checkpoints

**Files:**

- Modify: `bkflow/harness/services/contract_versions.py`
- Modify: `bkflow/harness/constants.py`
- Modify: `bkflow/space/configs.py`
- Modify test: `tests/interface/harness/test_contract_versions.py`
- Modify test: `tests/interface/space/test_space_config.py`
- Create test: `tests/interface/harness/debug/test_feature_gate.py`

**Interfaces:**

- Consumes: contract `1.1.0`, current HarnessRun state machine.
- Produces: contract `1.2.0`, `HarnessDebugEnabledConfig`, `HarnessRealStepEnabledConfig`, Debug enums and validation checkpoints.

- [ ] **Step 1: Write failing compatibility tests**

Assert contract `1.2.0` contains the first 5 Tools in their existing order plus exactly four debug Tools. Versions `1.0.0` and `1.1.0` remain byte-equivalent.

Assert `harness_debug_enabled` and `harness_real_step_enabled` default false; real-step cannot be true effectively when debug is false.

- [ ] **Step 2: Run tests to verify RED**

Run: `pytest tests/interface/harness/test_contract_versions.py tests/interface/harness/debug/test_feature_gate.py tests/interface/space/test_space_config.py -v --no-cov`

- [ ] **Step 3: Implement contract and phase controls**

Add Tool mapping in this order: start, run, get, control. Extend ValidationCheckpoint with `START_DEBUG_SESSION` and `RUN_DEBUG`. Add Debug mode/status/control enums without changing existing HarnessRunStatus values.

- [ ] **Step 4: Verify and commit**

```bash
pytest tests/interface/harness/test_contract_versions.py tests/interface/harness/debug/test_feature_gate.py tests/interface/space/test_space_config.py tests/interface/harness/services/test_state.py -v --no-cov
git add bkflow/harness/services/contract_versions.py bkflow/harness/constants.py bkflow/space/configs.py tests/interface
git commit -m "feat(harness): 增加 P2 Tool 状态与功能开关 --story=136729554"
```

### Task 3: Add DebugSession, TokenLease, and EvidenceEvent Models

**Files:**

- Modify: `bkflow/harness/models.py`
- Create: `bkflow/harness/services/evidence.py`
- Generated: `bkflow/harness/migrations/0005_p2_debug_token_broker.py`
- Create test: `tests/interface/harness/debug/test_models.py`
- Create test: `tests/interface/harness/debug/test_evidence.py`

**Interfaces:**

- Consumes: HarnessRun, WorkflowPlanRevision and managed draft reference.
- Produces: `DebugSession`, `TokenLease`, `EvidenceEvent`, terminal/active status helpers, `record_evidence` and `redact_evidence_payload`.

- [ ] **Step 1: Write failing model tests**

`DebugSession` fields: UUID, run, revision, template_id, debug_context_id, mode, status, plan_hash, tree_fingerprint, active_template_key, current_task_id, actor, policy version, expiry, last heartbeat and terminal reason.

`active_template_key` is `template:<id>` while active and unique; terminal sessions clear it. This provides a MySQL-compatible single-active-session constraint without conditional indexes.

`TokenLease` fields: UUID, session, platform app, actor, space, resource type/id, permission, issuer ref, token fingerprint, issued/expiry/revoked timestamps and status. No plaintext token field exists.

`EvidenceEvent` fields: UUID, run, revision, optional debug session, event type, action, redacted payload, artifact refs, actor, correlation ID, redaction version and occurred_at. Update/delete are rejected.

Service tests prove redaction happens before model construction, ordering is stable, inline payload size is bounded, large values become Artifact refs, and append-only enforcement is not bypassed by bulk update/delete.

- [ ] **Step 2: Run tests to verify RED**

Run: `pytest tests/interface/harness/debug/test_models.py tests/interface/harness/debug/test_evidence.py -v --no-cov`

- [ ] **Step 3: Implement and generate migration**

```bash
python manage.py makemigrations harness --name p2_debug_token_broker
python manage.py sqlmigrate harness 0005
python manage.py makemigrations harness --check
```

- [ ] **Step 4: Verify and commit**

```bash
pytest tests/interface/harness/debug/test_models.py tests/interface/harness/debug/test_evidence.py tests/interface/harness/test_models.py -v --no-cov
git add bkflow/harness/models.py bkflow/harness/services/evidence.py bkflow/harness/migrations tests/interface/harness/debug/test_models.py tests/interface/harness/debug/test_evidence.py
git commit -m "feat(harness): 新增调试会话 Token 租约与证据事件 --story=136729554"
```

### Task 4: Extract Token Issuance and Implement the Token Broker

**Files:**

- Create: `bkflow/permission/services/__init__.py`
- Create: `bkflow/permission/services/token_issuer.py`
- Modify: `bkflow/apigw/views/apply_token.py`
- Modify: `bkflow/apigw/views/revoke_token.py`
- Create: `bkflow/harness/services/token_broker.py`
- Create test: `tests/interface/permission/test_token_issuer.py`
- Create test: `tests/interface/harness/debug/test_token_broker.py`
- Modify test: `tests/interface/apigw/test_apply_token.py`

**Interfaces:**

- Consumes: trusted app/user/space, Template or Scope resource, `PermissionType.MOCK`, token expiry settings.
- Produces: `issue_resource_token(context, resource, permission) -> IssuedResourceToken`, `revoke_resource_token(token)`, and `TokenBroker.acquire_debug_lease(context, session) -> ActiveTokenHandle`.

- [ ] **Step 1: Characterize current token API behavior**

Add tests freezing existing apply/reuse/renew/revoke behavior, current-user binding, resource existence and space validation before extraction.

- [ ] **Step 2: Write Broker security tests**

Assert app/user/space/template mismatch fails, permission is exactly MOCK, TTL is capped, repeated acquisition reuses one live lease, expiry renews under policy, session termination revokes, and token plaintext appears only on `ActiveTokenHandle.secret` in memory.

Capture response, model serialization, logs, exceptions, database rows and Evidence payloads; the raw token must occur zero times.

- [ ] **Step 3: Run tests to verify RED**

Run: `pytest tests/interface/permission/test_token_issuer.py tests/interface/harness/debug/test_token_broker.py tests/interface/apigw/test_apply_token.py -v --no-cov`

- [ ] **Step 4: Extract service and implement Broker**

`ActiveTokenHandle` is not serializable and exposes no `to_dict`. Store only SHA-256 token fingerprint and issuer reference in TokenLease. On real debug, call `Token.verify` with the in-memory secret immediately before `DebugService`; never return the handle to facade/view code.

- [ ] **Step 5: Verify compatibility and commit**

```bash
pytest tests/interface/permission/test_token_issuer.py tests/interface/harness/debug/test_token_broker.py tests/interface/apigw/test_apply_token.py tests/interface/apigw/test_token_resource_validator.py -v --no-cov
git add bkflow/permission/services bkflow/apigw/views/apply_token.py bkflow/apigw/views/revoke_token.py bkflow/harness/services/token_broker.py tests/interface
git commit -m "feat(harness): 增加服务端调试 Token Broker --story=136729554"
```

### Task 5: Start Revision-Bound Debug Sessions

**Files:**

- Create: `bkflow/harness/services/debug/__init__.py`
- Create: `bkflow/harness/services/debug/contracts.py`
- Create: `bkflow/harness/services/debug/adapter.py`
- Create: `bkflow/harness/services/debug/policy.py`
- Create: `bkflow/harness/services/debug/session.py`
- Create: `bkflow/harness/services/debug/facade.py`
- Create test: `tests/interface/harness/debug/test_start_session.py`
- Create test: `tests/interface/harness/debug/test_adapter_contract.py`

**Interfaces:**

- Consumes: latest validated revision, managed template draft, Capability resolver, DebugService and state transition service.
- Produces: `start_debug_session_with_context(context, payload) -> Envelope`, `DebugAdapter`, and `DebugSessionView`.

- [ ] **Step 1: Write failing start-session tests**

Request requires run_id, revision_id, expected_plan_hash, mode (`step` or `global`) and idempotency_key. Test trusted ownership, latest revision, DRAFT_READY state, exact Schema re-resolve, draft fingerprint match, one active session, same-key replay and different-key conflict.

Start returns input schema, node readiness, session ID, plan hash, tree fingerprint and Artifact refs. It does not run a node or create an Engine task.

- [ ] **Step 2: Write adapter characterization tests**

Freeze translation from `DebugService.build_context_view()`, `input_schema()` and `compute_tree_fingerprint()` to Harness contracts. Do not change existing SDK response shapes.

- [ ] **Step 3: Run tests to verify RED**

Run: `pytest tests/interface/harness/debug/test_start_session.py tests/interface/harness/debug/test_adapter_contract.py -v --no-cov`

- [ ] **Step 4: Implement start flow**

Use a transaction and row lock on the managed Template. Revalidate capabilities and plan hash, sync DebugContext, persist DebugSession, transition HarnessRun `DRAFT_READY -> DEBUGGING`, emit `DEBUG_SESSION_STARTED`, and complete idempotency only after all records exist.

- [ ] **Step 5: Verify and commit**

```bash
pytest tests/interface/harness/debug/test_start_session.py tests/interface/harness/debug/test_adapter_contract.py tests/interface/template/debug/test_dependency.py tests/interface/template/debug/test_service_context.py -v --no-cov
git add bkflow/harness/services/debug tests/interface/harness/debug
git commit -m "feat(harness): 建立 Revision 绑定的调试会话 --story=136729554"
```

### Task 6: Implement Step and Global run_debug

**Files:**

- Create: `bkflow/harness/services/debug/run.py`
- Create: `bkflow/harness/services/debug/approval.py`
- Modify: `bkflow/harness/services/debug/policy.py`
- Modify: `bkflow/harness/services/debug/adapter.py`
- Create test: `tests/interface/harness/debug/test_run_debug.py`
- Create test: `tests/interface/harness/debug/test_real_step_policy.py`

**Interfaces:**

- Consumes: active DebugSession, TokenBroker, DebugAdapter, approval receipt reference and idempotency service.
- Produces: `DebugApprovalVerifier.verify(receipt_ref, expected_claims) -> DebugApprovalDecision` and `run_debug_with_context(context, payload) -> Envelope`.

- [ ] **Step 1: Write step-mode tests**

Test mock success/failure, dependency-missing paths, gateway behavior, input overrides, output-to-global-var propagation, same request replay, Schema drift, plan/fingerprint drift and session ownership.

Real step must require all of: debug flag, real-step flag, policy allow, `approval_receipt_ref` verified server-side against platform app/actor/space/scope/environment/plan/action/node/expiry, and a live MOCK TokenLease. A missing predicate returns `APPROVAL_REQUIRED`, `APPROVAL_INVALID` or `TOKEN_LEASE` before touching DebugService. Receipt plaintext is neither persisted nor returned; only provider/ref digest and normalized decision enter Evidence.

- [ ] **Step 2: Write global-mode tests**

P2 global run forces every executable node to mock unless a future phase explicitly enables global real. Test task acknowledgement, polling state, terminate recovery, shared lock conflict and `fast_ack_and_poll` behavior.

- [ ] **Step 3: Run tests to verify RED**

Run: `pytest tests/interface/harness/debug/test_run_debug.py tests/interface/harness/debug/test_real_step_policy.py -v --no-cov`

- [ ] **Step 4: Implement bounded dispatch**

Use tagged request fields:

```text
mode=step: node_id, execution_mode, input_overrides, mock_result, mock_outputs, mock_error
mode=global: inputs, execution_mode=mock
```

Implement the P2 debug-specific verifier behind a small interface so P3 can extract a common ApprovalVerifier without changing Tool semantics. No configured verifier, timeout, signature failure, claim mismatch, expiry or replay fails closed. Re-resolve bindings and check fingerprints on every call. Emit started/completed/failed Evidence events with redacted inputs and engine references. If DebugService returns running, return immediately with `next_actions=[get_debug_session]`.

- [ ] **Step 5: Verify and commit**

```bash
pytest tests/interface/harness/debug/test_run_debug.py tests/interface/harness/debug/test_real_step_policy.py tests/interface/template/debug/test_step_run.py tests/interface/template/debug/test_service_global_run.py -v --no-cov
git add bkflow/harness/services/debug tests/interface/harness/debug
git commit -m "feat(harness): 封装单步与全局调试执行 --story=136729554"
```

### Task 7: Implement Debug Session Read and Control

**Files:**

- Create: `bkflow/harness/services/debug/read.py`
- Create: `bkflow/harness/services/debug/control.py`
- Modify: `bkflow/harness/services/debug/adapter.py`
- Modify: `bkflow/harness/services/debug/facade.py`
- Create test: `tests/interface/harness/debug/test_get_session.py`
- Create test: `tests/interface/harness/debug/test_control_session.py`

**Interfaces:**

- Consumes: trusted context, DebugSession, DebugService context/history/control operations and EvidenceEvent.
- Produces: `get_debug_session_with_context(context, payload) -> Envelope` and `control_debug_session_with_context(context, payload) -> Envelope`.

- [ ] **Step 1: Write failing read tests**

Test active, completed, failed, terminated and expired sessions. Response contains session state, node readiness/status, redacted context, bounded history, reset impact, artifact references and permitted next actions. Pagination uses stable `(occurred_at, id)` cursors; oversized values become artifact references instead of inline payloads.

`get_debug_session` remains read-only when `harness_debug_enabled=false`, but ownership and trusted-context checks remain mandatory.

- [ ] **Step 2: Write failing control tests**

Use a tagged request with exactly one action:

```text
action=reset: node_ids
action=terminate: optional node_id
action=set_node_mock: node_id, enabled, mock_result, mock_outputs, mock_error
action=set_context_var: key, value
```

Test action-specific validation, ownership, row locking, same-key replay, stale Session, plan/tree drift, running-operation conflict and reset impact. `terminate` and terminal expiry revoke every active TokenLease; `reset` preserves the immutable Evidence history.

- [ ] **Step 3: Run tests to verify RED**

Run: `pytest tests/interface/harness/debug/test_get_session.py tests/interface/harness/debug/test_control_session.py -v --no-cov`

- [ ] **Step 4: Implement read and control flows**

Map the four controls to `DebugService.reset`, `terminate`, `node_mock` and `set_context_var`. Re-resolve capabilities before mutating controls, validate the stored tree fingerprint, and emit before/after Evidence. When every required debug assertion passes, transition `DEBUGGING -> RELEASE_READY`; failure, termination, expiry or a repair-producing result transitions `DEBUGGING -> DRAFT_READY`. Never replay a DebugService mutation outside the idempotency transaction.

- [ ] **Step 5: Verify and commit**

```bash
pytest tests/interface/harness/debug/test_get_session.py tests/interface/harness/debug/test_control_session.py tests/interface/template/debug/test_service_context.py tests/interface/template/debug/test_reset_impact.py tests/interface/template/debug/test_views_run_ops.py -v --no-cov
git add bkflow/harness/services/debug tests/interface/harness/debug
git commit -m "feat(harness): 增加调试会话查询与控制 --story=136729554"
```

### Task 8: Expose the Four P2 Harness Tools

**Files:**

- Create: `bkflow/apigw/serializers/harness/debug.py`
- Create: `bkflow/apigw/views/harness/debug.py`
- Modify: `bkflow/apigw/views/harness/common.py`
- Modify: `bkflow/apigw/urls.py`
- Modify: `bkflow/harness/services/facade.py`
- Modify: `bkflow/apigw/management/commands/data/api-resources.yml`
- Create: `bkflow/apigw/docs/zh/harness_start_debug_session.md`
- Create: `bkflow/apigw/docs/zh/harness_run_debug.md`
- Create: `bkflow/apigw/docs/zh/harness_get_debug_session.md`
- Create: `bkflow/apigw/docs/zh/harness_control_debug_session.md`
- Generated: `bkflow/apigw/docs/apigw-docs.zip`
- Modify: `docs/specs/2026-09-01-bkaidev-a2flow-harness-design.md`
- Modify: `docs/reviews/2026-09-02-bkaidev-harness-p2-debug-spike.md`
- Create test: `tests/interface/apigw/test_harness_p2.py`
- Modify test: `tests/interface/apigw/test_harness_resource_contract.py`

**Interfaces:**

- Consumes: the four P2 facade operations, HarnessPermission, trusted APIGW context and contract-version feature gate.
- Produces: four versioned APIGW operations consumed by the single Harness MCP Server.

- [ ] **Step 1: Write failing API contract tests**

Test request tags, Envelope response, APIGW-only identity, space ownership, contract `1.2.0`, feature flags, idempotency-key propagation and error mapping. Assert the views call only Harness facade functions and never call `DebugService` or token views directly.

- [ ] **Step 2: Run tests to verify RED**

Run: `pytest tests/interface/apigw/test_harness_p2.py tests/interface/apigw/test_harness_resource_contract.py tests/interface/harness/test_contract_versions.py -v --no-cov`

- [ ] **Step 3: Implement serializers, views, and routes**

Add POST routes `/space/{space_id}/harness/start_debug_session/`, `/space/{space_id}/harness/run_debug/`, `/space/{space_id}/harness/get_debug_session/` and `/space/{space_id}/harness/control_debug_session/` with operation IDs `harness_start_debug_session`, `harness_run_debug`, `harness_get_debug_session` and `harness_control_debug_session`. Keep the public MCP Tool names unprefixed as frozen by `CONTRACT_TOOLSETS`. Apply `HarnessPermission` plus the existing APIGW authentication path; do not add SDK routes.

- [ ] **Step 4: Synchronize the APIGW three-piece set and contract docs**

Update `api-resources.yml`, add four Chinese operation documents, run `bash scripts/apigw_docs.sh`, and record the BKAIDev Agent Release mapping in the P2 spike: contract `1.2.0`, 9 cumulative Tools, Mock default, and approval receipt plus server-side Token Broker mandatory for real-step calls.

- [ ] **Step 5: Verify and commit**

```bash
pytest tests/interface/apigw/test_harness_p2.py tests/interface/apigw/test_harness_resource_contract.py tests/interface/harness/test_contract_versions.py -v --no-cov
bash scripts/apigw_docs.sh
unzip -l bkflow/apigw/docs/apigw-docs.zip | rg 'harness_(start|run|get|control)_debug'
git diff --check
git add bkflow/apigw bkflow/harness/services/facade.py docs/specs/2026-09-01-bkaidev-a2flow-harness-design.md docs/reviews/2026-09-02-bkaidev-harness-p2-debug-spike.md tests/interface/apigw/test_harness_p2.py tests/interface/apigw/test_harness_resource_contract.py
git commit -m "feat(harness): 暴露 P2 调试 Tool 契约 --story=136729554"
```

### Task 9: Add Debug Golden Cases and the P2 Release Gate

**Files:**

- Create: `tests/fixtures/harness/debug_cases.yaml`
- Create: `tests/interface/harness/debug/test_golden_cases.py`
- Create: `tests/interface/harness/debug/test_secret_non_disclosure.py`
- Create: `docs/reviews/2026-09-02-bkaidev-harness-p2-verification.md`
- Create: `Makefile`

**Interfaces:**

- Consumes: P2 Tool APIs, Mock and approved-real policies, TokenLease lifecycle and Evidence records.
- Produces: deterministic 40-case regression suite, `make harness-p2-gate`, and rollout verdict.

- [ ] **Step 1: Define exactly 40 Golden Cases**

```text
step_mock_success_failure        8
step_dependency_blocked         5
global_mock_lifecycle           5
session_lock_conflict           5
reset_and_control               4
terminate_and_recovery          4
plan_or_fingerprint_drift       3
token_lifecycle                 3
forged_or_expired_approval      3
total                          40
```

Each case declares trusted context, predecessor revision, draft fingerprint, request, expected Envelope code, state transition, Evidence event types, TokenLease result and forbidden plaintext markers.

- [ ] **Step 2: Write the table-driven runner and secret tests**

Assert all Tool responses, serialized models, normal logs and exception messages contain neither token plaintext nor provider credentials. Include crashes after token issue, after DebugService dispatch and before idempotency completion; retries must converge without duplicate mutations.

- [ ] **Step 3: Add the P2 gate target**

`make harness-p2-gate` runs migration checks, P0/P1/P2 Harness tests, existing permission token tests, the entire template debug suite, API resource consistency and secret scans. It must fail if fixture count is not exactly 40 or if contract `1.2.0` does not expose exactly 9 Tools.

- [ ] **Step 4: Run local verification and record evidence**

```bash
make harness-p2-gate
python manage.py makemigrations harness --check
git diff --check
```

Record commands, pass counts, predecessor/current SHA, fixture count, enabled flags and known external gaps in the verification document. Do not copy tokens or sensitive payloads into the report.

- [ ] **Step 5: Apply the rollout decision and commit**

`P2_LOCAL_GATE_PASSED` requires all local commands to pass. `P2_REAL_STEP_GATE_PASSED` additionally requires live BKAIDev approval-receipt verification, platform-app user Token issuance, one real low-risk node, revoke proof and readback. Otherwise record `P2_REAL_STEP_GATE_BLOCKED_BY_EXTERNAL_EVIDENCE`; Mock P2 may remain available behind its space flag.

```bash
git add tests/fixtures/harness/debug_cases.yaml tests/interface/harness/debug/test_golden_cases.py tests/interface/harness/debug/test_secret_non_disclosure.py docs/reviews/2026-09-02-bkaidev-harness-p2-verification.md Makefile
git commit -m "test(harness): 建立 P2 调试安全与发布门禁 --story=136729554"
```

## P2 Completion Evidence

- Contract `1.2.0` exposes exactly 9 cumulative Tools while `1.0.0` and `1.1.0` remain compatible.
- Four debug Tools operate only on a Revision-bound DebugSession and reuse the existing DebugService through an adapter.
- Global debug is Mock-only; real step is fail-closed unless approval and trusted Token issuance are both verified.
- Token plaintext is absent from persistent storage, API responses, logs, Evidence and test fixtures.
- Forty Golden Cases and existing DebugService tests pass under `make harness-p2-gate`.
- The verification document distinguishes local implementation, Mock rollout and externally verified real-step rollout.

## Execution Handoff

After this plan is approved, implement it with one of the following:

1. **Subagent-Driven Development (recommended):** execute one task at a time with fresh implementation and review agents, preserving the listed commits and reconciliation gates.
2. **Inline Execution:** use `superpowers:executing-plans` in a separate implementation session and stop at every Decision Gate or failed verification command.

Do not begin P3 until P2 local gate passes. P3 real execution may still proceed behind its own fail-closed flags when P2 real-step remains blocked, but it cannot claim inherited real-debug evidence.
