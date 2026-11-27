### Description

`POST /space/{space_id}/apply_token_by_app/` lets an application request a BKFLOW-TOKEN for a specified user. The gateway verifies the application and its permission to call the endpoint. BKFlow checks that the calling application is bound to the target space. The calling application must establish that the user is entitled to the requested access before requesting a token.

### Authentication and parameters

| Parameter | Location | Required | Description |
| --- | --- | --- | --- |
| bk_app_code | Gateway credentials | Yes | Calling application ID |
| bk_app_secret | Gateway credentials | Yes | Calling application secret |
| space_id | Path | Yes | Target space ID |
| X-Bk-Tenant-Id | Header | Conditional | Required for global applications in multi-tenant mode. Single-tenant applications default to their verified tenant. The request tenant must match the space tenant |
| user | JSON body | Yes | Username receiving the grant. Up to 32 characters and must be nonempty after trimming whitespace |
| resource_type | JSON body | Single grant | `TEMPLATE`, `TASK`, or `SCOPE` |
| resource_id | JSON body | Single grant | Resource ID, up to 32 characters. Use `scope_type_scope_value` for `SCOPE` |
| permission_type | JSON body | Single grant | `VIEW`, `EDIT`, `OPERATE`, or `MOCK` |
| grants | JSON body | Composite grant | Array of 1 to 32 grants, each with `resource_type`, `resource_id`, and `permission_type` |

The release configuration grants `bk_fara` access to this gateway resource. User authentication is unnecessary when requesting the token. When calling a user-authenticated SDK endpoint, the authenticated username must match the user named in the token.

### Request examples

```json
{"user":"alice","resource_type":"TEMPLATE","resource_id":"42","permission_type":"VIEW"}
```

When `TOKEN_COMPOSITE_ENABLED` is enabled, a request with no top-level resource fields can contain `grants`.

```json
{"user":"alice","grants":[{"resource_type":"TEMPLATE","resource_id":"42","permission_type":"VIEW"}]}
```

### Response

```json
{
  "result": true,
  "code": 0,
  "data": {
    "space_id": 1,
    "user": "alice",
    "token": "0123456789abcdef0123456789abcdef",
    "expired_time": "2026-11-27T08:00:00Z",
    "resource_type": "TEMPLATE",
    "resource_id": "42"
  }
}
```

Composite responses include the complete `grants` array in place of the top-level resource fields inside `data`. An active token can be reused for the same user, space, and complete grant set. Expiration and automatic renewal follow the space configuration.

Invalid usernames return HTTP 200 with `result: false`, `code: 400`, and `data: null`. A caller or tenant mismatch returns HTTP 403.
