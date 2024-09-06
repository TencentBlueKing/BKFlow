### 资源描述

获取任务状态

### 输入通用参数说明
|   参数名称   |    参数类型  |  必须  |     参数说明     |
| ------------ | ------------ | ------ | ---------------- |
| bk_app_code   | string | 是 | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| bk_app_secret | string | 是 | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": "ne7b82d4b9fd3378b93f97c2222a4b62",
        "state": "FINISHED",
        "root_id:": "ne7b82d4b9fd3378b93f97c2222a4b62",
        "parent_id": "ne7b82d4b9fd3378b93f97c2222a4b62",
        "version": "va054509441974d90bb82390de3320743",
        "loop": 1,
        "retry": 0,
        "skip": false,
        "error_ignorable": false,
        "error_ignored": false,
        "children": {
            "n112ae5c16c233efa5f3bff5b6c6375b": {
                "id": "n112ae5c16c233efa5f3bff5b6c6375b",
                "state": "FINISHED",
                "root_id:": "ne7b82d4b9fd3378b93f97c2222a4b62",
                "parent_id": "ne7b82d4b9fd3378b93f97c2222a4b62",
                "version": "v5fc1c39bf2d5408a8c6dab13708ba54c",
                "loop": 1,
                "retry": 0,
                "skip": false,
                "error_ignorable": false,
                "error_ignored": false,
                "children": {},
                "elapsed_time": 0,
                "start_time": "2023-06-15 17:29:41 +0800",
                "finish_time": "2023-06-15 17:29:41 +0800"
            },
            "nd1b94a5f14432d58622caee297273ca": {
                "id": "nd1b94a5f14432d58622caee297273ca",
                "state": "FINISHED",
                "root_id:": "ne7b82d4b9fd3378b93f97c2222a4b62",
                "parent_id": "ne7b82d4b9fd3378b93f97c2222a4b62",
                "version": "va79eab4eb3f64b4482a861ea5a211824",
                "loop": 1,
                "retry": 0,
                "skip": false,
                "error_ignorable": false,
                "error_ignored": false,
                "children": {},
                "elapsed_time": 0,
                "start_time": "2023-06-15 17:29:41 +0800",
                "finish_time": "2023-06-15 17:29:41 +0800"
            },
            "n97aec67e7a7341a9c2c36604cc8335c": {
                "id": "n97aec67e7a7341a9c2c36604cc8335c",
                "state": "FINISHED",
                "root_id:": "ne7b82d4b9fd3378b93f97c2222a4b62",
                "parent_id": "ne7b82d4b9fd3378b93f97c2222a4b62",
                "version": "v7612ecd5ed59462db4c10e481052621f",
                "loop": 1,
                "retry": 0,
                "skip": false,
                "error_ignorable": false,
                "error_ignored": false,
                "children": {},
                "elapsed_time": 0,
                "start_time": "2023-06-15 17:29:41 +0800",
                "finish_time": "2023-06-15 17:29:41 +0800"
            }
        },
        "elapsed_time": 0,
        "start_time": "2023-06-15 17:29:41 +0800",
        "finish_time": "2023-06-15 17:29:41 +0800"
    },
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

| 字段              | 类型     | 描述        |
|-----------------|--------|-----------|
| id              | string | 任务实例ID    |
| state           | string | 任务状态      |
| root_id         | string | 根任务ID     |
| parent_id       | string | 父任务ID     |
| version         | string | 任务版本      |
| loop            | int    | 任务循环次数    |
| retry           | int    | 任务重试次数    |
| skip            | bool   | 任务是否跳过    |
| error_ignorable | bool   | 任务是否忽略错误  |
| error_ignored   | bool   | 任务是否忽略错误  |
| children        | dict   | 节点状态列表    |
| elapsed_time    | int    | 任务耗时，单位：秒 |
| start_time      | string | 任务开始时间    |
| finish_time     | string | 任务结束时间    |