### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Update a space variable


### Common authentication parameters
| Parameter          | Type     | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### Path parameters

| Parameter        | Type      | Required  | Description         |
|-------------|---------|-----|--------------|
| space_id    | int     | Yes   | Space ID         |
| variable_id | int     | Yes   | Variable ID         |

#### Request body

| Field            | Type       | Required  | Description                               |
|---------------|----------|-----|----------------------------------|
| name          | string   | No   | Variable name                              |
| key           | string   | No   | Variable key; must be unique within the space                   |
| variable_type | string   | No   | Variable type: space (space-level) or scope (scope-level) |
| value         | string   | No   | Variable value                              |
| desc          | string   | No   | Variable description                             |

### variable_type parameter

The `variable_type` parameter specifies the variable scope. Currently, the space type is supported.


### Request example

```json
{
    "name": "新的数据库连接地址",
    "desc": "更新后的数据库连接地址描述",
    "variable_type": "space",
    "value": "new-db-host:3306"
}
```

### Response example

```json
{
    "result": true,
    "code": 0,
    "data": {
        "id": 1,
        "space_id": 6,
        "name": "新的数据库连接地址",
        "key": "db_host",
        "variable_type": "space",
        "value": "new-db-host:3306",
        "desc": "更新后的数据库连接地址描述",
        "creator": "admin",
        "create_at": "2024-01-15T10:30:00.000000+08:00",
        "updated_by": "admin",
        "update_at": "2024-01-15T11:30:00.000000+08:00"
    }
}
```

### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| code    | int    | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | dict   | Response data                  |

#### data[item]

| Field            | Type      | Description          |
|---------------|---------|-------------|
| id            | int     | Variable ID        |
| space_id      | int     | Space ID        |
| name          | string  | Variable name         |
| key           | string  | Variable key       |
| variable_type | string  | Variable type        |
| value         | string  | Variable value         |
| desc          | string  | Variable description        |
| creator       | string  | Created by         |
| create_at     | string  | Creation time        |
| updated_by    | string  | Last updated by       |
| update_at     | string  | Last update time      |
