### 资源描述

导入简化流程 JSON 并创建模板

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| access_token  | string | 否  | 用户或应用 access_token，详情参考 AccessToken API                     |

#### 接口参数

| 字段           | 类型     | 必选 | 描述                                |
|--------------|--------|----|-----------------------------------|
| name         | string | 是  | 模板名称                              |
| simple_flow  | list   | 是  | 简化流程 JSON 数组                      |
| creator      | string | 否  | 创建人                               |
| desc         | string | 否  | 模板描述                              |
| scope_type   | string | 否  | 流程范围类型，与 scope_value 必须同时填写或同时不填写 |
| scope_value  | string | 否  | 流程范围值，与 scope_type 必须同时填写或同时不填写   |
| auto_release | bool   | 否  | 是否自动发布，默认为 false                  |

simple_flow 数组中支持以下节点类型：

| type        | 描述   | 必填字段                  |
|-------------|------|-----------------------|
| StartEvent  | 开始节点 | id, name              |
| EndEvent    | 结束节点 | id, name              |
| Activity    | 任务节点 | id, name, code        |
| Link        | 连线   | source, target        |

### 请求参数示例

```json
{
    "name": "消息展示",
    "desc": "通过简化流程 JSON 创建的模板",
    "auto_release": false,
    "simple_flow": [
        {"type": "StartEvent", "id": "start", "name": "开始"},
        {"type": "Activity", "id": "n1", "name": "消息展示", "code": "bk_display"},
        {"type": "EndEvent", "id": "end", "name": "结束"},
        {"type": "Link", "source": "start", "target": "n1"},
        {"type": "Link", "source": "n1", "target": "end"}
    ]
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": 3,
        "space_id": "1",
        "name": "消息展示",
        "desc": "通过简化流程 JSON 创建的模板",
        "notify_config": {},
        "scope_type": null,
        "scope_value": null,
        "source": null,
        "version": null,
        "is_enabled": true,
        "bk_app_code": null,
        "extra_info": {},
        "creator": "",
        "create_at": "2026-03-13T06:59:38.890Z",
        "update_at": "2026-03-13T06:59:38.890Z",
        "updated_by": "",
        "pipeline_tree": {
            "activities": {
                "n1": {
                    "id": "n1",
                    "name": "消息展示",
                    "type": "ServiceActivity",
                    "incoming": ["lb"],
                    "outgoing": "l7",
                    "stage_name": "消息展示",
                    "component": {
                        "code": "bk_display",
                        "version": "v1.0",
                        "data": {}
                    },
                    "auto_retry": {
                        "enable": false,
                        "interval": 0,
                        "times": 1
                    },
                    "timeout_config": {
                        "action": "forced_fail",
                        "enable": false,
                        "seconds": 10
                    },
                    "error_ignorable": false,
                    "retryable": true,
                    "skippable": true,
                    "optional": true,
                    "labels": [],
                    "loop": null
                }
            },
            "gateways": {},
            "flows": {
                "lb": {
                    "id": "lb",
                    "is_default": false,
                    "source": "n4",
                    "target": "n1"
                },
                "l7": {
                    "id": "l7",
                    "is_default": false,
                    "source": "n1",
                    "target": "nb"
                }
            },
            "start_event": {
                "id": "n4",
                "name": "开始",
                "type": "EmptyStartEvent",
                "incoming": "",
                "outgoing": "lb",
                "labels": []
            },
            "end_event": {
                "id": "nb",
                "name": "结束",
                "type": "EmptyEndEvent",
                "incoming": ["l7"],
                "outgoing": "",
                "labels": []
            },
            "constants": {},
            "outputs": []
        }
    },
    "code": 0,
    "trace_id": "xxxxxxxxx"
}
```

### 返回结果参数说明

| 字段       | 类型     | 描述                    |
|----------|--------|-----------------------|
| result   | bool   | 返回结果，true为成功，false为失败 |
| code     | int    | 返回码，0表示成功，其他值表示失败     |
| message  | string | 错误信息                  |
| data     | dict   | 返回数据                  |
| trace_id | string | open telemetry trace_id |

#### data[item]

| 字段            | 类型     | 描述       |
|---------------|--------|----------|
| id            | int    | 流程ID     |
| space_id      | string | 流程所属空间ID |
| name          | string | 流程名称     |
| desc          | string | 流程描述     |
| notify_config | dict   | 通知配置     |
| scope_type    | string | 流程范围类型   |
| scope_value   | string | 流程范围ID   |
| source        | string | 流程来源     |
| version       | string | 流程版本     |
| is_enabled    | bool   | 流程是否启用   |
| bk_app_code   | string | 绑定的应用编码  |
| extra_info    | dict   | 流程扩展信息   |
| creator       | string | 流程创建者    |
| create_at     | string | 流程创建时间   |
| update_at     | string | 流程更新时间   |
| updated_by    | string | 流程更新者    |
| pipeline_tree | dict   | 流程树详情    |
