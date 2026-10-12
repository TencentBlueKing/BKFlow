# BKAIDev a2flow Harness P1 verification gate

## Status and evidence identity

Overall status: **`P1_RELEASE_GATE_BLOCKED_BY_PROVIDER_EVIDENCE`**. The P1
provider-SPI implementation and local regression gate are complete, but this is
not an external-provider or BKAIDev release-readiness declaration.

The historical implementation predecessor for Task 8 is
`95d76db06ce77e65af447fbf3d58948cdf374353`; the initial Task 8 implementation
commit is `2efd426dc6b3a1da0a715a429e4525e8e1039cc5`, and the exact-snapshot follow-up
is `02dfc4e11d25f1e3acd43843ae84a373cbb14f06`. The verified predecessor for the
current fair return-path follow-up is
`c686a898c3665f0d1cbd8472a7f4ce323e1ca2e8`. The latest results below were
obtained in the current worktree containing that predecessor plus the
generation-based wakeup implementation, tests, and verification-document diff.
The follow-up commit cannot embed its own SHA without a self-hash paradox;
review its scoped diff to confirm those changes.

All commands below ran in the isolated `ai/a2flow-harness-p1` worktree with the
repository Python 3.9 virtual environment and ignored SQLite `local_settings.py`.
`PASS_LOCAL` never means external provider, BKAIDev, MySQL/PostgreSQL, staging,
or pilot acceptance.

## Fixed 36-case retrieval corpus

Fixture `harness-p1-knowledge-golden-v1`, schema version `2`, contains exactly:

| Group | Count | Primary boundary |
| --- | ---: | --- |
| `global_public_common` | 6 | Global/Public visibility and Global preservation |
| `platform_specific` | 6 | matching platform and mismatched-platform denial |
| `space_private` | 6 | matching space and cross-space pre-filtering |
| `scope_private` | 6 | Scope > Space > Public and mismatched-Scope denial |
| `conflict_precedence` | 4 | specificity, Global policy validation, deterministic precedence |
| `expired_or_retired` | 3 | expiry/lifecycle denial before provider calls |
| `cross_space_denied` | 3 | zero provider calls and zero citations |
| `malicious_instruction` | 2 | advisory-only prompt-injection containment |
| **Total** | **36** | |

Every case pins a complete `TrustedHarnessContext`, query/classification/top-k,
binding definitions, eligible and forbidden source IDs, external-provider
snapshot, expected citations, conflict annotations, errors and Tool result.
The v2 expected-source catalog freezes every normalized hit field: title,
excerpt, citation/source/hit/content-snapshot refs, tier, provider, trust,
applicable scope, provider/final score, expiry and `ADVISORY` policy effect.
Each case also freezes query fingerprint, complete conflict refs/resolution,
warnings/errors/artifact refs, semantic audit hit/snapshot/provider outcomes,
and the complete ten-key Facade Envelope. The audit literal additionally pins
the full trusted-context snapshot and an explicit `run_id: null` for every
current case.

The runner creates real `KnowledgeSourceBinding` rows and executes unmodified
`HarnessFacade.search_workflow_knowledge -> eligible_bindings ->
KnowledgeProviderRegistry -> KnowledgeRouter -> KnowledgeRetrievalAudit`; only
the external provider response is replaced by a deterministic test double.
Runtime database IDs are normalized to fixture source IDs; dynamic duration and
the call digest that contains a runtime primary key are excluded. All remaining
values are compared to independent literals. Audit normalization reads the
persisted `eligible_binding_ids` and reverses the complete runtime-ID map; it
does not reconstruct IDs from fixture eligibility. Unknown, duplicate, missing
or reordered binding IDs and extra, missing or reordered provider summaries
all fail. Dynamic `duration_ms` and `call_ref` are limited to range, URI format
and uniqueness checks; all stable summary fields remain literal. The test
imports no production digest, scoring, conflict or merge helper to construct
expected values.

Initial RED evidence: before the corpus existed, the new runner collected 37
tests and failed all 37 with the expected missing `knowledge_cases.yaml` error.
Snapshot-hardening RED evidence: the follow-up runner collected 41 tests and
failed all 41 because schema v1 lacked the required literal source catalog and
per-case semantic snapshots.
Audit-identity RED evidence: after the audit comparator began reading the
persisted identity/context/run facts, 37 case/schema tests failed and nine
existing mutation tests passed because the v2 audit literals had not yet added
`trusted_context_snapshot` and `run_id`.

GREEN command and result:

```bash
pytest tests/interface/harness/knowledge/test_golden_cases.py \
  -q --disable-warnings --no-cov
```

Result: **50 passed in 2.62s** (36 real Facade case executions, one exact
schema/count/unique-ID guard, four expected-snapshot mutation tests, and nine
actual-audit mutation tests). The first mutation set independently changes
expected citation, content snapshot, excerpt and conflict topic while retaining
source ordering. The second mutates actual eligible IDs (empty, reordered,
unknown, duplicate), provider summaries (extra, missing, reordered), trusted
context and run attachment. Every mutation is required to trigger failure.

## Security and authority boundaries

The Task 8 security suite measures behavior through real binding eligibility,
Provider registry, Router, Facade Envelope and retrieval-audit persistence:

- cross-space, mismatched-Scope, expired and retired bindings make exactly zero
  provider calls and never enter eligible binding audit IDs;
- malicious knowledge stays `policy_effect=ADVISORY`, cannot change contract
  Tool sets, L0/L1 risk policy, Validator/draft entrypoints, provider-call order,
  or specificity ordering;
- query, provider exception/content, credential reference and provider-config
  sentinels do not occur in response, artifact, audit serialization or captured
  logs; content citations and snapshots are replaced by opaque digests;
- timeout exception text is normalized to `RETRYABLE_INFRA` and is not
  reflected across the Facade boundary;
- contract `1.0.0` remains exactly four Tools and `1.1.0` remains exactly five.

```bash
pytest tests/interface/harness/knowledge/test_golden_cases.py \
  tests/interface/harness/knowledge/test_security_boundaries.py \
  -q -rs --disable-warnings --no-cov
```

Result: **63 passed in 3.13s**. The security file contributes 13 tests after
parameter expansion; the secret assertions scan observed result/Envelope,
artifact, audit and log values rather than the fixture itself.

## Full local P1 gate

```bash
pytest tests/interface/harness \
  tests/interface/apigw/test_harness_p0.py \
  tests/interface/apigw/test_harness_p1.py \
  tests/interface/apigw/test_harness_resource_contract.py \
  -q -rs --disable-warnings --no-cov
```

Result: **791 passed, 8 skipped in 12.52s**. There were no xfails. The eight
skips are inherited SQLite limitations and must not be represented as
MySQL/PostgreSQL evidence:

| File / boundary | Count | Not proved by SQLite |
| --- | ---: | --- |
| `tests/interface/harness/test_security_boundaries.py` | 1 | public-draft two-connection row lock |
| `tests/interface/harness/services/test_idempotency.py` | 2 | two-connection idempotency ownership/retry lock |
| `tests/interface/harness/services/test_validator_concurrency.py` | 5 | whole-run validation serialization |
| **Total** | **8** | real production-database lock semantics |

The aggregate includes all P0 and P1 Harness tests, the four P0 public routes,
the P1 route, and the APIGW resource/archive contract. Disabling the P1 flag is
covered by the real feature-gate tests while the complete P0 Harness suite stays
green; this is local repository isolation, not a BKAIDev connection readback.

The Provider registry contributes **26 passed in 0.21s**. Its focused
concurrency subset contributes **5 passed in 0.18s** with unhandled pytest
thread warnings promoted to errors. The added return-path case proves that,
after batch A yields one of two slots to waiting request B, B's completion wakes
A and lets A submit its remaining source while A's other provider call remains
blocked. The generation check and slot transition share one Condition, so the
retry cannot lose the release wakeup. Timeout waiter cleanup and close races
complete without a queue-removal exception or deadlock.

## Repository, migration, and APIGW structure

Commands and observed results:

```bash
python manage.py check
python manage.py makemigrations harness --check --dry-run
git diff --check
unzip -t bkflow/apigw/docs/apigw-docs.zip
```

- `manage.py check` exits 0 with the pre-existing
  `label.Label.label_scope` callable-default warning and the local naive
  `Token.expired_time` runtime warning.
- Harness migration check exits 0 with **No changes detected in app
  'harness'**. The chain is `0001 -> 0002 ->
  0003_capabilitybinding_conversion_fingerprint ->
  0004_p1_knowledge_router`; no migration was authored by Task 8.
- `git diff --check` exits 0.
- the APIGW archive integrity check exits 0 and contains all five Harness
  Chinese documents, including `harness_search_workflow_knowledge.md`.
- structural YAML parsing observes **105 paths, 107 operations, five Harness
  operation IDs**. The Harness IDs are the P0 four plus exactly
  `harness_search_workflow_knowledge`.

The complete Envelope byte budget, YAML authentication flags, route/view
mapping, and byte-for-byte Chinese-document/archive consistency are enforced by
`test_harness_p1.py` and `test_harness_resource_contract.py` inside the
791-pass gate.

## External provider probe and BKAIDev release status

No real provider endpoint/credential/configuration, BKAIDev Agent Release,
staging space, or production database was available to Task 8. Therefore the
six frozen provider probes retain these exact statuses:

| Probe | Status | Missing external evidence |
| --- | --- | --- |
| SP-P1-01 service authentication | `NOT_RUN_EXTERNAL / BLOCKED` | authenticated request/response and provider request ID |
| SP-P1-02 source/citation stability | `NOT_RUN_EXTERNAL / BLOCKED` | repeated provider response and stable source/chunk evidence |
| SP-P1-03 snapshot/version | `NOT_RUN_EXTERNAL / BLOCKED` | immutable native corpus revision or reviewed digest input |
| SP-P1-04 ACL/caller attribution | `NOT_RUN_EXTERNAL / BLOCKED` | allowed/denied traces with app/actor/space attribution |
| SP-P1-05 limits/timeout | `NOT_RUN_EXTERNAL / BLOCKED` | measured provider top-k/bytes/latency behavior |
| SP-P1-06 classification/redaction | `NOT_RUN_EXTERNAL / BLOCKED` | provider-side classification and sanitized capture |

Likewise, a real BKAIDev `1.1.0` connection exposing exactly five Tools and a
parallel `1.0.0` connection exposing exactly four are
**`NOT_RUN_EXTERNAL / BLOCKED`**. Repository snapshots prove the intended
contract only. Real MySQL and PostgreSQL migration/concurrency execution is
**`NOT_RUN_EXTERNAL / BLOCKED`**; SQLite schema/tests cannot clear it.

## Gate decision

| Gate | Status |
| --- | --- |
| 36 exact Golden snapshots through real Facade/ACL/Registry/Router/Audit | `PASS_LOCAL` |
| cross-space/lifecycle zero calls and prompt-injection containment | `PASS_LOCAL` |
| secret and timeout non-reflection across result/audit/log | `PASS_LOCAL` |
| contract `1.0.0` four Tools / `1.1.0` five Tools | `PASS_LOCAL` |
| 107 APIGW operations and five Harness resources/documents | `PASS_LOCAL` |
| Harness migration/system/diff checks | `PASS_LOCAL` |
| six authenticated provider probes | `NOT_RUN_EXTERNAL / BLOCKED` |
| BKAIDev five-Tool/legacy four-Tool connection readback | `NOT_RUN_EXTERNAL / BLOCKED` |
| MySQL/PostgreSQL migration and row-lock evidence | `NOT_RUN_EXTERNAL / BLOCKED` |
| **P1 release** | **`P1_RELEASE_GATE_BLOCKED_BY_PROVIDER_EVIDENCE`** |

P2 may consume locally proven `KnowledgeHit` citations as read-only advisory
context. It must not treat them as a permission, current capability fact,
Validator result, Tool instruction, or production-provider readiness signal.
