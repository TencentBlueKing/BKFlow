### 资源描述

获取任务节点信息

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| HTTP_BKFLOW_TOKEN | string | 是  | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 接口申请。该 token 用于验证用户对指定任务的查看权限 |

### 路径参数

| 字段        | 类型     | 必选 | 描述   |
|-----------|--------|----|------|
| task_id   | string | 是  | 任务ID |
| node_id   | string | 是  | 节点ID |

### 接口参数

| 字段                | 类型     | 必选 | 描述     |
|-------------------|--------|----|--------|
| component_code    | string | 是  | 插件code |
| space_id          | int    | 是  | 空间ID   |


### 返回结果示例

```json
{
     "result": true,
     "data": {
          "id": "nf8c5d3caee13bfebb4a19f308294f1f",
          "state": "FINISHED",
          "root_id:": "n6766bff75cf35bc91c74488344b4039",
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

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |

#### data 字段说明

| 字段                   | 类型     | 描述                |
|----------------------|--------|-------------------|
| id                   | string | 节点id              |
| state                | string | 节点状态              |
| root_id              | string | 根节点id             |
| parent_id            | string | 父节点id             |
| version              | string | 节点版本              |
| loop                 | int    | 循环次数              |
| retry                | int    | 重试次数              |
| skip                 | bool   | 是否跳过              |
| error_ignorable      | bool   | 是否可忽略错误           |
| error_ignored        | bool   | 是否忽略错误            |
| children             | dict   | 子节点信息             |
| elapsed_time         | int    | 延迟时间              |
| start_time           | string | 开始时间              |
| finish_time          | list   | 结束时间              |
| histories            | list   | 历史信息              |
| history_id           | list   | 历史记录id，获取全部记录时为-1 |
| inputs               | dict   | 输入信息              |
| outputs              | dict   | 输出信息              |
| ex_data              | string | 失败信息              |

