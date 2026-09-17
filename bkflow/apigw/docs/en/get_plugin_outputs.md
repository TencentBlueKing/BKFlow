### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get plugin outputs

### Common authentication parameters
| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

#### Endpoint parameters

| Field             | Type       | Required    | Description                     |
|----------------|----------|-------|------------------------|
| plugin_id      | string   | Yes     | Plugin ID, uniquely identifying a plugin type        |
| plugin_version | string   | No     | Plugin version                   |

### Request example

```json
{
    "plugin_id": "bk_plugin_example"
}
```

### Response example

```json
{
    "result": true,
    "data": {
        "output": [
            {
                "name": "执行结果",
                "key": "_result",
                "type": "boolean",
                "schema": {
                    "type": "boolean",
                    "description": "执行结果的布尔值，True or False",
                    "enum": []
                }
            },
            {
                "name": "循环次数",
                "key": "_loop",
                "type": "int",
                "schema": {
                    "type": "int",
                    "description": "循环执行次数",
                    "enum": []
                }
            },
            {
                "name": "当前流程循环次数",
                "key": "_inner_loop",
                "type": "int",
                "schema": {
                    "type": "int",
                    "description": "在当前流程节点循环执行次数，由父流程重新进入时会重置（仅支持新版引擎）",
                    "enum": []
                }
            }
        ],
        "form": null,
        "output_form": null,
        "desc": "这是一个示例插件",
        "form_is_embedded": false,
        "group_name": "蓝鲸服务",
        "group_icon": "",
        "name": "示例插件",
        "base": "",
        "code": "test_api",
        "version": "v1.0.0",
        "is_default_version": false
    },
    "code": 0,
    "message": ""
}
```

### Response parameters

| Field        | Type           | Description                    |
|-----------|--------------|-----------------------|
| result    | bool         | Operation result: true for success, false for failure |
| code      | int          | Response code: 0 for success, any other value for failure     |
| message   | string       | Success/error message               |
| data      | object/array | Plugin data                  |

#### data[item]

| Field               | Type      | Description               |
|------------------|---------|------------------|
| code             |  string | Plugin code             |
| version          | string  | Plugin version             |
| name             | string  | Plugin name             |
| group_name       | string  | Plugin group name           |
| group_icon       | string  | Plugin group icon           |
| desc             | string  | Plugin description             |
| form             | object  | Plugin input form configuration         |
| output           | object  | Plugin output configuration           |
| output_form      | object  | Plugin output form configuration         |
| form_is_embedded | bool    | Whether the form is embedded           |
| base             | object  | Basic configuration             |
