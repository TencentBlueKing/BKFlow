### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get the tag tree

### Common authentication parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| bk_app_code | string | Yes | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| bk_app_secret | string | Yes | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### Path parameters:

| Field | Type | Required | Description |
|------------|-------|----------|--------|
| space_id   | int   | YES      | Space ID   |
| task_id    | int   | YES      | Task ID   |

#### Interface parameters

| Field | Type | Required | Description |
|---------|--------|----------|------|
| node_id | string | NO    | Node ID |

### Response example

```json
{
    "result": true,
    "message": "success",
    "data": [
        {
            "id": 5,
            "operator": "xxx",
            "instance_id": 3,
            "operate_date": "2024-09-24T15:29:29.078977+08:00",
            "extra_info": {},
            "node_id": "",
            "operate_type": "create",
            "operate_source": "api",
            "operate_type_name": "创建",
            "operate_source_name": "api 接口"
        }
    ]
}
```

### Description of returned result parameters

| Field   | Type     | Description            |
|---------|--------|-----------------------|
| result  | bool   | Returns the result: true for success, false for failure. |
| message | string | error message                  |
| data    | dict   | Return data                  |


#### data[item]

| Field   | Type     | Description              |
|---------------------|---------|--------------|
| id                  | int     | Record ID         |
| operator            | string  | Operator          |
| instance_id         | int     | Task Instance ID       |
| operate_date        | string  | Operation time         |
| extra_info          | object  | Extended Information         |
| node_id             | string  | Node ID; if empty, indicates a task-level operation. |
| operate_type        | string  | Operation Type         |
| operate_source      | string  | Operation Source         |
| operate_type_name   | string  | Operation Type Name       |
| operate_source_name | string  | Operation Source Name       |