### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Configure node mocks for workflow debugging (SDK endpoint)

### HTTP header parameters

| Parameter         | Type | Required | Description |
|--------------| --- | --- | --- |
| BKFLOW-TOKEN | string | Yes | Access token obtained from `/space/{space_id}/apply_token/`, with permission type `MOCK` |

### Endpoint parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| space_id | int | Yes | Space ID |
| template_id | int | Yes | Workflow template ID |
| node_id | string | Yes | Node ID |
| enable | bool | No | Whether mock is enabled; switching from mock to real resets this node's results and removes its bound output variables |
| mock_result | string | No | Mock result: `success` or `fail` |
| mock_outputs | dict | No | Mock outputs |
| mock_error | string | No | Mock failure message |

Exclusive and conditional parallel gateways do not support mocks. Calling this endpoint for either returns an error indicating that conditional gateways do not support mocks.

### Disabling Mock

- When `enable=false` changes a node from `mock` to `real`, both its current state and its entry in `debug_snapshot.nodes` become `not_run`. Execution inputs, outputs, duration, errors and log references are cleared. The result entry's `execution_mode` becomes `real`; configured inputs and Mock presets are preserved.
- All output variables bound to this node in the current draft are removed from `global_vars`, including old keys absent from the latest `mock_outputs`. Values from an earlier global run are not restored. Other nodes' results and output variables, and unrelated manual inputs, are preserved; downstream nodes are not recursively reset.
- Disabling an already-real node does not clear results again. Configuring or disabling Mock is rejected during an active run. Mode, results and variables are changed atomically. No historical snapshot is fabricated when none exists.
- Default real steps retain dependency checks: consumers of missing variables expose `can_step=false` and `missing_vars` in `debug_context`, and execution is rejected with an unmet-dependency error. They become runnable after the producer supplies values again. Explicit `input_overrides` retain their existing behavior; ordinary step requests should not automatically submit stale overrides.
- Saving successful Mock presets still updates their bound global variables immediately. Only disabling Mock triggers this cleanup. After disabling, clients should reload `debug_context` to refresh node results and downstream eligibility.
- No database migration or legacy backfill is required; cleanup takes effect on the disable action. During a rolling release, behavior is consistent only after all Interface instances have been updated.

### Request example

```json
{
  "space_id": 1,
  "template_id": 100,
  "node_id": "node1",
  "enable": true,
  "mock_result": "success",
  "mock_outputs": {
    "k": "v"
  }
}
```

To disable, send `{"space_id": 1, "template_id": 100, "node_id": "node1", "enable": false}`.

### Response data

| data field | Type | Description |
| --- | --- | --- |
| node_id | string | Node ID |
| execution_mode | string | Current mode, `real` after disabling |
| updated_global_vars | dict | Complete debug globals after the operation; removed output keys are absent |
