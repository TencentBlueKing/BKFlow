### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get tag reference counts

### Common authentication parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| bk_app_code | string | Yes | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| bk_app_secret | string | Yes | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

#### Endpoint parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| label_ids | string | Yes | Comma-separated tag IDs, such as `1,2,3` |

### Notes

- For a root `label_id` with children, its reference count is the sum of the counts for **all child tags**.
- Task reference counts come from the task module.

### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "label_ids": "1,2,3"
}
```

### Response example

```json
{
    "result": true,
    "data": {
        "1": {
            "template_count": 2,
            "task_count": 5
        },
        "2": {
            "template_count": 0,
            "task_count": 1
        }
    },
    "code": 0
}
```

### Response parameters

| Field | Type | Description |
| --- | --- | --- |
| result | bool | Operation result: true for success, false for failure |
| code | int | Response code: 0 for success, any other value for failure |
| message | string | Error message |
| data | dict | Response data, keyed by label_id strings |

#### data[label_id]

| Field | Type | Description |
| --- | --- | --- |
| template_count | int | Template reference count |
| task_count | int | Task reference count |
