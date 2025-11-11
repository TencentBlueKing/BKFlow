### 资源描述

获取第三方插件元数据（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 接口参数

| 字段          | 类型     | 必选 | 描述    |
|-------------|--------|----|-------|
| plugin_code | string | 是  | 插件代码  |

### 请求参数示例

```
GET /sdk/plugin_service/meta/?plugin_code=example_plugin
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "plugin_code": "example_plugin",
        "meta": {
            "version": "1.0.0",
            "description": "插件元数据描述",
            "author": "作者",
            "tags": ["tag1", "tag2"]
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

| 字段         | 类型     | 描述       |
|------------|--------|----------|
| plugin_code | string | 插件代码     |
| meta       | dict   | 插件元数据    |


