### 资源描述

获取uniform_api插件列表（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称         | 参数类型   | 必须 | 参数说明                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW_TOKEN | string | 是  | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 接口申请。该 token 用于验证用户对指定空间资源的访问权限（需要提供 template_id 或 task_id） |

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

本接口的返回结构取决于统一API接入平台配置的 `catalog_mode`，存在两种形态：

- **远端透传模式（remote，默认模式）**：后端直接透传上游统一API返回的数据，结构由接入平台决定。`display_content` 等扩展字段依赖上游实现；
- **缓存模式（cache_first / cache_only 且目录缓存已初始化）**：后端返回本地开放插件目录的缓存数据，字段为固定的插件目录结构（见下文缓存模式示例）。

> 说明：当前默认模式为 remote，仅当接入平台将 `catalog_mode` 配置为 `cache_first` 或 `cache_only`、且目录缓存已初始化时，才会走缓存模式，并非所有请求都会自动切换。实际响应外层会包裹标准网关结构 `{ "result": true, "code": "0", "message": "", "data": {...} }`，下文说明均以 data 内结构为准。

#### 远端透传模式示例

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

#### 缓存模式示例

```json
{
  "result": true,
  "code": "0",
  "message": "",
  "data": {
    "total": 1,
    "apis": [
      {
        "id": "plugin-xxx",
        "name": "通用HTTP请求",
        "plugin_source": "builtin",
        "plugin_code": "http_request",
        "wrapper_version": "1.0.0",
        "default_version": "1.0.0",
        "latest_version": "1.2.0",
        "versions": ["1.0.0", "1.1.0", "1.2.0"],
        "meta_url_template": "http://example.com/meta/{plugin_code}",
        "source_key": "aidev",
        "category": "network",
        "category_name": "网络",
        "description": "通用HTTP请求插件"
      }
    ]
  }
}
```

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
| apis | list | 统一API插件列表（详见下方各模式字段说明） |

#### 远端透传模式 apis[item] 字段说明

> 结构由上游接入平台决定，以下为示例字段，实际以接入平台返回为准；`display_content` 等扩展字段依赖上游实现，不同 category 的字段可能不同。

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
| display_content | dict  | 展示内容，由上游实现决定，字段可变（详见 display_content 示例字段说明） |
| source_key     | string | 统一API来源标识，对应接入平台配置的 source_key         |

#### display_content 示例字段说明（依赖上游实现）

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

#### 缓存模式 apis[item] 字段说明

> 仅在 `catalog_mode` 为 `cache_first` / `cache_only` 且目录缓存已初始化时返回，固定为本地开放插件目录结构（对应 `_build_cached_catalog_data`）。

| 字段              | 类型     | 描述                                       |
|-----------------|--------|------------------------------------------|
| id              | string | 插件ID（对应 plugin_id）                         |
| name            | string | 插件名称（对应 plugin_name）                     |
| plugin_source   | string | 插件来源（如 builtin）                            |
| plugin_code     | string | 插件code                                  |
| wrapper_version | string | 包装版本                                     |
| default_version | string | 默认版本                                     |
| latest_version  | string | 最新版本                                     |
| versions        | list   | 可用版本列表                                   |
| meta_url_template | string | 元数据地址模板（含 `{plugin_code}` 占位符）           |
| source_key      | string | 统一API来源标识                              |
| category        | string | 分类标识（对应 group_name）                       |
| category_name   | string | 分类名称（对应 group_display_name）                 |
| description     | string | 插件描述                                     |

> 注意：缓存模式**不包含** `alias`、`meta_url`、`group`、`plugin_type`、`version`、`display_content` 等字段。SDK 若按远端透传示例读取这些字段，在缓存模式下会取到空值/缺失；调用前请确认目标空间的 `catalog_mode` 配置。
