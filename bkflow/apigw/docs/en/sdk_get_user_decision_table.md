### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get user decision table plugins (SDK endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### HTTP header parameters

| Parameter         | Type   | Required | Description                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | Yes  | Access token obtained from `/space/{space_id}/apply_token/`. This token verifies the user's permission to access the specified space and template. |

### Endpoint parameters

| Field         | Type     | Required | Description       |
|------------|--------|----|----------|
| space_id   | int    | No  | Space ID     |
| template_id | int    | No  | Template ID     |

### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "space_id": 1,
    "template_id": 1
}
```

### Response example

```json
{
  "result": true,
  "data": {
    "count": 29,
    "next": "",
    "previous": null,
    "results": [
      {
        "id": 66,
        "create_at": "2025-06-23 17:07:48+0800",
        "update_at": "2025-06-23 17:07:48+0800",
        "creator": "v_jinhpeng",
        "updated_by": "v_jinhpeng",
        "is_deleted": false,
        "name": "新画布决策",
        "desc": "",
        "space_id": 1,
        "template_id": 1222,
        "scope_type": "",
        "scope_value": "",
        "data": {
          "inputs": [
            {
              "id": "fieldf90fc9ce",
              "desc": "",
              "from": "inputs",
              "name": "文本",
              "tips": "",
              "type": "string"
            }
          ],
          "outputs": [
            {
              "id": "fieldfc79a383",
              "desc": "",
              "from": "outputs",
              "name": "数字",
              "tips": "",
              "type": "int"
            }
          ],
          "records": [
            {
              "inputs": {
                "type": "common",
                "conditions": [
                  {
                    "right": {
                      "obj": {
                        "type": "string",
                        "value": "11"
                      },
                      "type": "value"
                    },
                    "compare": "equals"
                  }
                ]
              },
              "outputs": {
                "fieldfc79a383": 22
              }
            }
          ]
        },
        "table_type": "single",
        "extra_info": {}
      }
    ]
  },
  "code": "0",
  "message": ""
}
```

### Response parameters

| Field       | Type      | Description                    |
|----------|---------|-----------------------|
| result   | bool    | Operation result: true for success, false for failure |
| code     | string  | Response code: 0 for success, any other value for failure     |
| message  | string  | Error message                  |
| data     | dict    | Response data                  |

#### data[item] fields

| Field          | Type     | Description    |
|-------------|--------|-------|
| id          | int    | Decision table ID |
| space_id    | int    | Space ID  |
| template_id | int    | Template ID  |
| name        | string | Decision table name |
| desc        | string | Decision table description |
| data        | dict   | Decision table data |
| create_at   | string | Creation time  |
| update_at   | string | Update time  |
| creator     | string | Created by   |
| updated_by  | string | Updated by   |
| is_deleted  | bool   | Whether deleted  |
| scope_type  | string | Scope type |
| scope_value | string | Scope value  |
