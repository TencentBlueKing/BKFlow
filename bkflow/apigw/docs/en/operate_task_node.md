### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Operate on a task node

### Common authentication parameters
| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |


#### Endpoint parameters
| Field       | Type     | Required | Description  |
|----------|--------|----|-----|
| operator | string | Yes  | Operator |

Additional parameters for the operation

| Operation type        | Required parameters    | Type          | Meaning       | Example                      |
|-------------|---------|-------------|----------|-------------------------|
| retry       | inputs  | json        | Node retry inputs   | {"param1": "value1"}    |
| callback    | data    | json/string | Callback data     | "this is callback data" |
| forced_fail | ex_data | str         | Forced failure error message | "forced fail by xxx"    |

### Special parameters

#### Open plugin callbacks

When `operation=callback` and the current node receives a callback through the BK-SOPS open plugin gateway, an explicit `operator` is no longer required in the request body. Instead:

1. Supply `X-Callback-Token` in the request headers.
2. Supply the open plugin callback data in the request body.

Header example:

| Header name        | Type     | Required | Description                       |
|-------------------|----------|------|----------------------------|
| X-Callback-Token  | string   | Yes   | Callback token dynamically issued by BKFlow during execute |

Open plugin callback body fields:

| Field                | Type     | Required | Description |
|---------------------|----------|------|------|
| open_plugin_run_id  | string   | Yes   | BK-SOPS open plugin execution instance ID |
| status              | string   | Yes   | Callback status, such as `SUCCEEDED` / `FAILED` |
| outputs             | dict     | No   | Plugin outputs |
| error_message       | string   | No   | Failure reason |
| truncated           | bool     | No   | Whether outputs were truncated |
| truncated_fields    | list     | No   | List of truncated fields |

Open plugin callback fields are checked for types and required values before forwarding to the engine. For example, a missing `status` returns `code=400` without triggering a node callback.

When `operation=forced_fail` succeeds, cancellation of the associated open plugin execution instance is dispatched asynchronously. Endpoint success means the node has entered the forced-failure state; it does not mean the remote plugin instance has finished cancelling.


Path parameters:

| Field        | Type     | Required | Description                                       |
|-----------|--------|----|------------------------------------------|
| operation | string | Yes  | Operation: retry, skip, callback, or forced_fail |

### Request example
```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "operator": "操作人"
}
```

Open plugin callback example:

```json
{
    "open_plugin_run_id": "8d3d6dc2f7cf4c5395b3a3c0ec5a37f1",
    "status": "SUCCEEDED",
    "outputs": {
        "job_instance_id": 1001
    }
}
```


### Response example

```json
{
    "result": true,
    "data": null,
    "message": "success",
    "trace_id": "3f16e62e57c543a9be6cff9556e48d07"
}
```
### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| code    | int    | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | dict   | Response data                  |
