### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get node outputs

### Common authentication parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| bk_app_code | string | Yes | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| bk_app_secret | string | Yes | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### Path parameters:

| Field | Type | Required | Description |
|------------|-------|----------|--------|
| space_id   | int   | YES      | Space ID   |

#### Interface parameters

| Field | Type | Required | Description |
|-----------|------|----------|------|
| node_ids  | list[string] | YES | Node IDs belonging to the task |
| task_id   | int  | YES      | Task ID |

### Request example

`POST /space/1/get_node_outputs/` with `Content-Type: application/json`.

```json
{"task_id": 17, "node_ids": ["n1", "n2"]}
```

### Response example

```json
{
    "result": true,
    "data": [
        {
            "n9ed147b84563b70a9487704a482a365": [
                {
                    "_result": true,
                    "_loop": 3,
                    "_inner_loop": 3
                }
            ]
        }
    ],
    "code": "0",
    "message": ""
}
```

### Description of returned result parameters

| Field   | Type     | Description                                                                                    |
|---------|----------|------------------------------------------------------------------------------------------------|
| result  | bool     | Returns the result: true for success, false for failure.                                       |
| code    | int/string | Return code: 0 indicates success, while other values indicate failure.                         |
| message | string   | error message                                                                                  |
| data    | list     | Node outputs, where the node ID is the key and the value is the list of outputs for that node. |

### Validation error example

Empty bodies, malformed JSON, invalid encoding and missing required fields return validation errors. HTTP status remains 200 for compatibility; callers must check `result` and `code`. The message is localized.

```json
{
    "result": false,
    "data": null,
    "code": 400,
    "message": "{\"body\": \"请求体必须是有效的 JSON\"}"
}
```
