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
      "config_changed": true,
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
      "config_changed": false,
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
      "config_changed": false,
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

### Node configuration changes

| Field | Type | Description |
| --- | --- | --- |
| nodes[].config_changed | bool | Whether the saved node name or execution configuration differs from its latest debug baseline. Independent of `status` and debug success or failure. |

The comparison uses the draft, or the published snapshot when no draft exists. Saving preserves debug_snapshot node membership, order, names, results, duration, input/output data and log references; its difference flags reflect the saved draft. Repeated saves do not clear a mismatch. Restoring the previously debugged configuration makes the flag `false` again.

- Global and real single-step debugging update a node's baseline from the frozen run configuration when polling confirms `running`, `waiting`, `finished` or `failed`. With no further saved changes, running nodes and nodes waiting for callbacks return `config_changed=false` without waiting for completion. This applies to both `nodes` and `debug_snapshot.nodes`. Mock runs and conditional gateway evaluation update the baseline on success or execution failure; editing Mock presets does not update it.
- Unreached nodes, nodes suspended before execution and nodes without a valid engine state keep their previous baselines. Dependency rejections, task creation failures and start failures do not update them either.
- If configuration A is running when B is saved, `config_changed` remains `true` while running or waiting and after A completes, until B actually executes or A is restored.
- Nodes that have never actually executed return `status=not_run` and `config_changed=false`. Saving parameters or renaming before their first execution, including while a global run has not reached them, does not mark them stale. Comparison begins after actual execution. Resetting an executed node to `not_run` preserves its baseline and does not turn it into a new node.
- Legacy records with only an initialization fingerprint and no reliable execution evidence default to `config_changed=false`. This includes old reset records where the distinction between never executed and previously executed has been lost. Confirmed completed results remain comparable, and another execution establishes reliable evidence. Fingerprints still use the `v2:` algorithm with an additional execution marker; only matching algorithm versions are compared, without reconstructing history from the current draft. Names with execution evidence remain independently comparable. A `false` value does not imply prior debugging or success; check `status` separately. `node_deleted` independently identifies deleted historical nodes.
- The comparison covers plugin configuration, execution options, gateway conditions, embedded subprocesses and loop configuration. Names are compared separately. Descriptions, coordinates, layout and external `incoming/outgoing` connections are excluded. Adding/removing other nodes or rewiring activity nodes does not mark an otherwise unchanged node. Gateway conditions/default branches and internal subcanvas execution structure remain part of their owning node's configuration. Changes to upstream outputs or global variables are not propagated to downstream nodes.
- Unsaved frontend edits and click-to-canvas linking are outside this field's scope.
- Saving structural or parameter changes preserves historical status, inputs, outputs, duration and logs. Frontend icons, success/failure counts and result details must use `debug_snapshot.nodes[].status`; show `config_changed` / `node_deleted` as independent hints. `debug_reset_impact` may still suggest resets after structural changes, but is read-only. Do not automatically call `debug_reset` on save to clear history.
- No database migration, initialization or bulk backfill is required. Reading `debug_context` applies the new rules. Validate after all Interface instances have been updated during a rolling deployment: old instances do not recognize execution markers and may return inconsistent change hints. Tasks started by old instances can continue syncing on the new code using their frozen configuration.

`supports_step` indicates single-step support and `supports_mock` indicates mock support. Both are `true` for activities. Exclusive and conditional parallel gateways have `supports_step=true` and `supports_mock=false`. Parallel and converge gateways have both set to `false` and only display global debugging status. Debug panels should filter out nodes where both are `false`.

All gateways have `execution_mode=real`. After debugging a conditional gateway, the frontend uses `selected_flow_ids` to mark selected connections green. `condition_results` can display each branch's original expression, evaluated expression, and match result. Both fields are empty arrays for parallel gateways, converge gateways, and activity nodes.


### Debug result snapshot

`nodes` continues to describe the saved draft for step execution, Mock settings and eligibility checks. Its new `node_name` is the current name. Use `debug_snapshot.nodes` for the result list; those names and results belong to the debug attempt, not the current canvas.

| Field | Type | Description |
| --- | --- | --- |
| debug_snapshot | object / null | Latest accumulated debug results; null for legacy records without a reliable snapshot, before the first new debug attempt, or after a full reset. Historical data is never fabricated from the current draft. |
| debug_snapshot.nodes[].node_id / node_type / node_name | string | Template node ID, type and debug-time name. |
| debug_snapshot.nodes[].config_changed | bool | Saved name or execution configuration differs from the reliable debug baseline; defaults to false without a baseline. |
| debug_snapshot.nodes[].node_deleted | bool | Node no longer exists in the saved draft. Its previous result and log reference remain available. |
| debug_snapshot.nodes[].execution_mode | string | Actual mode used for this result: real / mock. Editing Mock presets preserves existing results; disabling Mock clears this node's result and sets this field to real. |
| debug_snapshot.nodes[].status / waiting_reason | string / string or null | Same runtime state and waiting reason meanings as existing node states. |
| debug_snapshot.nodes[].inputs / outputs | object | Recorded input/output values. Gateway outputs contain selected_flow_ids and condition_results. Inputs are {} if not collected. |
| debug_snapshot.nodes[].configured_inputs | object / null | Configuration inputs frozen when debugging starts, mapped by parameter name. Preserves expressions, nested structures and empty values without variable substitution, using existing credential masking rules. Available for unexecuted nodes too; null when historical configuration is unavailable. Never reconstructed from the current draft. |
| debug_snapshot.nodes[].duration_ms / error_detail / log_ref | int or null / object or null / object or null | Recorded duration, error and engine log reference. |
| debug_snapshot.nodes[].operator / last_run_at | string / string or null | Debug initiator and recorded run time; null when no reliable time was recorded. |

- A successfully started global run replaces the full snapshot. Real, Mock and gateway steps update only their target; other nodes keep their own latest results. The snapshot can therefore combine several step attempts rather than represent one engine task.
- Runtime results continue to update while running, using the frozen launch-time tree, names and output-variable bindings. Saving, renaming or deleting nodes does not rewrite the snapshot list. Dependency, create or start failures preserve the previous snapshot.
- Ordering follows the frozen control flow: predecessors precede successors and joins follow all branches. Parallel branches use a stable node-ID order, not chronological execution order. Loop back-edges are not expanded repeatedly. A subcanvas is one node; start/end events are excluded.
- A newly stepped node is inserted according to that run's flow order without reordering previous entries. The next global run establishes a new full ordering.
- Explicit node reset clears only that result; full reset clears the snapshot. Termination preserves completed results and resets active nodes to not_run, as before.
- Switching from Mock to real with `node_mock(enable=false)` resets only that node's current state and snapshot result to `not_run`, clears execution results and changes the result entry's `execution_mode` to `real`, while retaining configured inputs. Its bound output variables are removed; consumers of these missing variables expose `can_step=false` and `missing_vars`. Other nodes retain their historical results. Disabling an already-real node does not reset it again.
- Reading this endpoint does not automatically backfill legacy names or snapshots; `backfill_debug_snapshots` can recover them from reliable historical tasks. Existing configuration hashes remain valid; a new attempt establishes a name baseline. Restoring the original name/configuration clears the marker.
- `node_deleted` and `config_changed` compare against the saved draft only. The frontend handles unsaved edits, canvas linking and user-facing hints. Deleted result nodes are not executable controls.

### Displaying input parameters

- For `status=not_run`, display `configured_inputs` as "Configured inputs (not executed, variables unresolved)". If null or absent on an older service, show "Configuration inputs not recorded" instead of using the current draft. Executed nodes continue to display actual `inputs`; an empty object must not silently fall back to configuration values. Local Mock execution has no engine inputs and keeps `inputs={}`; configuration values may be shown separately.
- Plugin nodes use each parameter's `value` from launch-time `component.data`. Subcanvas/subprocess nodes expose only `pipeline.constants` parameters with `show_type=show`, without expanding inner nodes. Gateways return `{}` because they have no such input parameters.
- A successfully started global run captures configuration inputs for all nodes, including unreached ones. A step updates only its target. Draft edits, deletion and runtime polling do not replace these values. Resetting a node clears runtime results but preserves its captured configuration; a full reset removes the entire snapshot.
- Existing snapshots without the field return null until a new debug attempt records it. Legacy snapshot backfill also captures these values when the original task node configuration is available, otherwise null. The backfill command does not overwrite existing snapshots. No database migration is required: the field lives in the existing JSON snapshot.
