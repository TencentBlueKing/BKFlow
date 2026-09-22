### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get task details

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

#### Endpoint parameters

| Field                | Type     | Required | Description                           |
|-------------------|--------|----|------------------------------|
| limit             | int    | No  | Items per page; limit must not exceed 200        |
| offset            | int    | No  | Offset                          |
| id                | string | No  | Template IDs, separated by commas                 |
| name              | string | No  | Workflow name, fuzzy match                   |
| label             | string | No  | Tag name                         |
| creator           | string | No  | Creator, exact match                   |
| updated_by        | string | No  | Updater, exact match                   |
| scope_type        | string | No  | Workflow scope type, exact match                  |
| scope_value       | string | No  | Workflow scope value, exact match                 |
| create_at_start   | string | No  | Creation time range start, such as 2023-08-25 07:49:45 |
| create_at_end     | string | No  | Creation time range end, such as 2023-08-25 07:49:46 |
| order_by          | string | No  | Sort field; defaults to creation time descending              |

### Response example

```json
{
    "result": true,
    "data": [
        {
            "id": 618,
            "space_id": 1,
            "name": "测试模板",
            "desc": null,
            "notify_config": {},
            "scope_type": null,
            "scope_value": null,
            "source": null,
            "version": "",
            "is_enabled": true,
            "extra_info": {},
            "creator": "",
            "create_at": "2024-07-30T06:27:52.642Z",
            "update_at": "2024-07-30T07:30:28.005Z",
            "updated_by": "",
            "labels": []
        }
    ],
    "count": 10,
    "code": 0
}
```

### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| code    | int    | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | dict   | Response data                  |

##### data[item]

| Field            | Type     | Description     |
|---------------|--------|--------|
| id            | int    | Workflow ID   |
| space_id      | int    | Workflow space ID |
| name          | string | Workflow name   |
| desc          | string | Workflow description   |
| notify_config | dict   | Workflow notification settings |
| scope_type    | string | Workflow scope type |
| scope_value   | string | Workflow scope value  |
| source        | string | Workflow source   |
| version       | string | Workflow version   |
| is_enabled    | bool   | Whether the workflow is enabled |
| extra_info    | dict   | Extended workflow information |
| creator       | string | Workflow creator  |
| create_at     | string | Workflow creation time |
| update_at     | string | Workflow update time |
| updated_by    | string | Workflow updater  |
| labels        | list   | Tag information   |
