### 资源描述

获取插件Tag分类（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 权限说明

该接口使用默认权限，**不需要 HTTP_BKFLOW_TOKEN**。

### 接口参数

无

### 请求参数示例

```
GET /sdk/plugin_service/tags/
```

### 返回结果示例

```json
{
    "result": true,
    "data": [
        {
            "id": 1,
            "name": "Tag1",
            "code_name": "tag1",
            "priority": 1
        }
    ],
    "code": "0",
    "message": ""
}
```

### 返回结果参数说明

| 字段        | 类型       | 描述                    |
|-----------|----------|-----------------------|
| result    | bool     | 返回结果，true为成功，false为失败 |
| code      | string   | 返回码，0表示成功，其他值表示失败     |
| message   | string   | 错误信息                  |
| data      | list     | 返回数据，标签列表             |

#### data[item] 字段说明

| 字段          | 类型     | 描述   |
|-------------|--------|------|
| id          | int    | 标签ID |
| name        | string | 标签名称 |
| code_name   | string | 标签代码 |
| priority    | int    | 优先级  |


