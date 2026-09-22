### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Create a task with bk_app_code authorization

This endpoint creates tasks from templates bound to a bk_app_code. The requester's bk_app_code must match the code bound to the template.

**Note: user authentication is required. The creator is taken from the gateway-authenticated user; no creator parameter is needed.**

### Common authentication parameters
| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| bk_username   | string | Yes  | Username for user authentication                                                 |


#### Endpoint parameters

| Field                    | Type     | Required | Description                                    |
|----------------------|--------|----|---------------------------------------|
| name                  | string | No  | Task name                                   |
| description           | string | No  | Description                                    |
| constants             | json   | No  | Task startup parameters                                |
| custom_span_attributes | dict   | No  | Custom Span attributes added to the execution root Span and every node Span; see below |


Path parameters:

| Field      | Type     | Required | Description                                              |
|---------|--------|----|-------------------------------------------------|
| template_id | int | Yes  | Template ID |


### Permissions

- The template must be bound to a bk_app_code (through bind_app_code when creating the template).
- The requester's bk_app_code must match the code bound to the template.
- User authentication is required; the gateway-authenticated user is the creator.

### Open plugin governance

If the template contains BK-SOPS open plugins (`uniform_api v4.0.0`), catalog availability, business versions, and space enablement are validated before task creation. On success, plugin reference and schema snapshots are saved. On failure, no task is created and a parameter validation error is returned.

### custom_span_attributes parameter

The `custom_span_attributes` parameter passes custom attributes to the execution root Span and every node Span when creating a task, allowing custom instrumentation.

**Parameter format:**
- Type: dictionary (dict)
- key: custom attribute name (string)
- value: custom attribute value (serializable string, number, etc.)

**Use cases:**
- Business instrumentation: business IDs, order IDs, and other business identifiers
- Request instrumentation: request IDs, trace IDs, and other request identifiers
- Environment instrumentation: environment types, regions, and other environment information

**Example:**
```json
{
    "custom_span_attributes": {
        "business_id": "12345",
        "request_id": "req-abc-123",
        "user_type": "vip"
    }
}
```

**Notes:**
- Custom attributes are stored in the task's `extra_info.custom_context.custom_span_attributes`.
- These attributes are added to the execution root Span with names in the form `bkflow.<key>`.
- These attributes are passed to every node Span through `TaskContext`.
- In node Spans, custom attributes take precedence over default attributes (such as space_id and task_id) with the same key.
- The execution root Span preserves built-in attributes such as `task_id`, `space_id`, `pipeline_instance_id`, and `operator`; custom attributes do not overwrite them.

### Request example

```json
{
    "name": "任务名称",
    "constants": {
        "${param1}": "value1"
    }
}
```

Request example with custom Span attributes:
```json
{
    "name": "任务名称",
    "constants": {
        "${param1}": "value1"
    },
    "custom_span_attributes": {
        "business_id": "12345",
        "request_id": "req-abc-123"
    }
}
```

### Response example

```json
{
	"result": true,
	"data": {
		"id": 10,
		"space_id": 1,
		"scope_type": null,
		"scope_value": null,
		"instance_id": "6e15e7cf27ab3129878cdd9b95fff006",
		"template_id": 4,
		"name": "任务名称",
		"creator": "创建者",
		"create_time": "2023-04-23T21:10:06.826644+08:00",
		"executor": "",
		"start_time": null,
		"finish_time": null,
		"description": "",
		"is_started": false,
		"is_finished": false,
		"is_revoked": false,
		"is_deleted": false,
		"is_expired": false,
		"snapshot_id": 3,
		"execution_snapshot_id": 8,
		"tree_info_id": null,
		"extra_info": {}
	},
	"code": "0",
	"message": ""
}
```

### Error response examples

The template is not bound to a bk_app_code:
```json
{
    "result": false,
    "message": "Template is not bindedto any bk_app_code. template_id=3"
}
```

bk_app_code mismatch:
```json
{
    "result": false,
    "message": "The current application does not have permission to operate this template, app=other_app, template bindedapp=your_app"
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

| Field                    | Type     | Description       |
|-----------------------|--------|----------|
| id                    | int    | Task ID     |
| space_id              | int    | Space ID     |
| scope_type            | string | Task scope type   |
| scope_value           | string | Task scope value    |
| instance_id           | string | Instance ID     |
| template_id           | int    | Template ID     |
| name                  | string | Task name     |
| creator               | string | Created by      |
| create_time           | string | Creation time     |
| executor              | string | Executor      |
| start_time            | string | Start time     |
| finish_time           | string | End time     |
| description           | string | Description       |
| is_started            | bool   | Whether started    |
| is_finished           | bool   | Whether finished    |
| is_revoked            | bool   | Whether revoked    |
| is_deleted            | bool   | Whether deleted    |
| is_expired            | bool   | Whether expired    |
| snapshot_id           | int    | Snapshot ID     |
| execution_snapshot_id | int    | Execution snapshot ID   |
| tree_info_id          | int    | Task topology ID |
| extra_info            | dict   | Additional task information   |
