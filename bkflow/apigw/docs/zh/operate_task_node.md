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