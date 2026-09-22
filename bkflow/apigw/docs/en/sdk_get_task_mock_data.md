### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get task mock data (SDK endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### HTTP header parameters

| Parameter         | Type   | Required | Description                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | Yes  | Access token obtained from `/space/{space_id}/apply_token/`. This token verifies the user's permission to view the specified task. |

### Path parameters

| Field     | Type     | Required | Description   |
|--------|--------|----|------|
| task_id | string | Yes  | Task ID |

### Endpoint parameters

None

### Request example

```
GET /sdk/task/get_task_mock_data/{task_id}/
```

### Response example

```json
{
    "result": true,
    "data": {
        "taskflow_id": 123,
        "nodes": [
            {
                "node_id": "node1",
                "data": {
                    "input1": "value1",
                    "input2": "value2"
                },
                "is_default": false
            }
        ]
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

| Field          | Type     | Description                    |
|-------------|--------|-----------------------|
| taskflow_id | int    | Task workflow ID                |
| nodes       | list   | Mock node data list             |

#### data.nodes[item] fields

| Field         | Type     | Description                    |
|------------|--------|-----------------------|
| node_id    | string | Node ID                  |
| data       | dict   | Node mock data              |
| is_default | bool   | Whether this is the default mock data            |
