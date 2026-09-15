### 资源描述

获取流程调试上下文（SDK接口）

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
GET /sdk/template/debug/context/?space_id=1&template_id=100
```

### 返回结果示例

```json
{
  "template_id": 100,
  "status": "idle",
  "locked_by": "",
  "active_task_id": null,
  "active_run_type": null,
  "active_node_id": null,
  "last_task_id": 456,
  "last_run_type": "global",
  "last_run_status": "failed",
  "last_error_detail": {
    "type": "runtime",
    "message": "multiple conditions meet",
    "task_id": 456,
    "failures": [
      {
        "node_id": "runtime_gateway_id",
        "template_node_id": null,
        "message": "multiple conditions meet"
      }
    ]
  },
  "last_inputs": {},
  "global_vars": {},
  "nodes": [
    {
      "node_id": "node1",
      "node_type": "ServiceActivity",
      "execution_mode": "real",
      "supports_step": true,
      "supports_mock": true,
      "status": "waiting",
      "waiting_reason": "callback",
      "selected_flow_ids": [],
      "condition_results": []
    },
    {
      "node_id": "gateway1",
      "node_type": "ExclusiveGateway",
      "execution_mode": "real",
      "supports_step": true,
      "supports_mock": false,
      "status": "finished",
      "waiting_reason": null,
      "selected_flow_ids": ["flow_true"],
      "condition_results": [
        {
          "flow_id": "flow_true",
          "name": "条件1",
          "expression": "${count} > 0",
          "resolved_expression": "1 > 0",
          "matched": true
        }
      ]
    },
    {
      "node_id": "parallel_gateway1",
      "node_type": "ParallelGateway",
      "execution_mode": "real",
      "supports_step": false,
      "supports_mock": false,
      "status": "finished",
      "waiting_reason": null,
      "selected_flow_ids": [],
      "condition_results": []
    }
  ]
}
```

`status` 表示上下文锁状态，取值为 `idle | running | terminating`。运行结果以 `last_run_status` 为准，取值为 `not_run | running | waiting | paused | finished | failed | revoked`。其中 `revoked` 仅表示全局调试被主动终止，前端展示为“调试终止”；单节点终止完成后为 `not_run`。

`active_task_id` 仅在任务运行期间有值，任务结束后清空；`last_task_id` 会保留最近一次真实引擎任务 ID。节点 `status` 取值为 `not_run | running | waiting | paused | finished | failed`。全局调试终止时，仍活跃的节点会恢复为 `not_run`，已完成或自然失败节点保留原状态。存在引擎调度记录时，`waiting_reason` 为 `callback | multiple_callback | poll`。

`nodes` 包含活动节点和流程中的全部网关节点：分支网关（`ExclusiveGateway`）、条件并行网关（`ConditionalParallelGateway`）、并行网关（`ParallelGateway`）和汇聚网关（`ConvergeGateway`）。开始、结束节点不在该数组中。

`supports_step` 表示节点是否支持单步调试，`supports_mock` 表示是否支持 Mock。活动节点两者均为 `true`；分支网关和条件并行网关为 `supports_step=true`、`supports_mock=false`；并行网关和汇聚网关两者均为 `false`，仅用于展示全局调试状态。前端调试控制面板应过滤 `supports_step=false` 且 `supports_mock=false` 的节点。

所有网关固定为 `execution_mode=real`。条件网关调试完成后，前端直接使用 `selected_flow_ids` 将命中的连线标记为绿色；`condition_results` 可用于展示每个分支的原始表达式、求值后的表达式和命中结果。并行网关、汇聚网关和活动节点的这两个字段均为空数组。
