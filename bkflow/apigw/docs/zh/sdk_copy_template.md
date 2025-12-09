### 资源描述

拷贝流程（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 权限说明

该接口需要用户是系统超级管理员或指定空间的超级管理员，**不需要 HTTP_BKFLOW_TOKEN**。

### 接口参数

| 字段      | 类型     | 必选 | 描述       |
|---------|--------|----|----------|
| space_id | int    | 是  | 目标空间ID   |
| template_id | int | 是  | 要拷贝的模板ID |

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "space_id": 2,
    "template_id": 1
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "template_id": 5,
        "template_name": "拷贝的流程名称"
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

#### data 字段说明

| 字段           | 类型     | 描述       |
|--------------|--------|----------|
| template_id  | int    | 新创建的模板ID |
| template_name | string | 新创建的模板名称 |


