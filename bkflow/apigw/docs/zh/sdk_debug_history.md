### 资源描述

获取流程调试历史（SDK接口）

### HTTP Header 参数说明

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| HTTP_BKFLOW_TOKEN | string | 是 | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 申请，权限类型建议为 `MOCK` |

### 接口参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| space_id | int | 是 | 空间ID |
| template_id | int | 是 | 流程模板ID |

### 请求参数示例

```
GET /sdk/template/debug/history/?space_id=1&template_id=100
```

### 返回结果示例

```json
{
  "runs": [
    {
      "task_id": 1,
      "operator": "admin",
      "started_at": "2026-07-06 10:00:00",
      "status": "finished"
    }
  ]
}
```
