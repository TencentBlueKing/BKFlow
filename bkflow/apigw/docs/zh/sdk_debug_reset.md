### 资源描述

重置流程调试上下文（SDK接口）

### HTTP Header 参数说明

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| HTTP_BKFLOW_TOKEN | string | 是 | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 申请，权限类型为 `MOCK` |

### 接口参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| space_id | int | 是 | 空间ID |
| template_id | int | 是 | 流程模板ID |
| node_ids | list | 否 | 指定重置的节点ID列表，不传则重置全部 |

### 请求参数示例

```json
{
  "space_id": 1,
  "template_id": 100,
  "node_ids": ["node1"]
}
```
