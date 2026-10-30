### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource Description

Retrieve snapshot details (SDK API)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### HTTP header parameters

| Parameter         | Type   | Required | Description                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | Yes  | Access token obtained from `/space/{space_id}/apply_token/`. This token verifies the user's permission to view the specified template. |

### Endpoint parameters

| Field      | Type     | Required | Description   |
|-------------|--------|----|------|
| snapshot_id | string | Yes  | Snapshot ID |


### Request example

```json
{
    "result": true,
    "data": {
        "id": 341,
        "create_time": "2026-10-28 11:46:36+0800",
        "update_time": "2026-10-28 11:46:36+0800",
        "version": "1.0.0",
        "template_id": 85,
        "desc": null,
        "draft": false,
        "auto_save": false,
        "creator": "xxx",
        "operator": "xxx",
        "md5sum": "xxx",
        "pipeline_tree": {
            "activities": {
                "n02ab8bbb0fd34e592ed90ad3f700220": {
                    "component": {
                        "code": "sleep_timer",
                        "data": {
                            "bk_timing": {
                                "hook": false,
                                "need_render": true,
                                "value": "5"
                            },
                            "force_check": {
                                "hook": false,
                                "need_render": true,
                                "value": true
                            }
                        },
                        "version": "legacy"
                    },
                    "error_ignorable": false,
                    "id": "n02ab8bbb0fd34e592ed90ad3f700220",
                    "incoming": [
                        "lbffdeddc2ee355489df5042d899ecf8"
                    ],
                    "loop": null,
                    "name": "定时",
                    "optional": true,
                    "outgoing": "l9d0c2ed80c334dfa8ca27de212be7ff",
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
            "canvas_mode": "horizontal",
            "constants": {},
            "end_event": {
                "id": "n1dbc0a5f0243409a1bf338dedb76ee0",
                "incoming": [
                    "l9d0c2ed80c334dfa8ca27de212be7ff"
                ],
                "name": "",
                "outgoing": "",
                "type": "EmptyEndEvent",
                "labels": []
            },
            "flows": {
                "lbffdeddc2ee355489df5042d899ecf8": {
                    "id": "lbffdeddc2ee355489df5042d899ecf8",
                    "is_default": false,
                    "source": "n403483bfc7f37f48329c51c518b3b2a",
                    "target": "n02ab8bbb0fd34e592ed90ad3f700220"
                },
                "l9d0c2ed80c334dfa8ca27de212be7ff": {
                    "id": "l9d0c2ed80c334dfa8ca27de212be7ff",
                    "is_default": false,
                    "source": "n02ab8bbb0fd34e592ed90ad3f700220",
                    "target": "n1dbc0a5f0243409a1bf338dedb76ee0"
                }
            },
            "gateways": {},
            "line": [
                {
                    "id": "lbffdeddc2ee355489df5042d899ecf8",
                    "source": {
                        "arrow": "Right",
                        "id": "n403483bfc7f37f48329c51c518b3b2a"
                    },
                    "target": {
                        "arrow": "Left",
                        "id": "n02ab8bbb0fd34e592ed90ad3f700220"
                    }
                },
                {
                    "id": "l9d0c2ed80c334dfa8ca27de212be7ff",
                    "source": {
                        "arrow": "Right",
                        "id": "n02ab8bbb0fd34e592ed90ad3f700220"
                    },
                    "target": {
                        "arrow": "Left",
                        "id": "n1dbc0a5f0243409a1bf338dedb76ee0"
                    }
                }
            ],
            "location": [
                {
                    "id": "n403483bfc7f37f48329c51c518b3b2a",
                    "type": "startpoint",
                    "x": 40,
                    "y": 150
                },
                {
                    "id": "n02ab8bbb0fd34e592ed90ad3f700220",
                    "type": "tasknode",
                    "name": "定时",
                    "stage_name": "",
                    "x": 240,
                    "y": 140,
                    "group": "蓝鲸服务(BK)",
                    "icon": ""
                },
                {
                    "id": "n1dbc0a5f0243409a1bf338dedb76ee0",
                    "type": "endpoint",
                    "x": 540,
                    "y": 150
                }
            ],
            "outputs": [],
            "start_event": {
                "id": "n403483bfc7f37f48329c51c518b3b2a",
                "incoming": "",
                "name": "",
                "outgoing": "lbffdeddc2ee355489df5042d899ecf8",
                "type": "EmptyStartEvent",
                "labels": []
            },
            "stage_canvas_data": [
                {
                    "id": "nodec6ec7e8bb4d3fb5ffcea70b6a19f",
                    "name": "",
                    "config": [],
                    "jobs": [
                        {
                            "id": "nodedc2dde0ef8ce42fd678df273ce6d",
                            "name": "",
                            "config": [],
                            "nodes": [
                                {
                                    "id": "node35d8a3338718018e90b1bcb7976a",
                                    "type": "Node"
                                }
                            ],
                            "type": "Job"
                        }
                    ],
                    "type": "Stage"
                }
            ]
        }
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
| data    | dict   | Return data              |


#### data Field Descriptions

| Field      | Type     | Description                    |
|--------------|--------|--------|
| id           | int    | Snapshot ID   |
| create_time  | string | Creation time   |
| update_time  | string | Update time   |
| version      | string | Released template version |
| template_id  | int    | Associated template ID |
| desc         | string | Snapshot description   |
| draft        | bool   | Whether it is a draft snapshot |
| auto_save    | bool   | Whether it is an auto-saved snapshot |
| creator      | string | Creator    |
| operator     | string | Latest operator  |
| md5sum     | string | Process MD5 hash  |
| pipeline_tree | dict  | Pipeline data |
