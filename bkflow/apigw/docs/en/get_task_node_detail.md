### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get task node details

### Common authentication parameters
| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

#### Endpoint parameters

| Field                   | Type     | Required | Description                                                         |
|----------------------|--------|----|------------------------------------------------------------|
| loop                 | int    | No  | Retrieve data from the specified loop; defaults to the latest loop                       |
| component_code       | string | No  | Plugin code of the node, used to format outputs; outputs are unformatted by default                   |
| include_snapshot_config | bool | No  | Whether data includes the node configuration snapshot (snapshot_config); default: false         |

### Response example

```json
{
    "result": true,
    "data": {
        "name": "定时",
        "error_ignorable": false,
        "state": "READY",
        "inputs": {
            "bk_timing": "30",
            "force_check": true
        },
        "outputs": [],
        "ex_data": ""
    },
    "message": ""
}
```

### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| code    | int    | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | dict   | Response data                  |

#### Data fields

| Field              | Type     | Description                                           |
|-----------------|--------|----------------------------------------------|
| name            | string | Node name                                         |
| error_ignorable | bool   | Whether node failures can be ignored                                    |
| state           | string | Node status                                         |
| inputs          | dict   | Node input parameters                                       |
| outputs         | list   | Node output parameters                                       |
| ex_data         | string | Error message when node execution fails                                 |
| snapshot_config | dict   | Node configuration snapshot, returned only when include_snapshot_config=true; null if retrieval fails |
