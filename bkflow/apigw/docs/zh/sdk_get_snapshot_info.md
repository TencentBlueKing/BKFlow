### 租户访问约束

开启多租户时，全租户应用必须通过 `X-Bk-Tenant-Id` 指定本次请求租户；单租户应用可省略该头，使用 JWT 中已认证的应用租户，显式传入时必须一致。本次请求租户必须与资源所属空间租户一致；同一个全租户应用应在各租户分别创建空间。原有应用与空间/模板绑定仍需满足。若 JWT 包含已认证用户，其租户也必须一致。缺少或不匹配时拒绝请求。

应用态接口不要求额外用户身份。SDK 用户态接口仍要求已认证用户，平台管理员和空间管理员同样不能跨租户。关闭多租户模式时保持单租户行为。

### 资源描述

获取快照详情（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称         | 参数类型   | 必须 | 参数说明                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | 是  | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 接口申请。该 token 用于验证用户对指定空间资源的访问权限（需要提供 template_id 或 task_id） |

### 路径参数

| 字段          | 类型     | 必选 | 描述   |
|-------------|--------|----|------|
| snapshot_id | string | 是  | 快照ID |

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": 341,
        "create_time": "2026-10-28 11:46:36+0800",
        "update_time": "2026-10-28 11:46:36+0800",
        "version": "1.0.0",
        "template_id": 85,
        "desc": null,
        "draft": false,
        "auto_save": false,
        "creator": "xxx",
        "operator": "xxx",
        "pipeline_tree": {
            "activities": {
                "n02ab8bbb0fd34e592ed90ad3f700220": {
                    "component": {
                        "code": "sleep_timer",
                        "data": {
                            "bk_timing": {
                                "hook": false,
                                "need_render": true,
                                "value": "5"
                            },
                            "force_check": {
                                "hook": false,
                                "need_render": true,
                                "value": true
                            }
                        },
                        "version": "legacy"
                    },
                    "error_ignorable": false,
                    "id": "n02ab8bbb0fd34e592ed90ad3f700220",
                    "incoming": [
                        "lbffdeddc2ee355489df5042d899ecf8"
                    ],
                    "loop": null,
                    "name": "定时",
                    "optional": true,
                    "outgoing": "l9d0c2ed80c334dfa8ca27de212be7ff",
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
            "canvas_mode": "horizontal",
            "constants": {},
            "end_event": {
                "id": "n1dbc0a5f0243409a1bf338dedb76ee0",
                "incoming": [
                    "l9d0c2ed80c334dfa8ca27de212be7ff"
                ],
                "name": "",
                "outgoing": "",
                "type": "EmptyEndEvent",
                "labels": []
            },
            "flows": {
                "lbffdeddc2ee355489df5042d899ecf8": {
                    "id": "lbffdeddc2ee355489df5042d899ecf8",
                    "is_default": false,
                    "source": "n403483bfc7f37f48329c51c518b3b2a",
                    "target": "n02ab8bbb0fd34e592ed90ad3f700220"
                },
                "l9d0c2ed80c334dfa8ca27de212be7ff": {
                    "id": "l9d0c2ed80c334dfa8ca27de212be7ff",
                    "is_default": false,
                    "source": "n02ab8bbb0fd34e592ed90ad3f700220",
                    "target": "n1dbc0a5f0243409a1bf338dedb76ee0"
                }
            },
            "gateways": {},
            "line": [
                {
                    "id": "lbffdeddc2ee355489df5042d899ecf8",
                    "source": {
                        "arrow": "Right",
                        "id": "n403483bfc7f37f48329c51c518b3b2a"
                    },
                    "target": {
                        "arrow": "Left",
                        "id": "n02ab8bbb0fd34e592ed90ad3f700220"
                    }
                },
                {
                    "id": "l9d0c2ed80c334dfa8ca27de212be7ff",
                    "source": {
                        "arrow": "Right",
                        "id": "n02ab8bbb0fd34e592ed90ad3f700220"
                    },
                    "target": {
                        "arrow": "Left",
                        "id": "n1dbc0a5f0243409a1bf338dedb76ee0"
                    }
                }
            ],
            "location": [
                {
                    "id": "n403483bfc7f37f48329c51c518b3b2a",
                    "type": "startpoint",
                    "x": 40,
                    "y": 150
                },
                {
                    "id": "n02ab8bbb0fd34e592ed90ad3f700220",
                    "type": "tasknode",
                    "name": "定时",
                    "stage_name": "",
                    "x": 240,
                    "y": 140,
                    "group": "蓝鲸服务(BK)",
                    "icon": ""
                },
                {
                    "id": "n1dbc0a5f0243409a1bf338dedb76ee0",
                    "type": "endpoint",
                    "x": 540,
                    "y": 150
                }
            ],
            "outputs": [],
            "start_event": {
                "id": "n403483bfc7f37f48329c51c518b3b2a",
                "incoming": "",
                "name": "",
                "outgoing": "lbffdeddc2ee355489df5042d899ecf8",
                "type": "EmptyStartEvent",
                "labels": []
            },
            "stage_canvas_data": [
                {
                    "id": "nodec6ec7e8bb4d3fb5ffcea70b6a19f",
                    "name": "",
                    "config": [],
                    "jobs": [
                        {
                            "id": "nodedc2dde0ef8ce42fd678df273ce6d",
                            "name": "",
                            "config": [],
                            "nodes": [
                                {
                                    "id": "node35d8a3338718018e90b1bcb7976a",
                                    "type": "Node"
                                }
                            ],
                            "type": "Job"
                        }
                    ],
                    "type": "Stage"
                }
            ]
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
| code    | string | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |


#### data 字段说明

| 字段           | 类型     | 描述     |
|--------------|--------|--------|
| id           | int    | 快照ID   |
| create_time  | string | 创建时间   |
| update_time  | string | 更新时间   |
| version      | string | 流程发布版本号 |
| template_id  | int    | 关联流程模板ID |
| desc         | string | 快照描述   |
| draft        | bool   | 是否为草稿快照 |
| auto_save    | bool   | 是否为自动保存快照 |
| creator      | string | 创建者    |
| operator     | string | 最近操作人  |
| pipeline_tree | dict  | 流程数据 |
