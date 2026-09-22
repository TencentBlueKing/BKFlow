### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get the tag tree

### Common authentication parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| bk_app_code | string | Yes | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| bk_app_secret | string | Yes | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

#### Endpoint parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| label_scope | string | No | Filter by tag scope: `task`, `template`, `common` |
| offset | int | No | Root-node pagination offset (only roots are paginated; subtrees remain intact) |
| limit | int | No | Root-node page size (only roots are paginated; subtrees remain intact); maximum: 200 |


### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "label_scope": "task",
    "task_ids": "1001,1002",
    "offset": 0,
    "limit": 50
}
```

### Response example

```json
{
    "result": true,
    "data": [
        {
            "id": 1,
            "name": "父标签",
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
            "full_path": "父标签",
            "parent_id": null,
            "children": [
                {
                    "id": 2,
                    "name": "子标签",
                    "creator": "tester",
                    "updated_by": "tester",
                    "space_id": 1,
                    "color": "#ffffff",
                    "description": "",
                    "created_at": "2024-08-02T08:53:20.173Z",
                    "updated_at": "2024-08-02T08:53:20.173Z",
                    "label_scope": ["task"],
                    "is_default": false,
                    "has_children": false,
                    "full_path": "父标签/子标签",
                    "parent_id": 1,
                    "children": []
                }
            ]
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
| count | int | Number of root nodes before pagination |
| data | list | Tag tree (root node list) |

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
| has_children | bool | Whether it has children (populated from children in the tree) |
| full_path | string | Full tag path |
| parent_id | int/null | Parent tag ID |
| children | list | Child node list (recursive) |
