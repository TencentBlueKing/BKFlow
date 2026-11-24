### 租户访问约束

开启多租户时，全租户应用必须通过 `X-Bk-Tenant-Id` 指定本次请求租户；单租户应用可省略该头，使用 JWT 中已认证的应用租户，显式传入时必须一致。本次请求租户必须与资源所属空间租户一致；同一个全租户应用应在各租户分别创建空间。若 JWT 包含已认证用户，其租户也必须一致。缺少或不匹配时拒绝请求。

应用态接口不要求额外用户身份。SDK 用户态接口仍要求已认证用户，平台管理员和空间管理员同样不能跨租户。关闭多租户模式时保持单租户行为。

### 资源描述

批量查询插件当前状态（SDK接口）

打开节点配置弹窗时，对画布内全部节点引用的插件身份批量查一次状态，而不是逐节点请求。查不到的身份兜底为 `enable`。本接口只做「展示态提示条」，不做保存拦截；保存拦截在保存流程接口（见 sdk_update_template）。

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
| items | object[] | 是 | 插件身份列表，每项必填 plugin_type、plugin_code；source_key、plugin_version 可选（默认空串） |

### 请求参数示例

```json
{
    "space_id": 1,
    "items": [
        {"plugin_type": "bk_plugin", "source_key": "", "plugin_code": "wecom_bot"},
        {"plugin_type": "api", "source_key": "api_job", "plugin_code": "bk_http_request"}
    ]
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "results": [
            {
                "plugin_type": "bk_plugin",
                "source_key": "",
                "plugin_code": "wecom_bot",
                "status": "disabled",
                "reason": "已统一迁移到「发送通知」插件，旧机器人即将停用",
                "replace_plugin": {
                    "plugin_type": "bk_plugin", "source_key": "", "plugin_code": "send_notify",
                    "name": "发送通知", "status": "enable"
                }
            }
        ]
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

#### results[item] 字段说明

| 字段 | 类型 | 描述 |
|------------|--------|------|
| plugin_type / source_key / plugin_code | string | 插件身份三元组 |
| status | string | 状态：enable/pending_review/disabled/expired |
| reason | string | 提示条直接展示的原因文案；其他状态为空串 |
| replace_plugin | object/null | 建议替换插件的身份、展示名与当前状态；无替代为 null |
