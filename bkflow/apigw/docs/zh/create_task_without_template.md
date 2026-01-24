### 资源描述

创建任务

### 输入通用参数说明
|   参数名称   |    参数类型  |  必须  |     参数说明     |
| ------------ | ------------ | ------ | ---------------- |
| bk_app_code   | string | 是 | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| bk_app_secret | string | 是 | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |


#### 接口参数

| 字段                    | 类型     | 必选 | 描述                                    |
|----------------------|--------|----|---------------------------------------|
| creator               | string | 是  | 创建者                                    |
| pipeline_tree         | json   | 是  | 任务结构树                                  |
| name                  | string | 否  | 任务名                                    |
| scope_type            | string | 否  | 任务范围类型                                 |
| scope_value           | string | 否  | 任务范围值                                  |
| description           | string | 否  | 描述                                    |
| constants             | json   | 否  | 任务启动参数                                |
| custom_span_attributes | dict   | 否  | 自定义 Span 属性，会添加到所有节点上报的 Span 中，详见下方说明 |

### custom_span_attributes 参数说明

`custom_span_attributes` 参数用于在创建任务时传递自定义属性到所有节点上报的 Span 中，支持用户通过自定义属性来进行埋点上报。

**参数格式要求：**
- 类型：字典（dict）
- key：自定义属性名称（字符串）
- value：自定义属性值（字符串、数字等可序列化的值）

**使用场景：**
- 业务埋点：传入业务ID、订单ID等业务标识进行埋点上报
- 请求埋点：传入请求ID、调用链ID等请求标识进行埋点上报
- 环境埋点：传入环境类型、区域等环境信息进行埋点上报

**参数示例：**
```json
{
    "custom_span_attributes": {
        "business_id": "12345",
        "request_id": "req-abc-123",
        "env": "prod"
    }
}
```

**注意事项：**
- 自定义属性会被存储在任务的 `extra_info.custom_context.custom_span_attributes` 中
- 这些属性会通过 `TaskContext` 传递到所有节点的 Span 中
- 自定义属性的优先级高于默认的 Span 属性（如 space_id、task_id 等），如果 key 相同会被覆盖

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "creator": "创建者",
    "pipeline_tree": {
        "name": "test",
        "activities": {
            "nf834705dbbb37c59ad114aa37314975": {
                "component": {
                    "code": "bk_display",
                    "data": {
                        "bk_display_message": {
                            "hook": false,
                            "need_render": true,
                            "value": ""
                        }
                    },
                    "version": "v1.0"
                },
                "error_ignorable": false,
                "id": "nf834705dbbb37c59ad114aa37314975",
                "incoming": [
                    "lee4ca362c673536958aa656cb36efda"
                ],
                "loop": null,
                "name": "消息展示",
                "optional": true,
                "outgoing": "l2e819009a9a3714ab108ad5c594bb73",
                "stage_name": "",
                "type": "ServiceActivity",
                "retryable": true,
                "skippable": true,
                "auto_retry": {
                    "enable": false,
                    "interval": 0,
                    "times": 1
                },
                "timeout_config": {
                    "enable": false,
                    "seconds": 10,
                    "action": "forced_fail"
                },
                "labels": []
            }
        },
        "end_event": {
            "id": "n2dfd1233f633cdf864fc3681eb2b0b3",
            "incoming": [
                "l2e819009a9a3714ab108ad5c594bb73"
            ],
            "name": "",
            "outgoing": "",
            "type": "EmptyEndEvent",
            "labels": []
        },
        "flows": {
            "lee4ca362c673536958aa656cb36efda": {
                "id": "lee4ca362c673536958aa656cb36efda",
                "is_default": false,
                "source": "n1df1598dba137aba81094851379435a",
                "target": "nf834705dbbb37c59ad114aa37314975"
            },
            "l2e819009a9a3714ab108ad5c594bb73": {
                "id": "l2e819009a9a3714ab108ad5c594bb73",
                "is_default": false,
                "source": "nf834705dbbb37c59ad114aa37314975",
                "target": "n2dfd1233f633cdf864fc3681eb2b0b3"
            }
        },
        "gateways": {},
        "line": [
            {
                "id": "lee4ca362c673536958aa656cb36efda",
                "source": {
                    "arrow": "Right",
                    "id": "n1df1598dba137aba81094851379435a"
                },
                "target": {
                    "arrow": "Left",
                    "id": "nf834705dbbb37c59ad114aa37314975"
                }
            },
            {
                "id": "l2e819009a9a3714ab108ad5c594bb73",
                "source": {
                    "arrow": "Right",
                    "id": "nf834705dbbb37c59ad114aa37314975"
                },
                "target": {
                    "arrow": "Left",
                    "id": "n2dfd1233f633cdf864fc3681eb2b0b3"
                }
            }
        ],
        "location": [
            {
                "id": "n1df1598dba137aba81094851379435a",
                "type": "startpoint",
                "x": 40,
                "y": 150
            },
            {
                "id": "nf834705dbbb37c59ad114aa37314975",
                "type": "tasknode",
                "name": "消息展示",
                "stage_name": "",
                "x": 240,
                "y": 140,
                "group": "蓝鲸服务(BK)",
                "icon": "",
                "optional": true,
                "error_ignorable": false,
                "retryable": true,
                "skippable": true,
                "auto_retry": {
                    "enable": false,
                    "interval": 0,
                    "times": 1
                },
                "timeout_config": {
                    "enable": false,
                    "seconds": 10,
                    "action": "forced_fail"
                }
            },
            {
                "id": "n2dfd1233f633cdf864fc3681eb2b0b3",
                "type": "endpoint",
                "x": 540,
                "y": 150
            }
        ],
        "outputs": [],
        "start_event": {
            "id": "n1df1598dba137aba81094851379435a",
            "incoming": "",
            "name": "",
            "outgoing": "lee4ca362c673536958aa656cb36efda",
            "type": "EmptyStartEvent",
            "labels": []
        },
        "constants": {},
        "projectBaseInfo": {},
        "notify_receivers": {
            "receiver_group": [],
            "more_receiver": ""
        },
        "notify_type": {
            "success": [],
            "fail": []
        },
        "template_labels": [],
        "internalVariable": {
            "${_system.task_name}": {
                "key": "${_system.task_name}",
                "name": "任务名称",
                "index": -1,
                "desc": "",
                "show_type": "hide",
                "source_type": "system",
                "source_tag": "",
                "source_info": {},
                "custom_type": "",
                "value": "",
                "hook": false,
                "validation": ""
            },
            "${_system.task_id}": {
                "key": "${_system.task_id}",
                "index": -2,
                "name": "任务ID",
                "desc": "",
                "show_type": "hide",
                "source_type": "system",
                "source_tag": "",
                "source_info": {},
                "custom_type": "",
                "value": "",
                "hook": false,
                "validation": ""
            },
            "${_system.task_start_time}": {
                "key": "${_system.task_start_time}",
                "name": "任务开始时间",
                "index": -3,
                "desc": "",
                "show_type": "hide",
                "source_type": "system",
                "source_tag": "",
                "source_info": {},
                "custom_type": "",
                "value": "",
                "hook": false,
                "validation": ""
            },
            "${_system.operator}": {
                "key": "${_system.operator}",
                "name": "任务的执行人（点击开始执行的人员）",
                "index": -4,
                "desc": "",
                "show_type": "hide",
                "source_type": "system",
                "source_tag": "",
                "source_info": {},
                "custom_type": "",
                "value": "",
                "hook": false,
                "validation": ""
            }
        },
        "spaceId": 1,
        "scopeInfo": {
            "scope_type": null,
            "scope_value": null
        }
    }
}
```

带自定义 Span 属性的请求参数示例：
```json
{
    "creator": "创建者",
    "pipeline_tree": {
        "name": "test",
        "activities": {},
        "end_event": {},
        "flows": {},
        "gateways": {},
        "start_event": {},
        "constants": {}
    },
    "name": "测试任务",
    "custom_span_attributes": {
        "business_id": "12345",
        "request_id": "req-abc-123",
        "env": "prod"
    }
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": 93,
        "space_id": 1,
        "scope_type": null,
        "scope_value": null,
        "instance_id": "nb2bf870164336798522536f036a4da7",
        "template_id": null,
        "name": "default_taskflow_instance",
        "creator": "创建者",
        "create_time": "2023-10-16T17:24:07.859339+08:00",
        "executor": "",
        "start_time": null,
        "finish_time": null,
        "description": "",
        "is_started": false,
        "is_finished": false,
        "is_revoked": false,
        "is_deleted": false,
        "is_expired": false,
        "snapshot_id": 80,
        "execution_snapshot_id": 77,
        "tree_info_id": null,
        "extra_info": {
            "notify_config": {
                "notify_type": {
                    "fail": [],
                    "success": []
                },
                "notify_receivers": {
                    "more_receiver": "",
                    "receiver_group": []
                }
            }
        }
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