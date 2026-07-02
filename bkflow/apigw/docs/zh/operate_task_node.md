### 资源描述

任务节点操作

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |


#### 接口参数
| 字段       | 类型     | 必选 | 描述  |
|----------|--------|----|-----|
| operator | string | 是  | 操作人 |

操作所需额外参数

| 操作类型        | 所需参数    | 类型          | 含义       | 示例                      |
|-------------|---------|-------------|----------|-------------------------|
| retry       | inputs  | json        | 重试节点输入   | {"param1": "value1"}    |
| callback    | data    | json/string | 回调数据     | "this is callback data" |
| forced_fail | ex_data | str         | 强制失败报错信息 | "forced fail by xxx"    |

### 特殊参数说明

#### 开放插件回调场景

当 `operation=callback` 且当前节点是通过标准运维开放插件网关回调时，请求体不再要求显式传入 `operator`，而是需要：

1. 在 Header 中传入 `X-Callback-Token`
2. 在请求体中传入开放插件回调数据

Header 示例：

| Header 名称        | 类型     | 必选 | 描述                       |
|-------------------|----------|------|----------------------------|
| X-Callback-Token  | string   | 是   | BKFlow 在 execute 时动态签发的回调令牌 |

开放插件回调请求体字段：

| 字段                | 类型     | 必选 | 描述 |
|---------------------|----------|------|------|
| open_plugin_run_id  | string   | 是   | 标准运维开放插件运行实例 ID |
| status              | string   | 是   | 回调状态，如 `SUCCEEDED` / `FAILED` |
| outputs             | dict     | 否   | 插件输出数据 |
| error_message       | string   | 否   | 失败原因 |
| truncated           | bool     | 否   | 输出是否被截断 |
| truncated_fields    | list     | 否   | 被截断的字段列表 |


路径参数:

| 字段        | 类型     | 必选 | 描述                                       |
|-----------|--------|----|------------------------------------------|
| operation | string | 是  | 操作，支持 retry, skip, callback, forced_fail |

### 请求参数示例
```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "operator": "操作人"
}
```

开放插件 callback 示例：

```json
{
    "open_plugin_run_id": "8d3d6dc2f7cf4c5395b3a3c0ec5a37f1",
    "status": "SUCCEEDED",
    "outputs": {
        "job_instance_id": 1001
    }
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
### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |
