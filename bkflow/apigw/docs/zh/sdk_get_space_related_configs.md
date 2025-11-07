### 资源描述

获取空间下的流程相关配置（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 路径参数

| 字段         | 类型     | 必选 | 描述    |
|------------|--------|----|-------|
| template_id | string | 是  | 流程模板ID |

### 接口参数

无

### 请求参数示例

```
GET /sdk/template/{template_id}/get_space_related_configs/
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "gateway_expression": {
            "enabled": true,
            "expression": "表达式配置"
        },
        "uniform_api": {
            "enabled": true,
            "config": "配置信息"
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
| data    | dict   | 返回数据                  |

#### data 字段说明

| 字段                | 类型   | 描述       |
|-------------------|------|----------|
| gateway_expression | dict | 网关表达式配置 |
| uniform_api       | dict | Uniform API配置 |


