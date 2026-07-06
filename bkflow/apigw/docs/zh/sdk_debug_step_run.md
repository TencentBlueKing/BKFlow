### 资源描述

执行流程单步调试（SDK接口）

### HTTP Header 参数说明

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| HTTP_BKFLOW_TOKEN | string | 是 | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 申请，权限类型为 `MOCK` |

### 接口参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| space_id | int | 是 | 空间ID |
| template_id | int | 是 | 流程模板ID |
| node_id | string | 是 | 节点ID |
| mode | string | 否 | 执行模式，`real` 或 `mock` |
| input_overrides | dict | 否 | 输入覆盖参数 |
| mock_result | string | 否 | mock 结果，`success` 或 `fail` |
| mock_outputs | dict | 否 | mock 输出 |
| mock_error | string | 否 | mock 失败信息 |

### 请求参数示例

```json
{
  "space_id": 1,
  "template_id": 100,
  "node_id": "node1",
  "mode": "mock",
  "mock_result": "success",
  "mock_outputs": {
    "k": "v"
  }
}
```
