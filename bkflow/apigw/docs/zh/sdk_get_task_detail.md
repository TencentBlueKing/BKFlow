### 租户访问约束

开启多租户时，全租户应用必须通过 `X-Bk-Tenant-Id` 指定本次请求租户；单租户应用可省略该头，使用 JWT 中已认证的应用租户，显式传入时必须一致。本次请求租户必须与资源所属空间租户一致；同一个全租户应用应在各租户分别创建空间。原有应用与空间/模板绑定仍需满足。若 JWT 包含已认证用户，其租户也必须一致。缺少或不匹配时拒绝请求。

应用态接口不要求额外用户身份。SDK 用户态接口仍要求已认证用户，平台管理员和空间管理员同样不能跨租户。关闭多租户模式时保持单租户行为。

### 资源描述

获取任务详情（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称         | 参数类型   | 必须 | 参数说明                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | 是  | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 接口申请。该 token 用于验证用户对指定任务的查看权限 |

### 路径参数

| 字段     | 类型     | 必选 | 描述   |
|--------|--------|----|------|
| task_id | string | 是  | 任务ID |

### 接口参数

| 字段       | 类型     | 必选 | 描述   |
|----------|--------|----|------|
| space_id | string | 是  | 空间ID |


### 返回结果示例
```json
{
     "result": true,
     "data": {
          "id": 15,
          "create_time": "2026-11-13 14:31:20+0800",
          "start_time": "2026-11-13 14:31:23+0800",
          "finish_time": "2026-11-13 14:31:23+0800",
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
               },
               "template_version": "1.0.1"
          },
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
               }
          },
          "outputs": [],
          "elapsed_time": 0,
          "space_id": 240,
          "tenant_id": "default",
          "scope_type": null,
          "scope_value": null,
          "instance_id": "n6e42c60e7ab3d229d7341dcdf7908c8",
          "template_id": 2211,
          "name": "xxx",
          "creator": "xxx",
          "create_method": "API",
          "trigger_method": "manual",
          "executor": "xxx",
          "description": "",
          "is_started": true,
          "is_finished": true,
          "is_revoked": false,
          "is_deleted": false,
          "is_expired": false,
          "snapshot_id": 100,
          "execution_snapshot_id": 100,
          "tree_info_id": 100,
          "auth": [
               "VIEW",
               "OPERATE",
               "FLOW_VIEW",
               "FLOW_EDIT",
               "FLOW_MOCK"
          ],
          "webhook_delivery_history": []
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

| 字段                       | 类型      | 描述                                                       |
|--------------------------|---------|----------------------------------------------------------|
| id                       | int     | 任务ID                                                     |
| create_time              | string  | 任务创建时间                                                   |
| start_time               | string  | 任务开始时间                                                   |
| finish_time              | string  | 任务结束时间，                                                  |
| extra_info               | dict    | 任务扩展信息，包含通知配置 `notify_config` 与模板版本 `template_version` 等 |
| pipeline_tree            | dict    | 任务对应的流程树                                                 |
| outputs                  | list    | 任务输出变量列表                                                 |
| elapsed_time             | int     | 任务已耗时长（秒）                                                |
| space_id                 | int     | 任务所属空间ID                                                 |
| tenant_id                | string  | 任务所属租户ID                                                 |
| scope_type               | string  | 任务作用范围类型（如业务/项目），为空时为 null                               |
| scope_value              | string  | 任务作用范围取值，为空时为 null                                       |
| instance_id              | string  | 流程引擎实例ID（运行时标识）                                          |
| template_id              | int     | 任务来源模板ID                                                 |
| name                     | string  | 任务名称                                                     |
| creator                  | string  | 任务创建者                                                    |
| create_method            | string  | 创建方式                                                     |
| trigger_method           | string  | 触发方式                                                     |
| executor                 | string  | 任务执行者                                                    |
| description              | string  | 任务描述                                                     |
| is_started               | bool    | 是否已启动                                                    |
| is_finished              | bool    | 是否已结束                                                    |
| is_revoked               | bool    | 是否已撤销                                                    |
| is_deleted               | bool    | 是否已删除                                                    |
| is_expired               | bool    | 是否已过期                                                    |
| snapshot_id              | int     | 任务模板快照ID                                                 |
| execution_snapshot_id    | int     | 任务执行快照ID                                                 |
| tree_info_id             | int     | 流程树信息ID                                                  |
| auth                     | list    | 当前请求用户对任务的权限列表                                           |
| webhook_delivery_history | list    | Webhook 记录列表                                             |

