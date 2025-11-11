### 资源描述

获取流程变量类型（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 接口参数

无

### 请求参数示例

```
GET /sdk/template/variable/
```

### 返回结果示例

```json
{
    "result": true,
    "data": [
        {
            "code": "input",
            "name": "输入",
            "desc": "输入变量",
            "type": "input",
            "status": true
        },
        {
            "code": "output",
            "name": "输出",
            "desc": "输出变量",
            "type": "output",
            "status": true
        }
    ],
    "code": 0
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | list   | 返回数据，变量类型列表            |

#### data[item] 字段说明

| 字段   | 类型     | 描述   |
|------|--------|------|
| code | string | 变量类型代码 |
| name | string | 变量类型名称 |
| desc | string | 变量类型描述 |
| type | string | 变量类型   |
| status | bool | 是否启用   |


