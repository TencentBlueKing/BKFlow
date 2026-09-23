### 租户访问约束

开启多租户时，全租户应用必须通过 `X-Bk-Tenant-Id` 指定本次请求租户；单租户应用可省略该头，使用 JWT 中已认证的应用租户，显式传入时必须一致。本次请求租户必须与资源所属空间租户一致；同一个全租户应用应在各租户分别创建空间。原有应用与空间/模板绑定仍需满足。若 JWT 包含已认证用户，其租户也必须一致。缺少或不匹配时拒绝请求。

应用态接口不要求额外用户身份。SDK 用户态接口仍要求已认证用户，平台管理员和空间管理员同样不能跨租户。关闭多租户模式时保持单租户行为。

### 资源描述

创建空间变量

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

#### 接口参数

| 字段            | 类型       | 必选   | 描述                               |
|---------------|----------|------|----------------------------------|
| name          | string   | 是    | 变量名                              |
| key           | string   | 是    | 变量唯一键，在空间内必须唯一                   |
| variable_type | string   | 是    | 变量类型，取值范围：space（空间级）、scope（作用域级） |
| value         | string   | 是    | 变量值                              |
| desc          | string   | 否    | 变量描述                             |

### variable_type 参数说明

`variable_type` 参数用于指定变量的作用范围，目前支持space类型


### 请求参数示例

```json
{
    "name": "数据库连接地址",
    "key": "db_host",
    "variable_type": "space",
    "value": "localhost:3306",
    "desc": "生产环境数据库连接地址"
}
```

### 返回结果示例

```json
{
    "result": true,
    "code": 0,
    "data": {
        "id": 1,
        "space_id": 6,
        "name": "数据库连接地址",
        "key": "db_host",
        "variable_type": "space",
        "value": "localhost:3306",
        "desc": "生产环境数据库连接地址",
        "creator": "admin",
        "create_at": "2024-01-15T10:30:00.000000+08:00",
        "updated_by": "admin",
        "update_at": "2024-01-15T10:30:00.000000+08:00"
    }
}
```

### 返回结果参数说明

| 字段        | 类型     | 描述                    |
|-----------|--------|-----------------------|
| result    | bool   | 返回结果，true为成功，false为失败 |
| code      | int    | 返回码，0表示成功，其他值表示失败     |
| message   | string | 错误信息                  |
| data      | dict   | 返回数据                  |

#### data[item]

| 字段            | 类型       | 描述          |
|---------------|----------|-------------|
| id            | int      | 变量ID        |
| space_id      | int      | 空间ID        |
| name          | string   | 变量名         |
| key           | string   | 变量唯一键       |
| variable_type | string   | 变量类型        |
| value         | string   | 变量值         |
| desc          | string   | 变量描述        |
| creator       | string   | 创建者         |
| create_at     | string   | 创建时间        |
| updated_by    | string   | 最后更新者       |
| update_at     | string   | 最后更新时间      |
