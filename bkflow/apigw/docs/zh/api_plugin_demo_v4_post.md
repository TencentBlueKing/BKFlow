# API 插件 Demo V4 POST 入口

用于 stage 环境验证 `uniform_api v4.0.0` 协议的 POST 类接口。网关资源使用 `/api_plugin_demo/v4/` 前缀匹配，实际能力由子路径区分。

## 子路径

| 子路径 | 说明 |
| ------ | ---- |
| `/api_plugin_demo/v4/execute/` | 模拟 V4 execute 响应 |
| `/api_plugin_demo/v4/execute/{open_plugin_run_id}/cancel/` | 模拟取消开放插件运行实例 |

## execute 请求示例

```bash
POST /api_plugin_demo/v4/execute/
```

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

## 返回说明

返回结构遵循 API 插件协议：

```json
{
  "result": true,
  "message": "",
  "data": {}
}
```
