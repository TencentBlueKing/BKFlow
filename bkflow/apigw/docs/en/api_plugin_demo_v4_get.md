# API Plugin Demo V4 GET endpoint

GET endpoints for verifying the `uniform_api v4.0.0` protocol in stage. The gateway resource matches the `/api_plugin_demo/v4/` prefix; subpaths select the operation.

## Subpaths

| Subpath | Description |
| ------ | ---- |
| `/api_plugin_demo/v4/category/` | Get V4 demo plugin categories |
| `/api_plugin_demo/v4/list_meta/` | Get the V4 demo plugin list |
| `/api_plugin_demo/v4/detail_meta/` | Get details of a plugin business version |
| `/api_plugin_demo/v4/status/` | Query the polling demo execution status |

## Request example

```bash
GET /api_plugin_demo/v4/category/
GET /api_plugin_demo/v4/list_meta/?limit=50&offset=0
GET /api_plugin_demo/v4/detail_meta/?api_id=demo_polling_job&version=1.1.0
GET /api_plugin_demo/v4/status/?task_tag=demo_polling_job:task-1-node-node-a-attempt-1
```

## Response

The response follows the API plugin protocol:

```json
{
  "result": true,
  "message": "",
  "data": {}
}
```
