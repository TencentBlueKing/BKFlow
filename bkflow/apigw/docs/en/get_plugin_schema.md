### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Query the parameter schema of a plugin

#### Description

Get the complete parameter schema (inputs and outputs) of the specified plugin.

An open plugin using `uniform_api v4.0.0` must be enabled in the current space. Existing V2/V3 plugins still use their original remote `meta_url`.

#### HTTP method

GET

#### Request parameters

| Parameter | Type | Required | Description |
|------|------|------|------|
| code | string | No | Plugin code. Specify at least one of `code` and `plugin_id`. |
| plugin_id | string | No | Open plugin ID. When supplied, this takes precedence over `code`, making it easier to query `uniform_api v4.0.0` open plugins. |
| version | string | No | Plugin version; defaults to the latest version |
| plugin_version | string | No | Open plugin business version. When supplied, this takes precedence over `version`. |
| plugin_source | string | No | Open plugin source type, used to disambiguate V4 open plugins |
| source_key | string | No | Open plugin source identifier, used when the same `plugin_id` exists in multiple sources |
| plugin_type | string | No | Disambiguates the plugin type. Values: component, remote_plugin, uniform_api |
| scope_type | string | No | Scope type |
| scope_id | string | No | scope ID |

#### Response parameters

| Parameter | Type | Description |
|------|------|------|
| result | bool | Whether the request succeeded |
| code | int | Error code; 0 for success |
| data | object | Plugin details |
| data.code | string | Plugin code |
| data.name | string | Plugin name |
| data.plugin_type | string | Plugin type |
| data.version | string | Plugin version |
| data.description | string | Plugin description |
| data.plugin_source | string | Open plugin source type, returned only for `uniform_api v4.0.0`, such as `builtin` or `third_party` |
| data.plugin_code | string | Plugin code in its source system, returned only for `uniform_api v4.0.0` |
| data.wrapper_version | string | BKFlow wrapper version, returned only for `uniform_api v4.0.0` |
| data.inputs | array | Input parameter list |
| data.inputs[].key | string | Parameter identifier |
| data.inputs[].name | string | Parameter |
| data.inputs[].type | string | Type |
| data.inputs[].required | bool | Whether required |
| data.inputs[].description | string | Parameter description |
| data.outputs | array | Output parameter list |

An unavailable or disabled `uniform_api v4.0.0` open plugin returns an error instead of a schema. These checks do not apply to existing V2/V3 plugins.

#### Request example

```bash
curl -X GET 'http://{host}/space/1/get_plugin_schema/?code=job_fast_execute_script&plugin_type=component'
```

Open plugin example:

```bash
curl -X GET 'http://{host}/space/1/get_plugin_schema/?plugin_id=open_plugin_001&plugin_version=1.2.0&plugin_type=uniform_api&source_key=source-b'
```

#### Response example

```json
{
    "result": true,
    "code": 0,
    "data": {
        "code": "job_fast_execute_script",
        "name": "快速执行脚本",
        "plugin_type": "component",
        "version": "v1.0.0",
        "description": "执行脚本",
        "inputs": [
            {
                "key": "script_content",
                "name": "脚本内容",
                "type": "string",
                "required": true,
                "description": ""
            }
        ],
        "outputs": [
            {
                "key": "_result",
                "name": "执行结果",
                "type": "bool",
                "description": ""
            }
        ]
    }
}
```

Open plugin response example:

```json
{
    "result": true,
    "code": 0,
    "data": {
        "code": "open_plugin_001",
        "name": "JOB 执行作业",
        "plugin_type": "uniform_api",
        "version": "1.2.0",
        "plugin_source": "builtin",
        "plugin_code": "job_execute_task",
        "wrapper_version": "v4.0.0",
        "description": "执行标准运维作业",
        "inputs": [],
        "outputs": []
    }
}
```
