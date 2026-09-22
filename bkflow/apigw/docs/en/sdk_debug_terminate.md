### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Terminate a workflow debug run (SDK endpoint)

### HTTP header parameters

| Parameter         | Type | Required | Description |
|--------------| --- | --- | --- |
| BKFLOW-TOKEN | string | Yes | Access token obtained from `/space/{space_id}/apply_token/`, with permission type `MOCK` |

### Endpoint parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| space_id | int | Yes | Space ID |
| template_id | int | Yes | Workflow template ID |
| node_id | string | No | Node ID. When supplied, terminate that node and reset it to not_run; otherwise terminate the current global debug task. |

### Terminate a single node

Request example:

```json
{
  "space_id": 1,
  "template_id": 100,
  "node_id": "node1"
}
```

Example `data` response:

```json
{
  "status": "idle",
  "reset_node_ids": ["node1"]
}
```

Successful single-node termination means state reconciliation is complete; there is no need to wait for `terminating`. On the next debug-context query, the target node's
`nodes[].status` is `not_run`; its inputs, outputs, duration, error, and log references are cleared. The context `status` is `idle`, and
`last_run_status` is `not_run`.

### Terminate global debugging

Request example:

```json
{
  "space_id": 1,
  "template_id": 100
}
```

Example `data` response:

```json
{
  "status": "terminating"
}
```

After receiving `terminating`, keep polling the debug context. A context `status` of `idle` means termination is complete; at that point,
`last_run_status` is `revoked`, displayed as "Debugging terminated". Nodes still in `running | waiting | paused` states
revert to `not_run`; completed or naturally failed nodes retain their states.
