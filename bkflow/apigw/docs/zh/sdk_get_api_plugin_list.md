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

### 接口参数

| 字段          | 类型      | 必选 | 描述                                                                                  |
|-------------|---------|----|-------------------------------------------------------------------------------------|
| template_id | int     | 否  | 模板ID                                                                                |
| task_id     | string  | 否  | 任务ID                                                                                |
| limit       | int     | 否  | 分页大小，默认 50                                                                          |
| offset      | int     | 否  | 分页偏移量，默认 0                                                                         |
| scope_type  | string  | 否  | 业务范围类型                                                                              |
| scope_value | string  | 否  | 业务范围值                                                                               |
| category    | string  | 否  | 分类标识，用于按分类筛选插件                                                                      |
| key         | string  | 否  | 分组/关键字标识                                                                            |
| api_name    | string  | 否  | 统一API的 api_key，默认取接入平台配置的默认 API_KEY；用于指定访问哪一个统一API列表配置             |

注意：template_id 和 task_id 参数至少需要传递一个

### 请求参数示例

```
GET /sdk/plugin_query/uniform_api/list/{space_id}/?template_id=10&category=model&limit=50&offset=0
```

### 返回结果示例

```json
{
     "result": true,
     "code": "0",
     "message": "",
     "data": {
         "total": 1,
         "apis": [
              {
                   "id": "model-65",
                   "name": "test",
                   "alias": "test",
                   "meta_url": "xxx",
                   "category": "model",
                   "group": "llm",
                   "plugin_type": "uniform_api",
                   "version": "v3.0.0",
                   "display_content": {
                        "llm_code": "test",
                        "llm_name": "test",
                        "base_model": "qwen",
                        "context_length": "128K",
                        "created_at": "2026-04-15 21:35:10",
                        "created_by": "xxx",
                        "description": "基于模型能力与资源情况推荐的大语言模型，当前指向 qwen3-5-397B",
                        "icon": "xxx",
                        "tag_names": [["工具调用"],["图生文"],["多轮会话"],["知识摘要"]]
                   },
                   "source_key": "aidev"
              }
         ]
     }
}
```

> 说明：实际响应会在外层包裹标准网关结构 `{ "result": true, "code": "0", "message": "", "data": {...} }`，下文 data 字段说明以 data 内结构为准。

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | string | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |

#### data 字段说明

| 字段   | 类型  | 描述            |
|------|-----|---------------|
| total | int | 插件总数          |
| apis | list | 统一API插件列表（详见 apis[item]） |

#### apis[item] 字段说明

| 字段             | 类型     | 描述                                   |
|----------------|--------|--------------------------------------|
| id             | string | 插件ID                                 |
| name           | string | 插件名称                                 |
| alias          | string | 插件别名                                 |
| meta_url       | string | 元数据地址                               |
| category       | string | 分类标识                                 |
| group          | string | 分组标识                                 |
| plugin_type    | string | 插件类型，固定为 uniform_api                  |
| version        | string | 插件版本                                 |
| display_content | dict  | 展示内容（详见 display_content 字段说明）         |
| source_key     | string | 统一API来源标识，对应接入平台配置的 source_key         |

#### display_content 字段说明

| 字段             | 类型      | 描述                                   |
|----------------|---------|--------------------------------------|
| llm_code       | string  | 大模型编码                                |
| llm_name       | string  | 大模型名称                                |
| base_model      | string  | 基础模型                                 |
| context_length  | string  | 上下文长度（如 128K）                        |
| created_at      | string  | 创建时间（格式 YYYY-MM-DD HH:mm:ss）          |
| created_by      | string  | 创建人                                  |
| description     | string  | 插件描述                                 |
| icon            | string  | 图标地址                                 |
| tag_names       | list   | 标签列表，每项为单元素数组（如 `[["工具调用"],["图生文"]]`） |
