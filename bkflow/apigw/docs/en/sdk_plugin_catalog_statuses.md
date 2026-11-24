### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Batch query plugin statuses (SDK endpoint)

When opening the node configuration panel, query the statuses of all plugin identities referenced by canvas nodes in one request rather than per node. Unmatched identities fall back to `enable`. This endpoint is only for display banners, not for save blocking; save blocking is handled by the save-template endpoint (see sdk_update_template).

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
| items | object[] | Yes | Plugin identity list. Each item requires `plugin_type` and `plugin_code`; `source_key` and `plugin_version` are optional (default empty string) |

### Request example

```json
{
    "space_id": 1,
    "items": [
        {"plugin_type": "bk_plugin", "source_key": "", "plugin_code": "wecom_bot"},
        {"plugin_type": "api", "source_key": "api_job", "plugin_code": "bk_http_request"}
    ]
}
```

### Response example

```json
{
    "result": true,
    "data": {
        "results": [
            {
                "plugin_type": "bk_plugin",
                "source_key": "",
                "plugin_code": "wecom_bot",
                "status": "disabled",
                "reason": "Migrated to Send Notification plugin",
                "replace_plugin": {
                    "plugin_type": "bk_plugin", "source_key": "", "plugin_code": "send_notify",
                    "name": "Send Notification", "status": "enable"
                }
            }
        ]
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

#### results[item] fields

| Field | Type | Description |
|------------|--------|------|
| plugin_type / source_key / plugin_code | string | Plugin identity triple |
| status | string | Status: enable/pending_review/disabled/expired |
| reason | string | Text to display directly in the banner; empty string for other statuses |
| replace_plugin | object/null | Suggested replacement identity, display name and status; null if none |
