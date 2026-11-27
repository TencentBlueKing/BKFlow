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

### Path parameters:

| Field     | Type    | Required | Description |
|-----------|---------|----------|-------------|
| space_id  | int     | YES      | Space ID    |
| task_id   | int     | YES      | Task ID     |


### Response example

```json
{
    "result": true,
    "data": [
        {
            "key": "${_system}",
            "value": "<SystemObject: {'task_space_id': 1, 'task_scope_type': None, 'task_scope_value': None, 'operator': 'xxx', 'executor': 'xxx', 'task_id': 1, 'task_name': 'xx', 'is_mock': False, 'task_start_time': ''}>"
        }
    ],
    "message": "",
    "exc": null,
    "exc_trace": null,
    "trace_id": "00-3eea4f12ad7d8fa47dcec2101e1454c5-ce9f6da4d3c2b4d6-01"
}
```

### Description of returned result parameters

| Field     | Type   | Description                                                                 |
|-----------|--------|-----------------------------------------------------------------------------|
| result    | bool   | Result flag. `true` indicates success, `false` indicates failure.           |
| message   | string | Error message. Empty string on success.                                     |
| exc       | -      | Exception object. `null` on success.                                        |
| exc_trace | -      | Exception traceback. `null` on success.                                     |
| trace_id  | string | Trace ID for troubleshooting and log search.                                |
| data      | array  | Returned data: list of currently rendered global variables of the task. See the table below for each item's structure. |

#### data[item]

| Field | Type   | Description                                                                                  |
|-------|--------|----------------------------------------------------------------------------------------------|
| key   | string | Global variable key, e.g. `${_system}` represents a built-in system variable.                |
| value | -      | The variable's currently rendered value. Its type depends on the variable; for `${_system}` it is a task-context object (with fields such as `task_space_id`, `task_scope_type`, `task_scope_value`, `operator`, `executor`, `task_id`, `task_name`, `is_mock`, `task_start_time`, etc.). |

