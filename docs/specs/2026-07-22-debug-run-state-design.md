# 调试运行状态修复设计

## 问题

当前 real 单步调试在请求内最多轮询 60 秒。暂停、审批、回调插件、长定时等节点进入引擎调度后仍会保持 `RUNNING`，最终被调试服务误判为超时失败。

全局调试结束时，`active_task_id` 会随锁一起清空，context 也没有保留最近一次任务的最终状态。网关失败又不属于活动节点，前端只看活动节点时会把失败任务展示为成功。

## 状态模型

调试锁状态和运行结果分开表达：

- `status`: `idle | running | terminating`，只表示调试上下文是否被占用。
- `last_run_status`: `not_run | running | waiting | paused | finished | failed | revoked`，表示最近一次真实引擎运行结果。
- `active_task_id`: 当前仍在运行的任务，结束后清空。
- `last_task_id`: 最近一次真实引擎任务，结束后保留。
- `active_run_type`: 当前任务类型，`global | step`。
- `active_node_id`: 单步任务对应的模板节点。
- `last_error_detail`: 最近一次任务级错误，包含活动节点或网关的运行时节点 ID 和异常信息。

节点增加 `waiting`、`paused` 状态和 `waiting_reason`。本次只支持等待态展示和已有终止能力，不新增主动暂停/恢复调试操作。

## 执行与同步

real 单步创建并启动微型任务后立即返回 `running`，不再在 HTTP 请求内同步轮询。任务 ID、运行类型和目标节点写入 context，后续由 `GET debug_context` 惰性同步。

引擎内部 `get_states` 增加可选参数 `include_schedule`。启用时，只为存在未结束调度记录的节点返回 `schedule_type`：

- `CALLBACK`、`MULTIPLE_CALLBACK`、`POLL` 映射为节点 `waiting`，并写入小写 `waiting_reason`。
- 引擎 `SUSPENDED` 映射为节点 `paused`。
- 其他 `RUNNING` 仍为 `running`。

调试同步同时请求 `with_ex_data`。任务失败时，即使失败节点是没有 DebugNodeState 的网关，也将异常写入 context 的 `last_error_detail`，并把 `last_run_status` 置为 `failed`。任务结束后释放锁、清空 active 字段，但保留 last 字段。

## 兼容性

原有字段语义保持不变，新增字段均有默认值。`get_states` 的调度信息是按需返回，不影响现有调用。mock 单步仍同步返回结果，不创建引擎任务。
