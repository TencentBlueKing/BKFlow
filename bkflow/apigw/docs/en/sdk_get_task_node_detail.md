### Tenant access constraints

When multi-tenancy is enabled, an all-tenant application must specify the request tenant through `X-Bk-Tenant-Id`. A single-tenant application may omit this header and use the authenticated application tenant in the JWT; any explicit header must match it. The request tenant must match the tenant of the resource's space. An all-tenant application must create separate spaces for each tenant. Existing application-to-space/template bindings still apply. If the JWT contains an authenticated user, that user's tenant must also match. Missing or mismatched tenant information causes the request to be rejected.

Application-authenticated endpoints do not require an additional user identity. SDK user-authenticated endpoints still require an authenticated user; platform administrators and space administrators cannot cross tenant boundaries. Disabling multi-tenancy preserves single-tenant behavior.

### Resource description

Get task node information

### Common authentication parameters

| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |

### HTTP header parameters

| Parameter         | Type   | Required | Description                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | Yes  | Access token obtained from `/space/{space_id}/apply_token/`. This token verifies the user's permission to view the specified task. |

### Path parameters

| Field        | Type     | Required | Description   |
|-----------|--------|----|------|
| task_id   | string | Yes  | Task ID |
| node_id   | string | Yes  | Node ID |

### Endpoint parameters

| Field                | Type     | Required | Description     |
|-------------------|--------|----|--------|
| component_code    | string | No  | Plugin code |
| space_id          | int    | Yes  | Space ID   |


### Response example

```json
{
     "result": true,
     "data": {
          "id": "nf8c5d3caee13bfebb4a19f308294f1f",
          "state": "FINISHED",
          "root_id": "n6766bff75cf35bc91c74488344b4039",
          "parent_id": "n6766bff75cf35bc91c74488344b4039",
          "version": "v583e76d40b3541be82b803cc8088aae0",
          "loop": 1,
          "retry": 1,
          "skip": true,
          "error_ignorable": false,
          "error_ignored": false,
          "children": {},
          "elapsed_time": 85,
          "start_time": "2026-04-28 11:52:02 +0800",
          "finish_time": "2026-04-28 11:53:27 +0800",
          "histories": [
               {
                    "id": 5538,
                    "node_id": "nf8c5d3caee13bfebb4a19f308294f1f",
                    "retry": 0,
                    "loop": 1,
                    "skip": false,
                    "version": "v2086f83701404cf9be89747c48a8fcc2",
                    "inputs": {
                         "_loop": 1,
                         "_inner_loop": 1,
                         "bk_http_request_method": "GET",
                         "bk_http_request_url": "123",
                         "bk_http_request_header": [],
                         "bk_http_request_body": "",
                         "bk_http_timeout": 5,
                         "bk_http_success_exp": ""
                    },
                    "outputs": [
                         {
                              "name": "响应内容",
                              "key": "data",
                              "value": "",
                              "preset": true
                         },
                         {
                              "name": "状态码",
                              "key": "status_code",
                              "value": "",
                              "preset": true
                         },
                         {
                              "name": "执行结果",
                              "key": "_result",
                              "value": false,
                              "preset": true
                         },
                         {
                              "name": "循环次数",
                              "key": "_loop",
                              "value": 1,
                              "preset": true
                         },
                         {
                              "name": "当前流程循环次数",
                              "key": "_inner_loop",
                              "value": 1,
                              "preset": true
                         },
                         {
                              "name": "ex_data",
                              "key": "ex_data",
                              "value": "请求异常，详细信息: Invalid URL '123': No scheme supplied. Perhaps you meant https://123?",
                              "preset": false
                         }
                    ],
                    "ex_data": "请求异常，详细信息: Invalid URL '123': No scheme supplied. Perhaps you meant https://123?",
                    "state": "FAILED",
                    "history_id": 5538,
                    "children": {},
                    "elapsed_time": 0,
                    "start_time": "2026-04-28 11:51:57 +0800",
                    "finish_time": "2026-04-28 11:51:57 +0800"
               }
          ],
          "history_id": -1,
          "inputs": {
               "_loop": 1,
               "_inner_loop": 1,
               "bk_http_request_method": "GET",
               "bk_http_request_url": "123",
               "bk_http_request_header": [],
               "bk_http_request_body": "",
               "bk_http_timeout": 5,
               "bk_http_success_exp": ""
          },
          "outputs": [
               {
                    "name": "响应内容",
                    "key": "data",
                    "value": "",
                    "preset": true
               },
               {
                    "name": "状态码",
                    "key": "status_code",
                    "value": "",
                    "preset": true
               },
               {
                    "name": "执行结果",
                    "key": "_result",
                    "value": false,
                    "preset": true
               },
               {
                    "name": "循环次数",
                    "key": "_loop",
                    "value": 1,
                    "preset": true
               },
               {
                    "name": "当前流程循环次数",
                    "key": "_inner_loop",
                    "value": 1,
                    "preset": true
               },
               {
                    "name": "ex_data",
                    "key": "ex_data",
                    "value": "请求异常，详细信息: Invalid URL '123': No scheme supplied. Perhaps you meant https://123?",
                    "preset": false
               }
          ],
          "ex_data": "请求异常，详细信息: Invalid URL '123': No scheme supplied. Perhaps you meant https://123?"
     },
     "message": "",
     "exc": null,
     "exc_trace": null
}
```

### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| message | string | Error message                  |
| data    | dict   | Response data                  |

#### Data fields

| Field                   | Type     | Description                |
|----------------------|--------|-------------------|
| id                   | string | Node ID              |
| state                | string | Node status              |
| root_id              | string | Root node ID             |
| parent_id            | string | Parent node ID             |
| version              | string | Node version              |
| loop                 | int    | Loop count              |
| retry                | int    | Retry count              |
| skip                 | bool   | Whether the node was skipped              |
| error_ignorable      | bool   | Whether errors can be ignored           |
| error_ignored        | bool   | Whether errors are ignored            |
| children             | dict   | Child node information             |
| elapsed_time         | int    | Delay              |
| start_time           | string | Start time              |
| finish_time          | list   | End time              |
| histories            | list   | History              |
| history_id           | list   | History record ID; -1 to retrieve all records |
| inputs               | dict   | Inputs              |
| outputs              | dict   | Outputs              |
| ex_data              | string | Failure information              |
