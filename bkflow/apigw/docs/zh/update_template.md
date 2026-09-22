### 租户访问约束

开启多租户时，全租户应用必须通过 `X-Bk-Tenant-Id` 指定本次请求租户；单租户应用可省略该头，使用 JWT 中已认证的应用租户，显式传入时必须一致。本次请求租户必须与资源所属空间租户一致；同一个全租户应用应在各租户分别创建空间。原有应用与空间/模板绑定仍需满足。若 JWT 包含已认证用户，其租户也必须一致。缺少或不匹配时拒绝请求。

应用态接口不要求额外用户身份。SDK 用户态接口仍要求已认证用户，平台管理员和空间管理员同样不能跨租户。关闭多租户模式时保持单租户行为。

多租户模式下，流程树中的子流程、嵌套子画布及转换后的子流程插件只能引用当前空间的有效模板。关闭多租户时保留原有引用行为。历史版本查询始终绑定所属模板。

### 资源描述

更新模板

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |


#### 接口参数

| 字段                | 类型        | 必选 | 描述               |
|-------------------|-----------|----|------------------|
| name              | string    | 否  | 模板名称             |
| operator          | string    | 否  | 更新人              |
| notify_config     | json      | 否  | 模板描述             |
| desc              | string    | 否  | 空间描述             |
| scope_type        | string    | 否  | 模板范围类型           |
| scope_value       | string    | 否  | 模板范围值            |
| source            | string    | 否  | 模板来源(空间接入方自定义字段) |
| version           | string    | 否  | 模板版本(空间接入方自定义字段) |
| extra_info        | string    | 否  | 模板额外信息           |
| pipeline_tree     | json      | 否  | 模板信息             |
| auto_release      | bool      | 否  | 是否自动发布           |
| label_ids         | list      | 否  | 标签ID列表           |
| enable_webhook    | bool      | 否  | webhook开关        |
| webhook_configs   | json      | 否  | webhook配置        |
| triggers          | list      | 否  | 触发器配置            |


### notify_config 示例:
```json
{
  "notify_type": {
    "success": [
      "weixin",
      "wecom_robot",
      "sms"
    ],
    "fail": [
      "mail",
      "voice",
      "weixin",
      "wecom_robot"
    ]
  },
  "notify_receivers": {
    "receiver_group": [],
    "more_receiver": ""
  }
}
```

### webhook_configs 示例：
```json
{
  "method": "POST",
  "endpoint": "xxx",
  "extra_info": {
    "headers": [
      {
        "key": "Content-Type",
        "value": "application/json",
        "doc": ""
      }
    ],
    "timeout": 10,
    "retry_times": 2,
    "interval": 60
  }
}
```


### triggers 示例:
```json
[
  {
    "id": null,  
    "config": {
      "mode": "form",
      "constants": {},
      "cron": {
        "minute": "*",
        "hour": "*",
        "day_of_month": "*",
        "month_of_year": "*",
        "day_of_week": "*"
      }
    },
    "is_deleted": false,
    "space_id": 1,
    "template_id": 10,
    "is_enabled": false,
    "name": "定时触发",
    "type": "periodic"
  }
]
```
第一次创建是id为null，后续在更新时需要传递具体的id

### 网关表达式校验说明

更新模板时，接口会对请求体中的 `pipeline_tree` 进行**分支网关表达式语言**校验：流程树内所有 `ExclusiveGateway` / `ConditionalParallelGateway` 网关节点的表达式语言，必须与所属空间的网关表达式配置（空间配置项 `gateway_expression`，默认值为 `boolrule`）保持一致。

校验规则：

- 未显式设置 `extra_info.parse_lang` 的老数据，默认按 `boolrule` 解析；
- 若网关 `parse_lang` 与空间配置不一致，则校验失败；
- 子流程（`SubCanvas` / `SubProcess`）内嵌的网关也会被递归校验；

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "模板名",
    "label_ids": [1, 2, 3]
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": 4,
        "space_id": "2",
        "name": "模板名",
        "labels": [],
        "desc": null,
        "notify_config": {},
        "scope_type": null,
        "scope_value": null,
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
        "source": null,
        "version": "",
        "is_enabled": true,
        "extra_info": {},
        "creator": "",
        "create_at": "2024-08-02T08:53:20.173Z",
        "update_at": "2024-08-02T08:53:20.173Z",
        "updated_by": "",
        "enable_webhook": false,
        "webhook_configs":{}
    },
    "code": 0
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

| 字段              | 类型     | 描述       |
|-----------------|--------|----------|
| id              | string | 流程ID     |
| space_id        | string | 流程所属空间ID |
| name            | string | 流程名称     |
| desc            | string | 流程描述     |
| notify_config   | dict   | 通知配置     |
| scope_type      | string | 流程范围类型   |
| scope_value     | string | 流程范围ID   |
| pipeline_tree   | dict   | 流程树详情    |
| source          | string | 流程来源     |
| version         | string | 流程版本     |
| is_enabled      | bool   | 流程是否启用   |
| extra_info      | dict   | 流程扩展信息   |
| creator         | string | 流程创建者    |
| create_at       | string | 流程创建时间   |
| update_at       | string | 流程更新时间   |
| updated_by      | string | 流程更新者    |
| labels          | list   | 标签列表（标签对象数组） |
| enable_webhook  | bool   | webhook开关    |
| webhook_configs | dict   | webhook配置    |

说明：

- 不传 `label_ids`：不更新模板标签
- 传 `label_ids: []`：清空模板标签
### 定时触发器时区

`triggers[].config.timezone` 可指定有效的 IANA 时区（例如 `Europe/Paris`）。新建时省略则保存当前请求的有效用户时区；编辑时省略则保留既有计划时区。历史未标时区的计划继续使用其已保存的 Engine 调度时区，不随编辑者切换。返回的 config 保留新计划的 timezone，界面按此显示和预览。
