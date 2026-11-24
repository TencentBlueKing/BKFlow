### 租户访问约束

开启多租户时，全租户应用必须通过 `X-Bk-Tenant-Id` 指定本次请求租户；单租户应用可省略该头，使用 JWT 中已认证的应用租户，显式传入时必须一致。本次请求租户必须与资源所属空间租户一致；同一个全租户应用应在各租户分别创建空间。若 JWT 包含已认证用户，其租户也必须一致。缺少或不匹配时拒绝请求。

应用态接口不要求额外用户身份。SDK 用户态接口仍要求已认证用户，平台管理员和空间管理员同样不能跨租户。关闭多租户模式时保持单租户行为。

### 资源描述

版本切换/换插件的参数差异（SDK接口）

对应版本切换后的「保留了 N 个参数、新增 N 个参数」提示 + 右侧「旧版本参数」抽屉，同时供换插件时入参重新映射复用。只管输入参数，不管输出参数。

判定规则：key 和中文名都相同才归为 `kept`，其余一律 `added`（不做隐式改名映射）。

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
| from_plugin | object | 是 | 切换前插件身份，必填 plugin_type、plugin_code；source_key、plugin_version 可选（默认空串） |
| to_plugin | object | 是 | 切换后插件身份，必填字段同 from_plugin |
| current_inputs | object | 否 | 当前节点已有输入参数值 {key: value}，用于回填 |

### 请求参数示例

```json
{
    "space_id": 1,
    "from_plugin": {
        "plugin_type": "api", "source_key": "api_job",
        "plugin_code": "bk_http_request", "plugin_version": "v1.2.0"
    },
    "to_plugin": {
        "plugin_type": "api", "source_key": "api_job",
        "plugin_code": "bk_http_request", "plugin_version": "v1.3.0"
    },
    "current_inputs": {"webhook": "https://example.com/hook"}
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "kept": ["webhook", "receiver"],
        "added": ["msg_content", "prompts"],
        "inputs": {
            "webhook": {"key": "webhook", "name": "Webhook", "type": "string", "value": "https://example.com/hook"},
            "content": {"key": "content", "name": "消息内容", "type": "string", "value": "hello", "to_key": "msg_content"}
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
| kept | array | 换版本后没变的输入参数 key（key 和中文名都相同） |
| added | array | 其余输入参数 key（新增/改了 key/改了中文名） |
| inputs | object | 旧版本的输入参数（含当前现值），key 为旧版本参数 key |

#### inputs[].xxx 字段说明

| 字段 | 类型 | 描述 |
|------------|--------|------|
| key / name / type | string | 旧版本参数的标识、中文名与类型 |
| value | any | 当前节点上的现值，没有填过值则无此字段 |
| to_key | string | 新版本里对得上的 key，仅为提示，不影响 kept/added 判定 |
