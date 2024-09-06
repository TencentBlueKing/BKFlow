### 资源描述

应用空间 webhook 配置

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

#### 接口参数

| 字段       | 类型   | 必选 | 描述                                                            |
|----------|------|----|---------------------------------------------------------------|
| webhooks | list | 是  | webhook 列表，列表中的每个元素对应一份 webhook 配置，每次调用会对当前空间的 webhook 配置进行覆盖 |

#### webhook 配置说明
| 字段         | 类型     | 必选 | 描述                                                                                 |
|------------|--------|----|------------------------------------------------------------------------------------|
| code       | string | 是  | webhook 编码，需唯一                                                                     |
| name       | string | 是  | webhook 名称                                                                         |
| endpoint   | string | 是  | webhook 请求地址                                                                       |
| events     | list   | 是  | webhook 订阅的事件列表, 支持的事件有: template_update，template_create，task_failed，task_finished |
| extra_info | json   | 否  | 额外扩展信息                                                                             |

### 请求参数示例

```json
{
    "webhooks": [
        {
            "code": "webhook1",
            "name": "webhook1",
            "endpoint": "http://webhook1.com",
            "events": ["template_update", "template_create"]
        },
        {
            "code": "webhook2",
            "name": "webhook2",
            "endpoint": "http://webhook2.com",
            "events": ["task_failed", "task_finished"]
        
        }
    ]
}
```

### 返回结果示例

```json
{
    "result": true,
    "message": "success",
    "data": {},
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