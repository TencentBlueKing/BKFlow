### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Publish a workflow (backend endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |


### Path parameters

| Field          | Type     | Required | Description   |
|-------------|--------|----|------|
| template_id | string | Yes  | Workflow ID |

### Endpoint parameters

| Field        | Type     | Required | Description     |
|-----------|--------|----|--------|
| force     | bool   | No  | Whether to force publication |
| version   | string | Yes  | Published version number  |
| desc      | string | No  | Version description   |


### Request example

```
POST /sdk/template/{template_id}/release_template/
```

### Response example

```json
{
     "result": true,
     "data": {
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
          "notify_config": {
               "notify_type": {
                    "fail": [],
                    "success": []
               },
               "notify_receivers": {
                    "more_receiver": "",
                    "receiver_group": []
               }
          },
          "version": "1.0.4",
          "desc": null,
          "subprocess_info": [],
          "creator": "xxx",
          "create_at": "2025-05-19T11:34:00.551630+08:00",
          "update_at": "2025-05-22T12:13:42.270250+08:00",
          "updated_by": "xxx",
          "space_id": 1,
          "name": "test",
          "scope_type": null,
          "scope_value": null,
          "source": null,
          "is_enabled": true,
          "extra_info": {}
     },
     "code": 0
}
```

### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| code    | int    | Response code: 0 for success, any other value for failure     |
| data    | dict   | Response data                  |



### Data fields

| Field              | Type       | Description       |
|-----------------|----------|----------|
| id              | string   | Workflow ID     |
| space_id        | string   | Space ID of the workflow |
| name            | string   | Workflow name     |
| desc            | string   | Workflow description     |
| notify_config   | dict     | Notification settings     |
| scope_type      | string   | Workflow scope type   |
| scope_value     | string   | Workflow scope ID   |
| pipeline_tree   | dict     | Workflow tree details    |
| source          | string   | Workflow source     |
| version         | string   | Workflow version     |
| is_enabled      | bool     | Whether the workflow is enabled   |
| extra_info      | dict     | Extended workflow information   |
| creator         | string   | Workflow creator    |
| create_at       | string   | Workflow creation time   |
| update_at       | string   | Workflow update time   |
| updated_by      | string   | Workflow updater    |
