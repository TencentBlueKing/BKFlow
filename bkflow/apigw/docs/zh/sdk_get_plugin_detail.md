### 资源描述

获取内置插件配置详情（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| HTTP_BKFLOW_TOKEN | string | 是  | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 接口申请。该 token 用于验证用户对指定空间的访问权限 |

### 路径参数

| 字段       | 类型     | 必选 | 描述    |
|----------|--------|----|-------|
| plugin_id | string | 是  | 插件代码  |

### 接口参数

| 字段       | 类型     | 必选 | 描述       |
|----------|--------|----|----------|
| space_id | int    | 否  | 空间ID     |
| version  | string | 否  | 插件版本    |

### 请求参数示例

```
GET /sdk/plugin/{plugin_id}/?space_id=1&version=1.0.0
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "code": "example_plugin",
        "name": "示例插件",
        "version": "1.0.0",
        "desc": "插件描述",
        "inputs": {
            "input1": {
                "type": "string",
                "label": "输入1",
                "required": true
            }
        },
        "outputs": {
            "output1": {
                "type": "string",
                "label": "输出1"
            }
        },
        "group_name": "分组名称",
        "status": true
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

| 字段        | 类型     | 描述       |
|-----------|--------|----------|
| code      | string | 插件代码     |
| name      | string | 插件名称     |
| version   | string | 插件版本     |
| desc      | string | 插件描述     |
| inputs    | dict   | 输入参数定义   |
| outputs   | dict   | 输出参数定义   |
| group_name | string | 分组名称     |
| status    | bool   | 是否启用     |


