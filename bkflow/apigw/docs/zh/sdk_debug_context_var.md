### 资源描述

设置流程调试上下文变量（SDK接口）

### HTTP Header 参数说明

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| HTTP_BKFLOW_TOKEN | string | 是 | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 申请，权限类型为 `MOCK` |

### 接口参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| space_id | int | 是 | 空间ID |
| template_id | int | 是 | 流程模板ID |
| key | string | 是 | 变量 key |
| value | any | 是 | 变量值 |

### 请求参数示例

```json
{
  "space_id": 1,
  "template_id": 100,
  "key": "${input}",
  "value": "value"
}
```
