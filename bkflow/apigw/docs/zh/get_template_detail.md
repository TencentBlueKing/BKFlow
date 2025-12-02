### 资源描述

获取流程详情

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 接口参数

| 字段              | 类型     | 必选 | 描述                                                                                                                                           |
|-----------------|--------|----|----------------------------------------------------------------------------------------------------------------------------------------------|
| with_mock_data  | bool   | 否  | 是否一起返回 mock 数据，默认为 false。 当设置为 true 时，返回数据中会增加 appoint_node_ids 和 mock_data 两个字段，且如果 appoint_node_ids 有指定 mock 执行节点时，pipeline_tree 会进行对应的精简。 |


路径参数:

| 字段      | 类型     | 必选 | 描述                                              |
|---------|--------|----|-------------------------------------------------|
| template_id | string | 是  | 节点 ID，可以通过 get_task_detail 或 get_task_states 获取 |

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": 3,
        "space_id": 2,
        "name": "测试模板",
        "desc": null,
        "notify_config": {},
        "scope_type": null,
        "scope_value": null,
        "pipeline_tree": {
            "id": "p92c20c7854104dd3975f46a1d8664417",
            "start_event": {
                "incoming": "",
                "outgoing": "f06a78d1dcbe64fb79136b07eb7e71309",
                "type": "EmptyStartEvent",
                "id": "ec628b28ea1c74e11b92b6be3bdc0e1b6",
                "name": null
            },
            "end_event": {
                "incoming": [
                    "f5b91a6141a504b1b86f932d7e6c021f0"
                ],
                "outgoing": "",
                "type": "EmptyEndEvent",
                "id": "e7533e78a1a724b51942fcdf63fa23a60",
                "name": null
            },
            "activities": {
                "e2945819d402e41a9b9f8252a1b806f1c": {
                    "incoming": [
                        "f06a78d1dcbe64fb79136b07eb7e71309"
                    ],
                    "outgoing": "f5b91a6141a504b1b86f932d7e6c021f0",
                    "type": "ServiceActivity",
                    "id": "e2945819d402e41a9b9f8252a1b806f1c",
                    "name": null,
                    "error_ignorable": false,
                    "timeout": null,
                    "skippable": true,
                    "retryable": true,
                    "component": {
                        "code": "example_component",
                        "inputs": {}
                    },
                    "optional": false
                }
            },
            "gateways": {},
            "flows": {
                "f06a78d1dcbe64fb79136b07eb7e71309": {
                    "is_default": false,
                    "source": "ec628b28ea1c74e11b92b6be3bdc0e1b6",
                    "target": "e2945819d402e41a9b9f8252a1b806f1c",
                    "id": "f06a78d1dcbe64fb79136b07eb7e71309"
                },
                "f5b91a6141a504b1b86f932d7e6c021f0": {
                    "is_default": false,
                    "source": "e2945819d402e41a9b9f8252a1b806f1c",
                    "target": "e7533e78a1a724b51942fcdf63fa23a60",
                    "id": "f5b91a6141a504b1b86f932d7e6c021f0"
                }
            },
            "data": {
                "inputs": {},
                "outputs": []
            }
        },
        "source": null,
        "version": "",
        "is_enabled": true,
        "extra_info": {}
    },
    "code": 0,
    "trace_id": "xxxxxxxxx"
}
```
### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |

### data 包含字段说明

| 字段               | 类型       | 描述                                                             |
|------------------|----------|----------------------------------------------------------------|
| id               | int      | 流程 ID                                                          |
| space_id         | int      | 流程对应的空间 ID                                                     |
| name             | string   | 流程名称                                                           |
| desc             | string   | 流程描述                                                           |
| notify_config    | dict     | 流程通知配置                                                         |
| scope_type       | string   | 流程所属作用域类型                                                       |
| scope_value      | string   | 流程所属作用域值                                                        |
| pipeline_tree    | dict     | 流程树，当 with_mock_data 传参为 true 时，为精简后的流程树 ｜                     |
| source           | string   | 流程来源，第三方系统对应的资源 ID ｜                                           |
| version          | string   | 流程版本号，对应第三方系统对应的资源版本 ｜                                         |
| is_enabled       | bool     | 是否启用                                                           |
| extra_info       | dict     | 额外信息                                                           |
| create           | string   | 流程创建人                                                          |
| create_at        | datetime | 创建时间                                                           |
| update_by        | string   | 流程更新人                                                          |
| update_at        | datetime | 更新时间                                                           |
| appoint_node_ids | list     | 当 with_mock_data 传参为 true 时返回，mock 执行时选中的节点 ID 列表              |
| mock_data        | list     | 当 with_mock_data 传参为 true 时返回，每个元素包含 node_id，data 和 is_default |