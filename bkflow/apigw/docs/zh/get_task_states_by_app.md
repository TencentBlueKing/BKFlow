### 资源描述

通过 bk_app_code 权限校验获取任务状态

此接口用于获取绑定了 bk_app_code 的流程创建的任务状态，请求方的 bk_app_code 需要与任务所属模板绑定的 bk_app_code 一致才能查看任务状态。

**注意：此接口需要用户认证。**

### 输入通用参数说明
|   参数名称   |    参数类型  |  必须  |     参数说明     |
| ------------ | ------------ | ------ | ---------------- |
| bk_app_code   | string | 是 | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| bk_app_secret | string | 是 | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| bk_username   | string | 是 | 用户名，用于用户认证 |

路径参数:

| 字段  | 类型  | 必选  | 描述  |
| --- | --- | --- | --- |
|  task_id   |  int   |  是  |  任务 ID |

### 权限说明

- 任务必须是由绑定了 bk_app_code 的流程模板创建
- 请求方的 bk_app_code 必须与任务所属模板绑定的 bk_app_code 一致
- 需要用户认证

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
            }
        },
        "elapsed_time": 0,
        "start_time": "2023-06-15 17:29:41 +0800",
        "finish_time": "2023-06-15 17:29:41 +0800"
    },
    "message": ""
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

