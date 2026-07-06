### 资源描述

API 插件 Demo V4 获取插件列表，用于 stage 环境验证 uniform_api v4.0.0 协议。

### 请求方法

GET

### 接口参数

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| limit | int | 否 | 分页大小 |
| offset | int | 否 | 分页偏移 |
| category | string | 否 | 插件分组 |

### 请求参数示例

```text
GET /api_plugin_demo/v4/list_meta/?limit=50&offset=0
```

### 返回结果示例

```json
{
  "result": true,
  "message": "",
  "data": {
    "total": 2,
    "apis": [
      {
        "id": "demo_polling_job",
        "name": "V4 Polling Demo 作业",
        "wrapper_version": "v4.0.0",
        "default_version": "1.0.0",
        "latest_version": "1.1.0",
        "versions": ["1.0.0", "1.1.0"],
        "meta_url_template": "http://bkflow.example/stage/api_plugin_demo/v4/detail_meta/?api_id=demo_polling_job&version={version}"
      }
    ]
  }
}
```
