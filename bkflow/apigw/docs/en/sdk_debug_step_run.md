### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Execute a workflow debug step (SDK endpoint)

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
| mode | string | No | Execution mode: `real` or `mock`; conditional gateways support only `real` |
| input_overrides | dict | No | Input overrides |
| mock_result | string | No | Mock result: `success` or `fail` |
| mock_outputs | dict | No | Mock outputs |
| mock_error | string | No | Mock failure message |

### Request example

```json
{
  "space_id": 1,
  "template_id": 100,
  "node_id": "node1",
  "mode": "mock",
  "mock_result": "success",
  "mock_outputs": {
    "k": "v"
  }
}
```

### real mode response example

A real step returns immediately after creating and starting an engine task. Poll `debug_context` for subsequent `running | waiting | paused | finished | failed` states.

```json
{
  "node_id": "node1",
  "task_id": 456,
  "status": "running",
  "log_ref": {
    "instance_id": 456,
    "node_id": "runtime_node_id",
    "version": "v1"
  }
}
```

Mock mode still returns `finished` or `failed` synchronously, with outputs, error details, and updated global variables.

### Conditional gateway real mode response example

Exclusive and conditional parallel gateways evaluate branch conditions synchronously and return only selected connections. They do not create engine tasks or execute downstream nodes. The frontend uses `selected_flow_ids` to mark selected paths green.

```json
{
  "node_id": "gateway1",
  "status": "finished",
  "selected_flow_ids": ["flow_true"],
  "condition_results": [
    {
      "flow_id": "flow_true",
      "name": "条件1",
      "expression": "${count} > 0",
      "resolved_expression": "1 > 0",
      "matched": true
    }
  ],
  "error_detail": null
}
```

If required upstream outputs are unavailable, the endpoint returns an unmet-dependency error with `missing_vars`. Execution errors, such as expression parsing failures or multiple matching exclusive branches, return `status=failed` synchronously and write `error_detail`. The same state and branch results are also available from `debug_context.nodes[]`.
