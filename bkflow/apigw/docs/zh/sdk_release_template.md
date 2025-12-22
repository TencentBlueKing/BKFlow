### 资源描述

发布流程（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| HTTP_BKFLOW_TOKEN | string | 是  | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 接口申请。该 token 用于验证用户对指定空间资源的访问权限（需要提供 template_id 或 task_id） |

### 路径参数

| 字段          | 类型     | 必选 | 描述   |
|-------------|--------|----|------|
| template_id | string | 是  | 流程ID |

### 接口参数

| 字段        | 类型     | 必选 | 描述    |
|-----------|--------|----|-------|
| version   | string | 是  | 发布版本号 |
| desc      | string | 否  | 版本描述  |


### 请求参数示例

```
POST /sdk/template/{template_id}/release_template/
```

### 返回结果示例

```json
{
     "result": true,
     "data": {
          "pipeline_tree": {
               "id": "pd0980c284042448380d29e046bf348fc",
               "start_event": {
                    "incoming": "",
                    "outgoing": "f22d707b4e7704868b51fbc504107da27",
                    "type": "EmptyStartEvent",
                    "id": "e39ce14ef5df644ccaa5236b50a9c44ca",
                    "name": null
               },
               "end_event": {
                    "incoming": [
                         "f520808740b9945f8b01fa1dd889945d9"
                    ],
                    "outgoing": "",
                    "type": "EmptyEndEvent",
                    "id": "e17aef95ed6934a428215b2a7a3fa4184",
                    "name": null
               },
               "activities": {
                    "e36e8026b07b5448299b52f91a9d265af": {
                         "incoming": [
                              "f22d707b4e7704868b51fbc504107da27"
                         ],
                         "outgoing": "f520808740b9945f8b01fa1dd889945d9",
                         "type": "ServiceActivity",
                         "id": "e36e8026b07b5448299b52f91a9d265af",
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
                    "f22d707b4e7704868b51fbc504107da27": {
                         "is_default": false,
                         "source": "e39ce14ef5df644ccaa5236b50a9c44ca",
                         "target": "e36e8026b07b5448299b52f91a9d265af",
                         "id": "f22d707b4e7704868b51fbc504107da27"
                    },
                    "f520808740b9945f8b01fa1dd889945d9": {
                         "is_default": false,
                         "source": "e36e8026b07b5448299b52f91a9d265af",
                         "target": "e17aef95ed6934a428215b2a7a3fa4184",
                         "id": "f520808740b9945f8b01fa1dd889945d9"
                    }
               },
               "data": {
                    "inputs": {},
                    "outputs": []
               }
          },
          "snapshot_id": 283,
          "notify_config": {
               "notify_type": {
                    "fail": [],
                    "success": []
               },
               "notify_receivers": {
                    "more_receiver": "",
                    "receiver_group": []
               }
          },
          "version": "1.0.4",
          "desc": null,
          "triggers": [],
          "subprocess_info": [],
          "creator": "xxx",
          "create_at": "2025-05-19T11:34:00.551630+08:00",
          "update_at": "2025-05-22T12:13:42.270250+08:00",
          "updated_by": "xxx",
          "is_deleted": false,
          "space_id": 1,
          "name": "test",
          "scope_type": null,
          "scope_value": null,
          "source": null,
          "is_enabled": true,
          "extra_info": {},
          "auth": [
               "VIEW",
               "EDIT",
               "MOCK"
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



### data 包含字段说明

| 字段              | 类型       | 描述       |
|-----------------|----------|----------|
| id              | string   | 流程ID     |
| space_id        | string   | 流程所属空间ID |
| name            | string   | 流程名称     |
| desc            | string   | 流程描述     |
| notify_config   | dict     | 通知配置     |
| scope_type      | string   | 流程范围类型   |
| scope_value     | string   | 流程范围ID   |
| pipeline_tree   | dict     | 流程树详情    |
| source          | string   | 流程来源     |
| version         | string   | 流程版本     |
| is_enabled      | bool     | 流程是否启用   |
| extra_info      | dict     | 流程扩展信息   |
| creator         | string   | 流程创建者    |
| create_at       | string   | 流程创建时间   |
| update_at       | string   | 流程更新时间   |
| updated_by      | string   | 流程更新者    |
| triggers        | list     | 触发器信息    |
| subprocess_info | list     | 子流程信息    |