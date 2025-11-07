### 资源描述

操作任务（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 路径参数

| 字段      | 类型     | 必选 | 描述       |
|---------|--------|----|----------|
| task_id | string | 是  | 任务ID     |
| action  | string | 是  | 操作类型      |

### action 说明

支持的操作类型：
- `start`: 启动任务
- `pause`: 暂停任务
- `resume`: 恢复任务
- `revoke`: 撤销任务

### 接口参数

| 字段      | 类型     | 必选 | 描述       |
|---------|--------|----|----------|
| operator | string | 否  | 操作人，默认为当前用户 |

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "operator": "admin"
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "task_id": 123,
        "state": "RUNNING"
    },
    "code": 0,
    "message": ""
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

| 字段      | 类型     | 描述   |
|---------|--------|------|
| task_id | int    | 任务ID |
| state   | string | 任务状态 |


