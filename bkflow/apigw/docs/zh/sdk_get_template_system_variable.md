### 资源描述

获取系统变量（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 接口参数

无

### 请求参数示例

```
GET /sdk/template/variable/system_variable/
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "executor": {
            "name": "执行人",
            "desc": "当前任务执行人",
            "type": "string"
        },
        "executor_nickname": {
            "name": "执行人昵称",
            "desc": "当前任务执行人昵称",
            "type": "string"
        },
        "space_id": {
            "name": "空间ID",
            "desc": "当前任务所属空间ID",
            "type": "integer"
        }
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
| data    | dict   | 返回数据，系统变量字典            |

#### data[variable_key] 字段说明

| 字段   | 类型     | 描述     |
|------|--------|--------|
| name | string | 变量名称   |
| desc | string | 变量描述   |
| type | string | 变量类型   |


