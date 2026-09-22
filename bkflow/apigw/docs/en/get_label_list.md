### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get tag list

### Common authentication parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| bk_app_code | string | Yes | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| bk_app_secret | string | Yes | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

#### Endpoint parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| offset | int | No | Offset; default: 0 |
| limit | int | No | Number of records; default: 100, maximum: 200 |
| label_scope | string | No | Filter by tag scope: `task`, `template`, `common` |
| parent_id | int | No | Parent tag ID. If omitted, the endpoint returns root tags (and also includes parents of matching child tags for compatibility). |
| name | string | No | Tag name, fuzzy match |
| is_default | bool | No | Whether this is a default tag |
| include_children | bool | No | Whether to include child tags |
| order_by | string | No | Sort field; default: `-updated_at`. Allowed: `created_at`, `updated_at`, `name`, `-created_at`, `-updated_at`, `-name` |

### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "offset": 0,
    "limit": 20,
    "label_scope": "task"
}
```

### Response example

```json
{
    "result": true,
    "data": [
        {
            "id": 1,
            "name": "标签名",
            "creator": "tester",
            "updated_by": "tester",
            "space_id": 1,
            "color": "#ffffff",
            "description": "",
            "created_at": "2024-08-02T08:53:20.173Z",
            "updated_at": "2024-08-02T08:53:20.173Z",
            "label_scope": ["task"],
            "is_default": false,
            "has_children": true,
            "full_path": "标签名",
            "parent_id": null
        }
    ],
    "count": 1,
    "code": 0
}
```

### Response parameters

| Field | Type | Description |
| --- | --- | --- |
| result | bool | Operation result: true for success, false for failure |
| code | int | Response code: 0 for success, any other value for failure |
| message | string | Error message |
| count | int | Total number of records |
| data | list | Response data |

#### data[item]

| Field | Type | Description |
| --- | --- | --- |
| id | int | Tag ID |
| name | string | Tag name |
| creator | string | Created by |
| updated_by | string | Updated by |
| space_id | int | Space ID (may be -1 for default tags) |
| color | string | Tag color |
| description | string | Tag description |
| created_at | string | Creation time |
| updated_at | string | Update time |
| label_scope | list | Tag scopes |
| is_default | bool | Whether this is a default tag |
| has_children | bool | Whether it has child tags |
| full_path | string | Full tag path |
| parent_id | int/null | Parent tag ID |
