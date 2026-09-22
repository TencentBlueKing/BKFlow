### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get workflow details

### Common authentication parameters
| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### Endpoint parameters

| Field              | Type     | Required | Description                                                                                                                                           |
|-----------------|--------|----|----------------------------------------------------------------------------------------------------------------------------------------------|
| with_mock_data  | bool   | No  | Whether to include mock data; default: false. When true, appoint_node_ids and mock_data are included, and pipeline_tree is pruned if appoint_node_ids specifies mock execution nodes. |
| format          | string | No  | Response format: raw (default, original format), pipeline_tree (same as raw), or plugin (plugin data structure). |


Path parameters:

| Field      | Type     | Required | Description                                              |
|---------|--------|----|-------------------------------------------------|
| template_id | string | Yes  | Node ID, obtainable from get_task_detail or get_task_states |

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
            "activities": {
                "e2945819d402e41a9b9f8252a1b806f1c": {
                    "incoming": [
                        "f06a78d1dcbe64fb79136b07eb7e71309"
                    ],
                    "outgoing": "f5b91a6141a504b1b86f932d7e6c021f0",
                    "type": "ServiceActivity",
                    "id": "e2945819d402e41a9b9f8252a1b806f1c",
                    "name": null,
                    "error_ignorable": false,
                    "timeout": null,
                    "skippable": true,
                    "retryable": true,
                    "component": {
                        "code": "example_component",
                        "inputs": {}
                    },
                    "optional": false
                }
            },
            "gateways": {},
            "flows": {
                "f06a78d1dcbe64fb79136b07eb7e71309": {
                    "is_default": false,
                    "source": "ec628b28ea1c74e11b92b6be3bdc0e1b6",
                    "target": "e2945819d402e41a9b9f8252a1b806f1c",
                    "id": "f06a78d1dcbe64fb79136b07eb7e71309"
                },
                "f5b91a6141a504b1b86f932d7e6c021f0": {
                    "is_default": false,
                    "source": "e2945819d402e41a9b9f8252a1b806f1c",
                    "target": "e7533e78a1a724b51942fcdf63fa23a60",
                    "id": "f5b91a6141a504b1b86f932d7e6c021f0"
                }
            },
            "data": {
                "inputs": {},
                "outputs": []
            }
        },
        "source": null,
        "version": "",
        "is_enabled": true,
        "extra_info": {},
        "triggers": []
    },
    "code": 0,
    "trace_id": "xxxxxxxxx"
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

| Field                | Type       | Description                                                             |
|-------------------|----------|----------------------------------------------------------------|
| id                | int      | Workflow ID                                                          |
| space_id          | int      | Space ID of the workflow                                                     |
| name              | string   | Workflow name                                                           |
| desc              | string   | Workflow description                                                           |
| notify_config     | dict     | Workflow notification settings                                                         |
| scope_type        | string   | Workflow scope type                                                      |
| scope_value       | string   | Workflow scope value                                                       |
| pipeline_tree     | dict     | Workflow tree; pruned when with_mock_data is true                     |
| source            | string   | Workflow source: resource ID in the third-party system                                           |
| version           | string   | Workflow version: resource version in the third-party system                                         |
| is_enabled        | bool     | Whether enabled                                                           |
| extra_info        | dict     | Additional information                                                           |
| create            | string   | Workflow creator                                                          |
| create_at         | datetime | Creation time                                                           |
| update_by         | string   | Workflow updater                                                          |
| update_at         | datetime | Update time                                                           |
| appoint_node_ids  | list     | Returned when with_mock_data is true: IDs of nodes selected for mock execution              |
| mock_data         | list     | Returned when with_mock_data is true: each item contains node_id, data, and is_default |
| triggers          | list     | Trigger configuration                                                          |

### data[triggers] fields

| Field          | Type       | Description     |
|-------------|----------|--------|
| id          | int      | Trigger ID |
| space_id    | int      | Space ID  |
| create_at   | datetime | Creation time   |
| update_at   | datetime | Update time   |
| config      | dict     | Schedule configuration   |
| updated_by  | string   | Updated by    |
| creator     | string   | Created by    |
| template_id | string   | Template ID   |
| is_deleted  | bool     | Whether deleted   |
| is_enabled  | bool     | Whether enabled   |
| name        | string   | Trigger name  |
| type        | string   | Trigger type  |

### Response example for format=plugin

When format is plugin, the endpoint returns the plugin data structure:

```json
{
    "result": true,
    "data": {
        "id": 3,
        "name": "测试模板",
        "desc": "模板描述信息",
        "version": "1.0.0",
        "space_id": 2,
        "scope_type": null,
        "scope_value": null,
        "creator": "admin",
        "create_at": "2024-01-01T00:00:00Z",
        "updated_by": "admin",
        "update_at": "2024-01-02T00:00:00Z",
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
                },
                "task_name": {
                    "title": "任务名称",
                    "type": "string"
                },
                "task_id": {
                    "title": "任务ID",
                    "type": "string"
                },
                "task_space_id": {
                    "title": "任务空间ID",
                    "type": "string"
                }
            },
            "required": ["executor", "task_name", "task_id", "task_space_id"],
            "definitions": {}
        }
    },
    "code": 0,
    "trace_id": "xxxxxxxxx"
}
```

### Data fields for format=plugin

| Field                   | Type     | Description                                        |
|----------------------|--------|-------------------------------------------|
| id                   | int    | Workflow ID                                     |
| name                 | string | Workflow name                                      |
| desc                 | string | Workflow description                                      |
| version              | string | Workflow version number                                     |
| space_id             | int    | Space ID                                     |
| scope_type           | string | Workflow scope type                                 |
| scope_value          | string | Workflow scope value                                  |
| creator              | string | Created by                                       |
| create_at            | datetime | Creation time                                    |
| updated_by           | string | Updated by                                       |
| update_at            | datetime | Update time                                    |
| inputs               | object | Input parameter JSON Schema, parsed from pipeline_tree       |
| outputs              | object | Output parameter JSON Schema, parsed from pipeline_tree       |
| context_inputs       | object | Context input parameter JSON Schema                       |
### Periodic trigger timezone

`triggers[].config.timezone` accepts a valid IANA timezone (for example `Europe/Paris`). When omitted on creation, the effective user timezone of the request is saved. When omitted on update, the existing schedule timezone is preserved. Legacy schedules without this field retain the timezone already stored in Engine, regardless of the editor. Returned config retains timezone for new schedules; the UI uses it for display and previews.
