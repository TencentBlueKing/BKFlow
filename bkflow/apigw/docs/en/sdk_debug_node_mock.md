### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Configure node mocks for workflow debugging (SDK endpoint)

### HTTP header parameters

| Parameter         | Type | Required | Description |
|--------------| --- | --- | --- |
| BKFLOW-TOKEN | string | Yes | Access token obtained from `/space/{space_id}/apply_token/`, with permission type `MOCK` |

### Endpoint parameters

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| space_id | int | Yes | Space ID |
| template_id | int | Yes | Workflow template ID |
| node_id | string | Yes | Node ID |
| enable | bool | No | Whether mock is enabled |
| mock_result | string | No | Mock result: `success` or `fail` |
| mock_outputs | dict | No | Mock outputs |
| mock_error | string | No | Mock failure message |

Exclusive and conditional parallel gateways do not support mocks. Calling this endpoint for either returns an error indicating that conditional gateways do not support mocks.

### Request example

```json
{
  "space_id": 1,
  "template_id": 100,
  "node_id": "node1",
  "enable": true,
  "mock_result": "success",
  "mock_outputs": {
    "k": "v"
  }
}
```
