### 租户访问约束

开启多租户时，全租户应用必须通过 `X-Bk-Tenant-Id` 指定本次请求租户；单租户应用可省略该头，使用 JWT 中已认证的应用租户，显式传入时必须一致。本次请求租户必须与资源所属空间租户一致；同一个全租户应用应在各租户分别创建空间。若 JWT 包含已认证用户，其租户也必须一致。缺少或不匹配时拒绝请求。

应用态接口不要求额外用户身份。SDK 用户态接口仍要求已认证用户，平台管理员和空间管理员同样不能跨租户。关闭多租户模式时保持单租户行为。

### 资源描述

插件可选版本列表（SDK接口）

对应画布节点配置的「插件版本」下拉。builtin/bk_plugin 的 `source_key` 恒为空串无法作为路径段，故 `source_key` 以 query 参数传递，传空串或来源 key 后端都会归一化。

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
| plugin_type | string | 是 | 插件类型：builtin/bk_plugin/api |
| plugin_code | string | 是 | 插件标识 |
| source_key | string | 否 | 来源id或空串，后端会归一化 |

### 请求参数示例

```
GET /api/plugin_catalog/plugins/versions/?space_id=1&plugin_type=api&source_key=api_job&plugin_code=bk_http_request
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "versions": ["v1.2.0", "v1.3.0"],
        "default_version": "v1.2.0",
        "latest_version": "v1.3.0"
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
| versions | array | 可选版本列表；bk_plugin 当前无版本模型返回空数组 |
| default_version | string | 默认版本 |
| latest_version | string | 最新版本 |
