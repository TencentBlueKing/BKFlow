### 资源描述

获取第三方插件配置详情（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 权限说明

该接口使用默认权限，**不需要 HTTP_BKFLOW_TOKEN**。

### 接口参数

| 字段            | 类型     | 必选 | 描述       |
|---------------|--------|----|----------|
| plugin_code   | string | 是  | 插件代码     |
| plugin_version | string | 否  | 插件版本     |
| with_app_detail | bool | 否  | 是否包含应用详情，默认为false |

### 请求参数示例

```
GET /sdk/plugin_service/detail/?plugin_code=example_plugin&plugin_version=1.0.0&with_app_detail=true
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "plugin_code": "example_plugin",
        "plugin_version": "1.0.0",
        "name": "示例插件",
        "desc": "插件描述",
        "inputs": {},
        "outputs": {},
        "deployed_statuses": {},
        "app": {
            "app_code": "example_app",
            "app_name": "示例应用"
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

| 字段              | 类型     | 描述       |
|-----------------|--------|----------|
| plugin_code     | string | 插件代码     |
| plugin_version  | string | 插件版本     |
| name            | string | 插件名称     |
| desc            | string | 插件描述     |
| inputs          | dict   | 输入参数定义   |
| outputs         | dict   | 输出参数定义   |
| deployed_statuses | dict | 部署状态     |
| app             | dict   | 应用详情（当with_app_detail=true时返回） |


