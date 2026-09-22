### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get system variables (SDK endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### Permissions

This endpoint uses the default permissions. **BKFLOW-TOKEN is not required**.

### Endpoint parameters

None

### Request example

```
GET /sdk/template/variable/system_variable/
```

### Response example

```json
{
    "result": true,
    "data": {
        "${_system.task_name}": {
            "key": "${_system.task_name}",
            "name": "任务名称",
            "index": -1,
            "desc": "",
            "show_type": "hide",
            "source_type": "system",
            "source_tag": "",
            "source_info": {},
            "custom_type": "",
            "value": "",
            "hook": false,
            "validation": ""
        },
        "${_system.task_id}": {
            "key": "${_system.task_id}",
            "index": -2,
            "name": "任务ID",
            "desc": "",
            "show_type": "hide",
            "source_type": "system",
            "source_tag": "",
            "source_info": {},
            "custom_type": "",
            "value": "",
            "hook": false,
            "validation": ""
        },
        "${_system.task_start_time}": {
            "key": "${_system.task_start_time}",
            "name": "任务开始时间",
            "index": -3,
            "desc": "",
            "show_type": "hide",
            "source_type": "system",
            "source_tag": "",
            "source_info": {},
            "custom_type": "",
            "value": "",
            "hook": false,
            "validation": ""
        },
        "${_system.operator}": {
            "key": "${_system.operator}",
            "name": "任务的执行人（点击开始执行的人员）",
            "index": -4,
            "desc": "",
            "show_type": "hide",
            "source_type": "system",
            "source_tag": "",
            "source_info": {},
            "custom_type": "",
            "value": "",
            "hook": false,
            "validation": ""
        }
    },
    "code": "0",
    "message": ""
}
```

### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| code    | string | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | dict   | Response data: system variable dictionary            |

#### data[item] fields

| Field                         | Type      | Description         |
|----------------------------|---------|------------|
| ${_system.task_name}       | string  | System variable: task name   |
| ${_system.task_id}         | string  | System variable: task ID   |
| ${_system.task_start_time} | string  | System variable: task start time |
| ${_system.operator}        | string  | System variable: task executor  |



#### ${_system.task_name}[messages] fields

| Field          | Type      | Description                     |
|-------------|---------|------------------------|
| key         | string  | Variable key                   |
| name        | string  | Variable name                   |
| desc        | string  | Variable description                   |
| index       | integer | Display order among frontend global variables; lower values come first     |
| show_type   | string  | Display type: hide / show |
| source_type | string  | Source type: system (system variable)      |
| source_tag  | string  | Source tag                   |
| source_info | object  | Source information                   |
| custom_type | string  | Custom type                  |
| value       | string  | Variable value                    |
| hook        | bool    | Whether hooks are enabled               |
| validation  | string  | Validation rules                   |
