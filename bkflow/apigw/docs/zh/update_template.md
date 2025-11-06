### 资源描述

更新模板

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |


#### 接口参数

| 字段                 | 类型     | 必选 | 描述               |
|--------------------|--------|----|------------------|
| name               | string | 否  | 模板名称             |
| operator           | string | 否  | 更新人              |
| notify_config      | json   | 否  | 模板描述             |
| desc               | string | 否  | 空间描述             |
| scope_type         | string | 否  | 模板范围类型           |
| scope_value        | string | 否  | 模板范围值            |
| source             | string | 否  | 模板来源(空间接入方自定义字段) |
| version            | string | 否  | 模板版本(空间接入方自定义字段) |
| extra_info         | string | 否  | 模板额外信息           |
| pipeline_tree      | json   | 否  | 模板信息             |


### notify_config 示例:
```json
{
  "notify_type": {
    "success": [
      "weixin",
      "wecom_robot",
      "sms"
    ],
    "fail": [
      "mail",
      "voice",
      "weixin",
      "wecom_robot"
    ]
  },
  "notify_receivers": {
    "receiver_group": [],
    "more_receiver": ""
  }
}
```

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "模板名"
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": 4,
        "space_id": "2",
        "name": "模板名",
        "desc": null,
        "notify_config": {},
        "scope_type": null,
        "scope_value": null,
        "pipeline_tree": {
            "id": "pd0980c284042448380d29e046bf348fc",
            "start_event": {
                "incoming": "",
                "outgoing": "f22d707b4e7704868b51fbc504107da27",
                "type": "EmptyStartEvent",
                "id": "e39ce14ef5df644ccaa5236b50a9c44ca",
                "name": null
            },
            "end_event": {
                "incoming": [
                    "f520808740b9945f8b01fa1dd889945d9"
                ],
                "outgoing": "",
                "type": "EmptyEndEvent",
                "id": "e17aef95ed6934a428215b2a7a3fa4184",
                "name": null
            },
            "activities": {
                "e36e8026b07b5448299b52f91a9d265af": {
                    "incoming": [
                        "f22d707b4e7704868b51fbc504107da27"
                    ],
                    "outgoing": "f520808740b9945f8b01fa1dd889945d9",
                    "type": "ServiceActivity",
                    "id": "e36e8026b07b5448299b52f91a9d265af",
                    "name": null,
                    "error_ignorable": false,
                    "timeout": null,
                    "skippable": true,
                    "retryable": true,
                    "component": {
                        "code": "example_component",
                        "inputs": {}
                    },
                    "optional": false
                }
            },
            "gateways": {},
            "flows": {
                "f22d707b4e7704868b51fbc504107da27": {
                    "is_default": false,
                    "source": "e39ce14ef5df644ccaa5236b50a9c44ca",
                    "target": "e36e8026b07b5448299b52f91a9d265af",
                    "id": "f22d707b4e7704868b51fbc504107da27"
                },
                "f520808740b9945f8b01fa1dd889945d9": {
                    "is_default": false,
                    "source": "e36e8026b07b5448299b52f91a9d265af",
                    "target": "e17aef95ed6934a428215b2a7a3fa4184",
                    "id": "f520808740b9945f8b01fa1dd889945d9"
                }
            },
            "data": {
                "inputs": {},
                "outputs": []
            }
        },
        "source": null,
        "version": "",
        "is_enabled": true,
        "extra_info": {},
        "creator": "",
        "create_at": "2024-08-02T08:53:20.173Z",
        "update_at": "2024-08-02T08:53:20.173Z",
        "updated_by": ""
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

| 字段            | 类型     | 描述       |
|---------------|--------|----------|
| id            | string | 流程ID     |
| space_id      | string | 流程所属空间ID |
| name          | string | 流程名称     |
| desc          | string | 流程描述     |
| notify_config | dict   | 通知配置     |
| scope_type    | string | 流程范围类型   |
| scope_value   | string | 流程范围ID   |
| pipeline_tree | dict   | 流程树详情    |
| source        | string | 流程来源     |
| version       | string | 流程版本     |
| is_enabled    | bool   | 流程是否启用   |
| extra_info    | dict   | 流程扩展信息   |
| creator       | string | 流程创建者    |
| create_at     | string | 流程创建时间   |
| update_at     | string | 流程更新时间   |
| updated_by    | string | 流程更新者    |