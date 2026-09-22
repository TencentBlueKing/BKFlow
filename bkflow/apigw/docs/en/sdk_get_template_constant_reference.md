### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get variable reference statistics (SDK endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### HTTP header parameters

| Parameter         | Type   | Required | Description                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | Yes  | Access token obtained from `/space/{space_id}/apply_token/`. This token verifies the user's permission to access the specified space. |

### Endpoint parameters

| Field          | Type   | Required  | Description          |
|-------------|------|-----|-------------|
| constants   | dict | Yes   | Global variables defined in the workflow  |
| activities  | dict | Yes   | Activity nodes in the workflow    |
| gateways    | dict | Yes   | Gateway nodes in the workflow    |

### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "constants": {
        "var1": {
            "key": "var1",
            "name": "变量1",
            "value": "value1"
        }
    },
    "activities": {},
    "gateways": {}
}
```

### Response example

```json
{
     "result": true,
     "data": {
          "defined": {
               "var1": {
                    "activities": ["node1", "node2"],
                    "conditions": [],
                    "constants": []
               }
          },
          "nodefined": {
               "${undefined_var}": {
                    "activities": ["node3"],
                    "conditions": [],
                    "constants": []
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
| data    | dict   | Response data                  |

#### Data fields

| Field       | Type   | Description                    |
|----------|------|-----------------------|
| defined  | dict | Defined variables and their reference locations          |
| nodefined | dict | Undefined variables and their reference locations          |

#### defined[node_key] and nodefined[node_key] fields

| Field        | Type     | Description                    |
|-----------|--------|-----------------------|
| activities | list | IDs of activity nodes referencing the variable        |
| conditions | list | IDs of condition nodes referencing the variable        |
| constants  | list | IDs of other constants referencing the variable        |
