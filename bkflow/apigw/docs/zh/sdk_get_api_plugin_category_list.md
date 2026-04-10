### 资源描述

获取uniform_api插件列表（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| HTTP_BKFLOW_TOKEN | string | 是  | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 接口申请。该 token 用于验证用户对指定空间资源的访问权限（需要提供 template_id 或 task_id） |

### 路径参数

| 字段            | 类型     | 必选 | 描述      |
|---------------|--------|----|---------|
| space_id      | string | 是  | 空间ID    |
| template_id   | int    | 是  | 模板ID    |
| task_id       | int    | 是  | 任务ID    |
| api_name      | string | 是  | API_KEY |

### 接口参数

无

### 请求参数示例

```
GET /sdk/plugin_query/uniform_api/category_list/{space_id}/
```

### 返回结果示例

```json
{
    "result": true,
    "data": [
        {
            "id": 1,
            "name": "model",
            "alias": "模型",
            "properties": {
                "llm": "大模型"
            }
        }
    ],
    "message": "",
    "code": "0"
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | string | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | list   | 返回数据                  |

#### data[item] 字段说明

| 字段         | 类型       | 描述   |
|------------|----------|------|
| id         | int      | 插件id |
| name       | string   | 插件名称 |
| alias      | string   | 插件别名 |
| properties | dict     | 插件属性 |


