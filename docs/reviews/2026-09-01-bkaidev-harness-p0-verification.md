# BKAIDev A2Flow Harness P0 verification gate

## Status and evidence identity

Overall status: **`BLOCKED_BY_EXTERNAL_EVIDENCE`**. This document is not a
release-ready declaration.

The implementation and tests recorded here were run at exact Git SHA
`0f4b8ebd38588d30e1476c18c9081e7e37cffa7f`. The following verification-doc
commit updates this document only. Its own SHA cannot be embedded in itself;
this avoids a self-hash paradox. Review that following commit's diff to confirm
that it changes this document only. All successful local items below mean
`PASS_LOCAL`, never deployed or pilot proof.

## P0 repository contract

| MCP-visible Tool | APIGW operation ID | Risk | P0 behavior |
| --- | --- | --- | --- |
| `search_workflow_capabilities` | `harness_search_workflow_capabilities` | L0 | Governed lightweight cards only |
| `get_plugin_schema` | `harness_get_plugin_schema` | L0 | Exact selected ref, version and Schema hash |
| `validate_workflow` | `harness_validate_workflow` | L0 | Trusted context, fresh resolution and immutable validation evidence |
| `create_workflow_draft` | `harness_create_workflow_draft` | L1 | One managed draft only; no release, debug, task or execution |

Repository route, Facade map, APIGW YAML and archived documentation checks find
exactly these four Harness operations. This is repository evidence only;
actual BKAIDev Tool visibility remains `NOT_RUN_EXTERNAL`.

## Exact local commands and results

The commands used the local repository's `.env` and
`.venv/bin/pytest`, resolved from the repository root.

### Golden Cases

```bash
pytest tests/interface/harness/test_golden_cases.py \
  -q --disable-warnings --no-cov
```

Result: **34 passed**. This is 30 parametrized Golden Cases plus four fixture,
catalog and real-service structural/provider-boundary tests.

### Security boundaries

```bash
pytest tests/interface/harness/test_security_boundaries.py \
  -q -rs --disable-warnings --no-cov
```

Result: **38 passed, 1 skipped**. The single skip is the two-connection public
draft lock-contention proof on SQLite; the public serial same-key exact-once
test still runs and passes locally.

### Task 10 focused aggregate

```bash
pytest tests/interface/harness \
  tests/interface/apigw/test_harness_p0.py \
  tests/interface/apigw/test_harness_resource_contract.py \
  tests/interface/apigw/test_list_plugins.py \
  tests/interface/apigw/test_get_plugin_schema.py \
  tests/interface/apigw/test_validate_a2flow.py \
  tests/interface/apigw/test_create_template_with_a2flow.py \
  tests/interface/plugin/services/test_plugin_schema_service.py \
  -q -rs --disable-warnings --no-cov
```

Result: **471 passed, 8 skipped**. There were **no xfails**. All eight skips are
explicit SQLite row-lock limitations:

| File / class or test | Count | What remains unproved on SQLite |
| --- | ---: | --- |
| `tests/interface/harness/services/test_idempotency.py::TestIdempotencyRowLockConcurrency` | 2 | Task 3 two-connection ownership/retry locking |
| `tests/interface/harness/services/test_validator_concurrency.py::TestWorkflowValidatorTwoConnectionTransactions` | 5 | Task 6 whole-run `select_for_update` serialization |
| `tests/interface/harness/test_security_boundaries.py::test_two_public_draft_connections_lock_then_replay_one_real_resource` | 1 | Task 10 public draft contention at the real lock SQL boundary |

The eight test definitions remain collected. They require a database with real
`select_for_update` semantics and are not presented as MySQL/PostgreSQL proof.

### APIGW resource and archived-document contract

```bash
pytest tests/interface/apigw/test_harness_resource_contract.py \
  -q --disable-warnings --no-cov
```

Result: **9 passed**. These tests structurally parse
`bkflow/apigw/management/commands/data/api-resources.yml`, verify the four
operation IDs, paths, POST methods, authentication settings and view routing,
and compare all four Chinese Harness documents byte-for-byte with entries in
`bkflow/apigw/docs/apigw-docs.zip`.

### Trusted scope and boundary remediation

```bash
pytest tests/interface/space/test_space_config.py -k harness \
  tests/interface/harness/services/test_context.py \
  tests/interface/harness/services/test_canonical.py \
  tests/interface/harness/test_safety.py \
  tests/interface/harness/test_security_boundaries.py \
  tests/interface/apigw/test_harness_resource_contract.py \
  -q -rs --disable-warnings --no-cov
```

Result: **110 passed, 1 skipped, 32 deselected**. This run covers same-space
component exclusion and scoped APIGW credential selection through public routes, the
space-wide null/null validate-to-draft round trip, the legal 1799-character
capability reference and max-plus-one rejection, one shared canonical scope
representation, bounded deployment configuration including Unicode/UTF-8
validation, shared secret-shaped value and correlation safety, and the exact
ten-key Envelope wording in all four archived docs.

### Canonical trusted-scope collision regression

```bash
pytest tests/interface/harness/services/test_canonical.py \
  tests/interface/space/test_space_config.py \
  tests/interface/harness/services/test_context.py \
  tests/interface/harness/services/test_draft.py \
  tests/interface/harness/services/test_validator.py \
  -q --disable-warnings --no-cov
```

Result: **144 passed**. Scoped identities use one compact, reversible JSON-array
encoding for persistence, plan hashing, idempotency fingerprints and trusted
run/draft comparisons. The regression covers two otherwise legal scopes that
move `:` between type and value, Unicode/quote/backslash/control escaping,
the 255-character Django `CharField` boundary, mixed-null rejection, and a
same-key pre-run request that must not replay across scopes. The internal
canonical value is not added to the public ten-key Envelope.

## Golden Case inventory and real boundaries

Fixture version `harness-p0-golden-v1` contains exactly:

| Group | Count |
| --- | ---: |
| `positive_selection` | 8 |
| `ambiguous_requires_clarification` | 6 |
| `zero_candidate` | 4 |
| `schema_validation_error` | 4 |
| `schema_drift` | 3 |
| `idempotent_draft_retry` | 3 |
| `forged_identity_rejected` | 2 |
| **Total** | **30** |

The cases execute an unmodified production `HarnessFacade`, the default Task 5
projection/resolver, Task 6 `WorkflowValidator`, `A2FlowV2Converter`,
`ValidatorHandler`, Task 7 managed-draft/idempotency path and real
Harness/Template database writes. A caller outside the Facade records the Tool
sequence from actual Envelope results; it does not replace Facade methods or
select the next Tool from fixture expectations. External provider network I/O
alone is substituted at `ComponentLibrary`, `PluginServiceApiClient` and
`UniformAPIClient`. A mutation/spy regression fails if production Facade
delegation or conversion is bypassed or broken. No fixture result is counted as
BKAIDev or pilot evidence.

## Measured security and forbidden-side-effect counters

The counters are derived from public route responses, recursive Harness logs,
newly persisted Harness/Template rows, before/after database counts and guarded
production entrypoint call counts. They are not literal success constants.

| Counter | Observed local value | Evidence test |
| --- | ---: | --- |
| `cross_space_leak` | 0 | `test_public_routes_measure_zero_cross_space_exposure` |
| `secret_or_token_exposure` | 0 | Provider/card split plus the C2 route/database scan suite below |
| `silent_schema_drift` | 0 | `test_real_search_schema_validate_drift_has_zero_silent_acceptance` |
| `duplicate_drafts` | 0 | `test_public_draft_same_key_replay_has_one_draft_and_no_high_phase_side_effects` |
| `published_templates` | 0 | Same successful public-draft test plus all public negative/drift probes |
| `created_tasks` | 0 | Guarded Interface-to-Engine `TaskComponentClient` calls |
| `real_executions` | 0 | Guarded task-control/node/debug calls and `DebugContext` database delta |

The hostile public-route matrix also proves that `auto_release`, publish,
release, debug, execute, `sdk_xxx`, token fields and direct-plugin actions are
closed-DTO rejected before Facade, provider, Task 7 or higher-phase entrypoints.
The shared value policy additionally rejects `credential://`, Bearer values,
BKAPI authorization variants and explicit authorization/token/secret
assignments before request hashing or any durable domain write. Ordinary prose
containing words such as “token” remains accepted, and only the closed,
authorized binding `credential://id/<int>` field bypasses that generic rule.
Unsafe trace IDs and request IDs are replaced with a generated opaque identifier
inside trusted-context construction; success and semantic-failure tests observe
the same safe value in Envelope, report, idempotency replay snapshot and audit,
with no raw header value or derived header hash persisted.

The C2 zero-exposure suite is
`test_public_success_replaces_malicious_correlation_before_every_durable_copy`,
`test_public_secret_shaped_values_under_safe_keys_leave_no_failure_evidence`,
`test_public_secret_shaped_idempotency_keys_are_never_hashed_or_persisted`, and
`test_public_safe_security_language_and_closed_binding_credential_ref_remain_compatible`.
Each derives its counter from actual responses, Harness logs and newly persisted
Harness/Template model fields rather than a constant.

### Local idempotent draft proof

`test_public_draft_same_key_replay_has_one_draft_and_no_high_phase_side_effects`
executes public search → Schema → validate → draft → same-key draft replay. The
two successful Envelopes contain the same template reference. Before/after
database observations show exactly one `Template`, one `TemplateSnapshot` with
`draft=True` and `version=None`, one Harness `harness_draft` artifact and one
completed draft idempotency record. The pytest database is ephemeral, so no
durable template ID is invented or recorded here. A real BKAIDev/pilot draft ID
is `NOT_RUN_EXTERNAL`.

## Migrations, framework checks and formatting truth

The committed Harness migration chain is:

| Migration | Repository status |
| --- | --- |
| `0001_initial.py` | Creates the P0 run, immutable revision, binding, report and idempotency models |
| `0002_harnessidempotencyrecord_status.py` | Adds the explicit idempotency status contract; depends on `0001` |
| `0003_capabilitybinding_conversion_fingerprint.py` | Adds the conversion fingerprint; depends on `0002` and is the current Harness migration head |

`python manage.py makemigrations harness --check --dry-run` exits 0 with **no
Harness changes**. Full-repository `makemigrations --check --dry-run` exits 1
because of pre-existing candidates
`space.0012_alter_spaceconfig_name` and
`template.0014_alter_templateoperationrecord_operate_type`; neither is created
or claimed by P0.

`python manage.py check` exits 0 with the existing
`label.Label.label_scope` JSONField callable-default warning. It also emits the
existing naive `Token.expired_time` runtime warning in this local environment.

Black is installed and was executed. Scoped changed Python files through the
tested SHA pass Black, flake8 and the repository pre-commit hooks. The broader
planned Black command currently reports **20 pre-existing files** that would be
reformatted and exits 1; this document does not relabel that baseline drift as
a Harness regression or as a passing repository-wide format gate.

## Release gate table

| Gate | Status | Evidence boundary |
| --- | --- | --- |
| 30 versioned Golden Cases and local service chains | `PASS_LOCAL` | 34-test Golden run above |
| Seven measured security/side-effect counters equal zero | `PASS_LOCAL` | 38-pass security run; one independent DB-lock skip |
| Four repository routes, Tool mappings and APIGW operation IDs | `PASS_LOCAL` | Security surface and 9-pass resource-contract tests |
| Harness migration chain and scoped model state | `PASS_LOCAL` | `0001` → `0002` → `0003`; scoped migration check clean |
| One logical MCP in a real BKAIDev configuration | `NOT_RUN_EXTERNAL` / `BLOCKED` | No SaaS configuration readback captured |
| Actual exactly-four Tool visibility in BKAIDev | `NOT_RUN_EXTERNAL` / `BLOCKED` | Repository allowlist is not runtime visibility |
| Agent Release prompt/model/MCP/Tool/knowledge pins | `NOT_RUN_EXTERNAL` / `BLOCKED` | No immutable Agent Release readback captured |
| Baseline-full-Schema versus on-demand-Schema comparison | `NOT_RUN_EXTERNAL` / `BLOCKED` | No BKAIDev measurements captured |
| 10–20 capability pilot with exact version/hash | `NOT_RUN_EXTERNAL` / `BLOCKED` | No pilot-space run/readback captured |
| Trusted app/user/space/scope/environment live attribution | `NOT_RUN_EXTERNAL` / `BLOCKED` | Local permission tests are not live SaaS evidence |
| Real BKAIDev-created draft ID and readback | `NOT_RUN_EXTERNAL` / `BLOCKED` | Local pytest IDs are ephemeral and omitted |
| MySQL/PostgreSQL two-connection lock execution | `NOT_RUN_EXTERNAL` / `BLOCKED` | Eight SQLite skips listed above; no production-DB run claimed |

Therefore the only honest aggregate decision is
**`BLOCKED_BY_EXTERNAL_EVIDENCE`**.

## Explicitly deferred phases

P0 does **not** implement or authorize:

- P1 Knowledge Router or `search_workflow_knowledge`;
- P2 debug Tools or Token Broker/TokenLease behavior;
- P3 approval, release, publish, task creation or workflow execution;
- P4 generation feedback, outcome ingestion or EvalOps closure.

Local tests and this document cannot advance those phase boundaries.
