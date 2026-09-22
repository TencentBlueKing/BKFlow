### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get workflow debug context (SDK endpoint)

### HTTP header parameters

| Parameter         | Type | Required | Description |
|--------------| --- | --- | --- |
| BKFLOW-TOKEN | string | Yes | Access token obtained from `/space/{space_id}/apply_token/`; permission type `MOCK` is recommended |

### Endpoint parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| space_id | int | Yes | Space ID |
| template_id | int | Yes | Workflow template ID |

### Request example

```
GET /sdk/template/debug/context/?space_id=1&template_id=100
```

### Response example

```json
{
  "template_id": 100,
  "status": "idle",
  "locked_by": "",
  "active_task_id": null,
  "active_run_type": null,
  "active_node_id": null,
  "last_task_id": 456,
  "last_run_type": "global",
  "last_run_status": "failed",
  "last_error_detail": {
    "type": "runtime",
    "message": "multiple conditions meet",
    "task_id": 456,
    "failures": [
      {
        "node_id": "runtime_gateway_id",
        "template_node_id": null,
        "message": "multiple conditions meet"
      }
    ]
  },
  "last_inputs": {},
  "global_vars": {},
  "nodes": [
    {
      "node_id": "node1",
      "node_type": "ServiceActivity",
      "execution_mode": "real",
      "supports_step": true,
      "supports_mock": true,
      "status": "waiting",
      "waiting_reason": "callback",
      "selected_flow_ids": [],
      "condition_results": []
    },
    {
      "node_id": "gateway1",
      "node_type": "ExclusiveGateway",
      "execution_mode": "real",
      "supports_step": true,
      "supports_mock": false,
      "status": "finished",
      "waiting_reason": null,
      "selected_flow_ids": ["flow_true"],
      "condition_results": [
        {
          "flow_id": "flow_true",
          "name": "条件1",
          "expression": "${count} > 0",
          "resolved_expression": "1 > 0",
          "matched": true
        }
      ]
    },
    {
      "node_id": "parallel_gateway1",
      "node_type": "ParallelGateway",
      "execution_mode": "real",
      "supports_step": false,
      "supports_mock": false,
      "status": "finished",
      "waiting_reason": null,
      "selected_flow_ids": [],
      "condition_results": []
    }
  ]
}
```

`status` represents the context lock state, with values `idle | running | terminating`. The execution result is represented by `last_run_status`, with values `not_run | running | waiting | paused | finished | failed | revoked`. Here, `revoked` means global debugging was explicitly terminated and is displayed as "Debugging terminated". After a single-node termination, the result is `not_run`.

`active_task_id` is populated only while the task is running and is cleared on completion; `last_task_id` retains the latest real engine task ID. Node `status` values are `not_run | running | waiting | paused | finished | failed`. When global debugging is terminated, active nodes revert to `not_run`; completed or naturally failed nodes retain their states. When engine scheduling records exist, `waiting_reason` is `callback | multiple_callback | poll`。

`nodes` contains activity nodes and all gateways: exclusive (`ExclusiveGateway`), conditional parallel (`ConditionalParallelGateway`), parallel (`ParallelGateway`), and converge (`ConvergeGateway`). Start and end nodes are excluded.

`supports_step` indicates single-step support and `supports_mock` indicates mock support. Both are `true` for activities. Exclusive and conditional parallel gateways have `supports_step=true` and `supports_mock=false`. Parallel and converge gateways have both set to `false` and only display global debugging status. Debug panels should filter out nodes where both are `false`.

All gateways have `execution_mode=real`. After debugging a conditional gateway, the frontend uses `selected_flow_ids` to mark selected connections green. `condition_results` can display each branch's original expression, evaluated expression, and match result. Both fields are empty arrays for parallel gateways, converge gateways, and activity nodes.
