### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get third-party plugins (SDK endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### Permissions

This endpoint uses the default permissions. **BKFLOW-TOKEN is not required**.

### Endpoint parameters

| Field          | Type     | Required | Description     |
|-------------|--------|----|--------|
| code        | string | No  | Plugin code   |
| name        | string | No  | Plugin name   |
| space_id    | int    | No  | Space ID   |
| tag         | int    | No  | Plugin category ID |
| manager     | string | No  | Administrator    |
| search_term | string | No  | Search keyword  |

### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "space_id": 123,
    "tag": 4
}
```

### Response example

```json
{
     "result": true,
     "data": {
          "count": 9,
          "plugins": [
               {
                    "code": "test",
                    "name": "示例插件",
                    "tag": 4,
                    "logo_url": "https://example/bk_plugin_app_default.png",
                    "created_time": "2025-04-13 16:53:09 +0800",
                    "updated_time": "2025-05-14 15:48:46 +0800",
                    "introduction": "",
                    "managers": [
                         "xxx"
                    ],
                    "extra_info": {}
               }
          ]
     },
     "message": "",
     "code": "0"
}
```

### Response parameters

| Field        | Type     | Description                    |
|-----------|--------|-----------------------|
| result    | bool   | Operation result: true for success, false for failure |
| code      | string | Response code: 0 for success, any other value for failure     |
| message   | string | Error message                  |
| data      | list   | Response data: plugin list             |

#### data[plugins] fields

| Field           | Type      | Description        |
|--------------|---------|-----------|
| code         | string  | Plugin code      |
| name         | string  | Plugin name      |
| tag          | int     | Plugin category    |
| logo_url     | string  | Plugin image URL   |
| created_time | string  | Plugin creation time    |
| updated_time | string  | Plugin update time    |
| introduction | string  | Plugin summary      |
| managers     | list    | Plugin administrator list   |
| extra_info   | dict    | Additional information      |
