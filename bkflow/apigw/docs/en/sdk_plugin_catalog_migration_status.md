### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Canvas-side check of whether a space has enabled the plugin catalog (SDK endpoint)

Returns exactly the same content as the space-configuration 4.1 `plugin_catalog_migration` endpoint (both use `get_status_view`), but with different permissions: this endpoint targets ordinary workflow editors on the canvas, using `AdminPermission | PluginSpaceSuperuserPermission | PluginTokenPermissions`, so any user with a valid `BKFLOW_TOKEN` can read it. The management endpoints 1.1 `plugins/summary` and 4.1 keep their original permissions.

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

### Request example

```
GET /api/plugin_catalog/plugins/migration_status/?space_id=1
```

### Response example

```json
{
    "result": true,
    "data": {
        "space_id": 1,
        "ready": true,
        "migrated_at": "2026-09-23 14:32",
        "migrated_by": "admin",
        "legacy_snapshot": {
            "filter_mode": "allow_list",
            "filter_mode_text": "Show only plugins in the allow list",
            "plugins": [
                {"code": "bk_http_request", "name": "HTTP Request"},
                {"code": "python_code", "name": "Python Code"}
            ],
            "scope_overrides": [
                {"scope": "node_bk_http_request_1", "mode": "deny_list", "plugin_codes": ["bk_display"]}
            ],
            "snapshot_note": "Saved when the plugin catalog was initialized; can be restored by re-initializing",
            "open_plugin_enabled_count": 12
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
| space_id | int | Space ID |
| ready | bool | Whether the plugin catalog migration is done; false means the space has not enabled the plugin catalog |
| migrated_at | string | Migration time, format YYYY-MM-DD HH:MM (without seconds) |
| migrated_by | string | Operator who ran the migration |
| legacy_snapshot | dict | Read-only snapshot of the old configuration at migration time, already shaped for direct rendering |

> When `ready=false`, the frontend should show "This space has not enabled the plugin catalog; contact operations to run initialization". This endpoint is read-only and provides no way to trigger migration; initializing existing spaces is only possible via `python manage.py initialize_plugin_catalog --all-spaces`, while new spaces are initialized automatically on `create_space`.
