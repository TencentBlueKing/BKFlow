### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Validate an a2flow v2 workflow definition

#### Description

Dry-run validation of an a2flow v2 workflow definition. Returns structured validation results without creating a template.

#### HTTP method

POST

#### Request parameters

| Parameter | Type | Required | Description |
|------|------|------|------|
| a2flow | object | Yes | a2flow v2 JSON definition |
| scope_type | string | No | Scope type |
| scope_value | string | No | Scope value |

#### Response parameters

| Parameter | Type | Description |
|------|------|------|
| result | bool | Whether the request succeeded |
| code | int | Error code |
| data.valid | bool | Whether the workflow is valid |
| data.version | string | a2flow version |
| data.node_count | int | Number of nodes |
| data.plugin_codes | array | List of plugin codes used |
| errors | array | List of validation errors |

#### Request example

```bash
curl -X POST 'http://{host}/space/1/validate_a2flow/' \
  -H 'Content-Type: application/json' \
  -d '{"a2flow": {"version": "2.0", "name": "测试", "nodes": [...]}}'
```

#### Successful response example

```json
{
    "result": true,
    "code": 0,
    "data": {
        "valid": true,
        "version": "2.0",
        "node_count": 3,
        "plugin_codes": ["job_fast_execute_script", "bk_notify"]
    }
}
```

#### Failed response example

```json
{
    "result": false,
    "code": 400,
    "errors": [
        {
            "type": "UNKNOWN_PLUGIN",
            "node_id": "n1",
            "field": "code",
            "value": "invalid_plugin",
            "message": "未知的插件 code: invalid_plugin"
        }
    ]
}
```
