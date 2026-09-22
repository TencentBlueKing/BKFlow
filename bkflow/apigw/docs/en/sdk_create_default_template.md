### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Create a workflow (SDK endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### Permissions

The user must be a system superuser or a superuser of the specified space. **BKFLOW-TOKEN is not required**.

### Path parameters

| Field      | Type     | Required | Description   |
|---------|--------|----|------|
| space_id | string | Yes  | Space ID |

### Endpoint parameters

| Field            | Type     | Required | Description               |
|---------------|--------|----|------------------|
| name          | string | Yes  | Template name             |
| desc          | string | No  | Template description             |
| notify_config | json   | No  | Notification settings             |
| scope_type    | string | No  | Template scope type           |
| scope_value   | string | No  | Template scope value            |
| source        | string | No  | Template source (custom field supplied by the space integrator) |
| extra_info    | dict   | No  | Additional template information           |
| label_ids     | list   | No  | List of tag IDs |

### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "新流程",
    "desc": "流程描述",
    "label_ids": [1, 2, 3]
}
```

### Response example

```json
{
    "result": true,
    "data": {
        "id": 4,
        "space_id": 2,
        "name": "新流程",
        "desc": "流程描述",
        "notify_config": {},
        "scope_type": null,
        "scope_value": null,
        "pipeline_tree": {},
        "source": null,
        "version": "",
        "is_enabled": true,
        "extra_info": {}
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

See the data field descriptions in `sdk_fetch_template.md`.
