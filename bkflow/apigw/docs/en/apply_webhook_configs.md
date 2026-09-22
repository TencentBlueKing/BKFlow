### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Apply space webhook configuration

### Common authentication parameters
| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

#### Endpoint parameters

| Field       | Type   | Required | Description                                                            |
|----------|------|----|---------------------------------------------------------------|
| webhooks | list | Yes  | Webhook list; each item defines one webhook. Every call replaces the current space's webhook configuration. |

#### Webhook configuration
| Field         | Type     | Required | Description                                                                                                                                                    |
|------------|--------|----|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| code       | string | Yes  | Unique webhook code                                                                                                                                        |
| name       | string | Yes  | Webhook name                                                                                                                                            |
| endpoint   | string | Yes  | Webhook request URL                                                                                                                                          |
| events     | list   | Yes  | Subscribed events: template_update, template_create, template_release, task_failed, task_finished, task_create, task_paused, task_resumed, task_revoked |
| extra_info | json   | No  | Additional extended information                                                                                                                                                |

### Request example

```json
{
    "webhooks": [
        {
            "code": "webhook1",
            "name": "webhook1",
            "endpoint": "http://webhook1.com",
            "events": ["template_update", "template_create", "template_release"]
        },
        {
            "code": "webhook2",
            "name": "webhook2",
            "endpoint": "http://webhook2.com",
            "events": ["task_failed", "task_finished", "task_create", "task_paused", "task_resumed", "task_revoked"]
        }
    ]
}
```

### Example with additional parameters
```json
{
     "webhooks": [
          {
               "code": "webhook1",
               "name": "webhook1",
               "endpoint": "http://webhook1.com",
               "events": ["template_update","template_create"],
               "extra_info": {
                    "authorization": {
                         "type": "basic",
                         "username": "123",
                         "password": "123",
                         "token": "123"
                    },
                    "headers": [
                         {
                              "key": "Content-Type",
                              "value": "application/json",
                              "doc": ""
                         }
                    ],
                    "timeout": 10,
                    "retry_times": 2,
                    "interval": 60
               }
          }
     ]
}
```

### Response example

```json
{
    "result": true,
    "message": "success",
    "data": {},
    "code": 0
}
```

### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| code    | int    | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | dict   | Response data                  |
