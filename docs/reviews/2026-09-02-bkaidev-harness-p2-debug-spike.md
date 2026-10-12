# BKAIDev a2flow Harness P2 debug and Token gate spike

## Status and evidence identity

```text
predecessor_sha = c12941c6430c8956548d299ec67e822d4166904c
branch = ai/a2flow-harness-p2
local_spike_status = P2_TASK1_PASS_LOCAL
real_step_status = P2_REAL_STEP_GATE_BLOCKED_BY_EXTERNAL_EVIDENCE
```

This spike freezes the P2 adapter direction from the exact P1 predecessor. It
does not claim that P2 is implemented or that a real BKAIDev Agent Release,
approval receipt, platform-application Token issuer, production database, or
live asynchronous recovery has been verified. Mock P2 may proceed; real-step
rollout remains fail-closed.

All local commands ran in the isolated `ai/a2flow-harness-p2` worktree. The
latest Harness migration is `0004_p1_knowledge_router`. Contract `1.0.0` still
has exactly four Tools and `1.1.0` has exactly five, in their frozen order.

## Predecessor reconciliation

| Gate | Fresh result | What it proves | What it does not prove |
| --- | --- | --- | --- |
| P0/P1 Harness plus P0/P1 APIGW/resource contract | `791 passed, 8 skipped in 12.73s` | The exact predecessor retains the complete local P0/P1 gate. | The eight skips remain SQLite two-connection row-lock limitations; this is not MySQL/PostgreSQL or BKAIDev evidence. |
| Entire existing debug suite | `120 passed in 2.75s` | Current DebugService, SDK views, permissions, state sync, stale-lock, step/global and compatibility behavior is green locally. | External Engine calls are test doubles; no BKAIDev MCP or live long-running Tool is exercised. |
| Existing apply-token and resource-validator tests | `9 passed in 2.37s` | The legacy API locally covers Token creation/reuse, configured renewal and resource validation. | It does not prove a platform application can issue a user-bound Token through BKAIDev, and the legacy response exposes Token plaintext. |

The P1 verification document remains the source for the eight inherited skip
reasons and the external Provider gate. P2 does not reinterpret those skips as
passes.

## Current DebugService contract

Runtime introspection was executed through Django's initialized shell, then the
return and side-effect boundaries were checked against
`bkflow/template/debug/service.py` and all 120 debug tests.

### Construction and read/projection operations

| Operation | Exact current signature | Return boundary | Read/write or external side effects |
| --- | --- | --- | --- |
| Constructor | `DebugService(template_id, space_id=None, pipeline_tree=None)` | Service instance | Lazily reads Template/TemplateSnapshot and space when values were not injected. It accepts no approval or Token parameter. |
| Input Schema | `input_schema(self)` | Ordered list of visible constants: `key`, `name`, `type`, `default`, `required=true` | No local write; reading `pipeline_tree` can load the draft snapshot/template. Hidden constants are excluded. |
| Context projection | `build_context_view(self) -> dict` | Template/context status, lock and active/last task facts, inputs/global vars, and node views ordered by `node_id` | Not a pure read: it calls `sync_node_states` and `sync_from_debug_task`, can create/prune/update DebugContext/DebugNodeState, query Engine state/details, propagate outputs and release a finished lock. Harness must treat polling as a recoverable state-sync operation. |
| History | `history(self) -> dict` | `{"runs": [{"task_id", "operator", "started_at", "status"}, ...]}` | Reads DEBUG task list and batch states; no local write. The call supplies no client-selected limit, so the current Task endpoint applies `BKFLOWDefaultPagination.default_limit=10` (`max_limit=200`). P2 must own a stable cardinality and byte limit instead of relying only on this downstream default. |
| Reset impact | `reset_impact(self) -> dict` | Sorted `reset_node_ids` and per-node `reasons` | Read-only and creates no DebugContext. It compares the saved tree fingerprint and current draft, then expands changes over control and data-flow closure. No prior baseline returns empty. |

`compute_tree_fingerprint` is **not** a DebugService method. The current callable
is `bkflow.template.debug.dependency.compute_tree_fingerprint(pipeline_tree:
dict) -> dict`; it returns per-activity config hashes plus `flows`, `gateways`
and `constants` hashes. DebugService calls it from `_refresh_tree_fingerprint`
and `reset_impact`. The P2 adapter must import or wrap this module function; it
must not assume `DebugService.compute_tree_fingerprint()` exists.

### Run and control operations

| Operation | Exact current signature | Return boundary | Persisted/external side effects and P2 ruling |
| --- | --- | --- | --- |
| Step run | `step_run(self, node_id, operator, mode=None, input_overrides=None, mock_result='success', mock_outputs=None, mock_error='') -> dict` | Mock returns terminal `finished`/`failed`, outputs/error, updated globals and no log ref. A supported gateway evaluates synchronously and returns selected flows/condition results. A real activity returns `node_id`, `task_id`, `status='running'` and `log_ref`. | Syncs node state first. Mock writes node result and successful output globals without an Engine task. Gateway uses the shared lock but no Engine task. Real checks dependencies, acquires the shared CAS lock, creates/starts a single-node DEBUG task and persists active/last task state. Non-`mock` values currently fall through to real, so the Harness adapter must validate the enum before calling. |
| Global run | `global_run(self, inputs: dict, operator: str) -> dict` | `{"task_id": <id>, "status": "running"}` | Reclaims a stale lock if eligible, acquires the shared lock, clears old run results while retaining Mock presets, stores inputs/fingerprint, creates and starts a DEBUG task. Failure releases the lock and best-effort deletes an orphan task. Raw DebugService materializes configured Mock nodes but does not force all nodes to Mock; P2 policy must do that before dispatch. |
| Reset | `reset(self, node_ids=None) -> list` | List of reset node IDs; the SDK view wraps it as `reset_node_ids`. | Syncs nodes, rejects a live lock unless it is stale/reclaimed, and clears run result fields while preserving Mock configuration. It does not clear DebugContext global vars. |
| Terminate | `terminate(self, node_id=None, operator='') -> dict` | Node terminate returns `status='idle'` and `reset_node_ids`; global terminate returns `status='terminating'`. | Marks terminating before Engine control. A node uses `forced_fail` with suppressed failure side effects, resets that node and releases the lock immediately. Global uses task revoke and relies on later state sync to reach revoked/release the lock. A rejected Engine operation restores the previous running state. |
| Node Mock | `node_mock(self, node_id, enable=True, mock_result='success', mock_outputs=None, mock_error='') -> dict` | `node_id`, resulting `execution_mode`, and `updated_global_vars` | Rejects active non-stale locks and all gateway Mock. It changes only configuration, not run status. A successful preset is immediately propagated to global vars; disabling Mock retains presets and previously propagated globals. |
| Context variable | `set_context_var(self, key, value) -> dict` | Entire updated `global_vars` map | Creates DebugContext when absent, rejects an active non-stale lock, and persists the value. P2 must add payload/redaction/size bounds before exposing it to the Agent. |

The raw service raises `DebugConflictError` and `DebugStateError`, and some
messages can originate from downstream task responses. The Harness adapter must
normalize these into bounded Envelope errors and Evidence; it must not reflect
untrusted Engine details or infer approval from successful dispatch.

## Local asynchronous and locking facts

- Real activity step and global run are already fast acknowledgement paths:
  both return `status='running'` immediately after create/start, without waiting
  for completion.
- Later `build_context_view()` polling calls `sync_from_debug_task()` to update
  node/context state, outputs, failure details and final lock release. Global
  termination similarly returns `terminating` until a later sync observes
  `REVOKED`.
- The template-scoped lock is a conditional database update from `idle` to
  `running`. A fresh lock conflicts. A `running`/`terminating` lock older than
  `BKFLOW_DEBUG_LOCK_TTL_SECONDS` (default 600 seconds) is reclaimed by another
  conditional update, with best-effort orphan-task revoke.
- Local tests prove the conflict and stale/fresh reclaim branches. They do not
  constitute a live multi-process MySQL/PostgreSQL race or BKAIDev refresh and
  disconnect recovery test.

## SP-P2 probe matrix

Every row separates repository/local evidence from evidence that requires a
real BKAIDev connection or platform integration.

| Probe | Actual local evidence | Local status | External evidence/status | Gate consequence |
| --- | --- | --- | --- | --- |
| SP-P2-01 approval receipt authenticity and binding | No approval verifier, signature/issuer trust store, replay check, or receipt claim binding exists in the predecessor. Prompt/UI confirmation is not a server-verifiable receipt. | `NOT_IMPLEMENTED_LOCAL` | No real BKAIDev approval receipt bound to actor, app, space/scope, plan hash, action, node and expiry was supplied. `NOT_RUN_EXTERNAL / BLOCKED`. | `approval_mode = deny_real`; zero real DebugService calls. |
| SP-P2-02 current-user identity through BKAIDev MCP | P0/P1 Harness tests locally preserve trusted app/user/space context and reject caller-supplied authority, but they use repository request fixtures. | `PASS_LOCAL` for Harness context only | No BKAIDev MCP connection/readback proves the authenticated platform app and current user arrive together. `NOT_RUN_EXTERNAL / BLOCKED`. | Mock implementation may use the existing trusted-context boundary; rollout waits for connection evidence. |
| SP-P2-03 platform application token issuance | Legacy `apply_token` binds `request.user.username`, space, resource and permission, then returns Token plaintext. There is no trusted issuer service, TokenLease or non-serializable server-only handle. | `LOCAL_GAP` | No platform application was shown issuing a MOCK Token for the current user/template or Scope through the live APIGW identity chain. `NOT_RUN_EXTERNAL / BLOCKED`. | `token_issue_mode = deny_real`; legacy `apply_token` must not be called by the Agent. |
| SP-P2-04 token expiry, renewal and revoke | `Token.verify` rejects expiry; `apply_token` reuses a matching unexpired Token and renews only when configured; `revoke_token` expires matched rows. The focused legacy tests are 9/9 green, but no P2 TokenLease exists. | `PASS_LOCAL_BASELINE` | No live issue-expire-renew-revoke/readback trace for a platform-issued user Token was supplied. `NOT_RUN_EXTERNAL / BLOCKED`. | Task 4 must extract a server-side issuer, cap TTL, store only a fingerprint and prove revoke without exposing plaintext. |
| SP-P2-05 running Tool refresh and polling recovery | Step real/global return `running`; context polling and terminate-to-sync recovery are covered by the 120-test debug suite. | `PASS_LOCAL` for DebugService lifecycle | No BKAIDev running Tool refresh, page reload, disconnect or multi-turn polling readback was run. `NOT_RUN_EXTERNAL / BLOCKED`. | Freeze fast acknowledgement plus polling, but do not claim SaaS recovery acceptance. |
| SP-P2-06 DebugContext lock conflict and stale reclaim | Source uses conditional updates for acquire/reclaim, default 600-second TTL and best-effort orphan revoke; stale/fresh/conflict tests pass in the local debug suite. | `PASS_LOCAL` | Real multi-process production-database contention/reclaim was not run. `NOT_RUN_EXTERNAL / BLOCKED` for production acceptance. | Reuse the lock and add one active Harness DebugSession per template; do not invent a parallel lock. |
| SP-P2-07 maximum history/Evidence response size | Current history is cardinality-bounded indirectly to the Task endpoint default 10 results because DebugService sends no limit. No P2 Evidence model, Harness byte budget, pagination cursor or Artifact spill exists. | `PASS_LOCAL` for current history cardinality; `LOCAL_GAP` for P2 Evidence/bytes | No large-result BKAIDev rendering or Artifact recovery was run. `NOT_RUN_EXTERNAL / BLOCKED`. | Task 3/7 must add explicit stable history/Evidence count and UTF-8 byte limits plus Artifact refs before Mock rollout. |

## Frozen modes

```text
approval_mode = deny_real
debug_call_mode = in_process_debug_service
token_issue_mode = deny_real
async_mode = fast_ack_and_poll
```

- `debug_call_mode = in_process_debug_service`: the Harness adapter calls the
  service layer directly after its own trusted-context, session, policy and
  idempotency checks. It does not loop through the ten SDK HTTP operations.
- `approval_mode = deny_real`: no configured server-verifiable receipt exists.
  Missing, invalid, expired, mismatched or replayed approval must stop before
  Token acquisition and DebugService dispatch.
- `token_issue_mode = deny_real`: the legacy API exposes plaintext and there is
  no verified platform-application issuer path. Real step remains unavailable
  until Task 4 and live issuer evidence exist.
- `async_mode = fast_ack_and_poll`: this matches the current DebugService
  `running` return contract. It is a local Harness design decision, not proof
  that BKAIDev currently survives refresh/disconnect; the Agent must use
  `get_debug_session` once P2 Tools exist.

## Agent, MCP, and rollout boundary

BKAIDev Agent remains the only LLM caller. BKFlow Harness and DebugService are
deterministic services and never decide by calling an LLM. The ten existing
`sdk_debug_*` operations remain canvas-facing SDK APIs and are not placed in the
MCP allowlist. The current repository
`CONTRACT_TOOLSETS["1.1.0"]` defines the four P0 Tools plus
`search_workflow_knowledge`; this is a repository contract snapshot, not live
BKAIDev mounting evidence. Real BKAIDev mounting/readback remains
`NOT_RUN_EXTERNAL / BLOCKED`. P2 later adds only `start_debug_session`,
`run_debug`, `get_debug_session` and `control_debug_session`.

Mock P2 may continue through contracts, DebugSession/Evidence, the in-process
adapter and Mock-only run/control flows. Until SP-P2-01 and SP-P2-03 have real
evidence, `execution_mode=real` must return a normalized approval/Token gate
error before DebugService or Engine access. P2 global real remains forbidden
regardless of those two probes; its policy is deferred to P3.

### Task 8 repository Tool mapping

The repository contract now defines one logical `BKFlow Workflow Harness MCP`
at contract `1.2.0` with nine cumulative, unprefixed public Tools. BKAIDev Agent
is the only LLM caller and selects these public Tools directly; BKFlow does not
call an LLM and the four P2 operations are not hidden behind one `harness`
super-Tool. The P2 APIGW mapping is:

| Public Tool | APIGW operationId | Frozen behavior |
| --- | --- | --- |
| `start_debug_session` | `harness_start_debug_session` | Bind latest validated Revision and managed draft facts without running a node. |
| `run_debug` | `harness_run_debug` | Mock by default; real step needs both approval and server Token Broker gates; global real is forbidden. |
| `get_debug_session` | `harness_get_debug_session` | Poll the deterministic Session and session-owned Evidence after fast acknowledgement. |
| `control_debug_session` | `harness_control_debug_session` | Apply the closed reset/terminate/mock/context control union. |

The Agent never receives the Token or calls the canvas-facing `sdk_debug_*`
operations. BKFlow owns deterministic Session/Evidence state and server-side
authorization. This mapping is `PASS_LOCAL` only after its repository tests and
generated APIGW documentation gate pass; BKAIDev MCP mounting, Tool discovery,
identity readback, long-running poll recovery, approval receipt, Token issuer,
and Agent Release readback remain `NOT_RUN_EXTERNAL / BLOCKED_BY_EXTERNAL_EVIDENCE`.

## Verification commands

```bash
pytest tests/interface/harness \
  tests/interface/apigw/test_harness_p0.py \
  tests/interface/apigw/test_harness_p1.py \
  tests/interface/apigw/test_harness_resource_contract.py \
  -q -rs --disable-warnings --no-cov
pytest tests/interface/template/debug -q -rs --disable-warnings --no-cov
pytest tests/interface/apigw/test_apply_token.py \
  tests/interface/apigw/test_token_resource_validator.py \
  -q -rs --disable-warnings --no-cov
rg -n 'SP-P2-0[1-7]|approval_mode =|debug_call_mode =|token_issue_mode =|async_mode =|predecessor_sha' \
  docs/reviews/2026-09-02-bkaidev-harness-p2-debug-spike.md
```

Local source and tests support the Mock implementation direction only. The
real-step release decision remains exactly
`P2_REAL_STEP_GATE_BLOCKED_BY_EXTERNAL_EVIDENCE`.
