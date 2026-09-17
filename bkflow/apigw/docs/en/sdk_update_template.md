### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Save a workflow (SDK endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### HTTP header parameters

| Parameter         | Type   | Required | Description                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | Yes  | Access token obtained from `/space/{space_id}/apply_token/`. This token verifies the user's permission to edit the specified template. |

### Path parameters

| Field         | Type     | Required | Description    |
|------------|--------|----|-------|
| template_id | string | Yes  | Workflow template ID |

### Endpoint parameters

| Field            | Type     | Required | Description               |
|---------------|--------|----|------------------|
| name          | string | Yes  | Template name             |
| operator      | string | No  | Updated by              |
| notify_config | json   | No  | Notification settings             |
| desc          | string | No  | Template description             |
| scope_type    | string | No  | Template scope type           |
| scope_value   | string | No  | Template scope value            |
| source        | string | No  | Template source (custom field supplied by the space integrator) |
| version       | string | No  | Template version (custom field supplied by the space integrator) |
| extra_info    | dict   | No  | Additional template information           |
| pipeline_tree | dict   | Yes  | Workflow tree              |
| triggers      | list   | Yes  | Workflow triggers            |

### notify_config example

```json
{
  "notify_type": {
    "success": ["weixin", "wecom_robot", "sms"],
    "fail": ["mail", "voice", "weixin", "wecom_robot"]
  },
  "notify_receivers": {
    "receiver_group": [],
    "more_receiver": ""
  }
}
```

### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "更新后的模板名",
    "desc": "更新后的描述",
    "pipeline_tree": {
        "id": "pd0980c284042448380d29e046bf348fc",
        "start_event": {
            "incoming": "",
            "outgoing": "f22d707b4e7704868b51fbc504107da27",
            "type": "EmptyStartEvent",
            "id": "e39ce14ef5df644ccaa5236b50a9c44ca",
            "name": null
        },
        "end_event": {
            "incoming": [
                "f520808740b9945f8b01fa1dd889945d9"
            ],
            "outgoing": "",
            "type": "EmptyEndEvent",
            "id": "e17aef95ed6934a428215b2a7a3fa4184",
            "name": null
        },
        "activities": {
            "e36e8026b07b5448299b52f91a9d265af": {
                "incoming": [
                    "f22d707b4e7704868b51fbc504107da27"
                ],
                "outgoing": "f520808740b9945f8b01fa1dd889945d9",
                "type": "ServiceActivity",
                "id": "e36e8026b07b5448299b52f91a9d265af",
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
            "f22d707b4e7704868b51fbc504107da27": {
                "is_default": false,
                "source": "e39ce14ef5df644ccaa5236b50a9c44ca",
                "target": "e36e8026b07b5448299b52f91a9d265af",
                "id": "f22d707b4e7704868b51fbc504107da27"
            },
            "f520808740b9945f8b01fa1dd889945d9": {
                "is_default": false,
                "source": "e36e8026b07b5448299b52f91a9d265af",
                "target": "e17aef95ed6934a428215b2a7a3fa4184",
                "id": "f520808740b9945f8b01fa1dd889945d9"
            }
        }
    },
    "triggers": []
}
```

### Response example

```json
{
    "result": true,
    "data": {
        "id": 4,
        "space_id": 2,
        "name": "更新后的模板名",
        "desc": "更新后的描述",
        "notify_config": {},
        "scope_type": null,
        "scope_value": null,
        "pipeline_tree": {},
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

| Field            | Type     | Description       |
|---------------|--------|----------|
| id            | int    | Workflow ID     |
| space_id      | int    | Space ID of the workflow |
| name          | string | Workflow name     |
| desc          | string | Workflow description     |
| notify_config | dict   | Notification settings     |
| scope_type    | string | Workflow scope type   |
| scope_value   | string | Workflow scope ID   |
| pipeline_tree | dict   | Workflow tree details    |
| source        | string | Workflow source     |
| version       | string | Workflow version     |
| is_enabled    | bool   | Whether the workflow is enabled   |
| extra_info    | dict   | Extended workflow information   |



### Periodic trigger timezone

`triggers[].config.timezone` accepts a valid IANA timezone (for example `Europe/Paris`). When omitted on creation, the effective user timezone of the request is saved. When omitted on update, the existing schedule timezone is preserved. Legacy schedules without this field retain the timezone already stored in Engine, regardless of the editor. Returned config retains timezone for new schedules; the UI uses it for display and previews.
