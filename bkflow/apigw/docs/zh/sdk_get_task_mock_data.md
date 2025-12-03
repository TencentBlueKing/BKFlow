### 资源描述

获取任务的mock数据（SDK接口）

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

| 字段     | 类型     | 必选 | 描述   |
|--------|--------|----|------|
| task_id | string | 是  | 任务ID |

### 接口参数

无

### 请求参数示例

```
GET /sdk/task/get_task_mock_data/{task_id}/
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "taskflow_id": 123,
        "nodes": [
            {
                "node_id": "node1",
                "data": {
                    "input1": "value1",
                    "input2": "value2"
                },
                "is_default": false
            }
        ]
    },
    "code": 0
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |

#### data 字段说明

| 字段          | 类型     | 描述                    |
|-------------|--------|-----------------------|
| taskflow_id | int    | 任务流程ID                |
| nodes       | list   | mock节点数据列表             |

#### data.nodes[item] 字段说明

| 字段         | 类型     | 描述                    |
|------------|--------|-----------------------|
| node_id    | string | 节点ID                  |
| data       | dict   | 节点mock数据              |
| is_default | bool   | 是否为默认mock数据            |


