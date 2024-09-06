### 资源描述

获取任务列表

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |


#### 接口参数
| 字段              | 类型     | 必选 | 描述                           |
|-----------------|--------|----|------------------------------|
| limit           | int    | 否  | 每页的数量, limit 最大数量为200        |
| offset          | int    | 否  | 偏移量                          |
| name            | string | 否  | 流程名   模糊匹配                   |
| creator         | string | 否  | 创建者   精确匹配                   |
| scope_type      | string | 否  | 流程范围   精确匹配                  |
| scope_value     | string | 否  | 流程范围值   精确匹配                 |
| create_at_start | string | 否  | 创建起始时间，如 2023-08-25 07:49:45 |
| create_at_end   | string | 否  | 创建结束时间，如 2023-08-25 07:49:46 |

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "count": 1,
        "next": null,
        "previous": null,
        "results": [
            {
                "id": 1671,
                "create_time": "2024-07-31 17:56:23+0800",
                "start_time": "2024-07-31 17:56:26+0800",
                "finish_time": "2024-07-31 17:59:14+0800",
                "space_id": 1,
                "scope_type": null,
                "scope_value": null,
                "instance_id": "n2d1ef9ff5193d39b2d13bb2faa5418c",
                "template_id": 616,
                "name": "default_taskflow_instance",
                "creator": "",
                "create_method": "API",
                "executor": "",
                "description": "",
                "is_started": true,
                "is_finished": true,
                "is_revoked": false,
                "is_deleted": false,
                "is_expired": false,
                "snapshot_id": 1671,
                "execution_snapshot_id": 1671,
                "tree_info_id": 1539,
                "extra_info": {}
            }
        ]
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

##### data[item]

| 名称                    | 类型     | 说明       |
|-----------------------|--------|----------|
| id                    | int    | 任务ID     |
| space_id              | int    | 任务所属空间ID |
| scope_type            | string | 任务范围类型   |
| scope_value           | string | 任务范围值    |
| instance_id           | string | 任务实例ID   |
| template_id           | int    | 任务模版ID   |
| name                  | string | 任务名      |
| creator               | string | 任务创建者    |
| create_method         | string | 任务创建方式   |
| create_time           | string | 任务创建时间   |
| executor              | string | 任务执行者    |
| start_time            | string | 任务开始时间   |
| finish_time           | string | 任务结束时间   |
| is_started            | bool   | 任务是否已开始  |
| is_finished           | bool   | 任务是否已结束  |
| is_revoked            | bool   | 任务是否已撤销  |
| is_deleted            | bool   | 任务是否已删除  |
| is_expired            | bool   | 任务是否已过期  |
| snapshot_id           | int    | 任务快照ID   |
| execution_snapshot_id | int    | 任务执行快照ID |
| tree_info_id          | int    | 任务树信息ID  |
| extra_info            | dict   | 任务额外信息   |
