### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get plugin configuration details (SDK endpoint; supports built-in, remote, and Uniform API plugins)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### HTTP header parameters

| Parameter         | Type   | Required | Description                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | Yes  | Access token obtained from `/space/{space_id}/apply_token/`. This token verifies the user's permission to access the specified space. |

### Endpoint parameters

| Field          | Type      | Required | Description                                                                                |
|-------------|---------|----|-----------------------------------------------------------------------------------|
| space_id    | string  | Yes  | Space ID                                                                              |
| template_id | string  | Yes  | Template ID                                                                              |
| plugin_type | string  | Yes  | Plugin type: component (built-in), remote_plugin (remote), or uniform_api (Uniform API) |
| plugin_code | string  | Yes  | Plugin code                                                                            |
| plugin_version | string  | Yes  | Plugin version                                                                              |
| source_key  | string  | No  | Uniform API plugin source identifier; required when plugin_type is uniform_api                                   |
| scope_type  | string  | No  | Business scope type                                                                            |
| scope_value | string  | No  | Business scope value (must be an integer when scope_type is biz or cmdb_biz)                                     |

### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "space_id": "1",
    "template_id": "10",
    "plugin_type": "component",
    "plugin_code": "bk_display",
    "plugin_version": "v1.0"
}
```

### Response example

```json
{
    "result": true,
    "message": "",
    "data": {
        "plugin_type": "component",
        "plugin_code": "bk_display",
        "plugin_version": "v1.0",
        "source_key": "bkflow",
        "plugin_source": "builtin",
        "protocol": "native",
        "wrapper_version": null,
        "name": "消息展示",
        "description": "本插件为仅用于消息展示的空节点",
        "inputs": [
            {
                "key": "bk_display_message",
                "name": "展示内容",
                "type": "string",
                "description": "",
                "required": true,
                "schema": {
                    "type": "string",
                    "description": "展示内容",
                    "enum": []
                }
            }
        ],
        "outputs": [
            {
                "key": "_result",
                "name": "执行结果",
                "type": "boolean",
                "description": "",
                "schema": {
                    "type": "boolean",
                    "description": "执行结果的布尔值，True or False",
                    "enum": []
                }
            },
            {
                "key": "_loop",
                "name": "循环次数",
                "type": "int",
                "description": "",
                "schema": {
                    "type": "int",
                    "description": "循环执行次数",
                    "enum": []
                }
            },
            {
                "key": "_inner_loop",
                "name": "当前流程循环次数",
                "type": "int",
                "description": "",
                "schema": {
                    "type": "int",
                    "description": "在当前流程节点循环执行次数，由父流程重新进入时会重置（仅支持新版引擎）",
                    "enum": []
                }
            }
        ],
        "credentials": [],
        "forms": {
            "input": {
                "type": "component_js",
                "key": "bk_display",
                "data": "/static/components/display/v1_0.js",
                "is_embedded": false,
                "base": ""
            },
            "output": null
        },
        "form_schema": null,
        "form_context": {
            "project": null,
            "biz_cc_id": null,
            "site_url": "/",
            "component": null,
            "variable": null,
            "template": null,
            "instance": null,
            "bk_plugin_api_host": {}
        },
        "execution_kind": "component",
        "url": null,
        "methods": [],
        "response_data_path": null,
        "polling": {},
        "callback": {},
        "credential_key": null
    }
}
```

### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| message | string | Error message                  |
| data    | dict   | Response data                  |

#### Data fields

| Field                 | Type       | Description                                                        |
|--------------------|----------|-----------------------------------------------------------|
| plugin_type        | string   | Plugin type: component (built-in), remote_plugin (remote), or uniform_api (Uniform API) |
| plugin_code        | string   | Plugin code                                                    |
| plugin_version     | string   | Plugin version                                                      |
| source_key         | string   | Uniform API source identifier; may be empty for built-in/remote plugins                                     |
| plugin_source      | string   | Plugin source                                                      |
| protocol           | string   | Protocol                                                        |
| wrapper_version    | string   | Wrapper version                                                      |
| name               | string   | Plugin name                                                      |
| description        | string   | Plugin description                                                      |
| inputs             | list     | Input parameter definitions                                                    |
| outputs            | list     | Output parameter definitions                                                    |
| credentials        | list     | Credential list                                                    |
| forms              | dict     | Form definition                                                      |
| form_schema        | dict     | Form schema                                                 |
| form_context       | dict     | Form context (project / biz_cc_id / site_url, etc.)                   |
| execution_kind     | string   | Execution type (such as component)                                         |
| url                | string   | Remote plugin URL (null for built-in plugins)                                        |
| methods            | list     | Supported HTTP methods of the remote plugin (empty for built-in plugins)                                 |
| response_data_path | string   | Response data extraction path                                                  |
| polling            | dict     | Polling configuration                                                      |
| callback           | dict     | Callback configuration                                                      |
| credential_key     | string   | Credential identifier                                                      |

Notes:
- This endpoint distinguishes the three plugin types (component, remote_plugin, uniform_api) using plugin_type and returns native form details in a common structure.
- When plugin_type is uniform_api, source_key is required; otherwise parameter validation fails.
