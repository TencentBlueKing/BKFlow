### 资源描述

检测流程变量的key（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 权限说明

该接口使用默认权限，**不需要 HTTP_BKFLOW_TOKEN**。

### 接口参数

| 字段 | 类型     | 必选 | 描述                    |
|----|--------|----|-----------------------|
| key | string | 是  | 变量key，支持格式为 ${key} 或 key |

### 请求参数示例

```
GET /sdk/template/variable/check_variable_key/?key=var_name
```

或

```
GET /sdk/template/variable/check_variable_key/?key=${var_name}
```

### 返回结果示例

```json
{
    "result": true,
    "data": null,
    "code": 0,
    "message": ""
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败。如果key不合法，会返回false并附带错误信息 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息，当key不合法时会返回错误提示 |
| data    | null   | 占位字段                |

### 注意事项

1. key 不能为空
2. key 不能是 Python 关键字（如 if, for, class 等）
3. key 不能在系统的变量黑名单中
4. 支持 `${key}` 格式，会自动提取中间的 key 值进行验证


