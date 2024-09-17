### 资源描述

创建 mock 任务

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |


#### 接口参数

| 字段          | 类型     | 必选 | 描述                                                                                                                                                              |
|-------------|--------|----|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| template_id | int    | 是  | 模板id                                                                                                                                                            |
| name        | string | 否  | 任务名                                                                                                                                                             |
| creator     | string | 是  | 创建者                                                                                                                                                             |
| description | string | 否  | 描述                                                                                                                                                              |
| constants   | dict   | 否  | 任务启动参数                                                                                                                                                          |
| mock_data   | dict   | 否  | mock 数据，包含 nodes（mock 任务使用 mock 执行的节点)，outputs（可选参数，mock 执行对应节点的节点输出)，mock_data_ids（mock 执行对应节点使用的 mock 数据 id，如果 outputs 没有传参，则会自动将创建任务时对应的 mock 数据 作为 outputs） |

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "空间名",
    "template_id": 4,
    "creator": "创建者",
    "mock_data": {
        "nodes": [
            "nd7927122ef6310eb309c2c8d3f70c23"
        ],
        "outputs": {
            "nd7927122ef6310eb309c2c8d3f70c23": {
                "callback_data": "abc"
            }
        },
        "mock_data_ids": {
            "nd7927122ef6310eb309c2c8d3f70c23": 1
        }
    }
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": 10,
        "space_id": 1,
        "scope_type": null,
        "scope_value": null,
        "instance_id": "6e15e7cf27ab3129878cdd9b95fff006",
        "template_id": 4,
        "name": "default_taskflow_instance",
        "creator": "",
        "create_time": "2023-04-23T21:10:06.826644+08:00",
        "create_method": "MOCK",
        "executor": "",
        "start_time": null,
        "finish_time": null,
        "description": "",
        "is_started": false,
        "is_finished": false,
        "is_revoked": false,
        "is_deleted": false,
        "is_expired": false,
        "snapshot_id": 3,
        "execution_snapshot_id": 8,
        "tree_info_id": null,
        "extra_info": {}
        },
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

#### data[item]

| 字段                    | 类型     | 描述       |
|-----------------------|--------|----------|
| id                    | int    | 任务ID     |
| space_id              | int    | 空间ID     |
| scope_type            | string | 任务范围类型   |
| scope_value           | string | 任务范围值    |
| instance_id           | string | 实例ID     |
| template_id           | int    | 模板ID     |
| name                  | string | 任务名称     |
| creator               | string | 创建者      |
| create_time           | string | 创建时间     |
| executor              | string | 执行者      |
| start_time            | string | 开始时间     |
| finish_time           | string | 结束时间     |
| description           | string | 描述       |
| is_started            | bool   | 是否已开始    |
| is_finished           | bool   | 是否已完成    |
| is_revoked            | bool   | 是否已撤销    |
| is_deleted            | bool   | 是否已删除    |
| is_expired            | bool   | 是否已过期    |
| snapshot_id           | int    | 快照ID     |
| execution_snapshot_id | int    | 执行快照ID   |
| tree_info_id          | int    | 任务拓扑信息ID |
| extra_info            | dict   | 任务额外信息   |
