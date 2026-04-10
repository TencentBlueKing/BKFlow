### 资源描述

获取流程的操作记录（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| HTTP_BKFLOW_TOKEN | string | 是  | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 接口申请。该 token 用于验证用户对指定模板的查看权限 |

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
     "data": {
          "result": true,
          "message": "success",
          "data": [
               {
                    "id": 1,
                    "instance_id": 123,
                    "operation_type": "CREATE",
                    "operator": "admin",
                    "operation_source": "WEB",
                    "operation_date": "2024-12-15T21:10:43.284071+08:00",
                    "operation_type_name": "创建",
                    "operation_source_name": "app 页面",
                    "version": ""
               }
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
| message | string | 返回消息                  |
| data    | dict   | 返回数据，操作记录列表           |
| code    | string | 返回状态码                 |

#### data[data][item] 字段说明

| 字段                    | 类型      | 描述     |
|-----------------------|---------|--------|
| id                    | int     | 记录ID   |
| instance_id           | int     | 实例ID   |
| operation_type        | string  | 操作类型   |
| operator              | string  | 操作人    |
| operation_date        | string  | 操作时间   |
| operation_source      | string  | 操作来源   |
| operation_type_name   | string  | 操作类型说明 |
| operation_source_name | string  | 操作来源说明 |
| version               | string  | 流程版本   |


