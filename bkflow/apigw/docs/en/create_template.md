### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

In multi-tenant mode, subprocesses, nested sub-canvases, and converted subprocess plugins in the workflow tree may reference only valid templates in the current space. Disabling multi-tenancy preserves existing reference behavior. Historical version queries are always bound to their owning template.

### Resource description

Create a template

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

#### Endpoint parameters

| Field                    | Type     | Required  | Description                  |
|-----------------------|--------|-----|---------------------|
| name                  | string | Yes   | Template name                |
| creator               | string | No   | Created by                 |
| source_template_id    | int    | No   | Source template ID (for copying into a new template)    |
| notify_config         | json   | No   | Template description                |
| desc                  | string | No   | Space description                |
| scope_type            | string | No   | Template scope type              |
| scope_value           | string | No   | Template scope value               |
| source                | string | No   | Template source (custom field supplied by the space integrator)    |
| version               | string | No   | Template version (custom field supplied by the space integrator)    |
| bind_app_code         | string | No   | Bound application code for application-based authorization |
| extra_info            | string | No   | Additional template information              |
| pipeline_tree         | string | No   | Template information                |
| auto_release          | bool   | No   | Whether to publish automatically              |
| label_ids             | list   | No   | List of tag IDs              |
| webhook_configs       | json   | No   | Webhook configuration           |

When source_template_id is provided, the new template uses the source template's pipeline_tree.
This creates a template based on an existing template. Only source templates in the same space are allowed.

When pipeline_tree is provided, the new template uses the supplied tree. If both pipeline_tree and source_template_id are supplied,
the source template's pipeline_tree takes precedence.

### Gateway expression validation

When creating a template, the endpoint validates the **branch gateway expression language** in `pipeline_tree`. Expressions in all `ExclusiveGateway` / `ConditionalParallelGateway` nodes must use the space's gateway expression setting (`gateway_expression`, default: `boolrule`).

Validation rules:

- Legacy data without an explicit `extra_info.parse_lang` defaults to `boolrule`.
- Validation fails if a gateway's `parse_lang` differs from the space setting.
- Gateways embedded in subprocesses (`SubCanvas` / `SubProcess`) are validated recursively.
- When copying through `source_template_id`, the final saved tree (the source template's `pipeline_tree`) undergoes the same validation.


### notify_config example

```json
{
  "notify_type": {
    "success": [
      "weixin",
      "wecom_robot",
      "sms"
    ],
    "fail": [
      "mail",
      "voice",
      "weixin",
      "wecom_robot"
    ]
  },
  "notify_receivers": {
    "receiver_group": [],
    "more_receiver": ""
  }
}
```

### webhook_configs example
```json
{
  "method": "POST",
  "endpoint": "xxx",
  "extra_info": {
    "headers": [
      {
        "key": "Content-Type",
        "value": "application/json",
        "doc": ""
      }
    ],
    "timeout": 10,
    "retry_times": 2,
    "interval": 60
  }
}
```

### Request example

```json
{
  "bk_app_code": "xxxx",
  "bk_app_secret": "xxxx",
  "bk_username or bk_token": "xxxx",
  "name": "模板名",
  "label_ids": [1, 2, 3]
}
```

### Response example

```json
{
  "result": true,
  "data": {
    "id": 4,
    "space_id": "2",
    "name": "模板名",
    "labels": [],
    "desc": null,
    "notify_config": {},
    "scope_type": null,
    "scope_value": null,
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
    "creator": "",
    "create_at": "2024-08-02T08:53:20.173Z",
    "update_at": "2024-08-02T08:53:20.173Z",
    "updated_by": "",
    "enable_webhook": false,
    "webhook_configs":{}
  },
  "code": 0
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

| Field              | Type     | Description           |
|-----------------|--------|--------------|
| id              | string | Workflow ID         |
| space_id        | string | Space ID of the workflow     |
| name            | string | Workflow name         |
| desc            | string | Workflow description         |
| notify_config   | dict   | Notification settings         |
| scope_type      | string | Workflow scope type       |
| scope_value     | string | Workflow scope ID       |
| pipeline_tree   | dict   | Workflow tree details        |
| source          | string | Workflow source         |
| version         | string | Workflow version         |
| is_enabled      | bool   | Whether the workflow is enabled       |
| extra_info      | dict   | Extended workflow information       |
| creator         | string | Workflow creator        |
| create_at       | string | Workflow creation time       |
| update_at       | string | Workflow update time       |
| updated_by      | string | Workflow updater        |
| labels          | list   | Tag list (array of tag objects) |
| enable_webhook  | bool   | Webhook enabled    |
| webhook_configs | dict   | Webhook configuration    |
