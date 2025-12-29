### 资源描述

回滚流程（SDK接口）

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

| 字段        | 类型     | 必选   | 描述       |
|-----------|--------|------|----------|
| version   | string | 是    | 需要回滚的版本号 |


### 请求参数示例

```
POST /sdk/template/{template_id}/rollback_template/
```

### 返回结果示例

```json
{
     "result": true,
     "data": {
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
| data    | dict   | 回滚后的流程数据              |

