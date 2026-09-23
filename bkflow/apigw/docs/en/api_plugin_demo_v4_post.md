# API Plugin Demo V4 POST endpoint

POST endpoints for verifying the `uniform_api v4.0.0` protocol in stage. The gateway resource matches the `/api_plugin_demo/v4/` prefix; subpaths select the operation.

## Subpaths

| Subpath | Description |
| ------ | ---- |
| `/api_plugin_demo/v4/execute/` | Simulate a V4 execute response |
| `/api_plugin_demo/v4/execute/{open_plugin_run_id}/cancel/` | Simulate cancellation of an open plugin execution instance |

## execute request example

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

## Response

The response follows the API plugin protocol:

```json
{
  "result": true,
  "message": "",
  "data": {}
}
```
