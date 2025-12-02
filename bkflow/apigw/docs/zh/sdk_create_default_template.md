### 资源描述

创建流程（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 权限说明

该接口需要用户是系统超级管理员或指定空间的超级管理员，**不需要 HTTP_BKFLOW_TOKEN**。

### 路径参数

| 字段      | 类型     | 必选 | 描述   |
|---------|--------|----|------|
| space_id | string | 是  | 空间ID |

### 接口参数

| 字段            | 类型     | 必选 | 描述               |
|---------------|--------|----|------------------|
| name          | string | 是  | 模板名称             |
| pipeline_tree | dict   | 是  | 流程树               |
| desc          | string | 否  | 模板描述             |
| notify_config | json   | 否  | 通知配置             |
| scope_type    | string | 否  | 模板范围类型           |
| scope_value   | string | 否  | 模板范围值            |
| source        | string | 否  | 模板来源(空间接入方自定义字段) |
| version       | string | 否  | 模板版本(空间接入方自定义字段) |
| extra_info    | dict   | 否  | 模板额外信息           |
| triggers      | list   | 否  | 触发器列表            |

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "新流程",
    "pipeline_tree": {
        "start_event": {},
        "end_event": {},
        "activities": {},
        "gateways": {},
        "flows": {}
    },
    "desc": "流程描述"
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": 4,
        "space_id": 2,
        "name": "新流程",
        "desc": "流程描述",
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

参考 `sdk_fetch_template.md` 中的 data 字段说明。


