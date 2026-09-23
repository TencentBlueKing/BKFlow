### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Create a task

The server derives the task tenant from the target space. Callers need not supply `tenant_id`; a request-body field with that name cannot override the space's tenant.

### Common authentication parameters
|   Parameter   |    Type  |  Required  |     Description     |
| ------------ | ------------ | ------ | ---------------- |
| bk_app_code   | string | Yes | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| bk_app_secret | string | Yes | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |


#### Endpoint parameters

| Field                    | Type     | Required | Description                                    |
|----------------------|--------|----|---------------------------------------|
| creator               | string | Yes  | Created by                                    |
| pipeline_tree         | json   | Yes  | Task structure tree                                  |
| name                  | string | No  | Task name                                    |
| scope_type            | string | No  | Task scope type                                 |
| scope_value           | string | No  | Task scope value                                  |
| description           | string | No  | Description                                    |
| constants             | json   | No  | Task startup parameters                                |
| custom_span_attributes | dict   | No  | Custom Span attributes added to the execution root Span and every node Span; see below |

### Open plugin governance

If `pipeline_tree` contains BK-SOPS open plugins (`uniform_api v4.0.0`), the server checks the following before creating the task:

- The plugin still exists in the current space's open plugin catalog.
- The plugin is available.
- The plugin's business version remains in the catalog's available version list.
- The plugin is enabled in the current space.

After validation, BKFlow writes open plugin reference and schema snapshots to the task's `extra_info` for execution and historical inspection.

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
        "env": "prod"
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
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "creator": "创建者",
    "pipeline_tree": {
        "name": "test",
        "activities": {
            "nf834705dbbb37c59ad114aa37314975": {
                "component": {
                    "code": "bk_display",
                    "data": {
                        "bk_display_message": {
                            "hook": false,
                            "need_render": true,
                            "value": ""
                        }
                    },
                    "version": "v1.0"
                },
                "error_ignorable": false,
                "id": "nf834705dbbb37c59ad114aa37314975",
                "incoming": [
                    "lee4ca362c673536958aa656cb36efda"
                ],
                "loop": null,
                "name": "消息展示",
                "optional": true,
                "outgoing": "l2e819009a9a3714ab108ad5c594bb73",
                "stage_name": "",
                "type": "ServiceActivity",
                "retryable": true,
                "skippable": true,
                "auto_retry": {
                    "enable": false,
                    "interval": 0,
                    "times": 1
                },
                "timeout_config": {
                    "enable": false,
                    "seconds": 10,
                    "action": "forced_fail"
                },
                "labels": []
            }
        },
        "end_event": {
            "id": "n2dfd1233f633cdf864fc3681eb2b0b3",
            "incoming": [
                "l2e819009a9a3714ab108ad5c594bb73"
            ],
            "name": "",
            "outgoing": "",
            "type": "EmptyEndEvent",
            "labels": []
        },
        "flows": {
            "lee4ca362c673536958aa656cb36efda": {
                "id": "lee4ca362c673536958aa656cb36efda",
                "is_default": false,
                "source": "n1df1598dba137aba81094851379435a",
                "target": "nf834705dbbb37c59ad114aa37314975"
            },
            "l2e819009a9a3714ab108ad5c594bb73": {
                "id": "l2e819009a9a3714ab108ad5c594bb73",
                "is_default": false,
                "source": "nf834705dbbb37c59ad114aa37314975",
                "target": "n2dfd1233f633cdf864fc3681eb2b0b3"
            }
        },
        "gateways": {},
        "line": [
            {
                "id": "lee4ca362c673536958aa656cb36efda",
                "source": {
                    "arrow": "Right",
                    "id": "n1df1598dba137aba81094851379435a"
                },
                "target": {
                    "arrow": "Left",
                    "id": "nf834705dbbb37c59ad114aa37314975"
                }
            },
            {
                "id": "l2e819009a9a3714ab108ad5c594bb73",
                "source": {
                    "arrow": "Right",
                    "id": "nf834705dbbb37c59ad114aa37314975"
                },
                "target": {
                    "arrow": "Left",
                    "id": "n2dfd1233f633cdf864fc3681eb2b0b3"
                }
            }
        ],
        "location": [
            {
                "id": "n1df1598dba137aba81094851379435a",
                "type": "startpoint",
                "x": 40,
                "y": 150
            },
            {
                "id": "nf834705dbbb37c59ad114aa37314975",
                "type": "tasknode",
                "name": "消息展示",
                "stage_name": "",
                "x": 240,
                "y": 140,
                "group": "蓝鲸服务(BK)",
                "icon": "",
                "optional": true,
                "error_ignorable": false,
                "retryable": true,
                "skippable": true,
                "auto_retry": {
                    "enable": false,
                    "interval": 0,
                    "times": 1
                },
                "timeout_config": {
                    "enable": false,
                    "seconds": 10,
                    "action": "forced_fail"
                }
            },
            {
                "id": "n2dfd1233f633cdf864fc3681eb2b0b3",
                "type": "endpoint",
                "x": 540,
                "y": 150
            }
        ],
        "outputs": [],
        "start_event": {
            "id": "n1df1598dba137aba81094851379435a",
            "incoming": "",
            "name": "",
            "outgoing": "lee4ca362c673536958aa656cb36efda",
            "type": "EmptyStartEvent",
            "labels": []
        },
        "constants": {},
        "projectBaseInfo": {},
        "notify_receivers": {
            "receiver_group": [],
            "more_receiver": ""
        },
        "notify_type": {
            "success": [],
            "fail": []
        },
        "template_labels": [],
        "internalVariable": {
            "${_system.task_name}": {
                "key": "${_system.task_name}",
                "name": "任务名称",
                "index": -1,
                "desc": "",
                "show_type": "hide",
                "source_type": "system",
                "source_tag": "",
                "source_info": {},
                "custom_type": "",
                "value": "",
                "hook": false,
                "validation": ""
            },
            "${_system.task_id}": {
                "key": "${_system.task_id}",
                "index": -2,
                "name": "任务ID",
                "desc": "",
                "show_type": "hide",
                "source_type": "system",
                "source_tag": "",
                "source_info": {},
                "custom_type": "",
                "value": "",
                "hook": false,
                "validation": ""
            },
            "${_system.task_start_time}": {
                "key": "${_system.task_start_time}",
                "name": "任务开始时间",
                "index": -3,
                "desc": "",
                "show_type": "hide",
                "source_type": "system",
                "source_tag": "",
                "source_info": {},
                "custom_type": "",
                "value": "",
                "hook": false,
                "validation": ""
            },
            "${_system.operator}": {
                "key": "${_system.operator}",
                "name": "任务的执行人（点击开始执行的人员）",
                "index": -4,
                "desc": "",
                "show_type": "hide",
                "source_type": "system",
                "source_tag": "",
                "source_info": {},
                "custom_type": "",
                "value": "",
                "hook": false,
                "validation": ""
            }
        },
        "spaceId": 1,
        "scopeInfo": {
            "scope_type": null,
            "scope_value": null
        }
    }
}
```

Request example with custom Span attributes:
```json
{
    "creator": "创建者",
    "pipeline_tree": {
        "name": "test",
        "activities": {},
        "end_event": {},
        "flows": {},
        "gateways": {},
        "start_event": {},
        "constants": {}
    },
    "name": "测试任务",
    "custom_span_attributes": {
        "business_id": "12345",
        "request_id": "req-abc-123",
        "env": "prod"
    }
}
```

### Response example

```json
{
    "result": true,
    "data": {
        "id": 93,
        "space_id": 1,
        "scope_type": null,
        "scope_value": null,
        "instance_id": "nb2bf870164336798522536f036a4da7",
        "template_id": null,
        "name": "default_taskflow_instance",
        "creator": "创建者",
        "create_time": "2023-10-16T17:24:07.859339+08:00",
        "executor": "",
        "start_time": null,
        "finish_time": null,
        "description": "",
        "is_started": false,
        "is_finished": false,
        "is_revoked": false,
        "is_deleted": false,
        "is_expired": false,
        "snapshot_id": 80,
        "execution_snapshot_id": 77,
        "tree_info_id": null,
        "extra_info": {
            "notify_config": {
                "notify_type": {
                    "fail": [],
                    "success": []
                },
                "notify_receivers": {
                    "more_receiver": "",
                    "receiver_group": []
                }
            }
        }
    },
    "code": "0",
    "message": ""
}

```

Failure example when an open plugin is not enabled:

```json
{
    "result": false,
    "code": 400,
    "data": null,
    "message": "开放插件 [open_plugin_001] 在当前空间未开放"
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
