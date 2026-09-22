### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Preview resolved workflow constants (SDK endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### Permissions

This endpoint uses the default permissions. **BKFLOW-TOKEN is not required**.

### Endpoint parameters

| Field        | Type   | Required | Description       |
|-----------|------|----|----------|
| constants  | dict | Yes  | Workflow constant definitions   |
| extra_data | dict | No  | Additional data for resolving constants |

### constants parameter

Example constants format:
```json
{
    "var1": {
        "key": "var1",
        "name": "变量1",
        "value": "${var2}",
        "source_type": "custom"
    }
}
```

### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "constants": {
        "var1": {
            "key": "var1",
            "name": "变量1",
            "value": "value1",
            "source_type": "custom"
        }
    },
    "extra_data": {}
}
```

### Response example

```json
{
    "result": true,
    "data": {
        "var1": "resolved_value1"
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
| data    | dict   | Response data: variable names mapped to resolved values |
