### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get task list

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
| name              | string | No  | Workflow name, fuzzy match                   |
| creator           | string | No  | Creator, exact match                   |
| scope_type        | string | No  | Workflow scope type, exact match                  |
| scope_value       | string | No  | Workflow scope value, exact match                 |
| label             | string | No  | Tag name                         |
| create_at_start   | string | No  | Creation time range start, such as 2023-08-25 07:49:45 |
| create_at_end     | string | No  | Creation time range end, such as 2023-08-25 07:49:46 |
| task_id_list      | array[int] | No  | Task IDs for exact list filtering. GET requests use repeated keys, such as `?task_id_list=1&task_id_list=3&task_id_list=5`. When supplied, this parameter must contain 1 to 50 values. |

### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "limit": 20,
    "offset": 0
}
```

### Response example

```json
{
    "result": true,
    "data": {
        "count": 1,
        "next": null,
        "previous": null,
        "results": [
            {
                "id": 1671,
                "create_time": "2024-07-31 17:56:23+0800",
                "start_time": "2024-07-31 17:56:26+0800",
                "finish_time": "2024-07-31 17:59:14+0800",
                "space_id": 1,
                "scope_type": null,
                "scope_value": null,
                "instance_id": "n2d1ef9ff5193d39b2d13bb2faa5418c",
                "template_id": 616,
                "name": "default_taskflow_instance",
                "creator": "",
                "create_method": "API",
                "executor": "",
                "description": "",
                "is_started": true,
                "is_finished": true,
                "is_revoked": false,
                "is_deleted": false,
                "is_expired": false,
                "snapshot_id": 1671,
                "execution_snapshot_id": 1671,
                "tree_info_id": 1539,
                "extra_info": {}
            }
        ]
    },
    "code": "0",
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

##### data[item]

| Field       | Type     | Description    |
|----------|--------|-------|
| count    | int    | Total number of records  |
| next     | string | Next page |
| previous | string | Previous page |
| results  | list   | Response data  |

##### result[item]

| Name                    | Type     | Description       |
|-----------------------|--------|----------|
| id                    | int    | Task ID     |
| space_id              | int    | Space ID of the task |
| scope_type            | string | Task scope type   |
| scope_value           | string | Task scope value    |
| instance_id           | string | Task instance ID   |
| template_id           | int    | Task template ID   |
| name                  | string | Task name      |
| creator               | string | Task creator    |
| create_method         | string | Task creation method   |
| create_time           | string | Task creation time   |
| executor              | string | Task executor    |
| start_time            | string | Task start time   |
| finish_time           | string | Task end time   |
| is_started            | bool   | Whether the task started  |
| is_finished           | bool   | Whether the task finished  |
| is_revoked            | bool   | Whether the task was revoked  |
| is_deleted            | bool   | Whether the task was deleted  |
| is_expired            | bool   | Whether the task expired  |
| snapshot_id           | int    | Task snapshot ID   |
| execution_snapshot_id | int    | Task execution snapshot ID |
| tree_info_id          | int    | Task tree information ID  |
| extra_info            | dict   | Additional task information   |
