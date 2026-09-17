### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get a task node configuration snapshot

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
| node_id   | string | Yes  | Node ID |

### Endpoint parameters

| Field        | Type  | Required | Description   |
|-----------|-----|----|------|
| space_id  | int | Yes  | Space ID |


### Response example

```json
{
     "result": true,
     "message": "success",
     "data": {
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
          "id": "nd08100455cb3f47b1be3e352d508650",
          "incoming": [
               "line3c5a376461d0e836213d39aee346"
          ],
          "name": "定时",
          "optional": true,
          "outgoing": "line1504dcca7856c15db80344ab1549",
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
}
```

### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| message | string | Error message                  |
| data    | dict   | Response data                  |
| page    | dict   | Pagination information                |

#### Data fields

| Field              | Type     | Description     |
|-----------------|--------|--------|
| component       | dict   | Node field information |
| error_ignorable | bool   | Whether skipped on failure |
| id              | string | Node ID   |
| incoming        | list   | Node in-degree   |
| name            | string | Node name   |
| optional        | dict   | Whether optional   |
| outgoing        | dict   | Node out-degree   |
| stage_name      | dict   | Step name   |
| type            | string | Node type   |
| retryable       | bool   | Whether retry is allowed |
| skippable       | bool   | Whether skipping is allowed |
| auto_retry      | dict   | Node retry configuration |
| timeout_config  | dict   | Node timeout configuration |
| labels          | list   | Node tags   |
