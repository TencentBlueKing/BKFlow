### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Create a mock task

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

| Field      | Type     | Required | Description   |
|---------|--------|----|------|
| template_id | string | Yes  | Template ID |

#### Endpoint parameters

| Field                    | Type     | Required | Description                                                                                                                                                              |
|----------------------|--------|----|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name                  | string | Yes  | Task name                                                                                                                                                             |
| creator               | string | Yes  | Created by                                                                                                                                                             |
| description           | string | No  | Description                                                                                                                                                              |
| constants             | dict   | No  | Task startup parameters                                                                                                                                                          |
| credentials           | dict   | No  | Credential dictionary containing credentials for API calls; see below                                                                                                                              |
| custom_span_attributes | dict   | No  | Custom Span attributes added to every node Span; see below                                                                                                                              |
| mock_data             | dict   | No  | Mock data: nodes (nodes using mock execution), outputs (optional outputs for those nodes), and mock_data_ids (mock data IDs used by those nodes; when outputs is omitted, the corresponding mock data at task creation is used as outputs) |

### credentials parameter

The `credentials` parameter passes API credentials when creating a task. It is a dictionary whose keys are credential identifiers and whose values are base64-encoded JSON strings.

**Credential format:**
- key: credential identifier
- value: a base64-encoded JSON string that decodes to a dictionary containing `bk_app_code` and `bk_app_secret`

**Credential priority for API plugins:**
1. If task creation supplies `credentials` and a credential key matches `api_gateway_credential_name` in the space settings, the supplied credential takes precedence.
2. If no matching credential is supplied, the space's `credential` setting is used.

**Credential example:**
```json
{
    "credentials": {
        "my_credential": "eyJia19hcHBfY29kZSI6ICJteV9hcHAiLCAiYmtfYXBwX3NlY3JldCI6ICJteV9zZWNyZXQifQ=="
    }
}
```

The base64-decoded content is:
```json
{
    "bk_app_code": "my_app",
    "bk_app_secret": "my_secret"
}
```

**Notes:**
- Credentials are stored in the task's `extra_info.custom_context.credentials` for workflow execution.
- Credentials are used only to authenticate API calls from Uniform API plugins (uniform_api).
- If the space's `api_gateway_credential_name` is a dictionary (supporting different credentials by scope), the system matches the credential name using the task's scope_type and scope_value.

### custom_span_attributes parameter

The `custom_span_attributes` parameter passes custom attributes to every node Span when creating a task, allowing custom instrumentation.

**Parameter format:**
- Type: dictionary (dict)
- key: custom attribute name (string)
- value: custom attribute value (serializable string, number, etc.)

**Use cases:**
- Business instrumentation: business IDs, order IDs, and other business identifiers
- Request instrumentation: request IDs, trace IDs, and other request identifiers
- Environment instrumentation: environment types, regions, and other environment information

**Example:**
```json
{
    "custom_span_attributes": {
        "business_id": "12345",
        "request_id": "req-abc-123",
        "test_mode": "mock"
    }
}
```

**Notes:**
- Custom attributes are stored in the task's `extra_info.custom_context.custom_span_attributes`.
- These attributes are passed to every node Span through `TaskContext`.
- Custom attributes take precedence over default Span attributes (such as space_id and task_id) with the same key.

### pipeline_tree version selection

When creating a mock task, the system selects the workflow version automatically:

1. **Prefer the draft:** if the template has a draft (`draft=True`), its `pipeline_tree` is used to create the debug task.
2. **Use the latest published version:** if there is no draft, the latest published version's `pipeline_tree` is used.

This ensures debugging uses the latest unpublished changes when available, otherwise the published stable version.

### Request example

Basic request example:
```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "空间名",
    "template_id": 4,
    "creator": "创建者",
    "mock_data": {
        "nodes": [
            "nd7927122ef6310eb309c2c8d3f70c23"
        ],
        "outputs": {
            "nd7927122ef6310eb309c2c8d3f70c23": {
                "callback_data": "abc"
            }
        },
        "mock_data_ids": {
            "nd7927122ef6310eb309c2c8d3f70c23": 1
        }
    }
}
```

Request example with credentials:
```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "空间名",
    "template_id": 4,
    "creator": "创建者",
    "credentials": {
        "my_credential": "eyJia19hcHBfY29kZSI6ICJteV9hcHAiLCAiYmtfYXBwX3NlY3JldCI6ICJteV9zZWNyZXQifQ=="
    },
    "mock_data": {
        "nodes": [
            "nd7927122ef6310eb309c2c8d3f70c23"
        ],
        "outputs": {
            "nd7927122ef6310eb309c2c8d3f70c23": {
                "callback_data": "abc"
            }
        },
        "mock_data_ids": {
            "nd7927122ef6310eb309c2c8d3f70c23": 1
        }
    }
}
```

Request example with custom Span attributes:
```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "空间名",
    "template_id": 4,
    "creator": "创建者",
    "custom_span_attributes": {
        "business_id": "12345",
        "request_id": "req-abc-123",
        "test_mode": "mock"
    },
    "mock_data": {
        "nodes": [
            "nd7927122ef6310eb309c2c8d3f70c23"
        ],
        "outputs": {
            "nd7927122ef6310eb309c2c8d3f70c23": {
                "callback_data": "abc"
            }
        },
        "mock_data_ids": {
            "nd7927122ef6310eb309c2c8d3f70c23": 1
        }
    }
}
```

### Response example

```json
{
    "result": true,
    "data": {
        "id": 10,
        "space_id": 1,
        "scope_type": null,
        "scope_value": null,
        "instance_id": "6e15e7cf27ab3129878cdd9b95fff006",
        "template_id": 4,
        "name": "default_taskflow_instance",
        "creator": "",
        "create_time": "2023-04-23T21:10:06.826644+08:00",
        "create_method": "MOCK",
        "executor": "",
        "start_time": null,
        "finish_time": null,
        "description": "",
        "is_started": false,
        "is_finished": false,
        "is_revoked": false,
        "is_deleted": false,
        "is_expired": false,
        "snapshot_id": 3,
        "execution_snapshot_id": 8,
        "tree_info_id": null,
        "extra_info": {}
        },
    "code": "0",
    "message": ""
}

```
### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| code    | int    | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | dict   | Response data                  |

#### data[item]

| Field                    | Type     | Description       |
|-----------------------|--------|----------|
| id                    | int    | Task ID     |
| space_id              | int    | Space ID     |
| scope_type            | string | Task scope type   |
| scope_value           | string | Task scope value    |
| instance_id           | string | Instance ID     |
| template_id           | int    | Template ID     |
| name                  | string | Task name     |
| creator               | string | Created by      |
| create_time           | string | Creation time     |
| executor              | string | Executor      |
| start_time            | string | Start time     |
| finish_time           | string | End time     |
| description           | string | Description       |
| is_started            | bool   | Whether started    |
| is_finished           | bool   | Whether finished    |
| is_revoked            | bool   | Whether revoked    |
| is_deleted            | bool   | Whether deleted    |
| is_expired            | bool   | Whether expired    |
| snapshot_id           | int    | Snapshot ID     |
| execution_snapshot_id | int    | Execution snapshot ID   |
| tree_info_id          | int    | Task topology ID |
| extra_info            | dict   | Additional task information   |
