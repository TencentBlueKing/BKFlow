# BKAIDev a2flow Harness P1 Knowledge Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不自建完整知识库产品的前提下，为 BKFlow Harness 增加按平台、空间和 Scope 隔离的联邦知识路由，并以第 5 个 MCP Tool `search_workflow_knowledge` 返回带来源、快照、引用和信任级别的流程知识。

**Architecture:** 知识内容继续存放在 BKAIDev、BKFara 或其他平台已有知识库；BKFlow 只保存 KnowledgeSourceBinding、ACL、快照引用和检索审计。Router 必须先做可信上下文和 ACL 过滤，再调用 provider 检索、重排和冲突合并；插件版本、Schema、权限和运行状态仍由 P0 Registry/Resolver 提供。

**Tech Stack:** Python 3.9.12、Django 3.2.25、Django REST Framework 3.12.4、Pydantic 1.10.6、pytest、jsonschema、BKFlow APIGW。

**Spec:** `docs/specs/2026-09-01-bkaidev-a2flow-harness-design.md`

## Global Constraints

- P1 只新增 `search_workflow_knowledge`，累计 5 个 Harness Tool；不得实现调试、Token Broker、发布、执行或反馈写入。
- BKAIDev Agent 仍是唯一对话和 LLM 主体；Knowledge Router 是被动、确定性的服务，不启动第二个 Agent。
- 不在 BKFlow 存储知识正文、向量索引或切片；只保存绑定、不可猜测的 source ref、快照、审计和脱敏 Artifact 引用。
- 知识负责“怎么选、怎么用、常见坑”；Registry/API 负责当前真实能力、精确版本、Schema 和权限。
- 所有知识内容均视为不可信数据，返回字段统一 `policy_effect=ADVISORY`，不得修改 Validator、Policy、Tool allowlist 或可信身份。
- 有效知识集合为 `Global + Public + trusted Platform + Space + Scope`；业务偏好冲突优先级固定为 `Scope > Space > Platform > Public`，Global 硬规则只能由代码/Policy 实现。
- ACL、环境、信任和有效期过滤必须发生在 provider 检索之前；禁止先跨库搜索再过滤结果。
- 旧 P0 contract `1.0.0` 和四个 Tool 必须继续可用；P1 使用 contract `1.1.0` 与独立开关 `harness_knowledge_router_enabled`。
- 总开关关闭时不创建新 HarnessRun；关闭 P1 开关不能影响 P0 搜索、Schema、校验和草稿能力。
- 数据库 migration 使用 `python manage.py makemigrations harness --name p1_knowledge_router` 生成，不手写。
- APIGW 资源、中文文档和 `bkflow/apigw/docs/apigw-docs.zip` 必须同步。
- 每个提交使用 `--story=136729554`，只暂存任务路径，不触碰工作区其他未跟踪文件。

---

## Inherited Contracts

- `TrustedHarnessContext` 的 platform/app/actor/space/scope/environment/policy/contract/correlation 字段。
- `HarnessPermission` 的 app、user、app-to-space、user-to-space 和总开关 AND 鉴权。
- P0 Envelope：`ok, run_id, revision_id, plan_hash, status, summary, artifact_refs, errors, next_actions, correlation_id`。
- P0 错误结构：category、code、message、path、repairable、retryable、suggested_action。
- `HarnessRun`、不可变 `WorkflowPlanRevision`、`CapabilityBinding`、`ValidationReport` 和幂等作用域。
- Tool Search 只搜索业务能力；Knowledge Search 返回业务知识，不返回或执行 MCP Tool Definition。

## Decision Gates

- **DG-P1-01 Provider API:** 验证 BKAIDev/平台知识库是否提供服务端检索 API、身份透传、source/chunk 引用、快照版本、超时和响应上限。无真实 API 时只实现 provider SPI 与 FakeProvider，P1 Release Gate 保持阻断。
- **DG-P1-02 Source ownership:** Global/Public 由 BKFlow Owner 管理，Platform 由平台 Owner 管理，Space/Scope 由业务 Owner 管理；Owner/Reviewer 映射必须在启用绑定前确认。
- **DG-P1-03 Contract rollout:** 只有 BKAIDev Agent Release 能按连接挂载 5 Tool 且仍兼容 P0 会话时，才能把部署 binding 从 `1.0.0` 升至 `1.1.0`。
- **DG-P1-04 Sensitive query:** Provider 无法证明查询和结果的分级/脱敏边界时，含敏感分类的绑定保持 disabled。

## Reconciliation Check

实际实施基线为 `ai/a2flow-harness-p0-clean@80a3922fd38edfe51d640df0782613c75bdb0edc`。开始 P1 前已按 P0 verification 的精确聚焦命令重跑：`471 passed, 8 skipped`；八个 skip 均为 SQLite 无法证明双连接行锁语义，不能替代 MySQL/PostgreSQL 并发证据。P0 本地代码已存在，但 P0 verification 仍标记外部 BKAIDev/试点证据未完成。

开始 Task 2 前必须确认工作树无未归属的 Harness 修改且 migration leaf 正是 `0003_capabilitybinding_conversion_fingerprint`。P1 继续生成 `0004_p1_knowledge_router` 并依赖该真实 leaf；禁止修改已落库 migration 或制造冲突 leaf 强行匹配旧计划。

必须确认 `HarnessFacade` 的四个 P0 方法、P0 contract `1.0.0`、`HarnessDeploymentConfig`、统一 Envelope 和 migration leaf `0003_capabilitybinding_conversion_fingerprint` 未发生破坏性变化。若变化，先更新本计划中的接口、migration 编号和兼容测试。

## File Responsibility Map

```text
bkflow/harness/
├── admin.py
├── constants.py
├── contracts.py
├── models.py
├── services/contract_versions.py
└── services/knowledge/
    ├── contracts.py
    ├── providers.py
    ├── eligibility.py
    ├── redaction.py
    ├── router.py
    └── audit.py

bkflow/harness/management/commands/sync_knowledge_bindings.py
bkflow/apigw/serializers/harness/knowledge.py
bkflow/apigw/views/harness/knowledge.py
tests/interface/harness/knowledge/
tests/fixtures/harness/knowledge_cases.yaml
```

### Task 1: Reconcile P0 and Freeze the Knowledge Provider Spike

**Files:**

- Create: `docs/reviews/2026-09-02-bkaidev-harness-p1-provider-spike.md`
- Reference: `docs/reviews/2026-09-01-bkaidev-harness-p0-verification.md`
- Reference: `docs/specs/2026-09-01-bkaidev-a2flow-harness-design.md`

**Interfaces:**

- Consumes: P0 contract `1.0.0`, `TrustedHarnessContext`, BKAIDev Agent Release and platform knowledge-provider documentation.
- Produces: `provider_mode`, `identity_mode`, `snapshot_mode`, measured limits, stop conditions and predecessor SHA.

- [ ] **Step 1: Re-run the P0 local regression gate**

Run the exact focused command recorded in the P0 verification document with `--no-cov`. Record pass count, duration, branch and SHA. A failure blocks P1 code until diagnosed.

- [ ] **Step 2: Execute the provider probe matrix**

The review must contain SP-P1-01 through SP-P1-06:

```text
SP-P1-01 service-to-service search authentication
SP-P1-02 source_ref and chunk/citation stability
SP-P1-03 snapshot/version availability
SP-P1-04 provider-side ACL and caller attribution
SP-P1-05 timeout, response bytes and top_k limits
SP-P1-06 query/result data classification and redaction
```

Each row records sanitized input, expected result, actual evidence, pass, owner and decision impact.

- [ ] **Step 3: Freeze provider decisions**

```text
provider_mode = external_search_api | provider_spi_only
identity_mode = trusted_user_passthrough | platform_service_identity
snapshot_mode = provider_native_snapshot | content_digest_snapshot
```

`provider_spi_only` permits local Router tests but blocks BKAIDev/space rollout. `platform_service_identity` requires Binding-level allowed actor/app enforcement before provider calls.

- [ ] **Step 4: Verify and commit the spike**

Run: `rg -n 'SP-P1-0[1-6]|provider_mode =|identity_mode =|snapshot_mode =|predecessor_sha' docs/reviews/2026-09-02-bkaidev-harness-p1-provider-spike.md`

Expected: six probes, three decisions and predecessor SHA are present; no PASS lacks a source link, exported config or captured response.

```bash
git add docs/reviews/2026-09-02-bkaidev-harness-p1-provider-spike.md
git commit -m "docs(harness): 固化 P1 知识源接入门禁 --story=136729554"
```

### Task 2: Add Versioned Toolsets and the P1 Feature Flag

**Files:**

- Create: `bkflow/harness/services/contract_versions.py`
- Modify: `bkflow/harness/services/facade.py`
- Modify: `bkflow/space/configs.py`
- Modify test: `tests/interface/space/test_space_config.py`
- Create test: `tests/interface/harness/test_contract_versions.py`
- Create test: `tests/interface/harness/knowledge/test_feature_gate.py`

**Interfaces:**

- Consumes: current `P0_TOOL_OPERATION_MAP` and `HarnessDeploymentConfig`.
- Produces: `tools_for_contract(version: str) -> Mapping[str, str]`, `require_tool_enabled(context, tool_name) -> None`, contract `1.1.0`, and `HarnessKnowledgeRouterEnabledConfig`.

- [ ] **Step 1: Write failing compatibility tests**

```python
def test_contract_1_0_keeps_exact_p0_toolset():
    assert tuple(tools_for_contract("1.0.0")) == (
        "search_workflow_capabilities",
        "get_plugin_schema",
        "validate_workflow",
        "create_workflow_draft",
    )

def test_contract_1_1_adds_only_knowledge_search():
    assert tuple(tools_for_contract("1.1.0"))[-1] == "search_workflow_knowledge"
    assert len(tools_for_contract("1.1.0")) == 5
```

Also assert: `1.0.0` rejects the P1 Tool, unknown versions fail closed, and the P1 flag defaults false without disabling P0.

- [ ] **Step 2: Run tests to verify RED**

Run: `pytest tests/interface/harness/test_contract_versions.py tests/interface/harness/knowledge/test_feature_gate.py tests/interface/space/test_space_config.py -v --no-cov`

Expected: imports/config choices fail because version registry and P1 flag do not exist.

- [ ] **Step 3: Implement version and flag support**

```python
CONTRACT_TOOLSETS = {
    "1.0.0": P0_TOOL_OPERATION_MAP,
    "1.1.0": {
        **P0_TOOL_OPERATION_MAP,
        "search_workflow_knowledge": "harness_search_workflow_knowledge",
    },
}
```

Add `HarnessKnowledgeRouterEnabledConfig` with name `harness_knowledge_router_enabled`, default `false`, choices `true/false`, `control=True`. Update `HarnessDeploymentConfig` to accept only `1.0.0` and `1.1.0` at this phase.

- [ ] **Step 4: Run compatibility tests**

Run: `pytest tests/interface/harness/test_contract_versions.py tests/interface/harness/knowledge/test_feature_gate.py tests/interface/space/test_space_config.py tests/interface/harness/services/test_facade.py -v --no-cov`

Expected: P0 Tool ordering and behavior stay unchanged; P1 requires both contract `1.1.0` and its feature flag.

- [ ] **Step 5: Commit**

```bash
git add bkflow/harness/services/contract_versions.py bkflow/harness/services/facade.py bkflow/space/configs.py tests/interface
git commit -m "feat(harness): 增加 P1 Tool 版本与功能开关 --story=136729554"
```

### Task 3: Add Knowledge Binding and Retrieval Audit Models

**Files:**

- Modify: `bkflow/harness/constants.py`
- Modify: `bkflow/harness/models.py`
- Create: `bkflow/harness/admin.py`
- Generated: `bkflow/harness/migrations/0004_p1_knowledge_router.py`
- Create test: `tests/interface/harness/knowledge/test_models.py`

**Interfaces:**

- Consumes: `HarnessRun`, `TrustedHarnessContext`.
- Produces: `KnowledgeSourceBinding`, `KnowledgeRetrievalAudit`, `KnowledgeTier`, `KnowledgeTrustLevel`, `KnowledgeBindingStatus`, and `KnowledgeRetrievalMode`.

- [ ] **Step 1: Write failing model and constraint tests**

Test the required dimensions:

```text
GLOBAL: no platform/space/scope
PUBLIC: no platform/space/scope
PLATFORM: platform_key required, no space/scope
SPACE: platform_key and space_id required, no scope
SCOPE: platform_key, space_id, scope_type and scope_value required
```

`KnowledgeSourceBinding` fields are provider, opaque source_ref, tier, platform/space/scope, trust level, priority, environment, allowed apps/actors, data classification, snapshot version, expiry, last verification, owner, reviewer, lifecycle, retrieval mode, max_top_k, redaction policy, credential_ref and non-secret provider_config.

`KnowledgeRetrievalAudit` fields are optional run, trusted context snapshot, query fingerprint, redacted query, eligible binding IDs, provider call summaries, hit refs, snapshot refs, correlation ID, duration and outcome. It must not contain resolved credentials or unrestricted document content.

- [ ] **Step 2: Run tests to verify RED**

Run: `pytest tests/interface/harness/knowledge/test_models.py -v --no-cov`

Expected: model and enum imports fail.

- [ ] **Step 3: Implement models and admin safety**

Enforce tier dimensions in `clean()` plus database `CheckConstraint`s. Active binding identity is unique on provider/source/platform/space/scope/environment. Register Binding in admin with tier/status/owner filters; register Audit read-only by denying add/change/delete.

- [ ] **Step 4: Generate and inspect migration**

```bash
python manage.py makemigrations harness --name p1_knowledge_router
python manage.py sqlmigrate harness 0004
python manage.py makemigrations harness --check
```

Expected: only P1 tables/constraints and no P0 data rewrite.

- [ ] **Step 5: Run tests and commit**

```bash
pytest tests/interface/harness/knowledge/test_models.py tests/interface/harness/test_models.py -v --no-cov
git add bkflow/harness/constants.py bkflow/harness/models.py bkflow/harness/admin.py bkflow/harness/migrations tests/interface/harness/knowledge/test_models.py
git commit -m "feat(harness): 新增知识源绑定与检索审计模型 --story=136729554"
```

### Task 4: Define the Provider SPI and Redaction Boundary

**Files:**

- Create: `bkflow/harness/services/knowledge/__init__.py`
- Create: `bkflow/harness/services/knowledge/contracts.py`
- Create: `bkflow/harness/services/knowledge/providers.py`
- Create: `bkflow/harness/services/knowledge/redaction.py`
- Create test: `tests/interface/harness/knowledge/test_providers.py`
- Create test: `tests/interface/harness/knowledge/test_redaction.py`

**Interfaces:**

- Consumes: eligible `KnowledgeSourceBinding` rows and trusted context.
- Produces: `KnowledgeProvider.search(binding, query) -> Sequence[ProviderKnowledgeHit]`, `KnowledgeProviderRegistry`, and `redact_knowledge_payload(value, policy_version) -> object`.

- [ ] **Step 1: Write failing provider contract tests**

```python
@dataclass(frozen=True)
class KnowledgeProviderQuery:
    query: str
    top_k: int
    source_ref: str
    snapshot_version: str
    correlation_id: str

@dataclass(frozen=True)
class ProviderKnowledgeHit:
    provider_hit_ref: str
    title: str
    excerpt: str
    citation_ref: str
    source_snapshot: str
    provider_score: float
```

Test registry rejection of unknown provider, provider timeout normalization to `RETRYABLE_INFRA`, maximum excerpt bytes, stable citation refs and absence of credential values in query/result dataclasses.

- [ ] **Step 2: Write failing redaction tests**

Fixtures cover access tokens, app secrets, cookies, authorization headers, passwords, private keys and nested credential-shaped objects. Assert redaction occurs before audit persistence and Envelope serialization.

- [ ] **Step 3: Run tests to verify RED**

Run: `pytest tests/interface/harness/knowledge/test_providers.py tests/interface/harness/knowledge/test_redaction.py -v --no-cov`

- [ ] **Step 4: Implement SPI and safe default**

Implement registry plus `FakeKnowledgeProvider` for deterministic tests. Add a real provider adapter only when DG-P1-01 identifies an authenticated API; otherwise production registration stays empty and readiness fails closed.

Resolve `credential_ref` through the existing server-side credential dispatcher inside the adapter call. The resolved secret exists only for that call and never enters dataclasses, logs, audits, exceptions or Tool output.

- [ ] **Step 5: Run tests and commit**

```bash
pytest tests/interface/harness/knowledge/test_providers.py tests/interface/harness/knowledge/test_redaction.py -v --no-cov
git add bkflow/harness/services/knowledge tests/interface/harness/knowledge
git commit -m "feat(harness): 定义知识 Provider 与脱敏边界 --story=136729554"
```

### Task 5: Enforce ACL-before-Retrieval and Binding Governance

**Files:**

- Create: `bkflow/harness/services/knowledge/eligibility.py`
- Create: `bkflow/harness/services/knowledge/bindings.py`
- Create: `bkflow/harness/management/__init__.py`
- Create: `bkflow/harness/management/commands/__init__.py`
- Create: `bkflow/harness/management/commands/sync_knowledge_bindings.py`
- Create test: `tests/interface/harness/knowledge/test_eligibility.py`
- Create test: `tests/interface/harness/knowledge/test_binding_sync.py`

**Interfaces:**

- Consumes: `TrustedHarnessContext`, active Binding queryset and versioned binding manifest.
- Produces: `eligible_bindings(context, classification) -> Sequence[KnowledgeSourceBinding]` and an apply-gated binding sync command.

- [ ] **Step 1: Write the ACL truth-table tests**

Cover Global/Public visibility, platform mismatch, space mismatch, Scope mismatch, environment mismatch, app/actor allowlists, expired snapshot, unverified trust, deprecated/retired source and data-classification denial. Mock providers and assert forbidden bindings receive zero provider calls.

- [ ] **Step 2: Write binding sync tests**

The command accepts a YAML manifest containing non-secret source metadata. Default mode prints create/update/retire diff and performs no writes; `--apply` performs an atomic sync. Removing a source marks it retired rather than deleting audit history.

Run: `pytest tests/interface/harness/knowledge/test_eligibility.py tests/interface/harness/knowledge/test_binding_sync.py -v --no-cov`

Expected: eligibility and command imports fail.

- [ ] **Step 3: Implement deterministic eligibility**

Query order is fixed as GLOBAL, PUBLIC, matching PLATFORM, matching SPACE, matching SCOPE. Filter status, trust, environment, expiry, app, actor and classification in the database before provider dispatch.

- [ ] **Step 4: Implement controlled binding sync**

Validate Owner/Reviewer, tier dimensions, provider registration, snapshot and credential reference existence before applying. Emit counts and binding IDs only; never print provider secrets or full config values.

- [ ] **Step 5: Verify and commit**

```bash
pytest tests/interface/harness/knowledge/test_eligibility.py tests/interface/harness/knowledge/test_binding_sync.py -v --no-cov
git add bkflow/harness/services/knowledge bkflow/harness/management tests/interface/harness/knowledge
git commit -m "feat(harness): 增加知识 ACL 路由与绑定治理 --story=136729554"
```

### Task 6: Implement Retrieval, Conflict Merge, and Audit

**Files:**

- Modify: `bkflow/harness/contracts.py`
- Create: `bkflow/harness/services/knowledge/router.py`
- Create: `bkflow/harness/services/knowledge/audit.py`
- Create test: `tests/interface/harness/knowledge/test_router.py`
- Create test: `tests/interface/harness/knowledge/test_audit.py`

**Interfaces:**

- Consumes: provider registry, `eligible_bindings`, redaction service and optional `run_id`.
- Produces: `KnowledgeQuery`, `KnowledgeHit`, `KnowledgeSearchResult`, and `KnowledgeRouter.search(context, request) -> KnowledgeSearchResult`.

- [ ] **Step 1: Write failing merge and conflict tests**

`KnowledgeHit` contains hit_ref, binding_id, tier, provider, title, redacted excerpt, citation_ref, source_ref, snapshot_version, trust_level, applicable scope, provider score, final score, expiry and `policy_effect="ADVISORY"`.

Test deduplication by `(source_ref, snapshot_version, provider_hit_ref)`, `top_k` cap, deterministic tie-breaking, Scope/Space/Platform/Public preference, Global hard-rule preservation, contradictory business guidance, partial provider timeout, zero-hit recovery and large-result Artifact fallback.

- [ ] **Step 2: Write failing audit tests**

Assert one audit row per Tool call, including zero-result and provider failure. Raw query is retained only after configured redaction; provider secrets, full documents and forbidden binding IDs never appear.

- [ ] **Step 3: Run tests to verify RED**

Run: `pytest tests/interface/harness/knowledge/test_router.py tests/interface/harness/knowledge/test_audit.py -v --no-cov`

- [ ] **Step 4: Implement Router pipeline**

```text
trusted context
-> eligible_bindings
-> per-binding top_k clamp
-> provider calls with bounded timeout
-> redact
-> normalize scores
-> deduplicate
-> specificity/trust/priority merge
-> conflict annotations
-> final top_k
-> audit
```

Provider failure is isolated per source. Return `RETRYABLE_INFRA` only when no usable source succeeds; otherwise return hits plus warning artifacts.

- [ ] **Step 5: Run tests and commit**

```bash
pytest tests/interface/harness/knowledge/test_router.py tests/interface/harness/knowledge/test_audit.py -v --no-cov
git add bkflow/harness/contracts.py bkflow/harness/services/knowledge tests/interface/harness/knowledge
git commit -m "feat(harness): 实现联邦知识检索与冲突合并 --story=136729554"
```

### Task 7: Expose search_workflow_knowledge and Synchronize APIGW

**Files:**

- Create: `bkflow/apigw/serializers/harness/knowledge.py`
- Create: `bkflow/apigw/views/harness/knowledge.py`
- Modify: `bkflow/apigw/views/harness/common.py`
- Modify: `bkflow/apigw/urls.py`
- Modify: `bkflow/harness/services/facade.py`
- Modify: `bkflow/apigw/management/commands/data/api-resources.yml`
- Create: `bkflow/apigw/docs/zh/harness_search_workflow_knowledge.md`
- Generated: `bkflow/apigw/docs/apigw-docs.zip`
- Create test: `tests/interface/apigw/test_harness_p1.py`
- Modify test: `tests/interface/apigw/test_harness_resource_contract.py`

**Interfaces:**

- Consumes: `KnowledgeRouter.search`, contract `1.1.0`, P0 Envelope and `HarnessPermission`.
- Produces: facade method `search_workflow_knowledge(context, request)` and operation `harness_search_workflow_knowledge`.

- [ ] **Step 1: Write failing serializer and endpoint tests**

Request fields are `query`, `top_k` capped at 20, optional `run_id`, `data_classification` and opaque `client_context`. Identity, platform, space, scope and environment fields are rejected.

Response uses the unchanged Envelope and returns hits through `artifact_refs`; `summary` is bounded. Test contract 1.0 rejection, 1.1 success, disabled flag, forged identity, cross-space run, empty result and provider timeout.

- [ ] **Step 2: Run tests to verify RED**

Run: `pytest tests/interface/apigw/test_harness_p1.py tests/interface/apigw/test_harness_resource_contract.py -v --no-cov`

- [ ] **Step 3: Add facade, serializer, view and route**

Add exactly one public P1 facade method and `P1_ACTION_RISK = {"search_workflow_knowledge": "L0"}`. The view remains a transport adapter and calls the existing Harness dispatch path.

- [ ] **Step 4: Add APIGW resource and documentation**

Use POST route `/space/{space_id}/harness/search_workflow_knowledge/` with app, user and resource verification all required. Document trust tiers, citations, advisory-only content, ACL-before-retrieval and error semantics.

Run: `bash scripts/apigw_docs.sh`

- [ ] **Step 5: Verify and commit**

```bash
pytest tests/interface/apigw/test_harness_p1.py tests/interface/apigw/test_harness_resource_contract.py tests/interface/harness/services/test_facade.py -v --no-cov
unzip -l bkflow/apigw/docs/apigw-docs.zip | rg 'harness_search_workflow_knowledge'
git add bkflow/apigw bkflow/harness/services/facade.py tests/interface/apigw
git commit -m "feat(harness): 暴露联邦知识检索 Tool --story=136729554"
```

### Task 8: Add Knowledge Golden Cases and the P1 Release Gate

**Files:**

- Create: `tests/fixtures/harness/knowledge_cases.yaml`
- Create: `tests/interface/harness/knowledge/test_golden_cases.py`
- Create: `tests/interface/harness/knowledge/test_security_boundaries.py`
- Create: `docs/reviews/2026-09-02-bkaidev-harness-p1-verification.md`
- Modify: `docs/reviews/2026-09-02-bkaidev-harness-p1-provider-spike.md`

**Interfaces:**

- Consumes: all P1 services and BKAIDev five-Tool Agent Release.
- Produces: versioned retrieval corpus, security evidence and P1 gate decision.

- [ ] **Step 1: Create 36 fixed cases**

```text
global_public_common = 6
platform_specific = 6
space_private = 6
scope_private = 6
conflict_precedence = 4
expired_or_retired = 3
cross_space_denied = 3
malicious_instruction = 2
total = 36
```

Each case pins trusted context, eligible source IDs, provider snapshot, expected citations, forbidden sources and expected Tool result.

- [ ] **Step 2: Add security and no-policy-override tests**

Assert cross-space/provider calls are zero, malicious content cannot change Tool sequence or hard policy, no secret appears in response/audit/log capture, expired sources are absent and provider timeouts do not expose configuration.

- [ ] **Step 3: Run the full P1 local gate**

```bash
pytest tests/interface/harness tests/interface/apigw/test_harness_p0.py tests/interface/apigw/test_harness_p1.py tests/interface/apigw/test_harness_resource_contract.py -v --no-cov
python manage.py check
python manage.py makemigrations harness --check
git diff --check
```

- [ ] **Step 4: Execute external retrieval acceptance when available**

Use Global/Public, BKFara Platform, one Space and one Scope binding. Record provider request ID, source/snapshot/citation, ACL decision, latency and redaction evidence. No external access means `P1_RELEASE_GATE_BLOCKED_BY_PROVIDER_EVIDENCE`.

- [ ] **Step 5: Verify BKAIDev release isolation**

Pin Agent Release to contract `1.1.0`, exactly five Tool names and knowledge snapshots. Confirm a `1.0.0` connection still sees only P0 Tools and disabling the P1 flag leaves all P0 tests green.

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/harness/knowledge_cases.yaml tests/interface/harness/knowledge docs/reviews/2026-09-02-bkaidev-harness-p1-*.md
git commit -m "test(harness): 建立 P1 知识检索门禁 --story=136729554"
```

## P1 Completion Evidence

- P0 predecessor SHA and rerun evidence.
- Six provider probes and three frozen provider decisions.
- Contract `1.0.0` four-Tool compatibility and `1.1.0` five-Tool snapshot.
- 36 Golden Cases with no cross-space/provider-call leakage.
- Every hit has source, tier, scope, snapshot, trust and citation.
- Knowledge remains advisory and cannot override Validator/Policy.
- External provider and BKAIDev evidence, or the exact blocked status.

## Follow-up Boundary

P1 does not create `KnowledgeCandidate` or publish knowledge changes. Feedback-derived candidates, Owner review and regression promotion belong to P4. P2 may consume KnowledgeHit citations as read-only context but must not treat them as permission or runtime truth.

## Execution Handoff

After this plan is approved, implement it with one of the following:

1. **Subagent-Driven Development (recommended):** execute one task at a time with independent implementation and review passes, preserving each Decision Gate and listed commit.
2. **Inline Execution:** use `superpowers:executing-plans` in a separate implementation session and stop at every failed provider, ACL, compatibility or verification gate.

Do not begin P2 until the P1 local gate passes. A provider-SPI-only implementation may be locally complete, but it cannot claim external knowledge retrieval readiness without provider and BKAIDev evidence.
