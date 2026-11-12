### 租户访问约束

开启多租户时，全租户应用必须通过 `X-Bk-Tenant-Id` 指定本次请求租户；单租户应用可省略该头，使用 JWT 中已认证的应用租户，显式传入时必须一致。本次请求租户必须与资源所属空间租户一致；同一个全租户应用应在各租户分别创建空间。原有应用与空间/模板绑定仍需满足。若 JWT 包含已认证用户，其租户也必须一致。缺少或不匹配时拒绝请求。

应用态接口不要求额外用户身份。SDK 用户态接口仍要求已认证用户，平台管理员和空间管理员同样不能跨租户。关闭多租户模式时保持单租户行为。

### 资源描述

批量获取任务执行实例pipeline树

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 路径参数:

| 字段         | 类型    | 必选   | 描述     |
|------------|-------|------|--------|
| space_id   | int   | 是    | 空间ID   |

#### 接口参数

| 字段         | 类型     | 必选    | 描述            |
|------------|--------|-------|---------------|
| task_ids   | string | 是     | 任务ID，多个以,号分割  |


### 返回结果示例

```json
{
    "result": true,
    "data": {
        "1": {
            "activities": {
                "n8698713071f3c19a8c65ad6cf21d8fb": {
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
                    "id": "n8698713071f3c19a8c65ad6cf21d8fb",
                    "incoming": [
                        "l48e87eb2fe23073a6cdfe354f7395b1"
                    ],
                    "loop": null,
                    "name": "消息展示",
                    "optional": true,
                    "outgoing": "lab4348a155931a99841d4b2fd1c4b2b",
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
                    "labels": [],
                    "template_node_id": "n36ab89190e73486ac44df57717e52fa"
                }
            },
            "canvas_mode": "horizontal",
            "constants": {},
            "end_event": {
                "id": "n7ee43b7bef03c6997b1bb4ecd98585f",
                "incoming": [
                    "lab4348a155931a99841d4b2fd1c4b2b"
                ],
                "name": "",
                "outgoing": "",
                "type": "EmptyEndEvent",
                "labels": []
            },
            "flows": {
                "l48e87eb2fe23073a6cdfe354f7395b1": {
                    "id": "l48e87eb2fe23073a6cdfe354f7395b1",
                    "is_default": false,
                    "source": "n2f89c1efe273024abb8c4c230e372ac",
                    "target": "n8698713071f3c19a8c65ad6cf21d8fb"
                },
                "lab4348a155931a99841d4b2fd1c4b2b": {
                    "id": "lab4348a155931a99841d4b2fd1c4b2b",
                    "is_default": false,
                    "source": "n8698713071f3c19a8c65ad6cf21d8fb",
                    "target": "n7ee43b7bef03c6997b1bb4ecd98585f"
                }
            },
            "gateways": {},
            "line": [
                {
                    "id": "l48e87eb2fe23073a6cdfe354f7395b1",
                    "source": {
                        "arrow": "Right",
                        "id": "n2f89c1efe273024abb8c4c230e372ac"
                    },
                    "target": {
                        "arrow": "Left",
                        "id": "n8698713071f3c19a8c65ad6cf21d8fb"
                    }
                },
                {
                    "id": "lab4348a155931a99841d4b2fd1c4b2b",
                    "source": {
                        "arrow": "Right",
                        "id": "n8698713071f3c19a8c65ad6cf21d8fb"
                    },
                    "target": {
                        "arrow": "Left",
                        "id": "n7ee43b7bef03c6997b1bb4ecd98585f"
                    }
                }
            ],
            "location": [
                {
                    "id": "n2f89c1efe273024abb8c4c230e372ac",
                    "type": "startpoint",
                    "x": 40,
                    "y": 150
                },
                {
                    "id": "n8698713071f3c19a8c65ad6cf21d8fb",
                    "type": "tasknode",
                    "name": "消息展示",
                    "stage_name": "",
                    "x": 240,
                    "y": 140,
                    "group": "蓝鲸服务(BK)",
                    "icon": ""
                },
                {
                    "id": "n7ee43b7bef03c6997b1bb4ecd98585f",
                    "type": "endpoint",
                    "x": 540,
                    "y": 150
                }
            ],
            "outputs": [],
            "start_event": {
                "id": "n2f89c1efe273024abb8c4c230e372ac",
                "incoming": "",
                "name": "",
                "outgoing": "l48e87eb2fe23073a6cdfe354f7395b1",
                "type": "EmptyStartEvent",
                "labels": []
            },
            "stage_canvas_data": [
                {
                    "id": "node079af7eeec4ca7af387b6ae2b08f",
                    "name": "",
                    "config": [],
                    "jobs": [
                        {
                            "id": "nodeb79ceaa6ce4457c7956e539193bf",
                            "name": "",
                            "config": [],
                            "nodes": [
                                {
                                    "id": "node37fbb15738f875854cc238bd0dd0",
                                    "type": "Node"
                                }
                            ],
                            "type": "Job"
                        }
                    ],
                    "type": "Stage"
                }
            ],
            "id": "n2f4614f1ed135a18eabbe9157f198ad"
        }
    },
    "code": "0",
    "message": ""
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                   |
|---------|--------|----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | string | 返回码，"0"表示成功，其他值表示失败   |
| message | string | 错误信息                 |
| data    | dict   | 返回数据，key为任务ID，value为该任务的pipeline结构 |

