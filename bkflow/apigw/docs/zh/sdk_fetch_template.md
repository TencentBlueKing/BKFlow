### 资源描述

获取流程详情（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| HTTP_BKFLOW_TOKEN | string | 是  | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 接口申请。该 token 用于验证用户对指定模板的查看权限 |

### 路径参数

| 字段         | 类型     | 必选 | 描述    |
|------------|--------|----|-------|
| template_id | string | 是  | 流程模板ID |

### 接口参数

| 字段             | 类型   | 必选 | 描述                                                                                                                                    |
|----------------|------|----|---------------------------------------------------------------------------------------------------------------------------------------|
| with_mock_data | bool | 否  | 是否一起返回 mock 数据，默认为 false。 当设置为 true 时，返回数据中会增加 appoint_node_ids 和 mock_data 两个字段，且如果 appoint_node_ids 有指定 mock 执行节点时，pipeline_tree 会进行对应的精简。 |

### 请求参数示例

```
GET /sdk/template/{template_id}/?with_mock_data=false
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": 3,
        "space_id": 2,
        "name": "测试模板",
        "desc": null,
        "notify_config": {},
        "scope_type": null,
        "scope_value": null,
        "pipeline_tree": {
            "id": "p92c20c7854104dd3975f46a1d8664417",
            "start_event": {},
            "end_event": {},
            "activities": {},
            "gateways": {},
            "flows": {},
            "data": {
                "inputs": {},
                "outputs": []
            }
        },
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

| 字段            | 类型     | 描述                    |
|---------------|--------|-----------------------|
| id            | int    | 流程ID                  |
| space_id      | int    | 流程所属空间ID              |
| name          | string | 流程名称                  |
| desc          | string | 流程描述                  |
| notify_config | dict   | 流程通知配置                |
| scope_type    | string | 流程所属作用域类型              |
| scope_value   | string | 流程所属作用域值               |
| pipeline_tree | dict   | 流程树详情                 |
| source        | string | 流程来源                  |
| version       | string | 流程版本号                 |
| is_enabled    | bool   | 是否启用                  |
| extra_info    | dict   | 额外信息                  |


