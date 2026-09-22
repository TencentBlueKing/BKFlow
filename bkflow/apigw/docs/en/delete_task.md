### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Batch delete tasks

### Common authentication parameters
| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |


#### Endpoint parameters

| Field        | Type    | Required   | Description           |
|-----------|-------|------|--------------|
| is_full   | bool  | No    | Whether to delete all tasks     |
| is_mock   | bool  | No    | Whether to delete all debug tasks   |
| task_ids  | list  | No    | List of task IDs to delete    |

### is_mock parameter
When is_full is supplied, is_mock must also be supplied.

### Request example

```json
{
  "bk_app_code": "xxxx",
  "bk_app_secret": "xxxx",
  "bk_username or bk_token": "xxxx",
  "task_ids": [1,2,3]
}
```


### Response example

```json
{
    "result": true,
    "data": null,
    "message": "success",
    "trace_id": "c8rbc1fas1cb498fa6fb74fc0f884159"
}

```
### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| message | string | Error message                  |
