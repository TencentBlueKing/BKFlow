### 资源描述

API 插件 Demo V4 取消插件运行实例，用于验证 terminate/revoke 时的开放插件 cancel 分支。

### 请求方法

POST

### 路径参数

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| open_plugin_run_id | string | 是 | execute 返回的 open_plugin_run_id |

### 请求参数示例

```text
POST /api_plugin_demo/v4/execute/demo_polling_job:task-1-node-node-a-attempt-1/cancel/
```

### 返回结果示例

```json
{
  "result": true,
  "message": "",
  "data": {
    "open_plugin_run_id": "demo_polling_job:task-1-node-node-a-attempt-1",
    "status": "CANCELLED"
  }
}
```
