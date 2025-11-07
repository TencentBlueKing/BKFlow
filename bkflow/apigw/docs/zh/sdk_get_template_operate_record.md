### 资源描述

获取流程的操作记录（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 路径参数

| 字段         | 类型     | 必选 | 描述    |
|------------|--------|----|-------|
| template_id | string | 是  | 流程模板ID |

### 接口参数

无

### 请求参数示例

```
GET /sdk/template/{template_id}/get_template_operation_record/
```

### 返回结果示例

```json
{
    "result": true,
    "message": "success",
    "data": [
        {
            "id": 1,
            "instance_id": 123,
            "operation_type": "CREATE",
            "operator": "admin",
            "operation_time": "2024-01-01T00:00:00Z",
            "operation_source": "WEB"
        }
    ]
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| message | string | 返回消息                  |
| data    | list   | 返回数据，操作记录列表          |

#### data[item] 字段说明

| 字段             | 类型     | 描述       |
|----------------|--------|----------|
| id             | int    | 记录ID     |
| instance_id    | int    | 实例ID     |
| operation_type | string | 操作类型     |
| operator       | string | 操作人      |
| operation_time | string | 操作时间     |
| operation_source | string | 操作来源     |


