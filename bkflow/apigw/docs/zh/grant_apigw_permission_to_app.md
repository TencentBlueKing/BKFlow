### 资源描述

给其他 app 授予 apigw 权限

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |


#### 接口参数

| 字段          | 类型     | 必选 | 描述              |
|-------------|--------|----|-----------------|
| apps        | list   | 是  | 授权的 app_code 列表 |
| permissions | list   | 是  | 授权的接口 id 列表     |


### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "apps": ["xxx"],
    "permissions": ["create_space"]
}
```

### 返回结果示例

```json
{
	"result": true,
	"data": "permission granted",
	"code": "0",
	"message": ""
}

```
### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |