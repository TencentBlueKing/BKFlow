# BKAIDev A2Flow Harness P1 knowledge-provider spike

## Status and evidence identity

Overall status: **`BLOCKED_BY_EXTERNAL_EVIDENCE`**. This spike freezes the
local contract and the safe implementation defaults; it is not evidence that
the provider is available in BKAIDev or in a pilot space.

`predecessor_sha = 80a3922fd38edfe51d640df0782613c75bdb0edc` (`ai/a2flow-harness-p0-clean`).
The P1 working branch is `ai/a2flow-harness-p1`, and the local regression was
run from the current checkout at `444f095744a088687ebc2e23b3b4a8bea709666a`.
The predecessor contract is P0 `1.0.0`; the relevant repository references are
`docs/reviews/2026-09-01-bkaidev-harness-p0-verification.md` and
`docs/specs/2026-09-01-bkaidev-a2flow-harness-design.md`.

No real BKAIDev Agent Release, platform knowledge-provider configuration,
service credential, or provider response was available in this run. Therefore
all six external probes are recorded as `NOT_RUN_EXTERNAL` and `BLOCKED`; no
provider PASS, URL, response, or limit is invented.

## Step 1: P0 local regression gate

Focused command (same test selection and flags as the P0 verification gate):

```bash
pytest tests/interface/harness tests/interface/apigw/test_harness_p0.py \
  tests/interface/apigw/test_harness_resource_contract.py \
  tests/interface/apigw/test_list_plugins.py \
  tests/interface/apigw/test_get_plugin_schema.py \
  tests/interface/apigw/test_validate_a2flow.py \
  tests/interface/apigw/test_create_template_with_a2flow.py \
  tests/interface/plugin/services/test_plugin_schema_service.py \
  -q -rs --disable-warnings --no-cov
```

Result: **471 passed, 8 skipped in 13.04s**. The run used the repository
`.venv/bin/pytest` with the shared local `.env`, on branch
`ai/a2flow-harness-p1` at SHA `444f095744a088687ebc2e23b3b4a8bea709666a`.
The eight skips are the documented SQLite limitation for two-connection
`select_for_update`/row-lock proofs: two idempotency tests, five validator
concurrency tests, and one public draft lock-contention test. They are not
claimed as MySQL/PostgreSQL evidence.

The initially attempted bare `pytest` could not be resolved by the active
pyenv selection; this is an environment invocation issue, not a test result.

## Step 2: Provider probe matrix

Each probe requires a sanitized request against a real BKAIDev/provider
configuration plus an exported configuration or captured response. None was
available, so the actual-evidence column intentionally contains no fabricated
value.

| Probe | Sanitized input | Expected result | Actual evidence / status | Pass | Owner | Decision impact |
| --- | --- | --- | --- | --- | --- | --- |
| SP-P1-01 service-to-service search authentication | `platform=BKFlow`, `space_id=<test-space>`, `query=<non-sensitive capability phrase>`, `top_k=5` | Provider accepts the platform service identity and returns a bounded result envelope | `NOT_RUN_EXTERNAL` / `BLOCKED`; no endpoint, credential, exported config, or response captured | `N/A (NOT_RUN_EXTERNAL)` | Platform/provider owner | Keep `provider_mode=provider_spi_only`; no external rollout or live Router call |
| SP-P1-02 source_ref and chunk/citation stability | Repeat the same sanitized query twice against one fixed test corpus | Stable opaque `source_ref`, chunk identity, citation offsets and content digest | `NOT_RUN_EXTERNAL` / `BLOCKED`; no repeated provider responses available | `N/A (NOT_RUN_EXTERNAL)` | Knowledge-provider owner | Use content digest locally; do not claim provider-native citation stability |
| SP-P1-03 snapshot/version availability | Same query with requested corpus/revision marker `<revision>` | Provider exposes an immutable corpus version/snapshot that can be recorded and replayed | `NOT_RUN_EXTERNAL` / `BLOCKED`; no version API/readback captured | `N/A (NOT_RUN_EXTERNAL)` | Knowledge-provider owner | Freeze `snapshot_mode=content_digest_snapshot` |
| SP-P1-04 provider-side ACL and caller attribution | Sanitized query from allowed and disallowed actor/app bindings in two test spaces | ACL is enforced before retrieval and caller/app/space attribution is returned or auditable | `NOT_RUN_EXTERNAL` / `BLOCKED`; no ACL result or attribution trace captured | `N/A (NOT_RUN_EXTERNAL)` | Platform IAM + provider owner | Freeze `identity_mode=platform_service_identity`; Binding actor/app, ACL, environment, trust-state and validity checks must all pass before calls |
| SP-P1-05 timeout, response bytes and top_k limits | Queries at bounded sizes with `top_k={1,5,20,21}`, total Router provider-phase budget `3s` | Documented provider limits and deterministic timeout/oversize behavior | `NOT_RUN_EXTERNAL` / `BLOCKED`; no provider measurements captured | `N/A (NOT_RUN_EXTERNAL)` | Knowledge-provider owner | Apply local budgets only: `top_k<=20`, default 5 per binding, one shared 3s provider-phase deadline, 65536 response bytes |
| SP-P1-06 query/result data classification and redaction | Sanitized query plus synthetic secret-shaped and personal-data markers | Classification, redaction and audit behavior are explicit and no secret/personal data leaks | `NOT_RUN_EXTERNAL` / `BLOCKED`; no provider classification/redaction response captured | `N/A (NOT_RUN_EXTERNAL)` | Security + knowledge-provider owner | Keep provider integration blocked until classification/redaction evidence is reviewed |

### Frozen knowledge-safety constraints

Every knowledge result is **untrusted advisory context only**. It must never
be treated as an executable instruction, tool-selection authority, permission
grant, or workflow command. BKAIDev Agent is the sole conversation/LLM 主体;
BKFlow does not generate LLM decisions and must not promote retrieved text into
an executable plan without the separately governed P0 contracts and trusted
validation path.

Before any provider call, the Router must filter the Binding and request on
allowed actor/app, provider ACL, target environment, trust state, and binding
validity/expiry. If any check is missing or rejected, the call is denied and
the query must not be sent to the provider.

`KnowledgeSourceBinding` is a read-only projection in Django Admin. Product
changes must go through the versioned `sync_knowledge_bindings` desired-state
manifest, where local shape, dual-review metadata and references are validated
before an atomic apply; omitted bindings are retired rather than deleted. The
model enforces only locally provable invariants. Tier-owner authorization and
provider snapshot existence remain external evidence checks owned exclusively
by the synchronizer, and a successful local save never claims those external
facts have been verified.

`content_digest_snapshot` permits only the minimum binding metadata, snapshot
identifier/digest, audit record, redacted artifact reference, and source
metadata needed for replay. It explicitly forbids durable storage of knowledge
正文, embeddings/vectors, or provider chunks/slices. Any retained excerpt must
be a bounded, redacted artifact reference rather than an unreviewed knowledge
payload.

## Step 3: Frozen decisions and local implementation budget

The conservative decisions for this task are:

```text
provider_mode = provider_spi_only
identity_mode = platform_service_identity
snapshot_mode = content_digest_snapshot
```

`provider_spi_only` permits local Router tests but blocks BKAIDev/space rollout.
`platform_service_identity` requires Binding-level allowed actor/app, ACL,
environment, trust-state and validity/expiry enforcement before every provider
call, with rejected requests never sent. `content_digest_snapshot` means the
local Router records only a digest and minimal source metadata; it does not
imply that the provider supplies a native immutable snapshot or authorize
storing knowledge正文, vectors, or chunks.

The local implementation budget is deliberately bounded and is **not a
measurement of provider limits**:

| Budget | Value | Meaning |
| --- | ---: | --- |
| Maximum `top_k` | 20 | Local request validation ceiling |
| Default `top_k` per binding | 5 | Local default |
| Excerpt size | 4096 UTF-8 bytes | Local truncation budget, applied without splitting invalid UTF-8 |
| Response size | 65536 bytes | Local response envelope budget |
| Timeout | 3s | One local Router provider-phase deadline shared by the bounded fan-out; unfinished work is cancelled where possible and adapters must enforce transport cancellation for already-running calls |

## Stop conditions and next gate

P1 knowledge-provider work must stop and remain `BLOCKED_BY_EXTERNAL_EVIDENCE`
until the owner supplies all of the following for the six probes: a reachable
provider/API identity, sanitized request and captured response or exported
configuration, exact corpus/source version evidence, ACL and caller
attribution evidence, measured timeout/size/top-k behavior, and reviewed data
classification/redaction results. A local mock or pytest result cannot clear
these external gates. After evidence is supplied, rerun the matrix against the
same predecessor contract and record the exact provider revision and evidence
links before enabling any BKAIDev or space rollout.

## Verification

The required structural check is satisfied by this document:

```text
rg -n 'SP-P1-0[1-6]|provider_mode =|identity_mode =|snapshot_mode =|predecessor_sha' docs/reviews/2026-09-02-bkaidev-harness-p1-provider-spike.md
```

No row marked `PASS` exists without an external source link, exported config,
or captured response. This report records local regression evidence separately
from external-provider evidence.

## P1 local gate follow-up (2026-09-04)

The historical spike decisions and all six blocked rows above remain
unchanged. Task 8 added a versioned 36-case corpus and a security suite that
exercise the real binding eligibility, Provider registry, Router, Facade and
audit boundaries with external retrieval mocked only at the provider SPI. The
implementation is based on predecessor
`95d76db06ce77e65af447fbf3d58948cdf374353`; the initial Task 8 commit is
`2efd426dc6b3a1da0a715a429e4525e8e1039cc5`, and the exact-snapshot follow-up is
`02dfc4e11d25f1e3acd43843ae84a373cbb14f06`. The verified predecessor for the
current fair return-path follow-up is
`c686a898c3665f0d1cbd8472a7f4ce323e1ca2e8`; the verification diff cannot embed
its own future commit SHA. On the current worktree containing that predecessor
plus the generation-based wakeup implementation/tests/docs, the complete local
P1 aggregate is **791 passed, 8 skipped in 12.52s**; the predecessor alone does
not contain or reproduce the new fair return-path regression test. The Provider
suite is **26 passed in 0.21s**, including a **5 passed in 0.18s** concurrency
subset with unhandled thread warnings promoted to errors. All eight skips are
documented SQLite row-lock limitations. Repository parsing observes 107 APIGW
operations and exactly five Harness operation IDs.

These local results do not supply a reachable provider API, provider request
ID, provider-native source/citation/snapshot evidence, provider-side ACL and
caller attribution, measured provider limits, classification/redaction proof,
or a BKAIDev Agent Release readback. SP-P1-01 through SP-P1-06 therefore remain
`NOT_RUN_EXTERNAL / BLOCKED`, and the release status is exactly
**`P1_RELEASE_GATE_BLOCKED_BY_PROVIDER_EVIDENCE`**. Real BKAIDev five-Tool
mounting and MySQL/PostgreSQL execution are also `NOT_RUN_EXTERNAL / BLOCKED`.
The detailed command and case evidence is recorded in
`2026-09-02-bkaidev-harness-p1-verification.md`.
