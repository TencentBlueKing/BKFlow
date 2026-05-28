### 资源描述

获取任务节点配置快照信息

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| HTTP_BKFLOW_TOKEN | string | 是  | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 接口申请。该 token 用于验证用户对指定任务的查看权限 |

### 路径参数

| 字段        | 类型     | 必选 | 描述   |
|-----------|--------|----|------|
| task_id   | string | 是  | 任务ID |
| node_id   | string | 是  | 节点ID |

### 接口参数

| 字段        | 类型  | 必选 | 描述   |
|-----------|-----|----|------|
| space_id  | int | 是  | 空间ID |


### 返回结果示例

```json
{
     "result": true,
     "message": "success",
     "data": {
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
          "id": "nd08100455cb3f47b1be3e352d508650",
          "incoming": [
               "line3c5a376461d0e836213d39aee346"
          ],
          "name": "定时",
          "optional": true,
          "outgoing": "line1504dcca7856c15db80344ab1549",
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
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |
| page    | dict   | 数据分页信息                |

#### data 字段说明

| 字段              | 类型     | 描述     |
|-----------------|--------|--------|
| component       | dict   | 节点字段信息 |
| error_ignorable | bool   | 是否失败跳过 |
| id              | string | 节点id   |
| incoming        | list   | 节点入度   |
| name            | string | 节点名称   |
| optional        | dict   | 是否可选   |
| outgoing        | dict   | 节点出度   |
| stage_name      | dict   | 步骤名称   |
| type            | string | 节点类型   |
| retryable       | bool   | 是否允许重试 |
| skippable       | bool   | 是否允许跳过 |
| auto_retry      | dict   | 节点重试配置 |
| timeout_config  | dict   | 节点超时配置 |
| labels          | list   | 节点标签   |

