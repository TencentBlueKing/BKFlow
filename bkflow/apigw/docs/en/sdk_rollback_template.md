### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Roll back a workflow (SDK endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### HTTP header parameters

| Parameter         | Type   | Required | Description                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | Yes  | Access token obtained from `/space/{space_id}/apply_token/`. This token verifies the user's permission to access resources in the specified space (template_id or task_id is required). |

### Path parameters

| Field          | Type     | Required | Description   |
|-------------|--------|----|------|
| template_id | string | Yes  | Workflow ID |

### Endpoint parameters

| Field        | Type     | Required   | Description       |
|-----------|--------|------|----------|
| version   | string | Yes    | Version to roll back to |


### Request example

```
POST /sdk/template/{template_id}/rollback_template/
```

### Response example

```json
{
     "result": true,
     "data": {
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
| data    | dict   | Workflow data after rollback              |
