### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get workflow details (SDK endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### HTTP header parameters

| Parameter         | Type   | Required | Description                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | Yes  | Access token obtained from `/space/{space_id}/apply_token/`. This token verifies the user's permission to view the specified template. |

### Path parameters

| Field         | Type     | Required | Description    |
|------------|--------|----|-------|
| template_id | string | Yes  | Workflow template ID |

### Endpoint parameters

| Field             | Type   | Required | Description                                                                                                                                    |
|----------------|------|----|---------------------------------------------------------------------------------------------------------------------------------------|
| with_mock_data | bool | No  | Whether to include mock data; default: false. When true, appoint_node_ids and mock_data are included, and pipeline_tree is pruned if appoint_node_ids specifies mock execution nodes. |

### Request example

```
GET /sdk/template/{template_id}/?with_mock_data=false
```

### Response example

```json
{
    "result": true,
    "data": {
        "id": 3,
        "space_id": 2,
        "name": "测试模板",
        "desc": null,
        "notify_config": {},
        "scope_type": null,
        "scope_value": null,
        "pipeline_tree": {
            "id": "p92c20c7854104dd3975f46a1d8664417",
            "start_event": {},
            "end_event": {},
            "activities": {},
            "gateways": {},
            "flows": {}
        },
        "source": null,
        "version": "",
        "is_enabled": true,
        "extra_info": {}
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

| Field            | Type     | Description                    |
|---------------|--------|-----------------------|
| id            | int    | Workflow ID                  |
| space_id      | int    | Space ID of the workflow              |
| name          | string | Workflow name                  |
| desc          | string | Workflow description                  |
| notify_config | dict   | Workflow notification settings                |
| scope_type    | string | Workflow scope type              |
| scope_value   | string | Workflow scope value               |
| pipeline_tree | dict   | Workflow tree details                 |
| source        | string | Workflow source                  |
| version       | string | Workflow version number                 |
| is_enabled    | bool   | Whether enabled                  |
| extra_info    | dict   | Additional information                  |
