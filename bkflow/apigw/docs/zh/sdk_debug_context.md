### 租户访问约束

开启多租户时，全租户应用必须通过 `X-Bk-Tenant-Id` 指定本次请求租户；单租户应用可省略该头，使用 JWT 中已认证的应用租户，显式传入时必须一致。本次请求租户必须与资源所属空间租户一致；同一个全租户应用应在各租户分别创建空间。原有应用与空间/模板绑定仍需满足。若 JWT 包含已认证用户，其租户也必须一致。缺少或不匹配时拒绝请求。

应用态接口不要求额外用户身份。SDK 用户态接口仍要求已认证用户，平台管理员和空间管理员同样不能跨租户。关闭多租户模式时保持单租户行为。

### 资源描述

获取流程调试上下文（SDK接口）

### HTTP Header 参数说明

| 参数名称         | 参数类型 | 必须 | 参数说明 |
|--------------| --- | --- | --- |
| BKFLOW-TOKEN | string | 是 | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 申请，权限类型建议为 `MOCK` |

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
      "config_changed": true,
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
      "config_changed": false,
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
      "config_changed": false,
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

### 节点配置变化标记

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| nodes[].config_changed | bool | 当前已保存的节点名称或执行配置是否与最近调试采用的内容不一致。与节点 `status` 独立，不代表调试成功或失败。 |

接口优先读取草稿，没有草稿时读取正式快照，并与该节点最近一次完成调试时采用的配置比较。保存配置不会修改 `debug_snapshot` 中的名称、节点集合、顺序或运行结果；快照差异标记会随已保存的草稿变化。重复保存不会解除不一致标记；恢复到已调试过的配置后，标记恢复为 `false`。

- 单步真实执行、Mock 执行和条件网关求值，无论成功还是执行失败，均更新该节点的调试配置基准。只修改 Mock 预设不更新基准。
- 全局调试仅更新实际完成或执行失败的节点，未执行到的节点不更新基准。请求被依赖检查拦截、创建任务失败或启动失败，也不更新基准。
- 如果按配置 A 发起调试，运行期间保存为 B，A 完成后仍返回 `config_changed=true`，直到 B 被调试或配置恢复为 A。
- 新节点首次出现时返回 `status=not_run`、`config_changed=false`；之后保存的执行配置发生变化时会标记为 `true`。存量节点缺少配置基准（空字符串或 `null`）时默认返回 `false`，不补写历史基准；重新调试建立基准后，开始比较后续配置变化。`false` 不代表已调试或调试成功，仍以 `status` 为准。
- 比较范围包括节点插件及参数、执行选项、网关条件、内嵌子流程和循环配置。节点名称单独比较，不改变已有配置哈希算法；说明、坐标及画布布局不参与比较；不推断上游输出或全局变量变更对下游的影响。
- 此字段只反映已保存配置，不包含前端尚未保存的修改，也不决定历史节点与当前画布的点击联动。

`supports_step` 表示节点是否支持单步调试，`supports_mock` 表示是否支持 Mock。活动节点两者均为 `true`；分支网关和条件并行网关为 `supports_step=true`、`supports_mock=false`；并行网关和汇聚网关两者均为 `false`，仅用于展示全局调试状态。前端调试控制面板应过滤 `supports_step=false` 且 `supports_mock=false` 的节点。

所有网关固定为 `execution_mode=real`。条件网关调试完成后，前端直接使用 `selected_flow_ids` 将命中的连线标记为绿色；`condition_results` 可用于展示每个分支的原始表达式、求值后的表达式和命中结果。并行网关、汇聚网关和活动节点的这两个字段均为空数组。


### 调试结果快照

`nodes` 仍对应当前已保存草稿，用于单步调试、Mock 配置和可执行性判断；新增的 `nodes[].node_name` 是当前名称。
结果列表应改为读取 `debug_snapshot.nodes`，其中 `node_name` 是调试时名称，不再从当前画布拼接。结果节点不是可执行节点列表，已删除节点不能再次单步执行。

```json
{
  "debug_snapshot": {
    "nodes": [
      {
        "node_id": "node1",
        "node_name": "调试时的名称",
        "node_type": "ServiceActivity",
        "execution_mode": "real",
        "status": "finished",
        "waiting_reason": null,
        "inputs": {},
        "outputs": {"result": "ok"},
        "duration_ms": 120,
        "error_detail": null,
        "log_ref": {"instance_id": 456, "node_id": "runtime_node1", "version": "v1"},
        "last_run_at": null,
        "operator": "admin",
        "config_changed": true,
        "node_deleted": false
      }
    ]
  }
}
```

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| debug_snapshot | object / null | 最新调试上下文的结果快照。没有新版本调试记录、存量记录无法还原或全量重置后为 null，不用当前草稿补造历史。 |
| debug_snapshot.nodes[].node_name | string | 本次调试采用的名称，保存草稿不覆盖。 |
| debug_snapshot.nodes[].config_changed | bool | 与已保存草稿相比，节点名称或执行配置不同。没有可靠基准时默认 false。 |
| debug_snapshot.nodes[].node_deleted | bool | 节点已不在当前已保存草稿中；旧结果及日志引用仍保留。 |
| debug_snapshot.nodes[].execution_mode | string | 结果对应的实际调试模式，real / mock，不随 Mock 预设调整而变化。 |
| debug_snapshot.nodes[].status / waiting_reason | string / string或null | 运行状态及等待原因，含义与现有节点态相同。 |
| debug_snapshot.nodes[].inputs / outputs | object | 已记录的输入输出。网关的 outputs 包含 selected_flow_ids 和 condition_results。未采集到的输入为 {}。 |
| debug_snapshot.nodes[].duration_ms / error_detail / log_ref | int或null / object或null / object或null | 保存的耗时、错误和日志引用。 |
| debug_snapshot.nodes[].operator / last_run_at | string / string或null | 发起调试的用户及已记录的运行时间；没有可靠时间时返回 null。 |

- 全局调试成功启动后建立整份快照；单步（真实、Mock、条件网关）只更新目标节点，其他节点保留各自最近结果。这里的快照可能包含多次单步结果，不表示同一个引擎任务。
- 运行期间名称、结构和节点集合已冻结，状态和结果随轮询更新；保存新草稿不改变运行结果的解释依据。创建、启动或依赖检查失败不会替换上次结果快照。
- 节点按调试时的控制流顺序返回，前驱在后继之前、汇聚在分支之后；并行分支按节点 ID 稳定展开，不代表真实执行先后。循环回边不重复展开；子画布作为一个节点，开始和结束节点不出现在列表中。
- 编辑名称、增删节点或调整连线不会改写旧列表；单步新增节点按本次流程位置插入，已有历史节点相对顺序不变。下一次全局调试重新建立完整顺序。
- 显式重置单节点会清空该节点结果；全量重置清空快照。终止调试沿用现有规则：保留已完成结果，活跃节点恢复 not_run。
- 存量缺失名称或快照不回填；名称基准在重新调试后建立。原有配置基准继续有效，不因升级而批量标记变化。
- 两种差异标记都只针对已保存的草稿。未保存编辑、点击画布联动和提示文案由前端结合当前画布处理。
