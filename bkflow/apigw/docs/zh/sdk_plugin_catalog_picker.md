### 租户访问约束

开启多租户时，全租户应用必须通过 `X-Bk-Tenant-Id` 指定本次请求租户；单租户应用可省略该头，使用 JWT 中已认证的应用租户，显式传入时必须一致。本次请求租户必须与资源所属空间租户一致；同一个全租户应用应在各租户分别创建空间。若 JWT 包含已认证用户，其租户也必须一致。缺少或不匹配时拒绝请求。

应用态接口不要求额外用户身份。SDK 用户态接口仍要求已认证用户，平台管理员和空间管理员同样不能跨租户。关闭多租户模式时保持单租户行为。

### 资源描述

画布统一选择插件列表（SDK接口）

对应画布「选择插件」面板：左侧目录树 + 右侧插件卡片列表由本接口一次返回，只返回 `enable` 状态的插件，与插件管理页口径一致。本接口不接收 `scope_type` / `scope_id`。

### 输入通用参数说明

| 参数名称 | 参数类型 | 必须 | 参数说明 |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code | string | 是 | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| bk_app_secret | string | 是 | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称 | 参数类型 | 必须 | 参数说明 |
|--------------|--------|----|------------------------------------------------------------|
| X-Bk-Tenant-Id | string | 否 | 多租户开启时全租户应用必填，单租户应用可省略；必须与资源空间租户一致 |

### 接口参数

| 字段 | 类型 | 必选 | 描述 |
|------------|---------|-----|----------|
| space_id | int | 是 | 空间ID |
| directory_id | string | 否 | 目录筛选，all/recommend/uncategorized/具体目录id，默认 all |
| plugin_type | string | 否 | 插件类型：all/builtin/bk_plugin/api，默认 all |
| keyword | string | 否 | 匹配名称或描述，默认 "" |
| ordering | string | 否 | 排序：recommend/-publish_time/publish_time/name/-usage_count/usage_count，默认 recommend |
| page | int | 否 | 页码，从 1 开始（最小 1），默认 1 |
| page_size | int | 否 | 每页条数，范围 1-200，默认 20 |

### 请求参数示例

```
GET /api/plugin_catalog/plugins/picker/?space_id=1&plugin_type=api&keyword=HTTP&page=1&page_size=20
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "count": 42,
        "page": 1,
        "page_size": 20,
        "results": [
            {
                "plugin_type": "builtin",
                "source_key": "builtin",
                "plugin_code": "bk_http_request",
                "plugin_name": "HTTP 请求",
                "plugin_desc": "在指定主机上执行一段脚本",
                "recommended": true,
                "directory_path": ["通用能力", "流程控制"],
                "usage_count": 46
            }
        ],
        "directories": {
            "tree": [
                {"id": 1, "name": "通用能力", "order": 1, "count": 11,
                 "children": [{"id": 2, "name": "流程控制", "order": 1, "count": 5, "children": []}]}
            ],
            "total_count": 234,
            "recommend_count": 6,
            "uncategorized_count": 34
        }
    },
    "message": "",
    "code": "0"
}
```

### 返回结果参数说明

| 字段 | 类型 | 描述 |
|---------|--------|-----------------------|
| result | bool | 返回结果，true为成功，false为失败 |
| code | string | 返回码，0表示成功，其他值表示失败 |
| message | string | 错误信息 |
| data | dict | 返回数据 |

#### data 字段说明

| 字段 | 类型 | 描述 |
|------------|--------|------|
| count | int | 右侧列表总数（仅启用状态插件） |
| page | int | 当前页码 |
| page_size | int | 每页条数 |
| results | list | 插件卡片列表 |
| directories | dict | 左侧目录树 + 计数，口径只算启用状态插件 |

#### results[item] 字段说明

| 字段 | 类型 | 描述 |
|------------|--------|------|
| plugin_type | string | 插件类型 |
| source_key | string | 来源id |
| plugin_code | string | 插件标识 |
| plugin_name | string | 插件展示名 |
| plugin_desc | string | 插件描述 |
| recommended | bool | 是否空间推荐 |
| directory_path | array | 分类路径数组，未分类为 [] |
| usage_count | int | 被选用次数（引用该插件的去重流程数） |

#### directories 字段说明

| 字段 | 类型 | 描述 |
|------------|--------|------|
| tree | array | 目录树，节点含 id/name/order/count/children |
| total_count | int | 空间插件计数 |
| recommend_count | int | 空间推荐计数 |
| uncategorized_count | int | 未分类插件计数 |
