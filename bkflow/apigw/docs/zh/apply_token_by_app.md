### 资源描述

调用应用为指定用户申请 BKFLOW-TOKEN。请求路径为 `POST /space/{space_id}/apply_token_by_app/`。网关校验应用身份及该接口的调用权限，BKFlow 校验应用与目标空间的绑定。调用应用应先确认目标用户有权访问对应资源并执行所申请的操作。

### 输入通用参数说明

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| bk_app_code | string | 是 | 调用方应用 ID |
| bk_app_secret | string | 是 | 调用方应用密钥 |

签发请求只需应用认证。发布同步会为 `bk_fara` 按资源授予此接口的网关调用权限。目标空间需绑定调用方应用。

### 接口参数

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| space_id | 路径 | string | 是 | 目标空间 ID |
| X-Bk-Tenant-Id | 请求头 | string | 条件必填 | 开启多租户时，全租户应用必填。单租户应用省略时使用应用租户，显式传入时须与应用租户一致。请求租户须与空间租户一致 |
| user | 请求体 | string | 是 | 被授权用户名，去除首尾空白后须非空，最长 32 字符 |
| resource_type | 请求体 | string | 单项必填 | `TEMPLATE`、`TASK`、`SCOPE` |
| resource_id | 请求体 | string | 单项必填 | 资源 ID，最长 32 字符。`SCOPE` 使用 `scope_type_scope_value`，例如 `biz_100` |
| permission_type | 请求体 | string | 单项必填 | `VIEW`、`EDIT`、`OPERATE`、`MOCK` |
| grants | 请求体 | list | 组合必填 | 1 至 32 条授权，含 `resource_type`、`resource_id` 和 `permission_type` |

### 组合申请与续期

传入任一顶层资源字段时按单项处理。使用组合申请时仅传顶层 `user` 和 `grants`，且环境须启用 `TOKEN_COMPOSITE_ENABLED`。全部授权的资源均通过校验后才会签发或续期。

相同用户、空间和完整授权集合可复用有效 Token。有效期和自动续期由空间配置决定。调用 SDK 用户态接口时，认证用户必须与被授权用户名一致。

### 请求参数示例

单项申请

```json
{
  "user": "alice",
  "resource_type": "TEMPLATE",
  "resource_id": "42",
  "permission_type": "VIEW"
}
```

组合申请

```json
{
  "user": "alice",
  "grants": [
    {"resource_type": "TEMPLATE", "resource_id": "42", "permission_type": "VIEW"},
    {"resource_type": "TASK", "resource_id": "18", "permission_type": "OPERATE"}
  ]
}
```

### 返回结果示例

单项申请成功

```json
{
  "result": true,
  "code": 0,
  "data": {
    "space_id": 1,
    "user": "alice",
    "token": "0123456789abcdef0123456789abcdef",
    "expired_time": "2026-11-27T08:00:00Z",
    "resource_type": "TEMPLATE",
    "resource_id": "42"
  }
}
```

缺少用户名时 HTTP 状态为 200，业务错误示例

```json
{
  "result": false,
  "code": 400,
  "message": "{\"user\": \"用户名必须是非空字符串\"}",
  "data": null
}
```

调用应用不匹配或请求租户不匹配时返回 HTTP 403。

### 返回结果参数说明

| data 字段 | 类型 | 说明 |
| --- | --- | --- |
| space_id | int | 空间 ID |
| user | string | 被授权用户名 |
| token | string | 32 字符的 BKFLOW-TOKEN |
| expired_time | string | 过期时间 |
| resource_type | string | 单项申请返回的资源类型 |
| resource_id | string | 单项申请返回的资源 ID |
| grants | list | 组合申请返回的完整授权集合，包含资源类型、资源 ID 和权限类型 |
