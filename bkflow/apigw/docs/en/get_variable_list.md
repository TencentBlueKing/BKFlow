### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get space variable list


### Common authentication parameters
| Parameter          | Type     | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### Path parameters

| Parameter       | Type     | Required   | Description |
|------------|--------|------|------|
| space_id   | int    | Yes    | Space ID |

#### Request body

| Field            | Type      | Required  | Description     |
|---------------|---------|-----|--------|
| name          | string  | No   | Variable name    |
| variable_type | string  | No   | Variable type   |
| key           | string  | No   | Variable key  |

### Request example

```json
{
    "key": "db_host",
    "variable_type": "space"
}
```

### Response example

```json
{
    "result": true,
    "code": 0,
    "data": [
        {
            "id": 1,
            "space_id": 6,
            "name": "数据库连接地址",
            "key": "db_host",
            "variable_type": "space",
            "value": "localhost:3306",
            "desc": "主数据库连接地址",
            "creator": "admin",
            "create_at": "2024-01-15T10:30:00.000000+08:00",
            "updated_by": "admin",
            "update_at": "2024-01-15T11:30:00.000000+08:00"
        }
    ]
}
```


### Response parameters

| Field       | Type     | Description                    |
|----------|--------|-----------------------|
| result   | bool   | Operation result: true for success, false for failure |
| code     | int    | Response code: 0 for success, any other value for failure     |
| message  | string | Error message                  |
| data     | list   | Response data list                |

#### data[item]

| Field            | Type       | Description          |
|---------------|----------|-------------|
| id            | int      | Variable ID        |
| space_id      | int      | Space ID        |
| name          | string   | Variable name         |
| key           | string   | Variable key       |
| variable_type | string   | Variable type        |
| value         | string   | Variable value         |
| desc          | string   | Variable description        |
| creator       | string   | Created by         |
| create_at     | string   | Creation time        |
| updated_by    | string   | Last updated by       |
| update_at     | string   | Last update time      |
