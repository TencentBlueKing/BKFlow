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

#### Interface parameters

| Field | Type | Required | Description                                 |
|------------|--------|----------|---------------------------------------------|
| task_ids   | string | YES      | Task ID，separate multiple IDs with commas. |


### Response example

```json
{
    "result": true,
    "data": {
        "1": {
            "activities": {
                "n8698713071f3c19a8c65ad6cf21d8fb": {
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
                    "id": "n8698713071f3c19a8c65ad6cf21d8fb",
                    "incoming": [
                        "l48e87eb2fe23073a6cdfe354f7395b1"
                    ],
                    "loop": null,
                    "name": "消息展示",
                    "optional": true,
                    "outgoing": "lab4348a155931a99841d4b2fd1c4b2b",
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
                    "labels": [],
                    "template_node_id": "n36ab89190e73486ac44df57717e52fa"
                }
            },
            "canvas_mode": "horizontal",
            "constants": {},
            "end_event": {
                "id": "n7ee43b7bef03c6997b1bb4ecd98585f",
                "incoming": [
                    "lab4348a155931a99841d4b2fd1c4b2b"
                ],
                "name": "",
                "outgoing": "",
                "type": "EmptyEndEvent",
                "labels": []
            },
            "flows": {
                "l48e87eb2fe23073a6cdfe354f7395b1": {
                    "id": "l48e87eb2fe23073a6cdfe354f7395b1",
                    "is_default": false,
                    "source": "n2f89c1efe273024abb8c4c230e372ac",
                    "target": "n8698713071f3c19a8c65ad6cf21d8fb"
                },
                "lab4348a155931a99841d4b2fd1c4b2b": {
                    "id": "lab4348a155931a99841d4b2fd1c4b2b",
                    "is_default": false,
                    "source": "n8698713071f3c19a8c65ad6cf21d8fb",
                    "target": "n7ee43b7bef03c6997b1bb4ecd98585f"
                }
            },
            "gateways": {},
            "line": [
                {
                    "id": "l48e87eb2fe23073a6cdfe354f7395b1",
                    "source": {
                        "arrow": "Right",
                        "id": "n2f89c1efe273024abb8c4c230e372ac"
                    },
                    "target": {
                        "arrow": "Left",
                        "id": "n8698713071f3c19a8c65ad6cf21d8fb"
                    }
                },
                {
                    "id": "lab4348a155931a99841d4b2fd1c4b2b",
                    "source": {
                        "arrow": "Right",
                        "id": "n8698713071f3c19a8c65ad6cf21d8fb"
                    },
                    "target": {
                        "arrow": "Left",
                        "id": "n7ee43b7bef03c6997b1bb4ecd98585f"
                    }
                }
            ],
            "location": [
                {
                    "id": "n2f89c1efe273024abb8c4c230e372ac",
                    "type": "startpoint",
                    "x": 40,
                    "y": 150
                },
                {
                    "id": "n8698713071f3c19a8c65ad6cf21d8fb",
                    "type": "tasknode",
                    "name": "消息展示",
                    "stage_name": "",
                    "x": 240,
                    "y": 140,
                    "group": "蓝鲸服务(BK)",
                    "icon": ""
                },
                {
                    "id": "n7ee43b7bef03c6997b1bb4ecd98585f",
                    "type": "endpoint",
                    "x": 540,
                    "y": 150
                }
            ],
            "outputs": [],
            "start_event": {
                "id": "n2f89c1efe273024abb8c4c230e372ac",
                "incoming": "",
                "name": "",
                "outgoing": "l48e87eb2fe23073a6cdfe354f7395b1",
                "type": "EmptyStartEvent",
                "labels": []
            },
            "stage_canvas_data": [
                {
                    "id": "node079af7eeec4ca7af387b6ae2b08f",
                    "name": "",
                    "config": [],
                    "jobs": [
                        {
                            "id": "nodeb79ceaa6ce4457c7956e539193bf",
                            "name": "",
                            "config": [],
                            "nodes": [
                                {
                                    "id": "node37fbb15738f875854cc238bd0dd0",
                                    "type": "Node"
                                }
                            ],
                            "type": "Job"
                        }
                    ],
                    "type": "Stage"
                }
            ],
            "id": "n2f4614f1ed135a18eabbe9157f198ad"
        }
    },
    "code": "0",
    "message": ""
}
```

### Description of returned result parameters

| Field   | Type     | Description                                                                                                                      |
|---------|----------|----------------------------------------------------------------------------------------------------------------------------------|
| result  | bool     | Returns the result: true for success, false for failure.                                                                         |
| code    | string   | Return code: 0 indicates success, while other values indicate failure.                                                           |
| message | string   | error message                                                                                                                    |
| data    | dict     | The returned data consists of key-value pairs where the key is the task ID and the value is the pipeline structure of that task. |

