### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get workflow operation records (SDK endpoint)

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### HTTP header parameters

| Parameter         | Type   | Required | Description                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | Yes  | Access token obtained from `/space/{space_id}/apply_token/`. This token verifies the user's permission to view the specified template. |

### Path parameters

| Field         | Type     | Required | Description    |
|------------|--------|----|-------|
| template_id | string | Yes  | Workflow template ID |

### Endpoint parameters

None

### Request example

```
GET /sdk/template/{template_id}/get_template_operation_record/
```

### Response example

```json
{
     "result": true,
     "data": {
          "result": true,
          "message": "success",
          "data": [
               {
                    "id": 1,
                    "instance_id": 123,
                    "operate_type": "CREATE",
                    "operator": "admin",
                    "operate_source": "WEB",
                    "operate_date": "2024-12-15T21:10:43.284071+08:00",
                    "operate_type_name": "创建",
                    "operate_source_name": "app 页面",
                    "version": ""
               }
          ]
     },
     "code": "0",
     "message": ""
}
```

### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| message | string | Response message                  |
| data    | dict   | Response data: list of operation records           |
| code    | string | Response status code                 |

#### data[data][item] fields

| Field                  | Type      | Description     |
|---------------------|---------|--------|
| id                  | int     | Record ID   |
| instance_id         | int     | Instance ID   |
| operate_type        | string  | Operation type   |
| operator            | string  | Operator    |
| operate_date        | string  | Operation time   |
| operate_source      | string  | Operation source   |
| operate_type_name   | string  | Operation type description |
| operate_source_name | string  | Operation source description |
| version             | string  | Workflow version   |
