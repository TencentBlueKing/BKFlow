### 资源描述

校验任务结构树是否合法

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |


#### 接口参数

| 字段            | 类型     | 必选 | 描述    |
|---------------|--------|----|-------|
| pipeline_tree | json   | 是  | 任务结构树 | 



### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
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

### 返回结果示例

```json
{
    "result": true,
    "data": {},
    "code": "0",
    "message": ""
}

```
### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | string | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |
