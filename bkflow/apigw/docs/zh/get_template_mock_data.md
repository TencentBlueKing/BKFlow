### 资源描述

获取流程 Mock 数据

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 接口参数

| 字段      | 类型     | 必选 | 描述                      |
|---------|--------|----|-------------------------|
| node_id | string | 否  | 基于节点 id 过滤对应节点的 Mock 数据 |


### 返回结果示例

```json
{
    "result": true,
    "data": [
        {
            "id": 1,
            "name": "Mock 数据方案1",
            "space_id": 1,
            "template_id": 1,
            "node_id": "nd64fbd5440932ee9658d47029751f46",
            "data": {
                "callback_data": {
                    "abc": "123"
                }
            },
            "is_default": true,
            "extra_info": null,
            "operator": "admin",
            "create_at": "2024-09-14T15:24:39.075179+08:00",
            "update_at": "2024-09-14T15:24:39.075289+08:00"
        }
    ],
    "code": 0,
    "message": ""
}
```
### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | list   | 返回数据                  |

### data[item]

| 字段          | 类型     | 描述               |
|-------------|--------|------------------|
| id          | int    | Mock 数据 ID       |
| name        | string | Mock 数据名称        |
| space_id    | int    | Mock 数据所属空间 ID   |
| template_id | int    | Mock 数据所属流程模板 ID |
| node_id     | string | Mock 数据所属节点 ID   |
| data        | dict   | Mock 数据内容        |
| is_default  | bool   | 是否为默认 Mock 数据    |
| extra_info  | dict   | 额外信息             |
| operator    | string | 操作人              |
| create_at   | string | 创建时间             |
| update_at   | string | 更新时间             |
