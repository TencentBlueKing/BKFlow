### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Update and replace space configuration

### Common authentication parameters
| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

#### Endpoint parameters

| Field     | Type   | Required | Description   |
|--------|------|----|------|
| config | json | Yes  | Space configuration |

#### Space settings
| Field                          | Type     | Required | Description                                                          |
|-----------------------------|--------|----|-------------------------------------------------------------|
| space_plugin_config         | json   | No  | Space plugin configuration                                                      |
| token_expiration            | string | No  | Token lifetime; default: 1 hour                                             |
| token_auto_renewal          | string | No  | Whether tokens renew automatically (default: enabled). Tokens renew during user operations to prevent expiration during use. |
| callback_hooks              | json   | No  | Callback configuration; prefer apply_webhook_configs                    |
| uniform_api                 | json   | No  | Uniform API configuration                                                     |
| api_gateway_credential_name | json   | No  | Default gateway credential name                                                 |
| superusers                  | json   | No  | Space administrator list; default: []                                              |
| canvas_mode                 | string | No  | Canvas layout: "horizontal" or "vertical"; default: horizontal            |

### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "config": {
        "token_auto_renewal": "true"
    }
}
```

### Response example

```json
{
    "result": true,
    "data": {
        "space_id": 2,
        "config": [
            {
                "key": "token_auto_renewal",
                "value": "true"
            },
            {
                "key": "token_expiration",
                "value": "1h"
            }
        ]
    },
    "code": 0,
    "trace_id": "ecb0dd8707194245a5a88b7f0e3b3c16"
}
```

### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| code    | int    | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | dict   | Current space configuration details            |

#### data[item]

| Field       | Type   | Description     |
|----------|------|--------|
| space_id | int  | Space ID   |
| config   | list | Space configuration list |
