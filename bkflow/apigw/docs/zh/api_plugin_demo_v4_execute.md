### 资源描述

API 插件 Demo V4 执行插件，用于验证 execute payload 中的 context、plugin_version、callback_url 和 callback_token。

### 请求方法

POST

### 接口参数

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| source_key | string | 是 | 开放插件来源 |
| plugin_id | string | 是 | 插件 ID |
| plugin_version | string | 是 | 插件业务版本 |
| client_request_id | string | 是 | BKFlow 本次调用唯一请求 ID |
| callback_url | string | 否 | BKFlow 节点回调 URL |
| callback_token | string | 否 | BKFlow 节点回调 token |
| inputs | object | 否 | 插件输入参数 |
| context | object | 否 | BKFlow 透传上下文 |

### 请求参数示例

```json
{
  "source_key": "OpenPluginV4Demo",
  "plugin_id": "demo_polling_job",
  "plugin_version": "1.1.0",
  "client_request_id": "task-1-node-node-a-attempt-1",
  "inputs": {
    "target_ip": "127.0.0.1"
  },
  "context": {
    "space_id": 1,
    "operator": "admin"
  }
}
```

### 返回结果示例

```json
{
  "result": true,
  "message": "",
  "data": {
    "open_plugin_run_id": "demo_polling_job:task-1-node-node-a-attempt-1",
    "status": "RUNNING",
    "received_context": {
      "space_id": 1,
      "operator": "admin"
    }
  }
}
```
