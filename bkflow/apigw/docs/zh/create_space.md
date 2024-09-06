### 资源描述

创建空间

### 输入通用参数说明
|   参数名称   |    参数类型  |  必须  |     参数说明     |
| ------------ | ------------ | ------ | ---------------- |
| bk_app_code   | string | 是 | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| bk_app_secret | string | 是 | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |


#### 接口参数

| 字段  | 类型  | 必选  | 描述                                                                 |
| --- | --- | --- |--------------------------------------------------------------------|
|  name   |  string   |  是   | 空间名                                                                |
|  platform_url   |  string   |  是   | 空间平台服务地址                                                           |
|  desc |  string   |  否   | 空间描述                                                               |
|  app_code   |  string   |  是   | 空间所绑定的app_code, 后续该空间下的资源只有该app_code有权限操作和访问，目前仅允许使用发起请求的 app_code |
|  config   |  dict   |  否  | 空间创建时所携带的配置信息                                                      |


### config 说明
config 允许传入空间下的配置，现阶段支持的配置有:
```json
{
    "space_plugin_config": {},
    "token_expiration": "token的过期时间，格式如：1h,1m。 默认是1h",
    "token_auto_renewal": "是否开启自动续期，'true' or 'false'",
    "callback_hooks": {
        "url": "回调url，需要是网关url",
        "callback_types": [
            "template"
        ]
    },
    "uniform_api": "",
    "api_gateway_credential_name": "api gateway 所使用的凭证名称"
}
```


### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "空间名",
    "platform_url": "http://www.tencent.com",
    "desc": "这是一段默认描述",
    "app_code": "bksops",
    "config": {}
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": 3,
        "name": "空间名",
        "desc": "这是一段默认描述",
        "platform_url": "http://www.tencent.com",
        "app_code": "bksops",
        "create_type": "API"
    },
    "code": 0
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
| ------- | ------ | --------------------- |
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict  | 返回数据                    |

### data
| 字段      | 类型     | 描述                    |
| ------- | ------ | --------------------- |
| id | int | 空间ID                |
| name | string | 空间名                |
| desc | string | 空间描述                  |
| platform_url | string | 空间服务地址                  |
| app_code    | string  | 空间描述     |
| create_type    | string  | 空间创建方式     |