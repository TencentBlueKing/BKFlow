### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Create a space

### Common authentication parameters
|   Parameter   |    Type  |  Required  |     Description     |
| ------------ | ------------ | ------ | ---------------- |
| bk_app_code   | string | Yes | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| bk_app_secret | string | Yes | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |


#### Endpoint parameters

When multi-tenancy is enabled, a verified `tenant_id` is required. When disabled, legacy requests may omit it or send an empty string to use `default`.

| Field  | Type  | Required  | Description                                                                 |
| --- | --- | --- |--------------------------------------------------------------------|
|  name   |  string   |  Yes   | Space name                                                                |
|  platform_url   |  string   |  Yes   | Space platform service URL                                                           |
|  desc |  string   |  No   | Space description                                                               |
|  app_code   |  string   |  Yes   | The app_code bound to the space. Only this application can access and operate resources in the space. Currently, this must be the app_code of the requesting application. |
| tenant_id | string | Conditionally required | Tenant ID, up to 32 characters; required when multi-tenancy is enabled and must match the application's request tenant |
| tenant_mode | string | No | Fixed to `single` (the default). All-tenant spaces are currently unsupported. |
|  config   |  dict   |  No  | Configuration supplied when creating the space                                                      |


### Configuration details
The config object accepts space settings. The following settings are currently supported:
```json
{
    "space_plugin_config": {},
    "token_expiration": "token的过期时间，格式如：1h,1m。 默认是1h",
    "token_auto_renewal": "是否开启自动续期，'true' or 'false'",
    "callback_hooks": {
        "url": "回调url，需要是网关url",
        "callback_types": [
            "template"
        ]
    },
    "uniform_api": "",
    "api_gateway_credential_name": "api gateway 所使用的凭证名称"
}
```


### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "空间名",
    "platform_url": "http://www.tencent.com",
    "desc": "这是一段默认描述",
    "app_code": "bksops",
    "tenant_id": "tenant-a",
    "config": {}
}
```

### Response example

```json
{
    "result": true,
    "data": {
        "id": 3,
        "name": "空间名",
        "desc": "这是一段默认描述",
        "platform_url": "http://www.tencent.com",
        "app_code": "bksops",
        "create_type": "API"
    },
    "code": 0
}
```

### Response parameters

| Field      | Type     | Description                    |
| ------- | ------ | --------------------- |
| result  | bool   | Operation result: true for success, false for failure |
| code    | int    | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | dict  | Response data                    |

### data
| Field      | Type     | Description                    |
| ------- | ------ | --------------------- |
| id | int | Space ID                |
| name | string | Space name                |
| desc | string | Space description                  |
| platform_url | string | Space service URL                  |
| app_code    | string  | Space description     |
| create_type    | string  | Space creation method     |
| tenant_id | string | Tenant ID of the space |
