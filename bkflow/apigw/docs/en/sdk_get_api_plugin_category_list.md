### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get Uniform API plugins (SDK endpoint)

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

| Field            | Type     | Required | Description      |
|---------------|--------|----|---------|
| space_id      | string | Yes  | Space ID    |


### Endpoint parameters

| Field            | Type     | Required | Description      |
|---------------|--------|----|---------|
| template_id   | int    | No  | Template ID    |
| task_id       | int    | No  | Task ID    |
| api_name      | string | No  | API_KEY |

Note: supply at least one of template_id and task_id.

### Request example

```
GET /sdk/plugin_query/uniform_api/category_list/{space_id}/
```

### Response example

```json
{
    "result": true,
    "data": [
        {
            "id": 1,
            "name": "model",
            "alias": "模型",
            "properties": {
                "llm": "大模型"
            }
        }
    ],
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
| data    | list   | Response data                  |

#### data[item] fields

| Field         | Type       | Description   |
|------------|----------|------|
| id         | int      | Plugin ID |
| name       | string   | Plugin name |
| alias      | string   | Plugin alias |
| properties | dict     | Plugin attributes |
