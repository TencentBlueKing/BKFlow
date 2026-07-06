### 资源描述

API 插件 Demo V4 获取指定插件业务版本详情，用于验证 schema、业务版本和调度配置。

### 请求方法

GET

### 接口参数

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| api_id | string | 是 | 插件 ID |
| version | string | 否 | 插件业务版本，不传时使用默认版本 |

### 请求参数示例

```text
GET /api_plugin_demo/v4/detail_meta/?api_id=demo_polling_job&version=1.1.0
```

### 返回结果示例

```json
{
  "result": true,
  "message": "",
  "data": {
    "id": "demo_polling_job",
    "plugin_version": "1.1.0",
    "wrapper_version": "v4.0.0",
    "url": "http://bkflow.example/stage/api_plugin_demo/v4/execute/",
    "methods": ["POST"],
    "polling": {
      "url": "http://bkflow.example/stage/api_plugin_demo/v4/status/",
      "task_tag_key": "open_plugin_run_id"
    }
  }
}
```
