### 资源描述

创建或获取资源访问 token

### 接口行为说明

- **申请新 token**：当同一空间、用户、资源类型、资源 ID 和权限类型下不存在有效 token 时，创建新的 token
- **返回已有 token**：当上述条件下已有未过期 token 时，返回最晚过期的一张；并发申请不保证只有一条记录
- **自动续期**：如果空间配置中开启了 `token_auto_renewal`（token 自动续期），每次获取已有 token 时会自动刷新其过期时间
- **过期时间**：由空间配置 `token_expiration` 决定，默认 1h、最短 1h；上限由部署配置 `BKAPP_TOKEN_EXPIRATION_MAX_EXPIRATION` 控制，默认 30 天

接入系统应先检查用户的业务权限。该接口要求通过网关的应用认证、用户认证及资源权限校验，后端还会检查调用应用是否绑定目标空间。用户名取自已认证的 `request.user.username`，请求体的额外 `user` 字段不能指定其他被授权人。

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| access_token  | string | 否  | 用户或应用 access_token，详情参考 AccessToken API                    |

`access_token` 是否使用取决于部署网关支持的认证方式，但用户身份认证本身为必需，不能只传应用凭证而省略用户身份。

#### 接口参数

| 字段              | 类型     | 必选 | 描述                                      |
|-----------------|--------|----|-----------------------------------------|
| resource_type   | string | 是  | 资源类型，支持TEMPLATE(模板)和TASK(任务)和SCOPE(作用域) |
| resource_id     | string | 是  | 资源的ID                                   |
| permission_type | string | 是  | 权限类型                                    |

`resource_id` 最长 32 位。`SCOPE` 使用 `scope_type_scope_value` 格式，例如 `biz_100`；当前校验要求恰好一个下划线，且空间内已存在相同 scope 的模板。虽然模型资源枚举包含 `LABEL`，该接口的资源校验尚不支持签发 `LABEL` token。

### permission_type 说明:

以下是主要资源权限类的能力关系。申请接口未严格校验资源与权限的组合，成功签发不等于所有接口都会认可该组合；实际授权还取决于动作权限配置。

当 resource_type 为 TASK 时，使用 VIEW (查看)和 OPERATE (操作)两种类型。

| 权限      | 权限范围           |
|---------|----------------|
| VIEW    | 仅拥有某个任务的查看权限   |
| OPERATE | 拥有某个任务的查看和操作权限 |


当 resource_type 为 TEMPLATE 时，支持 VIEW (查看) 和 EDIT(编辑) 和 MOCK(调试) 三种权限类型。

| 权限   | 权限范围                               |
|------|------------------------------------|
| VIEW | 仅拥有某个流程的查看权限                       |
| EDIT | 拥有某个流程的查看和编辑权限                     |
| MOCK | 拥有某个流程的查看、编辑和调试权限，并可访问、操作该模板创建的 MOCK 任务；不自动授权普通任务 |

当 resource_type 为 SCOPE 时，

| 权限      | 权限范围                   |
|---------|------------------------|
| VIEW    | 拥有某个作用域下的任务和流程查看权限 |
| EDIT    | 拥有某个作用域下流程的查看、编辑权限，不自动授予任务操作权限 |
| OPERATE | 拥有某个作用域下任务的查看、操作权限；模板侧另允许 preview_task_tree |
| MOCK    | 拥有某个作用域下流程的查看、编辑、调试权限，以及任务权限类中的查看、操作和 mock 数据访问；该任务权限类不限制 create_method |

MOCK 调试能力可能创建、启动或终止真实引擎任务，并非只读模拟数据。任务 token 可以沿父任务关系授权后代任务，子任务 token 不会反向授权父任务；scope 按资源当前的作用域属性判断。`FLOW_VIEW`、`FLOW_EDIT`、`FLOW_MOCK` 是任务详情中展示模板权限的标记，不是本接口可签发的新权限类型。

### 请求参数示例

以下仅为业务请求体，应用凭证和用户认证材料需按网关认证协议另行提供。

```json
{
  "resource_type": "TEMPLATE",
  "resource_id": "1",
  "permission_type": "VIEW"
}
```

### 返回结果示例

```json
{
  "result": true,
  "data": {
    "space_id": 3,
    "resource_type": "TEMPLATE",
    "resource_id": "1",
    "user": "admin",
    "token": "<BKFLOW_TOKEN>",
    "expired_time": "2026-09-08T13:00:00"
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

### data

| 字段              | 类型     | 描述                           |
|-----------------|--------|------------------------------|
| space_id        | int    | 空间ID                         |
| user            | string | 被授权用户名 |
| resource_type   | string | 资源类型：TEMPLATE、TASK、SCOPE |
| resource_id     | string | 资源的ID                        |
| token           | string | token                        |
| expired_time    | string | 过期时间                         |

当前返回数据由 `Token.to_json()` 生成，不包含 `permission_type`；调用方应保留申请时使用的权限类型。`<BKFLOW_TOKEN>` 为示例占位符，实际值为 32 位字符串。

### 相关空间配置

| 配置名称               | 说明                                         |
|--------------------|----------------------------------------------|
| token_expiration   | token 过期时间，如 `1h`（1小时）、`24h`（24小时）等  |
| token_auto_renewal | token 自动续期开关，值为 `true` 时每次获取已有 token 会刷新过期时间 |

可通过 `renew_space_config` 接口配置上述选项。普通业务请求校验 token 时不会刷新到期时间；页面通过独立续期接口续期，或由接入方再次调用本接口获取有效票据。
