### 资源描述

更新并覆盖空间下的配置

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

#### 接口参数

| 字段     | 类型   | 必选 | 描述   |
|--------|------|----|------|
| config | json | 是  | 空间配置 |

#### 空间配置说明
| 字段                          | 类型     | 必选 | 描述                                                          |
|-----------------------------|--------|----|-------------------------------------------------------------|
| space_plugin_config         | json   | 否  | 空间插件配置                                                      |
| token_expiration            | string | 否  | token过期时间，默认为1h                                             |
| token_auto_renewal          | string | 否  | 是否开启token自动续期，默认为开启，token会在用户操作的过程中自动续期，避免用户操作过程中token失效的问题 |
| callback_hooks              | json   | 否  | 回调配置, 请优先使用 apply_webhook_configs 进行回调配置                    |
| uniform_api                 | json   | 否  | 统一API配置                                                     |
| api_gateway_credential_name | json   | 否  | 默认使用的网关凭证名称                                                 |
| superusers                  | json   | 否  | 空间管理员列表， 默认为[]                                              |
| canvas_mode                 | string | 否  | 空间画布布局方式，合法值为 "horizontal" 和 "vertical"，默认为横版画布。            |

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "config": {
        "token_auto_renewal": "true"
    }
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "space_id": 2,
        "config": [
            {
                "key": "token_auto_renewal",
                "value": "true"
            },
            {
                "key": "token_expiration",
                "value": "1h"
            }
        ]
    },
    "code": 0,
    "trace_id": "ecb0dd8707194245a5a88b7f0e3b3c16"
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 当前空间下的配置详情            |

#### data[item]

| 字段       | 类型   | 描述     |
|----------|------|--------|
| space_id | int  | 空间ID   |
| config   | list | 空间配置列表 |