### 资源描述

流程常量预览结果（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 接口参数

| 字段        | 类型   | 必选 | 描述       |
|-----------|------|----|----------|
| constants  | dict | 是  | 流程常量定义   |
| extra_data | dict | 否  | 额外数据，用于常量计算 |

### constants 说明

constants 格式示例：
```json
{
    "var1": {
        "key": "var1",
        "name": "变量1",
        "value": "${var2}",
        "source_type": "custom"
    }
}
```

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "constants": {
        "var1": {
            "key": "var1",
            "name": "变量1",
            "value": "value1",
            "source_type": "custom"
        }
    },
    "extra_data": {}
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "var1": "resolved_value1"
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
| data    | dict   | 返回数据，key为变量名，value为解析后的值 |


