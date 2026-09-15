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
| mode | string | 否 | 执行模式，`real` 或 `mock`；条件网关仅支持 `real` |
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

### real 模式返回结果示例

real 单步创建并启动引擎任务后立即返回。调用方通过 `debug_context` 轮询任务后续的 `running | waiting | paused | finished | failed` 状态。

```json
{
  "node_id": "node1",
  "task_id": 456,
  "status": "running",
  "log_ref": {
    "instance_id": 456,
    "node_id": "runtime_node_id",
    "version": "v1"
  }
}
```

mock 模式仍同步返回 `finished` 或 `failed` 及对应输出、错误详情和更新后的全局变量。

### 条件网关 real 模式返回结果示例

分支网关和条件并行网关同步计算分支条件，只返回命中的连线，不创建引擎任务，也不会执行命中连线后的节点。前端使用 `selected_flow_ids` 将对应路径标记为绿色。

```json
{
  "node_id": "gateway1",
  "status": "finished",
  "selected_flow_ids": ["flow_true"],
  "condition_results": [
    {
      "flow_id": "flow_true",
      "name": "条件1",
      "expression": "${count} > 0",
      "resolved_expression": "1 > 0",
      "matched": true
    }
  ],
  "error_detail": null
}
```

条件网关依赖的前序节点输出尚不存在时，接口返回“依赖未满足”及 `missing_vars`。表达式解析失败、分支网关同时命中多个条件等执行错误会同步返回 `status=failed`，并将错误写入 `error_detail`；随后也可从 `debug_context.nodes[]` 获取相同状态和分支结果。
