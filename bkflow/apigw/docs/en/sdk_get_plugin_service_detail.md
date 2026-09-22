### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get third-party plugin configuration details (SDK endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### Permissions

This endpoint uses the default permissions. **BKFLOW-TOKEN is not required**.

### Endpoint parameters

| Field            | Type     | Required | Description       |
|---------------|--------|----|----------|
| plugin_code   | string | Yes  | Plugin code     |
| plugin_version | string | No  | Plugin version     |
| with_app_detail | bool | No  | Whether to include application details; default: false |

### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "plugin_code": "example_plugin",
    "plugin_version": "1.0.0",
    "with_app_detail": true
}
```

### Response example

```json
{
    "result": true,
    "data": {
        "plugin_code": "example_plugin",
        "plugin_version": "1.0.0",
        "name": "示例插件",
        "desc": "插件描述",
        "inputs": {},
        "outputs": {},
        "deployed_statuses": {},
        "app": {
            "app_code": "example_app",
            "app_name": "示例应用"
        }
    },
    "message": "",
    "code": "0"
}
```

### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| code    | string | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | dict   | Response data                  |

#### Data fields

| Field              | Type     | Description       |
|-----------------|--------|----------|
| plugin_code     | string | Plugin code     |
| plugin_version  | string | Plugin version     |
| name            | string | Plugin name     |
| desc            | string | Plugin description     |
| inputs          | dict   | Input parameter definitions   |
| outputs         | dict   | Output parameter definitions   |
| deployed_statuses | dict | Deployment status     |
| app             | dict   | Application details (returned when with_app_detail=true) |
