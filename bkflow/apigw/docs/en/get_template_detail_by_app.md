### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get workflow details with bk_app_code authorization

This endpoint accesses workflows bound to a bk_app_code. The requester's bk_app_code must match the code bound to the template.

**Note: user authentication is required.**

### Common authentication parameters
| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| bk_username   | string | Yes  | Username for user authentication                                                 |

### Endpoint parameters

| Field              | Type     | Required | Description                                                                                                                                           |
|-----------------|--------|----|----------------------------------------------------------------------------------------------------------------------------------------------|
| with_mock_data  | bool   | No  | Whether to include mock data; default: false. When true, appoint_node_ids and mock_data are included, and pipeline_tree is pruned if appoint_node_ids specifies mock execution nodes. |
| format          | string | No  | Response format: raw (default, original format), pipeline_tree (same as raw), or plugin (plugin data structure). |


Path parameters:

| Field      | Type     | Required | Description                                              |
|---------|--------|----|-------------------------------------------------|
| template_id | int | Yes  | Template ID |

### Permissions

- The template must be bound to a bk_app_code (through bind_app_code when creating the template).
- The requester's bk_app_code must match the code bound to the template.
- User authentication is required.

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
        "bk_app_code": "your_app_code",
        "pipeline_tree": {
            "id": "p92c20c7854104dd3975f46a1d8664417",
            "start_event": {
                "incoming": "",
                "outgoing": "f06a78d1dcbe64fb79136b07eb7e71309",
                "type": "EmptyStartEvent",
                "id": "ec628b28ea1c74e11b92b6be3bdc0e1b6",
                "name": null
            },
            "end_event": {
                "incoming": [
                    "f5b91a6141a504b1b86f932d7e6c021f0"
                ],
                "outgoing": "",
                "type": "EmptyEndEvent",
                "id": "e7533e78a1a724b51942fcdf63fa23a60",
                "name": null
            },
            "activities": {},
            "gateways": {},
            "flows": {},
            "data": {
                "inputs": {},
                "outputs": []
            }
        },
        "source": null,
        "version": "",
        "is_enabled": true,
        "extra_info": {}
    },
    "code": 0,
    "trace_id": "xxxxxxxxx"
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

### Data fields

| Field               | Type       | Description                                                             |
|------------------|----------|----------------------------------------------------------------|
| id               | int      | Workflow ID                                                          |
| space_id         | int      | Space ID of the workflow                                                     |
| name             | string   | Workflow name                                                           |
| desc             | string   | Workflow description                                                           |
| notify_config    | dict     | Workflow notification settings                                                         |
| scope_type       | string   | Workflow scope type                                                       |
| scope_value      | string   | Workflow scope value                                                        |
| bk_app_code      | string   | Bound BlueKing application code                                                       |
| pipeline_tree    | dict     | Workflow tree; pruned when with_mock_data is true                     |
| source           | string   | Workflow source: resource ID in the third-party system                                           |
| version          | string   | Workflow version: resource version in the third-party system                                         |
| is_enabled       | bool     | Whether enabled                                                           |
| extra_info       | dict     | Additional information                                                           |
| creator          | string   | Workflow creator                                                          |
| create_at        | datetime | Creation time                                                           |
| updated_by       | string   | Workflow updater                                                          |
| update_at        | datetime | Update time                                                           |
| appoint_node_ids | list     | Returned when with_mock_data is true: IDs of nodes selected for mock execution              |
| mock_data        | list     | Returned when with_mock_data is true: each item contains node_id, data, and is_default |

### Response example for format=plugin

When format is plugin, the endpoint returns the plugin data structure:

```json
{
    "result": true,
    "data": {
        "desc": "插件描述信息",
        "version": "0.0.1",
        "enable_plugin_callback": true,
        "inputs": {
            "type": "object",
            "properties": {
                "param1": {
                    "title": "参数1",
                    "type": "string"
                }
            },
            "required": ["param1"],
            "definitions": {}
        },
        "outputs": {
            "type": "object",
            "properties": {
                "output1": {
                    "title": "输出1",
                    "type": "string"
                }
            },
            "required": ["output1"],
            "definitions": {}
        },
        "context_inputs": {
            "type": "object",
            "properties": {
                "executor": {
                    "title": "任务执行人",
                    "type": "string"
                }
            },
            "required": ["executor"],
            "definitions": {}
        },
        "forms": {
            "renderform": "(function () { ... })();"
        },
        "app": {
            "url": "http://example.com/",
            "urls": ["http://example.com/"],
            "name": "示例应用",
            "code": "example-app"
        }
    },
    "code": 0,
    "trace_id": "xxxxxxxxx"
}
```

### Data fields for format=plugin

| Field                   | Type     | Description                                        |
|----------------------|--------|-------------------------------------------|
| desc                 | string | Plugin description                                    |
| version              | string | Plugin version number                                     |
| enable_plugin_callback | bool   | Whether plugin callbacks are enabled                                  |
| inputs               | object | Plugin input parameter JSON Schema                       |
| outputs              | object | Plugin output parameter JSON Schema                       |
| context_inputs       | object | Plugin context input parameter JSON Schema                    |
| forms                | object | Form configuration, including renderform                    |
| app                  | object | Application information, including url, urls, name, code, etc.          |
