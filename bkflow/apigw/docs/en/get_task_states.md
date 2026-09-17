### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get task status

### Common authentication parameters
|   Parameter   |    Type  |  Required  |     Description     |
| ------------ | ------------ | ------ | ---------------- |
| bk_app_code   | string | Yes | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |
| bk_app_secret | string | Yes | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### Response example

```json
{
    "result": true,
    "data": {
        "id": "ne7b82d4b9fd3378b93f97c2222a4b62",
        "state": "FINISHED",
        "root_id:": "ne7b82d4b9fd3378b93f97c2222a4b62",
        "parent_id": "ne7b82d4b9fd3378b93f97c2222a4b62",
        "version": "va054509441974d90bb82390de3320743",
        "loop": 1,
        "retry": 0,
        "skip": false,
        "error_ignorable": false,
        "error_ignored": false,
        "children": {
            "n112ae5c16c233efa5f3bff5b6c6375b": {
                "id": "n112ae5c16c233efa5f3bff5b6c6375b",
                "state": "FINISHED",
                "root_id:": "ne7b82d4b9fd3378b93f97c2222a4b62",
                "parent_id": "ne7b82d4b9fd3378b93f97c2222a4b62",
                "version": "v5fc1c39bf2d5408a8c6dab13708ba54c",
                "loop": 1,
                "retry": 0,
                "skip": false,
                "error_ignorable": false,
                "error_ignored": false,
                "children": {},
                "elapsed_time": 0,
                "start_time": "2023-06-15 17:29:41 +0800",
                "finish_time": "2023-06-15 17:29:41 +0800"
            },
            "nd1b94a5f14432d58622caee297273ca": {
                "id": "nd1b94a5f14432d58622caee297273ca",
                "state": "FINISHED",
                "root_id:": "ne7b82d4b9fd3378b93f97c2222a4b62",
                "parent_id": "ne7b82d4b9fd3378b93f97c2222a4b62",
                "version": "va79eab4eb3f64b4482a861ea5a211824",
                "loop": 1,
                "retry": 0,
                "skip": false,
                "error_ignorable": false,
                "error_ignored": false,
                "children": {},
                "elapsed_time": 0,
                "start_time": "2023-06-15 17:29:41 +0800",
                "finish_time": "2023-06-15 17:29:41 +0800"
            },
            "n97aec67e7a7341a9c2c36604cc8335c": {
                "id": "n97aec67e7a7341a9c2c36604cc8335c",
                "state": "FINISHED",
                "root_id:": "ne7b82d4b9fd3378b93f97c2222a4b62",
                "parent_id": "ne7b82d4b9fd3378b93f97c2222a4b62",
                "version": "v7612ecd5ed59462db4c10e481052621f",
                "loop": 1,
                "retry": 0,
                "skip": false,
                "error_ignorable": false,
                "error_ignored": false,
                "children": {},
                "elapsed_time": 0,
                "start_time": "2023-06-15 17:29:41 +0800",
                "finish_time": "2023-06-15 17:29:41 +0800"
            }
        },
        "elapsed_time": 0,
        "start_time": "2023-06-15 17:29:41 +0800",
        "finish_time": "2023-06-15 17:29:41 +0800"
    },
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

| Field              | Type     | Description        |
|-----------------|--------|-----------|
| id              | string | Task instance ID    |
| state           | string | Task status      |
| root_id         | string | Root task ID     |
| parent_id       | string | Parent task ID     |
| version         | string | Task version      |
| loop            | int    | Task loop count    |
| retry           | int    | Task retry count    |
| skip            | bool   | Whether the task was skipped    |
| error_ignorable | bool   | Whether task errors are ignored  |
| error_ignored   | bool   | Whether task errors are ignored  |
| children        | dict   | Node status list    |
| elapsed_time    | int    | Task duration in seconds |
| start_time      | string | Task start time    |
| finish_time     | string | Task end time    |
