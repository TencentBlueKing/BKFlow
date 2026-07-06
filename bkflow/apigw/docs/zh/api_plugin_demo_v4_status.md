### 资源描述

API 插件 Demo V4 查询插件运行状态，用于验证 polling 调度分支。

### 请求方法

GET

### 接口参数

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| task_tag | string | 是 | execute 返回的 open_plugin_run_id |
| status | string | 否 | 演示状态，可选 SUCCEEDED、FAILED、RUNNING，默认 SUCCEEDED |

### 请求参数示例

```text
GET /api_plugin_demo/v4/status/?task_tag=demo_polling_job:task-1-node-node-a-attempt-1
```

### 返回结果示例

```json
{
  "result": true,
  "message": "",
  "data": {
    "open_plugin_run_id": "demo_polling_job:task-1-node-node-a-attempt-1",
    "status": "SUCCEEDED",
    "outputs": {
      "job_instance_id": "demo-job-task-1-node-node-a-attempt-1",
      "message": "demo open plugin finished"
    }
  }
}
```
