### 资源描述

任务节点操作

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| HTTP_BKFLOW_TOKEN | string | 是  | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 接口申请。该 token 用于验证用户对指定任务的操作权限 |


### 路径参数:

| 字段         | 类型      | 必选 | 描述                                       |
|------------|---------|----|------------------------------------------|
| task_id    | int     | 是  | 任务ID                                     |
| node_id    | int     | 是  | 节点ID                                     |
| operation  | string  | 是  | 操作，支持 retry, skip, callback, forced_fail |

操作所需额外参数

| 操作类型        | 所需参数    | 类型          | 含义       | 示例                      |
|-------------|---------|-------------|----------|-------------------------|
| retry       | inputs  | json        | 重试节点输入   | {"param1": "value1"}    |
| callback    | data    | json/string | 回调数据     | "this is callback data" |
| forced_fail | ex_data | str         | 强制失败报错信息 | "forced fail by xxx"    |

### 接口参数

| 字段       | 类型      | 必选 | 描述   |
|----------|---------|----|------|
| space_id | int     | 是  | 空间ID |


### 返回结果示例

```json
{
    "result": true,
    "data": null,
    "message": "success",
    "exc": null,
    "exc_trace": null
}
```
### 返回结果参数说明

| 字段        | 类型       | 描述                    |
|-----------|----------|-----------------------|
| result    | bool     | 返回结果，true为成功，false为失败 |
| message   | string   | 错误信息                  |
| data      | dict     | 返回数据                  |
| exc       | string   | 异常信息                  |
| exc_trace | string   | 异常堆栈跟踪信息              |