### 资源描述

更新空间变量


### 输入通用参数说明
| 参数名称          | 类型     | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 路径参数说明

| 参数名称        | 类型      | 必须  | 参数说明         |
|-------------|---------|-----|--------------|
| space_id    | int     | 是   | 空间ID         |
| variable_id | int     | 是   | 变量ID         |

#### 请求体参数

| 字段      | 类型       | 必选  | 描述                               |
|---------|----------|-----|----------------------------------|
| name    | string   | 否   | 变量名                              |
| key     | string   | 否   | 变量唯一键，在空间内必须唯一                   |
| type    | string   | 否   | 变量类型，取值范围：space（空间级）、scope（作用域级） |
| value   | string   | 否   | 变量值                              |
| desc    | string   | 否   | 变量描述                             |

### type 参数说明

`type` 参数用于指定变量的作用范围，目前支持space类型


### 请求参数示例

```json
{
    "name": "新的数据库连接地址",
    "desc": "更新后的数据库连接地址描述",
    "key": "new_db_host",
    "value": "new-db-host:3306"
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
        "name": "新的数据库连接地址",
        "key": "db_host",
        "type": "space",
        "value": "new-db-host:3306",
        "desc": "更新后的数据库连接地址描述",
        "creator": "admin",
        "create_at": "2024-01-15T10:30:00.000000+08:00",
        "updated_by": "admin",
        "update_at": "2024-01-15T11:30:00.000000+08:00"
    }
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |

#### data[item]

| 字段          | 类型      | 描述          |
|-------------|---------|-------------|
| id          | int     | 变量ID        |
| space_id    | int     | 空间ID        |
| name        | string  | 变量名         |
| key         | string  | 变量唯一键       |
| type        | string  | 变量类型        |
| value       | string  | 变量值         |
| desc        | string  | 变量描述        |
| creator     | string  | 创建者         |
| create_at   | string  | 创建时间        |
| updated_by  | string  | 最后更新者       |
| update_at   | string  | 最后更新时间      |
