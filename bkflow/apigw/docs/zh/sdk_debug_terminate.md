### 资源描述

终止流程调试运行（SDK接口）

### HTTP Header 参数说明

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| HTTP_BKFLOW_TOKEN | string | 是 | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 申请，权限类型为 `MOCK` |

### 接口参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| space_id | int | 是 | 空间ID |
| template_id | int | 是 | 流程模板ID |
| node_id | string | 否 | 节点ID；传入时终止单节点并恢复为未调试，不传时终止当前全局调试任务 |

### 单节点终止

请求示例：

```json
{
  "space_id": 1,
  "template_id": 100,
  "node_id": "node1"
}
```

返回 `data` 示例：

```json
{
  "status": "idle",
  "reset_node_ids": ["node1"]
}
```

单节点终止成功后已经完成状态收敛，不需要等待 `terminating`。前端重新请求调试上下文时，目标节点
`nodes[].status` 为 `not_run`，节点输入、输出、耗时、错误和日志引用均已清空；上下文 `status` 为 `idle`，
`last_run_status` 为 `not_run`。

### 全局调试终止

请求示例：

```json
{
  "space_id": 1,
  "template_id": 100
}
```

返回 `data` 示例：

```json
{
  "status": "terminating"
}
```

前端收到 `terminating` 后继续轮询调试上下文。上下文 `status` 变为 `idle` 表示终止完成；此时
`last_run_status` 为 `revoked`，前端展示为“调试终止”。终止时仍处于 `running | waiting | paused` 的节点
恢复为 `not_run`，已经完成或自然失败的节点保留原状态。
