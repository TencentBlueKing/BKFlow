### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Plugin version diff (SDK endpoint)

Backs the "N parameters kept, N parameters added" notice after a version switch plus the "Old version parameters" drawer, and is reused for input remapping when switching plugins. Only input parameters are covered, not outputs.

Rule: a parameter is `kept` only when both its key and Chinese name are identical; everything else is `added` (no implicit rename mapping).

### Common authentication parameters

| Parameter | Type | Required | Description |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code | string | Yes | Application ID, available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| bk_app_secret | string | Yes | Application secret, available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### HTTP header parameters

| Parameter | Type | Required | Description |
|--------------|--------|----|------------------------------------------------------------|
| X-Bk-Tenant-Id | string | No | Required for all-tenant apps when multi-tenancy is enabled; may be omitted by single-tenant apps; must match the resource space tenant |

### Endpoint parameters

| Field | Type | Required | Description |
|------------|---------|-----|----------|
| space_id | int | Yes | Space ID |
| from_plugin | object | Yes | Plugin identity before switch; `plugin_type` and `plugin_code` required, `source_key` and `plugin_version` optional (default empty string) |
| to_plugin | object | Yes | Plugin identity after switch; same required/optional fields as from_plugin |
| current_inputs | object | No | Current node input values {key: value}, used for backfilling |

### Request example

```json
{
    "space_id": 1,
    "from_plugin": {
        "plugin_type": "api", "source_key": "api_job",
        "plugin_code": "bk_http_request", "plugin_version": "v1.2.0"
    },
    "to_plugin": {
        "plugin_type": "api", "source_key": "api_job",
        "plugin_code": "bk_http_request", "plugin_version": "v1.3.0"
    },
    "current_inputs": {"webhook": "https://example.com/hook"}
}
```

### Response example

```json
{
    "result": true,
    "data": {
        "kept": ["webhook", "receiver"],
        "added": ["msg_content", "prompts"],
        "inputs": {
            "webhook": {"key": "webhook", "name": "Webhook", "type": "string", "value": "https://example.com/hook"},
            "content": {"key": "content", "name": "Message", "type": "string", "value": "hello", "to_key": "msg_content"}
        }
    },
    "message": "",
    "code": "0"
}
```

### Response parameters

| Field | Type | Description |
|---------|--------|-----------------------|
| result | bool | Operation result: true for success, false for failure |
| code | string | Response code: 0 for success, any other value for failure |
| message | string | Error message |
| data | dict | Response data |

#### data fields

| Field | Type | Description |
|------------|--------|------|
| kept | array | Keys of input parameters unchanged after the switch (key and Chinese name both identical) |
| added | array | Keys of all other input parameters (new / key changed / name changed) |
| inputs | object | Input parameters of the old version with current values, keyed by old-version parameter key |

#### inputs[].xxx fields

| Field | Type | Description |
|------------|--------|------|
| key / name / type | string | Old-version parameter key, Chinese name and type |
| value | any | Current value on the node; absent if never filled |
| to_key | string | Matching key in the new version, for reference only; does not affect kept/added |
