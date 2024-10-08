### 资源描述

获取空间配置

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "space_id": 1,
        "config": [
            {
                "key": "canvas_mode",
                "value": "horizontal"
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

#### data[item]
| 字段       | 类型   | 描述     |
|----------|------|--------|
| space_id | int  | 空间ID   |
| config   | list | 空间配置列表 |
