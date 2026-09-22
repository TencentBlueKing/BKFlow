### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Operate on a task with bk_app_code authorization

This endpoint operates on tasks created from templates bound to a bk_app_code. The requester's bk_app_code must match the code bound to the task's template.

**Note: user authentication is required. The operator is taken from the gateway-authenticated user; no operator parameter is needed.**

### Common authentication parameters
|   Parameter   |    Type  |  Required  |     Description     |
| ------------ | ------------ | ------ | ---------------- |
| bk_app_code   | string | Yes | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| bk_app_secret | string | Yes | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| bk_username   | string | Yes | Username for user authentication |


Path parameters:

| Field  | Type  | Required  | Description  |
| --- | --- | --- | --- |
|  task_id   |  int   |  Yes  |  Task ID |
|  operation   |  string   |  Yes  |  Operation: start, pause, resume, or revoke |

### Permissions

- The task must have been created from a template bound to a bk_app_code.
- The requester's bk_app_code must match the code bound to the task's template.
- User authentication is required; the gateway-authenticated user is the operator.

### Open plugin governance

When `operation=start` and the execution snapshot contains BK-SOPS open plugins (`uniform_api v4.0.0`), catalog availability and space enablement are checked again before starting. If validation fails, the task does not start and a parameter validation error is returned.

When `operation=revoke` succeeds, cancellation requests for associated open plugin instances are dispatched asynchronously. Success means the workflow engine accepted the revocation, not that every remote plugin instance has finished cancelling.

### Request example
```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username": "xxxx"
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

### Error response examples

The task's template is not bound to a bk_app_code:
```json
{
    "result": false,
    "message": "Template associated with task is not bindedto any bk_app_code. task_id=10, template_id=3"
}
```

bk_app_code mismatch:
```json
{
    "result": false,
    "message": "The current application does not have permission to operate this task, app=other_app, template bindedapp=your_app"
}
```

### Response parameters

| Field      | Type     | Description                    |
| ------- | ------ | --------------------- |
| result  | bool   | Operation result: true for success, false for failure |
| code    | int    | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | dict  | Response data                    |
