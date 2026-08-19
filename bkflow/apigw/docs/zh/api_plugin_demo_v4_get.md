# API 插件 Demo V4 GET 入口

用于 stage 环境验证 `uniform_api v4.0.0` 协议的 GET 类接口。网关资源使用 `/api_plugin_demo/v4/` 前缀匹配，实际能力由子路径区分。

## 子路径

| 子路径 | 说明 |
| ------ | ---- |
| `/api_plugin_demo/v4/category/` | 获取 V4 demo 插件分类 |
| `/api_plugin_demo/v4/list_meta/` | 获取 V4 demo 插件列表 |
| `/api_plugin_demo/v4/detail_meta/` | 获取指定插件业务版本详情 |
| `/api_plugin_demo/v4/status/` | 查询 polling demo 运行状态 |

## 请求示例

```bash
GET /api_plugin_demo/v4/category/
GET /api_plugin_demo/v4/list_meta/?limit=50&offset=0
GET /api_plugin_demo/v4/detail_meta/?api_id=demo_polling_job&version=1.1.0
GET /api_plugin_demo/v4/status/?task_tag=demo_polling_job:task-1-node-node-a-attempt-1
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
