### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Batch delete templates

### Common authentication parameters
| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

#### Path parameters

| Field       | Type | Required | Description   |
|----------| --- | --- |------|
| space_id | int | Yes | Space ID |

#### Endpoint parameters

| Field | Type   | Required | Description     |
| --- |------| --- |--------|
| template_ids | list | Yes | List of template IDs |


### Response example

```json
{
    "result": true,
    "data": {},
    "code": 0,
    "trace_id": "3b9bc1fa61cb498ea6fb74fc0f444159"
}
```

### Deletion failure example
```json
{
    "result": false,
    "data": {
        "root_template_info": {
            "1": [
                {
                    "root_template_id": "20",
                    "root_template_name": "测试流程"
                }
            ]
        },
        "decision_info": {
            "1": [
                {
                    "id": 5,
                    "name": "决策表A"
                }
            ]
        }
    },
    "code": 400,
    "message": "模板被引用，无法删除",
    "trace_id": "00-36749a2619963cadf480a1597d98a6ee-33ff46feb2870f06-01"
}
```

### Response parameters

| Field      | Type     | Description                |
| ------- | ------ |-------------------|
| result  | bool   | Operation result: true for success, false for failure |
| code    | int    | Response code: 0 for success, any other value for failure |
| message | string | Error message              |
| data    | dict  | Response data (reference information on deletion failure; see the structure below) |

#### Data structure on failure

When deletion fails, `data` may contain the following fields:

| Field      | Type     | Description                |
| ------- | ------ |-------------------|
| root_template_info | dict  | Subprocess references from parent workflows: keys are subprocess template IDs and values are lists of referencing parent workflows (including `root_template_id` and `root_template_name`) |
| decision_info | dict  | Decision tables associated with templates: keys are template IDs and values are lists of associated decision tables (including `id` and `name`); returned only when associated decision tables exist |
