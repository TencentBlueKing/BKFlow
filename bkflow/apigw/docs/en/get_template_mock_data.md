### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get workflow mock data

### Common authentication parameters
| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### Endpoint parameters

| Field      | Type     | Required | Description                      |
|---------|--------|----|-------------------------|
| node_id | string | No  | Filter mock data by node ID |


### Response example

```json
{
    "result": true,
    "data": [
        {
            "id": 1,
            "name": "Mock 数据方案1",
            "space_id": 1,
            "template_id": 1,
            "node_id": "nd64fbd5440932ee9658d47029751f46",
            "data": {
                "callback_data": {
                    "abc": "123"
                }
            },
            "is_default": true,
            "extra_info": null,
            "operator": "admin",
            "create_at": "2024-09-14T15:24:39.075179+08:00",
            "update_at": "2024-09-14T15:24:39.075289+08:00"
        }
    ],
    "code": 0,
    "message": ""
}
```
### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| code    | int    | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | list   | Response data                  |

### data[item]

| Field          | Type     | Description               |
|-------------|--------|------------------|
| id          | int    | Mock data ID       |
| name        | string | Mock data name        |
| space_id    | int    | Space ID of the mock data   |
| template_id | int    | Workflow template ID of the mock data |
| node_id     | string | Node ID of the mock data   |
| data        | dict   | Mock data content        |
| is_default  | bool   | Whether this is the default mock data    |
| extra_info  | dict   | Additional information             |
| operator    | string | Operator              |
| create_at   | string | Creation time             |
| update_at   | string | Update time             |
