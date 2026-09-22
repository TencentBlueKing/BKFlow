### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Create or retrieve a resource access token. This endpoint supports legacy single-grant requests and the new grants format.

### Endpoint behavior

- **Issue a new token:** if no valid token exists for the same space, user, resource type, resource ID, and permission type, create one.
- **Return an existing token:** if valid tokens already exist for that combination, return the one expiring latest. Concurrent requests may create multiple records.
- **Automatic renewal:** when the space enables `token_auto_renewal`, retrieving an existing token refreshes its expiration.
- **Lifetime:** determined by `token_expiration`, with a default and minimum of 1 hour. The deployment setting `BKAPP_TOKEN_EXPIRATION_MAX_EXPIRATION` sets the maximum (default: 30 days).

The integrating system must first check the user's business permissions. Gateway application authentication, user authentication, and resource permission checks are required. The backend also checks that the calling application is bound to the target space. The username comes from authenticated `request.user.username`; an extra `user` field cannot grant access to someone else.

### Composite grants switch and compatibility

`TOKEN_COMPOSITE_ENABLED` is enabled by default, so grants requests work without an environment override. Set `BKAPP_TOKEN_COMPOSITE_ENABLED=false` to disable it. Explicit values enable it only when they equal `true` (case-insensitive); `false`, `0`, and `1` do not enable it. Disabling it does not affect legacy single-grant requests or authentication, renewal, and revocation of existing composite tokens.

- If any legacy field (`resource_type`, `resource_id`, `permission_type`) is present, the legacy format takes precedence and extra `grants` are ignored. Incomplete legacy fields return the original required-field errors.
- The new format is used only when no legacy field is present and `grants` exists. `grants` must be a nonempty array with at most 32 raw entries; length is checked before deduplication. Each entry uses the three required fields and resource validation below. Errors identify `grants[index]`, with zero-based indexes.
- All resources must pass validation before issue or renewal; partial grants are not allowed. The username and space always come from the authenticated identity and URL respectively.
- After complete triples are deduplicated and sorted, the same user, space, and full set may reuse a token. Subsets, supersets, and different operations do not share a composite token. Concurrent requests may produce equivalent tokens, each containing all grants.
- Single and multiple grants use the same grant-detail storage. A deduplicated single grant may reuse a legacy token, but the new response still includes `grants`. A legacy request does not reuse a multi-grant token containing that grant.
- Grants are never appended to or replaced on issued tokens. Revoke the entire token and request a new one when role permissions change.

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| access_token  | string | No  | User or application access_token; see the AccessToken API                    |

Whether `access_token` is used depends on the authentication methods supported by the deployed gateway. User authentication itself is mandatory; application credentials alone are insufficient.

#### Legacy single-grant fields (also used by each grants entry)

| Field              | Type     | Required | Description                                      |
|-----------------|--------|----|-----------------------------------------|
| resource_type   | string | Yes  | Resource type: TEMPLATE (template), TASK (task), or SCOPE (scope) |
| resource_id     | string | Yes  | Resource ID                                   |
| permission_type | string | Yes  | Permission type                                    |

`resource_id` is limited to 32 characters. `SCOPE` uses `scope_type_scope_value`, such as `biz_100`; current validation requires exactly one underscore and an existing template with that scope in the space. Although the model enum includes `LABEL`, this endpoint does not yet issue `LABEL` tokens.

### permission_type parameter

The main resource permission relationships are listed below. The application endpoint does not strictly validate resource/permission combinations, so successful issuance does not mean every endpoint accepts the combination. Actual authorization also depends on action permission settings.

For resource_type TASK, use VIEW or OPERATE.

| Permission      | Permission scope           |
|---------|----------------|
| VIEW    | View a specific task only   |
| OPERATE | View and operate on a specific task |


For resource_type TEMPLATE, use VIEW, EDIT, or MOCK.

| Permission   | Permission scope                               |
|------|------------------------------------|
| VIEW | View a specific workflow only                       |
| EDIT | View and edit a specific workflow                     |
| MOCK | View, edit, and debug a specific workflow, and access/operate MOCK tasks created from it; ordinary tasks are not automatically authorized |

For resource_type SCOPE:

| Permission      | Permission scope                   |
|---------|------------------------|
| VIEW    | View tasks and workflows in a scope |
| EDIT    | View and edit workflows in a scope; does not automatically grant task operation permissions |
| OPERATE | View and operate tasks in a scope; also allows preview_task_tree on templates |
| MOCK    | View, edit, and debug workflows in a scope, plus viewing, operating, and accessing mock data through the task permission class; that task permission class does not restrict create_method |

MOCK debugging may create, start, or terminate real engine tasks; it is not a read-only simulation. Task tokens can authorize descendant tasks through parent relationships, but a child token does not authorize its parent. Scope matching uses the resource's current scope. `FLOW_VIEW`, `FLOW_EDIT`, and `FLOW_MOCK` are template permission indicators displayed in task details, not additional permission types issued by this endpoint.

### Request example

The following is only the business request body. Supply application credentials and user authentication separately according to the gateway protocol.

```json
{
  "resource_type": "TEMPLATE",
  "resource_id": "1",
  "permission_type": "VIEW"
}
```

### Response example

```json
{
  "result": true,
  "data": {
    "space_id": 3,
    "resource_type": "TEMPLATE",
    "resource_id": "1",
    "user": "admin",
    "token": "<BKFLOW_TOKEN>",
    "expired_time": "2026-09-09T05:00:00Z"
  },
  "code": 0
}
```

### New request and response format

A user who needs to debug template `100` and operate ordinary task `200` can request one token:

```json
{
  "grants": [
    {"resource_type": "TEMPLATE", "resource_id": "100", "permission_type": "MOCK"},
    {"resource_type": "TASK", "resource_id": "200", "permission_type": "OPERATE"}
  ]
}
```

```json
{
  "result": true,
  "data": {
    "space_id": 3,
    "user": "admin",
    "token": "<BKFLOW_TOKEN>",
    "expired_time": "2026-09-09T05:00:00Z",
    "grants": [
      {"resource_type": "TASK", "resource_id": "200", "permission_type": "OPERATE"},
      {"resource_type": "TEMPLATE", "resource_id": "100", "permission_type": "MOCK"}
    ]
  },
  "code": 0
}
```

In the new format, data contains `space_id`, `user`, `token`, `expired_time`, and normalized `grants`, without top-level resource fields or internal digests. Each grant matches independently; grants do not combine into template operation permissions. Legacy data fields remain as listed below. Both responses use the current JSON time encoding (UTC `Z` in examples). The success wrapper does not require `message`; the deployment may include `trace_id`.

### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| code    | int    | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | dict   | Response data                  |

### data

| Field              | Type     | Description                           |
|-----------------|--------|------------------------------|
| space_id        | int    | Space ID                         |
| user            | string | Authorized username |
| resource_type   | string | Resource type: TEMPLATE, TASK, SCOPE |
| resource_id     | string | Resource ID                        |
| token           | string | token                        |
| expired_time    | string | Expiration time                         |

Legacy data is generated by `Token.to_json()` and does not include `permission_type`; callers should retain the requested permission type. `<BKFLOW_TOKEN>` is a placeholder for the actual 32-character token.

### Related space settings

| Setting name               | Description                                         |
|--------------------|----------------------------------------------|
| token_expiration   | Token lifetime, such as `1h` (1 hour) or `24h` (24 hours)  |
| token_auto_renewal | Automatic token renewal; when `true`, retrieving an existing token refreshes its expiration |

Configure these settings through `renew_space_config`. Token validation on ordinary business requests does not refresh expiration. Pages renew through a dedicated endpoint, or integrators can call this endpoint again to retrieve a valid token.
