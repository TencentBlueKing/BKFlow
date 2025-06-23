### 资源描述

创建模板

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

#### 接口参数

| 字段             | 类型     | 必选 | 描述               |
|----------------|--------|----|------------------|
| name           | string | 是  | 模板名称             |
| pipeline_data  | json   | 是  | 模板信息             |
| creator        | string | 否  | 创建人              |
| notify_config  | json   | 否  | 模板描述             |
| desc           | string | 否  | 空间描述             |
| scope_type     | string | 否  | 模板范围类型           |
| scope_value    | string | 否  | 模板范围值            |
| source         | string | 否  | 模板来源(空间接入方自定义字段) |
| version        | string | 否  | 模板版本(空间接入方自定义字段) |
| extra_info     | string | 否  | 模板额外信息           |


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
