### 资源描述

任务操作

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
|  operation   |  string   |  是  |  操作，支持 start, pause, resume, revoke |

### 开放插件治理说明

当 `operation=start` 且任务执行快照中包含标准运维开放插件（`uniform_api v4.0.0`）时，BKFlow 会在启动前再次校验：

- 插件是否仍存在
- 插件是否仍为可用状态
- 插件是否仍在当前空间开启

若校验失败，任务不会进入执行态，而是直接返回 `400` 错误信息。

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

开放插件治理失败示例：

```json
{
    "result": false,
    "code": 400,
    "data": null,
    "message": "开放插件 [open_plugin_001] 在当前空间未开放"
}
```
### 返回结果参数说明

| 字段      | 类型     | 描述                    |
| ------- | ------ | --------------------- |
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict  | 返回数据                    |
