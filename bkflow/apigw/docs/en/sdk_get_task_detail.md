### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Retrieve task details (SDK API)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### HTTP header parameters

| Parameter         | Type   | Required | Description                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | Yes  | Access token obtained from `/space/{space_id}/apply_token/`. This token verifies the user's permission to view the specified task. |

### Path parameters

| Field        | Type     | Required | Description   |
|-----------|--------|----|------|
| task_id   | string | Yes  | Task ID |

### Endpoint parameters

| Field                | Type     | Required | Description     |
|-------------------|--------|----|--------|
| space_id          | int    | Yes  | Space ID   |


### Example of returned results
```json
{
     "result": true,
     "data": {
          "id": 15,
          "create_time": "2026-11-13 14:31:20+0800",
          "start_time": "2026-11-13 14:31:23+0800",
          "finish_time": "2026-11-13 14:31:23+0800",
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
               },
               "template_version": "1.0.1"
          },
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
          "outputs": [],
          "elapsed_time": 0,
          "space_id": 240,
          "tenant_id": "default",
          "scope_type": null,
          "scope_value": null,
          "instance_id": "n6e42c60e7ab3d229d7341dcdf7908c8",
          "template_id": 2211,
          "name": "xxx",
          "creator": "xxx",
          "create_method": "API",
          "trigger_method": "manual",
          "executor": "xxx",
          "description": "",
          "is_started": true,
          "is_finished": true,
          "is_revoked": false,
          "is_deleted": false,
          "is_expired": false,
          "snapshot_id": 100,
          "execution_snapshot_id": 100,
          "tree_info_id": 100,
          "auth": [
               "VIEW",
               "OPERATE",
               "FLOW_VIEW",
               "FLOW_EDIT",
               "FLOW_MOCK"
          ],
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
| code    | string | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | dict   | Response data                  |

#### data.nodes[item] fields

| Field                    | Type      | Description                                              |
|--------------------------|-----------|----------------------------------------------------------|
| id                       | int       | Task ID                                                  |
| create_time              | string    | Task creation time                                       |
| start_time               | string    | Task start time                                          |
| finish_time              | string    | Task finish time                                         |
| extra_info               | dict      | Task extra information, including the notification config `notify_config` and template version `template_version`, etc. |
| pipeline_tree            | dict      | The pipeline tree corresponding to the task              |
| outputs                  | list      | Task output variable list                                |
| elapsed_time             | int       | Task elapsed time (in seconds)                           |
| space_id                 | int       | Space ID that the task belongs to                        |
| tenant_id                | string    | Tenant ID that the task belongs to                       |
| scope_type               | string    | Task scope type (e.g. business/project); null when empty |
| scope_value              | string    | Task scope value; null when empty                        |
| instance_id              | string    | Pipeline engine instance ID (runtime identifier)         |
| template_id              | int       | Source template ID of the task                           |
| name                     | string    | Task name                                                |
| creator                  | string    | Task creator                                             |
| create_method            | string    | Creation method                                          |
| trigger_method           | string    | Trigger method                                           |
| executor                 | string    | Task executor                                            |
| description              | string    | Task description                                         |
| is_started               | bool      | Whether the task has started                             |
| is_finished              | bool      | Whether the task has finished                            |
| is_revoked               | bool      | Whether the task has been revoked                        |
| is_deleted               | bool      | Whether the task has been deleted                        |
| is_expired               | bool      | Whether the task has expired                             |
| snapshot_id              | int       | Task template snapshot ID                                |
| execution_snapshot_id    | int       | Task execution snapshot ID                               |
| tree_info_id             | int       | Pipeline tree info ID                                    |
| auth                     | list      | Permission list of the current requesting user for the task |
| webhook_delivery_history | list      | Webhook delivery history list                            |

