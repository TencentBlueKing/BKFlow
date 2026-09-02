# BKAIDev a2flow Harness Spike + P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Use superpowers:test-driven-development for every behavior change, superpowers:systematic-debugging for unexpected failures, and superpowers:verification-before-completion before claiming a task or phase complete.

**Goal:** 在 `feat/a2flow` 现有能力之上，交付一个由 BKAIDev SaaS 单智能体调用的 BKFlow Workflow Harness P0：以 1 个逻辑 MCP 暴露 4 个稳定控制 Tool，完成能力检索、精确 Schema 获取、确定性校验和草稿创建，并为后续知识联邦、调试、发布执行和反馈闭环建立可信上下文、版本、证据与状态基础。

**Architecture:** BKAIDev Agent 是唯一持有对话上下文并访问 LLM 的主体；BKFlow Interface 提供 Hard Harness 状态机、能力真值、版本绑定、校验、幂等和 Evidence；BKFlow Engine 在 P0 不承载生成会话。P0 不在 Django 请求进程内实现第二套 Agent 或自主 MCP 循环，而是新增 4 个 APIGW Harness operation，由 BKAIDev 平台托管的 1 个 MCP 连接映射成 4 个 MCP-visible Tool。

**Tech Stack:** Python 3.9.12、Django 3.2.25、Django REST Framework 3.12.4、Pydantic 1.10.6、pytest、YAML、BKFlow APIGW。

**Spec:** `docs/specs/2026-09-01-bkaidev-a2flow-harness-design.md`

## Global Constraints

- 当前计划只实现 BKAIDev Spike 与 P0；P1-P4 在前一阶段门禁通过后分别形成独立实施计划。
- BKAIDev Agent 是唯一 Agent 和唯一 LLM 原生接口调用方；Harness MCP 只提供被动、确定性的控制 Tool。
- 对话上下文归 BKAIDev；结构化生成状态、版本、Evidence 和幂等记录归 BKFlow Interface；Engine 只保存实际执行上下文。
- 真实 `platform_app`、`actor`、`space_id`、scope 和 environment 只能从可信网关/MCP 连接推导，禁止接受模型输入覆盖。
- Tool Search 搜索用于构建流程的业务能力；不得把 Harness 控制 Tool 当作业务能力候选。
- 业务插件 Schema 是生成与校验数据，不代表允许 Agent 直接执行插件。
- P0 只能创建未发布草稿；不得发布模板、创建任务、启动真实执行或调用 `sdk_xxx` 画布 SDK。
- 所有 capability 必须绑定精确版本和 `schema_hash`；无版本来源统一显式标记为 `unversioned`，不得静默选择 latest。
- 所有写操作必须携带幂等键；重试必须返回同一资源或明确冲突，不得生成重复草稿。
- 数据库迁移必须通过 `makemigrations` 生成，不得手写 migration。
- 新增 APIGW operation 后必须同步资源 YAML、中文文档和 `apigw-docs.zip`。
- 既有 a2flow V2 API 行为必须保持兼容；Harness 通过抽取 service 复用，不复制整段 view 逻辑。
- 每个任务遵循 Red-Green-Refactor，并以最小可审查提交结束；commit 关联 `--story=136729554`。

## Phase and Tool Budget

| Phase | Scope | New Tool | Cumulative | Plan gate |
|---|---|---:|---:|---|
| Spike | 验证 BKAIDev Agent、MCP 映射、连接可信字段、上下文持久性 | 0 | 0 | Spike 结论可复现 |
| P0 | 能力检索、精确 Schema、校验、草稿 | 4 | 4 | 本计划完成 |
| P1 | 联邦知识路由 | 1 | 5 | 单独计划 |
| P2 | 单步调试、全局调试、Token Broker | 4 | 9 | 单独计划 |
| P3 | 审批、发布、执行控制 | 5 | 14 | 单独计划 |
| P4 | 生成反馈闭环 | 1 | 15 | 单独计划 |

P0 MCP-visible Tool 固定为：

1. `search_workflow_capabilities`
2. `get_plugin_schema`
3. `validate_workflow`
4. `create_workflow_draft`

仅当 Spike 证明 BKAIDev 无法在刷新、上下文压缩或多轮 Tool 调用后稳定携带 `run_id`，才允许增加第 16 个可选 Tool `start_generation_run`。该结论必须先修改 spec，再修改后续计划；P0 实现不得自行加入。

## P0 File Responsibility Map

```text
bkflow/harness/
├── __init__.py
├── apps.py
├── constants.py
├── exceptions.py
├── models.py
├── contracts.py
├── permissions.py
├── migrations/__init__.py
├── data/capability_manifest_overrides.yaml
└── services/
    ├── __init__.py
    ├── context.py
    ├── canonical.py
    ├── state.py
    ├── idempotency.py
    ├── capability_ref.py
    ├── projection.py
    ├── resolver.py
    ├── validator.py
    ├── draft.py
    └── facade.py

bkflow/template/services/
├── __init__.py
└── a2flow_template.py

bkflow/apigw/serializers/harness/
├── __init__.py
├── common.py
├── capabilities.py
└── workflow.py

bkflow/apigw/views/harness/
├── __init__.py
├── capabilities.py
└── workflow.py

tests/interface/harness/
tests/interface/apigw/test_harness_p0.py
tests/fixtures/harness/
docs/reviews/2026-09-01-bkaidev-harness-p0-spike.md
```

## Stable P0 Interfaces

The implementation must preserve these domain contracts so APIGW serializers remain transport adapters rather than business logic containers:

```python
@dataclass(frozen=True)
class TrustedHarnessContext:
    platform_key: str
    platform_app: str
    actor: str
    space_id: int
    scope_type: Optional[str]
    scope_value: Optional[str]
    target_environment: str
    policy_version: str
    mcp_contract_version: str
    correlation_id: str


@dataclass(frozen=True)
class ResolvedCapability:
    capability_ref: str
    plugin_type: str
    code: str
    source_key: Optional[str]
    resolved_version: str
    schema_hash: str
    schema: Dict[str, Any]
    risk_level: str
```

`HarnessFacade` exposes exactly four public P0 methods named after the MCP-visible Tools. All four return the same Envelope keys:

```text
ok
run_id
revision_id
plan_hash
status
summary
artifact_refs
errors
next_actions
correlation_id
```

## Task 1: Freeze the BKAIDev P0 Integration Spike

**Files:**

- Create: `docs/reviews/2026-09-01-bkaidev-harness-p0-spike.md`
- Reference: `docs/specs/2026-09-01-bkaidev-a2flow-harness-design.md`

**Step 1: Write the probe matrix before backend implementation**

Document exact probes, expected evidence, and pass/fail criteria for:

- One BKAIDev SaaS Agent can bind one logical MCP connection and see exactly four approved Tool names.
- MCP Tool input/output supports nested JSON objects without stringifying a2flow.
- BKAIDev can retain and resend `run_id`, `revision_id`, `plan_hash`, and `correlation_id` across at least five Tool turns.
- Page refresh, conversation compaction, and one transient Tool error do not silently substitute a different run.
- The MCP/APIGW connection exposes authenticated app and user identity; route `space_id` resolves a server-side Harness deployment binding containing platform, scope, environment, policy and MCP contract version.
- Tool response size and timeout limits are sufficient for exact plugin Schema; record measured limits.
- The Agent prompt can prohibit direct plugin execution and stop after `DRAFT` in P0.

Use this evidence table, with no blank result cells after execution:

```markdown
| Probe ID | Input | Expected | Actual evidence | Pass | Decision impact |
|---|---|---|---|---|---|
| SP-01 | List MCP tools | Exactly four P0 names | Screenshot or exported config | yes/no | MCP mapping |
```

**Step 2: Record two explicit architecture decisions**

The Spike document must end with one selected value for each decision:

```text
mcp_adapter = bkaidev_managed | separate_bkflow_adapter
run_creation = validate_workflow_implicit | start_generation_run_required
```

Select `bkaidev_managed` unless the platform demonstrably cannot map APIGW operations to MCP tools. Select `validate_workflow_implicit` unless SP-03/SP-04 fail.

If either fallback value is selected, stop this plan after Task 1 and update the approved spec before touching backend code.

**Step 3: Verify the Spike document is complete**

Run:

```bash
rg -n "SP-0[1-7]|mcp_adapter =|run_creation =|Actual evidence" docs/reviews/2026-09-01-bkaidev-harness-p0-spike.md
placeholder_pattern='T''BD|TO''DO|待补''充|待验''证'
rg -n "$placeholder_pattern" docs/reviews/2026-09-01-bkaidev-harness-p0-spike.md
```

Expected: all seven probes and both decisions exist; the second command returns no matches.

**Step 4: Commit**

```bash
git add docs/reviews/2026-09-01-bkaidev-harness-p0-spike.md
git commit -m "docs(harness): 固化 BKAIDev P0 接入探针 --story=136729554"
```

## Task 2: Add the Harness Django App and Immutable P0 Records

**Files:**

- Modify: `module_settings.py`
- Create: `bkflow/harness/__init__.py`
- Create: `bkflow/harness/apps.py`
- Create: `bkflow/harness/constants.py`
- Create: `bkflow/harness/models.py`
- Create: `bkflow/harness/migrations/__init__.py`
- Generated: `bkflow/harness/migrations/0001_initial.py`
- Test: `tests/interface/harness/test_models.py`

**Step 1: Write failing model tests**

Cover these records and invariants:

- `HarnessRun`: platform key, platform app, actor, space, scope, environment, status, policy version, MCP contract version, client context and artifact references.
- `WorkflowPlanRevision`: UUID primary key, run FK, monotonic sequence, optional parent revision, intent spec, canonical a2flow, `plan_hash`; unique `(run, sequence)`.
- `CapabilityBinding`: revision, node ID, capability ref, resolved version, schema hash, optional credential ref and risk level; unique `(revision, node_id)`.
- `ValidationReport`: required run FK, nullable revision FK, checkpoint, validator version, result, risk manifest, errors, warnings and correlation ID. A failed first validation is attached to the run with `revision=None`.
- `HarnessIdempotencyRecord`: trusted caller scope, Tool name, non-null `run_scope`, optional run FK, idempotency key, request hash, response snapshot and resource reference; unique `(platform_app, actor, space_id, tool_name, run_scope, idempotency_key)`.
- Updating an existing `WorkflowPlanRevision` raises an error.

Example failing assertion:

```python
def test_workflow_plan_revision_rejects_update(db, harness_run):
    revision = WorkflowPlanRevision.objects.create(
        run=harness_run,
        sequence=1,
        intent_spec={"goal": "restart service"},
        canonical_a2flow={"version": "2.0"},
        plan_hash="a" * 64,
    )
    revision.plan_hash = "b" * 64
    with pytest.raises(ImmutableRevisionError):
        revision.save()
```

**Step 2: Run the focused test and confirm RED**

```bash
pytest tests/interface/harness/test_models.py -v
```

Expected: import/model failures because `bkflow.harness` does not exist.

**Step 3: Implement the app and models**

Add `"bkflow.harness"` to Interface `INSTALLED_APPS` in the repository-root `module_settings.py`. Base records on `bkflow.utils.models.CommonModel`. Define explicit text choices in `constants.py`; do not reuse Engine execution statuses.

Use `PROTECT` for revision/binding/report relations and make revision rows immutable by allowing `save()` only while `self._state.adding` is true. A UUID default exists before the first insert, so checking only whether `pk` is non-null is incorrect. Do not expose a QuerySet update path for revisions. Keep JSON defaults callable.

**Step 4: Generate and inspect the migration**

```bash
python manage.py makemigrations harness
python manage.py sqlmigrate harness 0001
```

Expected: five tables, the three unique constraints above, no destructive operation.

**Step 5: Run focused tests and framework checks**

```bash
pytest tests/interface/harness/test_models.py -v
python manage.py check
python manage.py makemigrations --check
```

Expected: all pass and no pending migration.

**Step 6: Commit**

```bash
git add module_settings.py bkflow/harness tests/interface/harness/test_models.py
git commit -m "feat(harness): 新增 P0 运行与版本模型 --story=136729554"
```

## Task 3: Implement Canonical Hashing, State Transitions, and Idempotency

**Files:**

- Create: `bkflow/harness/exceptions.py`
- Create: `bkflow/harness/services/__init__.py`
- Create: `bkflow/harness/services/canonical.py`
- Create: `bkflow/harness/services/state.py`
- Create: `bkflow/harness/services/idempotency.py`
- Test: `tests/interface/harness/services/test_canonical.py`
- Test: `tests/interface/harness/services/test_state.py`
- Test: `tests/interface/harness/services/test_idempotency.py`

**Step 1: Write deterministic hash tests**

Assert that reordered object keys produce the same hash, list order remains significant, Unicode is stable, and semantically different values produce different hashes.

The canonical form is exactly:

```python
json.dumps(
    value,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
).encode("utf-8")
```

Expose `canonical_json_bytes`, `sha256_json`, `schema_hash` and `plan_hash`. All hashes are lowercase 64-character SHA-256 hex strings.

`plan_hash` must be calculated from one canonical object containing canonical a2flow, sorted CapabilityBindings with exact version and Schema hash, trusted space/scope/environment, credential references and authorization scope, plus execution/risk/retry/timeout/compensation/postcondition policies. It must exclude model name, conversation wording, display copy, token plaintext and transient trace metadata.

**Step 2: Write state-machine tests**

P0 allows only:

```text
INTENT_CAPTURED -> PLANNING -> VALIDATING
VALIDATING -> NEEDS_REPAIR
NEEDS_REPAIR -> VALIDATING
VALIDATING -> DRAFT_READY
```

These are the approved spec state names. P0 `validate_workflow` persists the validation checkpoint and leaves a valid revision eligible for draft creation; only successful `create_workflow_draft` completes `VALIDATING -> DRAFT_READY`. Reject skipping validation, mutation after `DRAFT_READY`, and every P1-P4 transition. State changes must persist atomically and emit a structured transition result.

**Step 3: Write idempotency tests**

The unique scope is:

```text
(platform_app, actor, space_id, tool_name, run_scope, idempotency_key)
```

`run_scope` is `run:<run_id>` after a run exists. On the first `validate_workflow`, it is the literal `pre-run`; caller/space/Tool/key still form a stable namespace, and the completed record stores the newly created run reference. This preserves first-write retry while ensuring every later write is scoped to its HarnessRun.

Assert:

- Same key plus same request hash returns the stored response.
- Same key plus a different request hash raises `IdempotencyConflict`.
- Same key in a different space or for a different actor is independent.
- Concurrent acquisition produces one owner and one replay, not two side effects.

**Step 4: Run tests and confirm RED**

```bash
pytest tests/interface/harness/services/test_canonical.py \
  tests/interface/harness/services/test_state.py \
  tests/interface/harness/services/test_idempotency.py -v
```

**Step 5: Implement the minimum services**

Use `transaction.atomic()` and row locking for state transition and idempotency acquisition. Store response snapshots only after the domain operation succeeds. Failed in-flight records must be retryable through an explicit failed status, never by silently overwriting a completed record.

**Step 6: Re-run tests and commit**

```bash
pytest tests/interface/harness/services/test_canonical.py \
  tests/interface/harness/services/test_state.py \
  tests/interface/harness/services/test_idempotency.py -v
git add bkflow/harness tests/interface/harness/services
git commit -m "feat(harness): 建立版本哈希状态机与幂等基础 --story=136729554"
```

## Task 4: Derive Trusted Context and Enforce AND Authorization

**Files:**

- Create: `bkflow/harness/contracts.py`
- Create: `bkflow/harness/permissions.py`
- Create: `bkflow/harness/services/context.py`
- Modify: `bkflow/space/configs.py`
- Test: `tests/interface/harness/services/test_context.py`
- Test: `tests/interface/harness/test_permissions.py`
- Modify test: `tests/interface/space/test_space_config.py`

**Step 1: Write forged-context tests**

Build requests whose body claims another app, actor, space, scope or environment. Assert `TrustedHarnessContext.from_request()` uses:

- `HarnessDeploymentConfig.platform_key` for `platform_key`.
- `request.app.bk_app_code` for `platform_app`.
- `request.user.username` for `actor`.
- the permission-checked route `space_id` and resolved `Space` for tenant boundary.
- the non-public `HarnessDeploymentConfig` for scope, environment, policy version and MCP contract version.
- request ID or generated UUID for `correlation_id`.

The body may carry user intent but must not override any identity or authority field.

**Step 2: Write AND authorization tests**

Each Harness endpoint requires all of the following:

```text
authenticated app
AND authenticated user
AND app-to-space authorization
AND user-to-space authorization
AND harness_enabled=true
```

Test every single missing predicate separately. Do not compose existing DRF permission classes with `|`; implement one Harness permission/service that evaluates the conjunction and returns stable error codes.

**Step 3: Add the space feature flag and server-side deployment binding**

Implement:

```python
class HarnessEnabledConfig(BaseSpaceConfig):
    name = "harness_enabled"
    desc = _("是否启用 AI 流程生成 Harness")
    default_value = "false"
    choices = ["true", "false"]
    control = True

    @classmethod
    def validate(cls, value: str):
        if value not in cls.choices:
            raise ValidationError("harness_enabled only supports true or false")
        return True


class HarnessDeploymentConfig(BaseSpaceConfig):
    name = "harness_deployment"
    desc = _("AI 流程生成 Harness 可信部署绑定")
    value_type = SpaceConfigValueType.JSON.value
    default_value = {}
    is_public = False
    control = True
```

`HarnessDeploymentConfig.validate()` must enforce a closed JSON Schema with required `platform_key`, `allowed_scope_types`, `scope_type`, `scope_value`, `target_environment`, `risk_policy_version`, and `mcp_contract_version`. `scope_type` and `scope_value` may both be null for space-wide generation; otherwise the selected type must be in `allowed_scope_types`. P0 requires `mcp_contract_version == "1.0.0"`. The authenticated app must equal `Space.app_code`; do not duplicate app credentials in JSON.

Default `harness_enabled=false` and empty deployment binding preserve existing spaces. Tests must cover missing config, explicit false, explicit true, invalid boolean, missing deployment keys, unknown keys, mismatched scope pairs, disallowed scope type, unsupported contract version, and valid space-wide/scoped bindings.

**Step 4: Run tests and confirm RED, then implement**

```bash
pytest tests/interface/harness/services/test_context.py \
  tests/interface/harness/test_permissions.py \
  tests/interface/space/test_space_config.py -v
```

Keep authorization errors free of space secrets and capability data.

**Step 5: Verify and commit**

```bash
pytest tests/interface/harness/services/test_context.py \
  tests/interface/harness/test_permissions.py \
  tests/interface/space/test_space_config.py -v
git add bkflow/harness bkflow/space/configs.py tests/interface
git commit -m "feat(harness): 接入可信上下文与空间鉴权 --story=136729554"
```

## Task 5: Build Capability Search Projection and Exact Schema Resolution

**Files:**

- Create: `bkflow/harness/data/capability_manifest_overrides.yaml`
- Create: `bkflow/harness/services/capability_ref.py`
- Create: `bkflow/harness/services/projection.py`
- Create: `bkflow/harness/services/resolver.py`
- Modify: `bkflow/plugin/services/plugin_schema_service.py`
- Test: `tests/interface/harness/services/test_capability_ref.py`
- Test: `tests/interface/harness/services/test_projection.py`
- Test: `tests/interface/harness/services/test_resolver.py`
- Modify test: `tests/interface/plugin/services/test_plugin_schema_service.py`

**Step 1: Write capability reference round-trip tests**

The reference format is deterministic and opaque to the Agent:

```text
cap_v1_ + urlsafe_base64(canonical_json({
  "plugin_type": "component",
  "source_key": null,
  "code": "demo_restart_service",
  "version": "1.0.0"
}))
```

Reject invalid prefix, malformed base64, missing keys, unsupported fields and decoded values that do not match the trusted-space resolver result.

**Step 2: Write search projection tests**

`search_workflow_capabilities` must return only lightweight cards:

```text
capability_ref, display_name, summary, plugin_type, resolved_version,
schema_hash, lifecycle, risk_level, side_effects, required_credentials,
matched_terms, score
```

It must not return full Schema, secrets, access tokens or unfiltered plugin metadata.

P0 ranking is deterministic: normalize query, tokenize name/alias/tag/use-case fields, filter ACL and scope before ranking, then sort by score and stable identity. `top_k` defaults to 10 and is capped at 20. Equal inputs and registry snapshots produce byte-equivalent output.

Cover exact-name, alias, Chinese token, ambiguous candidates returning `AMBIGUOUS_CAPABILITY` plus a clarification action, no-result, cross-space filtering, stable tie-breaking and `top_k=21` rejection.

**Step 3: Write exact Schema resolution tests**

Resolve `capability_ref` against `PluginSchemaService` and return `ResolvedCapability`. Assert:

- The current caller still has access in the trusted space.
- Resolved version exactly equals the reference version.
- Computed Schema hash equals the reference/current hash.
- Missing version uses the explicit `unversioned` sentinel.
- Version or Schema drift returns a typed `SCHEMA_DRIFT` error and requires the Agent to search/select again.

Do not let a client supply arbitrary raw plugin code as a substitute for a reference.

**Step 4: Add the safe metadata override manifest**

Start with a schema-valid, non-sensitive file:

```yaml
manifest_version: p0-v1
defaults:
  lifecycle: VERIFIED
  risk_level: L1
  side_effects: unknown
capabilities: []
```

The manifest may enrich aliases, tags, use cases, lifecycle and risk metadata only. Runtime plugin Registry/API remains the capability and Schema truth. Unknown or conflicting entries fail startup validation; no space ID, token or credential may be committed.

**Step 5: Run focused tests and confirm RED**

```bash
pytest tests/interface/harness/services/test_capability_ref.py \
  tests/interface/harness/services/test_projection.py \
  tests/interface/harness/services/test_resolver.py \
  tests/interface/plugin/services/test_plugin_schema_service.py -v
```

**Step 6: Implement projection and resolver**

Extend `PluginSchemaService` with an explicit resolved-version field without changing existing public response fields. Keep ranking independent of the database backend so Golden Cases can run on fixtures.

**Step 7: Verify legacy compatibility and commit**

```bash
pytest tests/interface/harness/services/test_capability_ref.py \
  tests/interface/harness/services/test_projection.py \
  tests/interface/harness/services/test_resolver.py \
  tests/interface/plugin/services/test_plugin_schema_service.py \
  tests/interface/apigw/test_list_plugins.py \
  tests/interface/apigw/test_get_plugin_schema.py -v
git add bkflow/harness bkflow/plugin/services/plugin_schema_service.py tests/interface
git commit -m "feat(harness): 增加能力检索投影与精确 Schema 绑定 --story=136729554"
```

## Task 6: Implement Deterministic Workflow Validation and Immutable Revisions

**Files:**

- Create: `bkflow/harness/services/validator.py`
- Modify: `bkflow/pipeline_converter/converters/a2flow_v2/converter.py`
- Modify: `bkflow/pipeline_converter/converters/a2flow_v2/data_models.py`
- Test: `tests/interface/harness/services/test_validator.py`
- Modify test: `tests/interface/pipeline_converter/test_converter.py`

**Step 1: Write validation contract tests**

The Tool request contains user intent, a2flow V2, per-node bindings and an idempotency key. Each node binding is exactly:

```python
{
    "node_id": "node_1",
    "capability_ref": "cap_v1_eyJjb2RlIjoiZGVtb19yZXN0YXJ0X3NlcnZpY2UiLCJwbHVnaW5fdHlwZSI6ImNvbXBvbmVudCIsInNvdXJjZV9rZXkiOm51bGwsInZlcnNpb24iOiIxLjAuMCJ9",
    "schema_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "credential_ref": None,
}
```

Assert `validate_workflow` performs these checks in order:

1. Derive trusted context and enforce authorization.
2. Acquire idempotency scope.
3. Resolve every capability reference in the trusted space.
4. Reject duplicate/missing/extra node bindings.
5. Verify exact version and Schema hash.
6. Validate node inputs against the resolved Schema.
7. Convert a2flow V2 to pipeline tree.
8. Run existing pipeline-tree validation.
9. Canonicalize the accepted input and create a new immutable revision.
10. Persist bindings and a validation report containing validator version, converter fingerprint and pipeline-tree hash; return the standard Envelope.

On first validation, create the `HarnessRun` implicitly when the Spike selected `validate_workflow_implicit`. A failed validation may create a run and a report, but must not create a valid revision or draft.

**Step 2: Test bounded repair semantics**

A corrected request creates a new revision and never mutates a previous accepted revision. Set `parent_revision_id` when an accepted parent exists; an initial failed attempt has only a run-level ValidationReport with `revision=None`, so its first accepted revision has no parent. The response must identify actionable paths such as `nodes.node_1.inputs.host` and typed codes such as:

```text
CAPABILITY_NOT_FOUND
CAPABILITY_FORBIDDEN
SCHEMA_DRIFT
SCHEMA_VALIDATION_ERROR
A2FLOW_CONVERSION_ERROR
PIPELINE_VALIDATION_ERROR
PLAN_HASH_MISMATCH
```

The server computes `plan_hash`; a client-provided hash is only an optimistic concurrency assertion.

**Step 3: Add converter metadata without changing legacy conversion**

If the current converter cannot report source mapping, add:

```python
@dataclass(frozen=True)
class ConversionResult:
    pipeline_tree: Dict[str, Any]
    converter_fingerprint: str
    source_map: Dict[str, str]
```

Add the method signature `def convert_with_metadata(self) -> ConversionResult` to `A2FlowV2Converter`; its body must execute the same conversion path as `.convert()` and capture the resulting metadata.

Existing `.convert()` must still return only the pipeline tree and preserve all legacy tests.

**Step 4: Run tests and confirm RED**

```bash
pytest tests/interface/harness/services/test_validator.py \
  tests/interface/pipeline_converter/test_converter.py \
  tests/interface/apigw/test_validate_a2flow.py -v
```

**Step 5: Implement and verify**

Use one database transaction for revision, bindings and validation report. Do not persist raw credentials or full authenticated headers. The Evidence artifact references include validator version, converter fingerprint, pipeline-tree hash and report ID.

```bash
pytest tests/interface/harness/services/test_validator.py \
  tests/interface/pipeline_converter/test_converter.py \
  tests/interface/apigw/test_validate_a2flow.py -v
```

**Step 6: Commit**

```bash
git add bkflow/harness bkflow/pipeline_converter tests/interface
git commit -m "feat(harness): 增加确定性流程校验与不可变修订 --story=136729554"
```

## Task 7: Extract Template Creation and Implement Draft-Only Creation

**Files:**

- Create: `bkflow/template/services/__init__.py`
- Create: `bkflow/template/services/a2flow_template.py`
- Modify: `bkflow/apigw/views/create_template_with_a2flow.py`
- Create: `bkflow/harness/services/draft.py`
- Test: `tests/interface/template/services/test_a2flow_template.py`
- Test: `tests/interface/harness/services/test_draft.py`
- Modify test: `tests/interface/apigw/test_create_template_with_a2flow.py`

**Step 1: Characterize the existing API before extraction**

Add tests that freeze existing behavior for valid creation, invalid a2flow, scope binding, app binding and current `auto_release` behavior. Run:

```bash
pytest tests/interface/apigw/test_create_template_with_a2flow.py -v
```

Expected: characterization tests pass against the pre-extraction implementation.

**Step 2: Define the reusable service contract**

Implement exactly:

```python
def create_template_from_a2flow(
    *,
    space_id: int,
    username: str,
    a2flow: dict,
    scope_type: Optional[str],
    scope_value: Optional[str],
    bind_app_code: str,
    auto_release: bool = False,
) -> Template


def update_template_draft_from_a2flow(
    *,
    template: Template,
    username: str,
    a2flow: dict,
    expected_space_id: int,
    expected_bind_app_code: str,
) -> TemplateSnapshot
```

Move the domain creation logic from the view into this service. The update helper must verify template ownership, space and bound app before calling the existing `Template.update_draft_snapshot()` path. Keep serializer/request handling and response adaptation in the legacy view.

**Step 3: Write Harness draft tests**

`create_workflow_draft` accepts only a previously validated `run_id`, `revision_id`, exact `plan_hash`, and idempotency key. Assert:

- `auto_release` is always false, even if the model sends true.
- `bind_app_code` always comes from `TrustedHarnessContext.platform_app`.
- Caller, space and revision must match the stored run.
- Stale revision or plan hash is rejected.
- Same idempotency retry returns the same template ID.
- A later validated revision for the same HarnessRun updates the existing managed template draft exactly once and keeps the same template ID.
- A draft cannot be created while the run is `NEEDS_REPAIR` or without a valid latest revision.
- The successful run status becomes `DRAFT_READY`, not `PUBLISHED` or `EXECUTING`.

**Step 4: Implement the draft service**

Before any template write, re-resolve every stored CapabilityBinding, recompute Schema hashes and `plan_hash`, and re-run conversion/validation against the stored canonical a2flow. Compare validator version, converter fingerprint and pipeline-tree hash with the accepted ValidationReport; if they changed, return `VALIDATION_STALE` and require `validate_workflow` to create a new revision.

For the first accepted revision, call `create_template_from_a2flow` with the stored canonical a2flow. For later accepted revisions of the same HarnessRun, call `update_template_draft_from_a2flow` on the previously recorded managed template. Never accept a second a2flow body, switch template ownership, or create one template per repair revision. Store only template/draft references in Harness artifacts. Never call debug, release or execution services.

**Step 5: Run compatibility tests**

```bash
pytest tests/interface/template/services/test_a2flow_template.py \
  tests/interface/harness/services/test_draft.py \
  tests/interface/apigw/test_create_template_with_a2flow.py -v
```

Expected: legacy and Harness behavior both pass.

**Step 6: Commit**

```bash
git add bkflow/template/services bkflow/apigw/views/create_template_with_a2flow.py \
  bkflow/harness/services/draft.py tests/interface
git commit -m "feat(harness): 复用 a2flow 创建服务并限制为草稿 --story=136729554"
```

## Task 8: Expose the Four P0 Facade and APIGW Operations

**Files:**

- Create: `bkflow/harness/services/facade.py`
- Create: `bkflow/apigw/serializers/harness/__init__.py`
- Create: `bkflow/apigw/serializers/harness/common.py`
- Create: `bkflow/apigw/serializers/harness/capabilities.py`
- Create: `bkflow/apigw/serializers/harness/workflow.py`
- Create: `bkflow/apigw/views/harness/__init__.py`
- Create: `bkflow/apigw/views/harness/capabilities.py`
- Create: `bkflow/apigw/views/harness/workflow.py`
- Modify: `bkflow/apigw/urls.py`
- Test: `tests/interface/harness/services/test_facade.py`
- Create: `tests/interface/apigw/test_harness_p0.py`

**Step 1: Freeze Tool-to-operation mapping**

```python
HARNESS_CONTRACT_VERSION = "1.0.0"

P0_TOOL_OPERATION_MAP = {
    "search_workflow_capabilities": "harness_search_workflow_capabilities",
    "get_plugin_schema": "harness_get_plugin_schema",
    "validate_workflow": "harness_validate_workflow",
    "create_workflow_draft": "harness_create_workflow_draft",
}
```

The APIGW operation IDs are prefixed to avoid collisions with existing APIs; the BKAIDev MCP-visible names remain the four approved names.

**Step 2: Write common Envelope serializer tests**

The common request contract supports `run_id` (optional on first write), `revision_id` (required after plan creation), `idempotency_key` (required on writes), `expected_plan_hash` (required for draft creation), and opaque non-secret `client_context.conversation_ref` plus `client_context.agent_release`. Identity and authority fields are not part of this contract.

All success and error responses expose exactly:

```text
ok, run_id, revision_id, plan_hash, status, summary, artifact_refs,
errors, next_actions, correlation_id
```

Error entries contain `category`, stable granular `code`, message, optional path, `repairable`, suggested action and `retryable`. Freeze the category enum to `USER_INPUT`, `CAPABILITY_NOT_FOUND`, `AMBIGUOUS_CAPABILITY`, `SCHEMA_DRIFT`, `VALIDATION`, `PERMISSION`, `APPROVAL_REQUIRED`, `APPROVAL_INVALID`, `TOKEN_LEASE`, `DEBUG_CONFLICT`, `RUNTIME`, `POSTCONDITION`, and `RETRYABLE_INFRA`; P0 exercises only its applicable subset, while later phases reuse the contract version. Errors must not contain tracebacks, tokens, credential bodies or plugin secrets.

**Step 3: Write four endpoint tests**

Routes:

```text
POST /space/{space_id}/harness/search_workflow_capabilities/
POST /space/{space_id}/harness/get_plugin_schema/
POST /space/{space_id}/harness/validate_workflow/
POST /space/{space_id}/harness/create_workflow_draft/
```

Assert each view only validates transport input, derives trusted context, calls the matching `HarnessFacade` method and serializes its result. Domain branches belong in Harness services.

Test valid requests, malformed requests, disabled flag, unauthorized app, unauthorized user, forged body identity, cross-space run ID, Schema drift, stale plan hash, and idempotent retry.

**Step 4: Run tests and confirm RED**

```bash
pytest tests/interface/harness/services/test_facade.py \
  tests/interface/apigw/test_harness_p0.py -v
```

**Step 5: Implement the facade and views**

`HarnessFacade` has exactly these public methods:

```python
search_workflow_capabilities(context, request)
get_plugin_schema(context, request)
validate_workflow(context, request)
create_workflow_draft(context, request)
```

P0 risk mapping:

```python
P0_ACTION_RISK = {
    "search_workflow_capabilities": "L0",
    "get_plugin_schema": "L0",
    "validate_workflow": "L0",
    "create_workflow_draft": "L1",
}
```

The facade must emit structured audit data for caller, space, Tool, risk, result, duration, run/revision and correlation ID, while redacting request secrets.

**Step 6: Verify and commit**

```bash
pytest tests/interface/harness/services/test_facade.py \
  tests/interface/apigw/test_harness_p0.py -v
git add bkflow/harness bkflow/apigw/serializers/harness \
  bkflow/apigw/views/harness bkflow/apigw/urls.py tests/interface
git commit -m "feat(harness): 暴露四个 P0 控制接口 --story=136729554"
```

## Task 9: Synchronize APIGW Resources and Configure the BKAIDev Agent Loop

**Files:**

- Modify: `bkflow/apigw/management/commands/data/api-resources.yml`
- Create: `bkflow/apigw/docs/zh/harness_search_workflow_capabilities.md`
- Create: `bkflow/apigw/docs/zh/harness_get_plugin_schema.md`
- Create: `bkflow/apigw/docs/zh/harness_validate_workflow.md`
- Create: `bkflow/apigw/docs/zh/harness_create_workflow_draft.md`
- Generated: `bkflow/apigw/docs/apigw-docs.zip`
- Modify: `docs/reviews/2026-09-01-bkaidev-harness-p0-spike.md`
- Test: `tests/interface/apigw/test_harness_resource_contract.py`

**Step 1: Write APIGW resource contract tests**

Assert the four operation IDs exist once, route/method match Task 8, and each resource has:

```yaml
backend:
  name: default
authConfig:
  appVerifiedRequired: true
  userVerifiedRequired: true
  resourcePermissionRequired: true
```

The test must also assert each operation has a matching Chinese Markdown document and the zip contains all four paths.

**Step 2: Add resources and full request/response docs**

Document:

- Trusted versus untrusted request fields.
- Stable Envelope and typed errors.
- Exact P0 Tool boundary.
- Version/hash/idempotency requirements.
- Draft-only guarantee.
- Example Tool inputs that contain no real token, secret, space ID or credential.

**Step 3: Regenerate the documentation archive**

```bash
bash scripts/apigw_docs.sh
```

Inspect changed archive entries:

```bash
unzip -l bkflow/apigw/docs/apigw-docs.zip | rg "harness_(search|get|validate|create)"
```

Expected: four Harness documents appear.

**Step 4: Record the BKAIDev configuration contract**

Append exact, sanitized configuration evidence to the Spike review:

- One BKAIDev SaaS-native Agent; no Agent SDK or second runtime.
- One logical connection name: `BKFlow Workflow Harness MCP`.
- Four MCP-visible Tool names mapped to four prefixed APIGW operations.
- Per-platform connection owns endpoint, app identity and space/scope/environment binding.
- P0 fixed knowledge bases are mounted read-only in BKAIDev and their source/version snapshot is recorded; BKFlow does not implement Knowledge Router before P1.
- The Agent Release record pins prompt version, model version, MCP contract `1.0.0`, Tool allowlist and fixed-knowledge snapshot.
- Agent prompt loop:

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

The prompt must explicitly forbid a second Agent, an autonomous MCP loop, direct plugin execution, debug, release and real execution in P0. Configure `harness_enabled` only for pilot spaces and verify higher-phase Tools are absent rather than merely hidden by prompt wording.

**Step 5: Run resource tests**

```bash
pytest tests/interface/apigw/test_harness_resource_contract.py -v
```

**Step 6: Commit**

```bash
git add bkflow/apigw/management/commands/data/api-resources.yml \
  bkflow/apigw/docs docs/reviews/2026-09-01-bkaidev-harness-p0-spike.md \
  tests/interface/apigw/test_harness_resource_contract.py
git commit -m "docs(apigw): 同步 Harness P0 资源与 BKAIDev 配置 --story=136729554"
```

## Task 10: Add Golden Cases, Security Negatives, and the P0 Release Gate

**Files:**

- Create: `tests/fixtures/harness/golden_cases.yaml`
- Create: `tests/interface/harness/test_golden_cases.py`
- Create: `tests/interface/harness/test_security_boundaries.py`
- Create: `docs/reviews/2026-09-01-bkaidev-harness-p0-verification.md`

**Step 1: Create exactly 30 versioned Golden Cases**

The fixture contains these exact groups:

| Group | Count | Expected outcome |
|---|---:|---|
| `positive_selection` | 8 | deterministic candidate and valid revision |
| `ambiguous_requires_clarification` | 6 | no arbitrary winner; clarification action |
| `zero_candidate` | 4 | empty result with recovery guidance |
| `schema_validation_error` | 4 | typed path-level errors |
| `schema_drift` | 3 | re-search required |
| `idempotent_draft_retry` | 3 | one draft resource |
| `forged_identity_rejected` | 2 | trusted context wins or request denied |
| **Total** | **30** | |

Every case pins registry snapshot, expected Tool sequence, expected capability/version/hash, expected final state and forbidden side effects.

**Step 2: Add explicit security boundary tests**

Cover:

- Cross-space capability, run, revision and draft access.
- Forged app/user/space/scope/environment body fields.
- Credential/token-shaped fields in logs and response errors.
- Full Schema leakage from search results.
- Direct plugin execution attempts.
- `auto_release=true`, publish/debug/execute fields in P0 requests.
- Concurrent duplicate draft requests.
- Schema changes between search, fetch and validation.

Expected invariant counters:

```text
cross_space_leak = 0
secret_or_token_exposure = 0
duplicate_drafts = 0
silent_schema_drift = 0
published_templates = 0
created_tasks = 0
real_executions = 0
```

**Step 3: Run the complete focused regression suite**

```bash
pytest tests/interface/harness \
  tests/interface/apigw/test_harness_p0.py \
  tests/interface/apigw/test_harness_resource_contract.py \
  tests/interface/apigw/test_list_plugins.py \
  tests/interface/apigw/test_get_plugin_schema.py \
  tests/interface/apigw/test_validate_a2flow.py \
  tests/interface/apigw/test_create_template_with_a2flow.py \
  tests/interface/plugin/services/test_plugin_schema_service.py -v
```

Expected: all pass, all 30 Golden Cases executed, no xfail for a P0 acceptance condition.

**Step 4: Run style, framework, migration and patch checks**

```bash
black --check bkflow/harness bkflow/template/services \
  bkflow/apigw/serializers/harness bkflow/apigw/views/harness tests/interface/harness
flake8 bkflow/harness bkflow/template/services \
  bkflow/apigw/serializers/harness bkflow/apigw/views/harness tests/interface/harness
python manage.py check
python manage.py makemigrations --check
git diff --check
```

Expected: all exit zero.

**Step 5: Run the on-demand Schema comparison in BKAIDev**

Using the same pinned Agent Release and a representative subset of the Golden Cases, compare:

```text
baseline = preload full Schema for all pilot capabilities
candidate = search lightweight cards, then load only selected exact Schemas
```

Record per case: selected capability accuracy, clarification/stop correctness, Schema count loaded, prompt-context size, Tool round trips, latency, token usage if BKAIDev exposes it, and final validation outcome. The candidate passes only if it preserves or improves correctness and materially reduces Schema/context loading; report measured data rather than a target invented after the run.

**Step 6: Execute the pilot capability verification**

Against a non-production pilot space with `harness_enabled=true`, resolve 10-20 representative runtime capabilities. Record sanitized evidence in the verification review:

- Query and candidate order.
- Exact resolved version and Schema hash.
- One positive validation and draft.
- One ambiguous query.
- One zero-result query.
- One intentional Schema-drift rejection.
- One idempotent draft retry.

The committed override manifest may remain free of sensitive space IDs. Pilot evidence must identify the tested environment and code SHA without including access tokens or full credential payloads.

**Step 7: Complete the P0 gate checklist**

The review can say PASS only when:

- One logical MCP is configured.
- Exactly four P0 Tools are visible.
- Trusted app/user/space/scope/environment attribution is correct.
- All 30 Golden Cases pass.
- The BKAIDev on-demand Schema comparison has recorded baseline and candidate evidence with no correctness regression.
- 10-20 pilot capabilities resolve exact version/hash.
- Every invariant counter in Step 2 is zero.
- P0 has created no published template, task or real execution.

A failed item keeps the phase incomplete; document the blocker and evidence rather than weakening the gate.

**Step 8: Commit**

```bash
git add tests/fixtures/harness tests/interface/harness \
  docs/reviews/2026-09-01-bkaidev-harness-p0-verification.md
git commit -m "test(harness): 建立 P0 Golden Cases 与发布门禁 --story=136729554"
```

## Spec Coverage Matrix

| Approved spec concern | Planned evidence |
|---|---|
| BKAIDev SaaS native single Agent and one logical MCP | Task 1 probes; Task 9 pinned Agent Release |
| 15 stable control Tools and phased allowlist | Phase budget; Task 8 P0 map; follow-up boundaries |
| Tool Search applies to business capabilities, not control Tools | Global constraints; Task 5 projection; Task 10 comparison |
| Trusted platform/app/user/space/scope/environment | Task 4; Task 8 negative API tests |
| Interface-owned run/revision/evidence state; no Engine conversation state | Global constraints; Tasks 2, 3 and 6 |
| Exact capability version, Schema hash and drift rejection | Tasks 3, 5, 6 and 7 |
| Unified Envelope, error taxonomy, idempotency and audit | Tasks 3 and 8 |
| P0 fixed knowledge only; federated Router deferred | Task 9; P1 boundary |
| Single-step/global debug and Token Broker | Explicitly excluded from P0; fixed P2 Tool and plan boundary |
| Approval, publish and application execution | Explicitly excluded from P0; fixed P3 Tool and plan boundary |
| Evidence feedback loop | P0 validation/audit evidence; full feedback fixed to P4 |
| P0 Golden Cases, capability pilot and no forbidden side effects | Task 10 release gate |

## P0 Completion Evidence

Implementation is complete only when the executor attaches all of the following to the verification review:

1. Task 1 Spike decisions and reproducible evidence.
2. Git SHA and exact test commands/output summaries.
3. Four APIGW operation IDs and four MCP-visible Tool names.
4. Migration check and generated migration name.
5. Golden Case group counts totaling 30.
6. Pilot capability count between 10 and 20.
7. BKAIDev Agent Release evidence pinning prompt/model/MCP/Tool allowlist/fixed-knowledge snapshot.
8. Baseline-versus-on-demand Schema comparison results.
9. Zero values for all forbidden-side-effect/security counters.
10. One successful draft ID proving idempotent replay returns the same resource.
11. Confirmation that P1 knowledge routing, P2 debug/Token Broker, P3 release/execution and P4 feedback are not implemented by P0.

## Follow-up Plan Boundaries

After P0 gate passes, create separate plans in this order:

1. P1: `search_workflow_knowledge`, federated Knowledge Router, global/space/business sources, citations, freshness and feedback ingestion.
2. P2: `start_debug_session`, `run_debug`, `get_debug_session`, `control_debug_session`; single-step and global debug; platform-owned Token Broker for `sdk_xxx` prerequisites.
3. P3: `prepare_release`, `publish_workflow`, `start_workflow_execution`, `get_workflow_execution`, `control_workflow_execution`; approval and runtime Evidence.
4. P4: `submit_generation_feedback`; outcome-to-knowledge and evaluation closure.

Each follow-up must reuse P0 trusted context, immutable revision, exact capability binding, state transition, idempotency and Envelope contracts. Do not reopen those contracts without a versioned migration and a spec change.
