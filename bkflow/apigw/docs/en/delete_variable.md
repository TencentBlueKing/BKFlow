### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Delete a space variable

### Common authentication parameters
| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

#### Path parameters

| Field          | Type    | Required  | Description    |
|-------------|-------|-----|-------|
| space_id    | int   | Yes   | Space ID  |
| variable_id | int   | Yes   | Variable ID  |


### Response example

```json
{
    "result": true,
    "code": 0,
    "message": "变量删除成功"
}
```

### Response parameters

| Field          | Type       | Description                      |
|-------------|----------|-------------------------|
| result      | bool     | Operation result: true for success, false for failure   |
| code        | int      | Response code: 0 for success, any other value for failure       |
| message     | string   | Operation result message                  |
