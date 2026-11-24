### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Canvas unified plugin picker list (SDK endpoint)

Backs the canvas "Select Plugin" panel: the left directory tree and the right plugin card list are returned by this single endpoint. Only plugins with `enable` status are returned, consistent with the plugin management page. This endpoint does not accept `scope_type` / `scope_id`.

### Common authentication parameters

| Parameter | Type | Required | Description |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code | string | Yes | Application ID, available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| bk_app_secret | string | Yes | Application secret, available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### HTTP header parameters

| Parameter | Type | Required | Description |
|--------------|--------|----|------------------------------------------------------------|
| X-Bk-Tenant-Id | string | No | Required for all-tenant apps when multi-tenancy is enabled; may be omitted by single-tenant apps; must match the resource space tenant |

### Endpoint parameters

| Field | Type | Required | Description |
|------------|---------|-----|----------|
| space_id | int | Yes | Space ID |
| directory_id | string | No | Directory filter: all/recommend/uncategorized/specific directory id, default all |
| plugin_type | string | No | Plugin type: all/builtin/bk_plugin/api, default all |
| keyword | string | No | Fuzzy match on name or description, default "" |
| ordering | string | No | Ordering: recommend/-publish_time/publish_time/name/-usage_count/usage_count, default recommend |
| page | int | No | Page number, starting from 1 (minimum 1), default 1 |
| page_size | int | No | Page size, range 1-200, default 20 |

### Request example

```
GET /api/plugin_catalog/plugins/picker/?space_id=1&plugin_type=api&keyword=HTTP&page=1&page_size=20
```

### Response example

```json
{
    "result": true,
    "data": {
        "count": 42,
        "page": 1,
        "page_size": 20,
        "results": [
            {
                "plugin_type": "builtin",
                "source_key": "builtin",
                "plugin_code": "bk_http_request",
                "plugin_name": "HTTP Request",
                "plugin_desc": "Run a script on the specified host",
                "recommended": true,
                "directory_path": ["Common", "Flow Control"],
                "usage_count": 46
            }
        ],
        "directories": {
            "tree": [
                {"id": 1, "name": "Common", "order": 1, "count": 11,
                 "children": [{"id": 2, "name": "Flow Control", "order": 1, "count": 5, "children": []}]}
            ],
            "total_count": 234,
            "recommend_count": 6,
            "uncategorized_count": 34
        }
    },
    "message": "",
    "code": "0"
}
```

### Response parameters

| Field | Type | Description |
|---------|--------|-----------------------|
| result | bool | Operation result: true for success, false for failure |
| code | string | Response code: 0 for success, any other value for failure |
| message | string | Error message |
| data | dict | Response data |

#### data fields

| Field | Type | Description |
|------------|--------|------|
| count | int | Total of the right-hand list (enabled plugins only) |
| page | int | Current page number |
| page_size | int | Page size |
| results | list | Plugin card list |
| directories | dict | Left directory tree and counts, enabled plugins only |

#### results[item] fields

| Field | Type | Description |
|------------|--------|------|
| plugin_type | string | Plugin type |
| source_key | string | Source id |
| plugin_code | string | Plugin code |
| plugin_name | string | Plugin display name |
| plugin_desc | string | Plugin description |
| recommended | bool | Whether recommended by the space |
| directory_path | array | Directory path array, [] if uncategorized |
| usage_count | int | Number of distinct flows referencing this plugin |

#### directories fields

| Field | Type | Description |
|------------|--------|------|
| tree | array | Directory tree, nodes contain id/name/order/count/children |
| total_count | int | Space plugins count |
| recommend_count | int | Space recommendations count |
| uncategorized_count | int | Uncategorized plugins count |
