### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get workflow snapshot list (SDK endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### HTTP header parameters

| Parameter         | Type   | Required | Description                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | Yes  | Access token obtained from `/space/{space_id}/apply_token/`. This token verifies the user's permission to access resources in the specified space (template_id or task_id is required). |

### Endpoint parameters

| Field          | Type     | Required | Description      |
|-------------|--------|----|---------|
| template_id | string | Yes  | Workflow ID    |
| version     | string | No  | Workflow snapshot version number |
| operator    | string | No  | Operator     |
| desc        | string | No  | Workflow version description  |


### Request example

```
GET /sdk/template/snapshot/list_snapshot/
```

### Response example

```json
{
     "result": true,
     "data": {
          "count": 3,
          "next": null,
          "previous": null,
          "results": [
               {
                    "id": 123,
                    "create_time": "2025-05-22 11:00:20+0800",
                    "update_time": "2025-05-22 11:00:20+0800",
                    "version": null,
                    "template_id": 1023,
                    "desc": "基于 1.0.0 版本的草稿",
                    "draft": true,
                    "creator": "xxx",
                    "operator": "xxx",
                    "md5sum": "18ce84fe15xlt0075edc4413a9f5575b"
               }
          ]
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

| Field      | Type       | Description       |
|---------|----------|----------|
| count   | int      | Total number of paginated records |
| results | list     | Response data     |


#### data[results] fields

| Field          | Type     | Description              |
|-------------|--------|-----------------|
| id          | int    | Snapshot ID            |
| create_time | string | Data creation time          |
| update_time | string | Data update time          |
| version     | string | Workflow version number (drafts have no version number) |
| template_id | string | Associated template ID         |
| desc        | string | Workflow version description          |
| draft       | bool   | Whether this is a draft         |
| creator     | string | Created by             |
| operator    | string | Operator             |
| md5sum      | string | MD5 hash of the workflow data       |
