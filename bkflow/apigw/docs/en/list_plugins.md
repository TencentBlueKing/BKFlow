### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Query available plugins in a space

#### Description

Query available plugins in the specified space, with type filtering, keyword search, and pagination.

When `plugin_type=uniform_api`, open plugins with `wrapper_version=v4.0.0` include only catalog entries enabled in the current space. Existing V2/V3 API plugins still return the original remote `meta_url` list and are unaffected by catalog enablement.

#### HTTP method

GET

#### Request parameters

| Parameter | Type | Required | Description |
|------|------|------|------|
| keyword | string | No | Fuzzy search by code or name |
| plugin_type | string | No | Filter by type: component, remote_plugin, uniform_api |
| plugin_source | string | No | Open plugin source type; filters only `uniform_api v4.0.0` catalog entries |
| with_detail | bool | No | Default: false (summaries only); true returns complete schemas |
| scope_type | string | No | Scope type |
| scope_id | string | No | scope ID |
| limit | int | No | Page size; default: 100, maximum: 200 |
| offset | int | No | Pagination offset; default: 0 |

#### Response parameters

| Parameter | Type | Description |
|------|------|------|
| result | bool | Whether the request succeeded |
| code | int | Error code; 0 for success |
| count | int | Total plugin count |
| data | array | Plugin list |
| data[].code | string | Plugin code |
| data[].name | string | Plugin name |
| data[].plugin_type | string | Plugin type |
| data[].version | string | Plugin version |
| data[].description | string | Plugin description |
| data[].group_name | string | Group name |
| data[].inputs | array | Input parameter list (returned when with_detail=true) |
| data[].outputs | array | Output parameter list (returned when with_detail=true) |

Open plugins using `uniform_api v4.0.0` are additionally controlled by space enablement: only enabled plugins appear in the list. These switches do not apply to existing V2/V3 plugins.

#### Request example

```bash
curl -X GET 'http://{host}/space/1/list_plugins/?plugin_type=component&keyword=脚本&limit=10'
```

#### Response example

```json
{
    "result": true,
    "code": 0,
    "count": 1,
    "data": [
        {
            "code": "job_fast_execute_script",
            "name": "快速执行脚本",
            "plugin_type": "component",
            "version": "v1.0.0",
            "description": "",
            "group_name": "作业平台(JOB)"
        }
    ]
}
```
