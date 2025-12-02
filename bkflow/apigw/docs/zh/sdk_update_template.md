### 资源描述

保存流程（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| HTTP_BKFLOW_TOKEN | string | 是  | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 接口申请。该 token 用于验证用户对指定模板的编辑权限 |

### 路径参数

| 字段         | 类型     | 必选 | 描述    |
|------------|--------|----|-------|
| template_id | string | 是  | 流程模板ID |

### 接口参数

| 字段            | 类型     | 必选 | 描述               |
|---------------|--------|----|------------------|
| name          | string | 否  | 模板名称             |
| operator      | string | 否  | 更新人              |
| notify_config | json   | 否  | 通知配置             |
| desc          | string | 否  | 模板描述             |
| scope_type    | string | 否  | 模板范围类型           |
| scope_value   | string | 否  | 模板范围值            |
| source        | string | 否  | 模板来源(空间接入方自定义字段) |
| version       | string | 否  | 模板版本(空间接入方自定义字段) |
| extra_info    | dict   | 否  | 模板额外信息           |
| pipeline_tree | dict   | 否  | 流程树               |

### notify_config 示例

```json
{
  "notify_type": {
    "success": ["weixin", "wecom_robot", "sms"],
    "fail": ["mail", "voice", "weixin", "wecom_robot"]
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
    "name": "更新后的模板名",
    "desc": "更新后的描述"
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": 4,
        "space_id": "2",
        "name": "更新后的模板名",
        "desc": "更新后的描述",
        "notify_config": {},
        "scope_type": null,
        "scope_value": null,
        "pipeline_tree": {},
        "source": null,
        "version": "",
        "is_enabled": true,
        "extra_info": {}
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

| 字段            | 类型     | 描述       |
|---------------|--------|----------|
| id            | int    | 流程ID     |
| space_id      | int    | 流程所属空间ID |
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


