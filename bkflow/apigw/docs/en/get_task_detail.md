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

### Response example

```json
{
    "result": true,
    "data": {
        "id": 1,
        "pipeline_tree": {},
        "space_id": 1,
        "scope_type": null,
        "scope_value": null,
        "instance_id": "1",
        "template_id": 1,
        "name": "default_taskflow_instance",
        "creator": "",
        "create_time": "2023-04-19T16:02:45.204292+08:00",
        "executor": "",
        "start_time": null,
        "finish_time": null,
        "description": "",
        "is_started": false,
        "is_finished": false,
        "is_revoked": false,
        "is_deleted": false,
        "is_expired": false,
        "snapshot_id": null,
        "execution_snapshot_id": null,
        "tree_info_id": null,
        "extra_info": {},
        "webhook_delivery_history": []
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


#### data[item]

| Field                                | Type     | Description          |
|-----------------------------------|--------|-------------|
| id                                | int    | Task ID        |
| pipeline_tree                     | dict   | Task tree data       |
| space_id                          | int    | Space ID        |
| scope_type                        | string | Scope type        |
| scope_value                       | string | Scope value         |
| instance_id                       | string | Instance ID        |
| template_id                       | int    | Template ID        |
| name                              | string | Task name        |
| creator                           | string | Created by         |
| create_time                       | string | Creation time        |
| executor                          | string | Executor         |
| start_time                        | string | Start time        |
| finish_time                       | string | End time        |
| description                       | string | Description          |
| is_started                        | bool   | Whether started       |
| is_finished                       | bool   | Whether finished       |
| is_revoked                        | bool   | Whether revoked       |
| is_deleted                        | bool   | Whether deleted       |
| is_expired                        | bool   | Whether expired       |
| snapshot_id                       | int    | Snapshot ID        |
| execution_snapshot_id             | int    | Execution snapshot ID      |
| tree_info_id                      | int    | Task topology ID    |
| webhook_delivery_history          | list   | Webhook request records |

#### data.pipeline_tree

| Field          | Type   | Description                         |
|-------------|------|----------------------------|
| start_event | dict | Start node information                     |
| end_event   | dict | End node information                     |
| activities  | dict | Task node information (standard plugins and subprocesses)           |
| gateways    | dict | Gateway node information (parallel, exclusive, and converge gateways)     |
| flows       | dict | Sequence flow information (node connections)                |
| constants   | dict | Global variable information; see below               |
| outputs     | list | Template outputs, identifying output fields in constants |
