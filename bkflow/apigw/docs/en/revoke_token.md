### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Revoke tokens

This endpoint sets matching records' `expired_time` to the current time. It does not delete records or stop running tasks. Filters are combined. For composite tokens, if one grant matches all resource conditions, the entire token and all its grants are revoked. Individual-grant revocation and a grants parameter are not supported.

Gateway application authentication and resource permissions are required, and the application-to-space binding is checked. Gateway user authentication is not required. The request's `user` filters the users whose tokens are revoked.

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| access_token  | string | No  | User or application access_token; see the AccessToken API                    |

#### Endpoint parameters

Note: these parameters filter tokens in the specified space. Omitting every filter expires all tokens in that space by setting their expiration to the current time. Make filters as precise as possible.

| Field              | Type     | Required      | Description                           |
|-----------------|--------|---------|------------------------------|
| resource_type   | string | No       | Resource type: TEMPLATE, TASK, SCOPE, LABEL; apply_token cannot currently issue LABEL tokens |
| resource_id     | string | No       | Resource ID                        |
| permission_type | string | No       | Permission type                         |
| user            | string | No       | Authorized username |
| token           | string | No       | token                        |

### permission_type parameter

The filter accepts VIEW, EDIT, OPERATE, and MOCK, matching the stored permission type exactly without expanding permission implications. For example, `permission_type=VIEW` does not also revoke EDIT or OPERATE tokens.

Templates usually use VIEW / EDIT / MOCK, tasks use VIEW / OPERATE, and scopes use VIEW / EDIT / OPERATE / MOCK. To revoke all of a user's tokens for a resource, omit `permission_type` while retaining user and resource filters.

### Request example

The following business request body revokes one exact token. Supply application authentication separately according to the gateway protocol.

```json
{
  "token": "<BKFLOW_TOKEN>"
}
```

### Response example

```json
{
    "result": true,
    "data": "1 tokens revoke success",
    "message": "",
    "code": 0
}
```

### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| code    | int    | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | string | Count of distinct parent token records matched and updated; excludes grant details and does not imply all tokens were previously valid |

### Composite token filtering and counting

Space, `token`, and `user` filters are ANDed with resource filters. Resource type, ID, and permission must match the same grant; fields cannot be combined across grant records. For a token containing `TEMPLATE/100/MOCK` and `TASK/200/OPERATE`:

- Revoking with `resource_type=TEMPLATE, resource_id=100` invalidates both grants.
- Filtering by `resource_type=TEMPLATE, resource_id=200` does not match the token.
- Filters match stored grants exactly; they do not expand scope membership, task ancestry, or permission implications.

The response remains `N tokens revoke success`, where N is the number of distinct parent tokens matched and updated. Multiple matching grants count once; expired tokens also count. Without resource conditions, parent records are filtered directly, allowing revocation of composite tokens with damaged grant details. An empty object revokes all tokens only in the URL's space.

### Ordering of revocation and renewal

Revocation and renewal coordinate through transactional locks on the parent token row. If revocation finishes first, renewal rejects the expired token; if renewal finishes first, revocation overwrites the renewed expiration. Token reuse rechecks validity after locking and cannot revive revoked tokens. A new request may issue a new token value.

Disabling composite-token issuance does not affect revocation of existing composite tokens. Revocation still changes expiration without deleting records or grants. Expired-token cleanup deletes grant details through cascading deletion. These behaviors require a deployed version containing the composite-token and lifecycle fixes; this document does not prove older deployments include them.
