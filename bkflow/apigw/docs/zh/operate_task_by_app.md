### 资源描述

通过 bk_app_code 权限校验执行任务操作

此接口用于对绑定了 bk_app_code 的流程创建的任务进行操作，请求方的 bk_app_code 需要与任务所属模板绑定的 bk_app_code 一致才能操作任务。

### 输入通用参数说明
|   参数名称   |    参数类型  |  必须  |     参数说明     |
| ------------ | ------------ | ------ | ---------------- |
| bk_app_code   | string | 是 | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| bk_app_secret | string | 是 | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |


#### 接口参数
| 字段  | 类型  | 必选  | 描述  |
| --- | --- | --- | --- |
|  operator   |  string   |  是  |  操作人 |


路径参数:

| 字段  | 类型  | 必选  | 描述  |
| --- | --- | --- | --- |
|  task_id   |  int   |  是  |  任务 ID |
|  operation   |  string   |  是  |  操作，支持 start, pause, resume, revoke |

### 权限说明

- 任务必须是由绑定了 bk_app_code 的流程模板创建
- 请求方的 bk_app_code 必须与任务所属模板绑定的 bk_app_code 一致

### 请求参数示例
```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "operator": "操作人"
}
```


### 返回结果示例

```json
{
    "result": true,
    "data": null,
    "message": "success",
    "trace_id": "3f16e62e57c543a9be6cff9556e48d07"
}
```

### 错误返回示例

任务所属模板未绑定 bk_app_code:
```json
{
    "result": false,
    "message": "Template associated with task is not bindedto any bk_app_code. task_id=10, template_id=3"
}
```

bk_app_code 不匹配:
```json
{
    "result": false,
    "message": "The current application does not have permission to operate this task, app=other_app, template bindedapp=your_app"
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
| ------- | ------ | --------------------- |
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict  | 返回数据                    |

