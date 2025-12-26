### 资源描述

创建申请token

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| access_token  | string | 否  | 用户或应用 access_token，详情参考 AccessToken API                    |

#### 接口参数

| 字段              | 类型     | 必选 | 描述                                      |
|-----------------|--------|----|-----------------------------------------|
| resource_type   | string | 是  | 资源类型，支持TEMPLATE(模板)和TASK(任务)和SCOPE(作用域) |
| resource_id     | string | 是  | 资源的ID                                   |
| permission_type | string | 是  | 权限类型                                    |

### permission_type 说明:

当 resource_type 为 TASK 时，支持 VIEW (查看)和 OPERATE (操作)两种类型。

| 权限      | 权限范围           |
|---------|----------------|
| VIEW    | 仅拥有某个任务的查看权限   | 
| OPERATE | 拥有某个任务的查看和操作权限 | 


当 resource_type 为 TEMPLATE 时，支持 VIEW (查看) 和 EDIT(编辑) 和 MOCK(调试) 三种权限类型。

| 权限   | 权限范围                               |
|------|------------------------------------|
| VIEW | 仅拥有某个流程的查看权限                       | 
| EDIT | 拥有某个流程的查看和编辑权限                     |
| MOCK | 拥有某个流程的查看和编辑权限，同时拥有该流程创建的所有任务的所有权限 |

当 resource_type 为 SCOPE 时，

| 权限      | 权限范围                   |
|---------|------------------------|
| VIEW    | 拥有某个作用域下作用域下的任务和流程查看权限 | 
| EDIT    | 拥有某个作用域下流程的编辑权限        |
| OPERATE | 拥有某个作用域下任务的操作权限        |
| MOCK    | 拥有某个作用域下流程的编辑、调试权限     |

### 请求参数示例

```json
{
  "bk_app_code": "xxxx",
  "bk_app_secret": "xxxx",
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
    "token": "8ce9f640f76f3fcbb4e22726bb726cd6",
    "permission_type": "VIEW",
    "expired_time": "2023-04-22 11:11:11"
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
| resource_type   | string | 资源类型，支持TEMPLATE(模板)和TASK(任务) |
| resource_id     | string | 资源的ID                        |
| permission_type | string | 权限类型                         |
| token           | string | token                        |
| expired         | string | 过期时间                         |