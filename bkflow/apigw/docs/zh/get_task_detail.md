### 资源描述

获取任务详情

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": 1,
        "pipeline_tree": {},
        "space_id": 1,
        "scope_type": null,
        "scope_value": null,
        "instance_id": "1",
        "template_id": 1,
        "name": "default_taskflow_instance",
        "creator": "",
        "create_time": "2023-04-19T16:02:45.204292+08:00",
        "executor": "",
        "start_time": null,
        "finish_time": null,
        "description": "",
        "is_started": false,
        "is_finished": false,
        "is_revoked": false,
        "is_deleted": false,
        "is_expired": false,
        "snapshot_id": null,
        "execution_snapshot_id": null,
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
| pipeline_tree         | dict   | 任务树数据    |
| space_id              | int    | 空间ID     |
| scope_type            | string | 范围类型     |
| scope_value           | string | 范围值      |
| instance_id           | string | 实例ID     |
| template_id           | int    | 模板ID     |
| name                  | string | 任务名称     |
| creator               | string | 创建者      |
| create_time           | string | 创建时间     |
| executor              | string | 执行者      |
| start_time            | string | 开始时间     |
| finish_time           | string | 结束时间     |
| description           | string | 描述       |
| is_started            | bool   | 是否已启动    |
| is_finished           | bool   | 是否已结束    |
| is_revoked            | bool   | 是否已撤销    |
| is_deleted            | bool   | 是否已删除    |
| is_expired            | bool   | 是否已过期    |
| snapshot_id           | int    | 快照ID     |
| execution_snapshot_id | int    | 执行快照ID   |
| tree_info_id          | int    | 任务拓扑信息ID |

#### data.pipeline_tree

| 字段          | 类型   | 描述                         |
|-------------|------|----------------------------|
| start_event | dict | 开始节点信息                     |
| end_event   | dict | 结束节点信息                     |
| activities  | dict | 任务节点（标准插件和子流程）信息           |
| gateways    | dict | 网关节点（并行网关、分支网关和汇聚网关）信息     |
| flows       | dict | 顺序流（节点连线）信息                |
| constants   | dict | 全局变量信息，详情见下面               |
| outputs     | list | 模板输出信息，标记 constants 中的输出字段 |
