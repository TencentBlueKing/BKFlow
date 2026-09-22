### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get built-in plugins (SDK endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### HTTP header parameters

| Parameter         | Type   | Required | Description                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | Yes  | Access token obtained from `/space/{space_id}/apply_token/`. This token verifies the user's permission to access the specified space. |

### Endpoint parameters

| Field         | Type      | Required  | Description       |
|------------|---------|-----|----------|
| space_id   | int     | Yes   | Space ID     |
| version    | string  | No   | Plugin version     |

### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "space_id": 1,
    "version": "1.0.0"
}
```

### Response example

```json
{
    "result": true,
    "data": [
        {
            "code": "example_plugin",
            "name": "示例插件",
            "version": "1.0.0",
            "desc": "插件描述",
            "group_name": "分组名称",
            "status": true
        }
    ],
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
| data    | list   | Response data: plugin list            |

#### data[item] fields

| Field        | Type     | Description   |
|-----------|--------|------|
| code      | string | Plugin code |
| name      | string | Plugin name |
| version   | string | Plugin version |
| desc      | string | Plugin description |
| group_name | string | Group name |
| status    | bool   | Whether enabled |
