### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Create a credential

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

#### Endpoint parameters

| Field      | Type     | Required | Description                    |
|---------|--------|----|-----------------------|
| name    | string | Yes  | Credential name, up to 32 characters          |
| desc    | string | No  | Credential description, up to 32 characters          |
| type    | string | Yes  | Credential type; currently supported: BK_APP (BlueKing application credentials) |
| content | json   | Yes  | Credential content, depending on the type          |

### type parameter

Currently supported credential types:

| Credential type  | Description        |
|-------|-----------|
| BK_APP | BlueKing application credentials    |

### content parameter

#### When type is BK_APP

content must contain the following fields:

```json
{
    "bk_app_code": "应用ID",
    "bk_app_secret": "应用密钥"
}
```

| Field            | Type     | Required | Description                    |
|---------------|--------|----|-----------------------|
| bk_app_code   | string | Yes  | BlueKing application ID                |
| bk_app_secret | string | Yes  | BlueKing application secret; must not consist entirely of '*' characters    |

### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "测试凭证",
    "desc": "这是一个测试凭证",
    "type": "BK_APP",
    "content": {
        "bk_app_code": "test_app",
        "bk_app_secret": "test_secret"
    }
}
```

### Response example

```json
{
     "id": 1,
     "space_id": 1,
     "desc": "这是一个测试凭证",
     "type": "BK_APP",
     "content": {
          "bk_app_code": "test_app",
          "bk_app_secret": "*********"
     }
}
```

### Response parameters

| Field       | Type     | Description                    |
|----------|--------|-----------------------|
| id       | int    | Credential ID                  |
| space_id | int    | Space ID                  |
| desc     | string | Credential description                  |
| type     | string | Credential type                  |
| content  | dict   | Credential content (sensitive information is masked)       |

### Notes

1. Credential names must be unique within a space.
2. Sensitive values (such as bk_app_secret) are masked as `*********` in responses.
3. Currently, only `BK_APP` is supported; more types will be supported later.
4. Creating a credential requires permissions for the corresponding space.
