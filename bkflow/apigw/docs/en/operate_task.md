### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Task operations

### Common authentication parameters
|   Parameter   |    Type  |  Required  |     Description     |
| ------------ | ------------ | ------ | ---------------- |
| bk_app_code   | string | Yes | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| bk_app_secret | string | Yes | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |


#### Endpoint parameters
| Field  | Type  | Required  | Description  |
| --- | --- | --- | --- |
|  operator   |  string   |  Yes  |  Operator |


Path parameters:

| Field  | Type  | Required  | Description  |
| --- | --- | --- | --- |
|  operation   |  string   |  Yes  |  Operation: start, pause, resume, or revoke |

### Open plugin governance

When `operation=start` and the execution snapshot contains BK-SOPS open plugins (`uniform_api v4.0.0`), BKFlow revalidates before starting:

- The plugin still exists.
- The plugin is still available.
- The plugin is still enabled in the current space.

If validation fails, the task does not start and a `400` error is returned.

When `operation=revoke` succeeds, cancellation requests for associated open plugin instances are dispatched asynchronously. Success means the workflow engine accepted the revocation, not that every remote plugin instance has finished cancelling.

### Request example
```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "operator": "操作人"
}
```


### Response example

```json
{
    "result": true,
    "data": null,
    "message": "success",
    "trace_id": "3f16e62e57c543a9be6cff9556e48d07"
}
```

Open plugin governance failure example:

```json
{
    "result": false,
    "code": 400,
    "data": null,
    "message": "开放插件 [open_plugin_001] 在当前空间未开放"
}
```
### Response parameters

| Field      | Type     | Description                    |
| ------- | ------ | --------------------- |
| result  | bool   | Operation result: true for success, false for failure |
| code    | int    | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | dict  | Response data                    |
