### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Validate a workflow variable key (SDK endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### Permissions

This endpoint uses the default permissions. **BKFLOW-TOKEN is not required**.

### Endpoint parameters

| Field | Type     | Required | Description                    |
|----|--------|----|-----------------------|
| key | string | Yes  | Variable key in the form ${key} or key |

### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "key": "var_name"
}
```

or

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "key": "${var_name}"
}
```

### Response example

```json
{
    "result": true,
    "data": null,
    "code": "0",
    "message": ""
}
```

### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Result: true for success, false for failure. Invalid keys return false with an error message. |
| code    | string | Response code: 0 for success, any other value for failure     |
| message | string | Error message returned for an invalid key |
| data    | null   | Placeholder field                |

### Notes

1. The key must not be empty.
2. The key must not be a Python keyword (such as if, for, or class).
3. The key must not be in the system's variable blocklist.
4. The `${key}` format is supported; the enclosed key is extracted for validation.
