# BKFlow Conditional Gateway Debugging Design

## Goal

Expose only nodes that have meaningful debug behavior, and make condition-bearing gateways independently debuggable without executing downstream nodes.

## Scope

- Keep activity nodes in the debug control panel.
- Add `ExclusiveGateway` and `ConditionalParallelGateway` to `debug_context.nodes`.
- Keep start events, end events, `ParallelGateway`, and `ConvergeGateway` out of `debug_context.nodes`.
- Allow real single-step evaluation for condition-bearing gateways.
- Do not support mock mode for gateways.
- Persist gateway status and selected outgoing flow IDs so callers can highlight the selected paths.

## API Contract

Gateway entries in `debug_context.data.nodes[]` use the existing node status fields and add explicit capabilities and branch results:

```json
{
  "node_id": "gateway1",
  "node_type": "ExclusiveGateway",
  "execution_mode": "real",
  "supports_mock": false,
  "status": "finished",
  "can_step": true,
  "missing_vars": [],
  "selected_flow_ids": ["flow_true"],
  "condition_results": [
    {
      "flow_id": "flow_true",
      "name": "condition 1",
      "expression": "${count} > 0",
      "resolved_expression": "1 > 0",
      "matched": true
    }
  ],
  "error_detail": null,
  "duration_ms": 1,
  "log_ref": null
}
```

Activity entries add `supports_mock: true` and return empty gateway result fields. This lets callers render capabilities without hard-coding node types.

`debug_step_run` accepts a condition gateway `node_id`. Gateway execution is synchronous and returns:

```json
{
  "node_id": "gateway1",
  "status": "finished",
  "selected_flow_ids": ["flow_true"],
  "condition_results": []
}
```

`debug_step_run` with `mode=mock`, and every `debug_node_mock` call for a gateway, return HTTP 400 with a clear message that gateways do not support mock.

## Evaluation Semantics

Gateway single-step evaluation does not create a task and does not execute any downstream node. It evaluates conditions from the current template draft using the current `DebugContext.global_vars`, with template constant defaults as fallback values.

- Expressions are rendered with bamboo-engine `Template` and evaluated with BKFlow's `pipeline_gateway_expr_func`, preserving boolrule, FEEL, and MAKO selection.
- `ExclusiveGateway` follows the configured strategy. The normal strategy requires exactly one matching condition; the first-match strategy stops at the first match.
- `ConditionalParallelGateway` selects every matching condition.
- If no condition matches, the configured default flow is selected.
- Missing produced variables, malformed expressions, no matching/default branch, and multiple matches in an exclusive gateway produce `status=failed` with `error_detail`.

The operation briefly acquires the template debug lock and releases it before returning. This prevents overlap with global or activity-node debugging while keeping gateway evaluation synchronous.

## Persistence And Global Runs

No migration is required. Gateway branch results are stored in the existing `DebugNodeState.outputs` JSON field:

```json
{
  "selected_flow_ids": ["flow_true"],
  "condition_results": []
}
```

`reset` clears these values through the existing result reset path.

During a real global debug run, gateway runtime IDs already appear in `get_node_id_map`. Once gateway states are included in `DebugNodeState`, the existing synchronization loop writes `running`, `finished`, or `failed` to the gateway. For a finished gateway, BKFlow calculates and stores the branch result from the synchronized debug context; for a failed gateway, it persists the engine node error in `error_detail` and the task-level failure remains in `last_error_detail`.

## Compatibility

- Existing activity node fields and behavior remain unchanged.
- Existing SDK methods remain valid because `debug_step_run` already accepts an arbitrary node ID and SDK responses are untyped dictionaries.
- Consumers that ignore the new fields continue to work.
- Legacy mock schemes apply only to activity nodes; gateways always remain in real mode.

## Verification

- Context tests verify that only activities and the two condition gateway types are returned.
- Unit tests cover boolrule selection, default branches, conditional parallel multi-selection, missing variables, malformed expressions, and exclusive multiple-match failure.
- Service tests verify synchronous gateway step state, mock rejection, lock release, reset behavior, and global-run gateway state synchronization.
- View tests verify standard response wrapping and HTTP 400 errors.

