### 资源描述

撤回 token

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| access_token  | string | 否  | 用户或应用 access_token，详情参考 AccessToken API                    |

#### 接口参数

注意: 以下参数将作为对应空间下 token 失效的过滤参数，如果不传任何参数，则所有 token 失效（将 token 的过期时间设置为当前时间）。所以，在调用此接口时，请保证过滤范围尽量精确。

| 字段              | 类型     | 必选      | 描述                           |
|-----------------|--------|---------|------------------------------|
| resource_type   | string | 否       | 资源类型，支持TEMPLATE(模板)和TASK(任务) |
| resource_id     | string | 否       | 资源的ID                        |
| permission_type | string | 否       | 权限类型                         |
| user            | string | 否 ｜ 用户名 | 
| token           | string | 否       | token                        |

### permission_type 说明:

当 resource_type 为 TASK 时，支持VIEW(查看)和OPERATE(操作)
两种类型。拥有OPERATE类型的全新则默认可以查看该任务，不需要额外申请VIEW权限的token。而申请了VIEW全新的token，则不能操作任务，
当 resource_type 为 TEMPLATE时，支持VIEW(查看)和EDIT(编辑) 两种权限类型。

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
    "data": "10 tokens revoke success",
    "message": "",
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