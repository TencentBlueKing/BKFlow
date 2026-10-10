### Harness P2：读取调试会话

传输参数校验失败统一返回 `SCHEMA_VALIDATION_ERROR`；`path` 仅引用服务端声明字段（无法安全定位时为 `request`），修复动作是 `repair_tool_arguments`，不回显原始参数或未知字段名。业务拒绝的错误分类及治理动作保持不变。

#### 接口说明

`harness_get_debug_session` 对应 MCP Tool `get_debug_session`，属于 `BKFlow Workflow Harness MCP` contract `1.2.0`。它读取 BKFlow 持久化的确定性 Session/Evidence，并在调试开关开启时只归并与本 Session `current_task_id` 精确匹配的 Engine 状态。

#### 请求方法

POST `/space/{space_id}/harness/get_debug_session/`

#### 租户边界

开启多租户时，全租户应用必须传 `X-Bk-Tenant-Id` 请求头；单租户应用可省略并使用已认证应用租户。应用本次请求租户、已认证用户租户和路由空间租户必须一致，Body 中的身份字段不能覆盖此边界。关闭多租户时忽略该请求头。

#### 可信字段与不可信字段

APIGW 应用、用户、路径空间、Scope、环境与 Session 归属是可信字段。Body 仅允许下表字段；Body 身份、Token、任意模板历史或 Engine task ID 都是不可信字段并拒绝。读请求不接受幂等请求头。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| session_id | uuid | 是 | 必须由当前可信上下文拥有。 |
| limit | integer | 否 | 1 至 100，默认 20。 |
| cursor | safe opaque string | 否 | 按 `(occurred_at,id)` 稳定翻页当前 Session 的 Evidence。 |
| node_limit | integer | 否 | 1 至 20，默认 10；独立控制节点页数量，实际还受 8 KiB 字节预算限制。 |
| node_cursor | safe opaque string | 否 | 使用 `context_page.next_cursor`；绑定当前 Session 和脱敏快照，不可跨会话或跨快照复用。 |
| node_id | string | 否 | 使用节点页返回的调试节点 id，定点读取单节点；不得与 node_cursor 同传。 |

#### 响应 Envelope

Envelope 顶层固定为 10 个键：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。上下文、节点状态和 Evidence 均经过有界深度脱敏；历史页还受累计 UTF-8 字节预算限制，`next_cursor` 只指向实际纳入的最后一项。

调试 feature flag 关闭时，本 Tool 仍可读取已持久化的 Session 与 Evidence，但不会解析 capability、访问插件目录、调用 Template DebugService、Engine 或 Token Broker，也不会做终态化或写 Evidence。生命周期清理由服务端 reaper 负责。

#### 大流程节点摘要与分页

`artifact_refs[0].context` 保留原兼容投影，超预算时可能仍返回 `omitted`。Agent 应读取新增的 `context_page`：

- `summary.total_nodes` / `summary.status_counts`：完整有界节点集合的数量和状态汇总；不把未运行节点误算为成功。
- `items`：当前页的脱敏节点状态、等待原因、错误、Mock 结果和网关选择等可用字段。
- `metadata`：有界脱敏的任务、输入及上下文信息；超限单独标记，不阻断节点读取。
- `snapshot_id` / `next_cursor`：快照标识和下一页。`next_cursor` 为 null 时本次遍历结束。

`artifact_refs[0].read_guidance` 区分运行轮询、节点翻页与历史翻页：

- `context_source=context_page`：以节点页为证据来源。终态兼容字段 `context.available=false, reason=session_terminal` 只表示不再读实时画布，不代表已保存的 `context_page` 不可用。值为 `unavailable` 时没有可用节点快照，不能伪报通过。
- `poll_required`：仅启用调试且会话为 RUNNING 时为 true；终态不再轮询任务。false 不代表已经验收通过，也不禁止 ACTIVE 会话继续受控调试。
- `node_query=all_nodes/single_node`：本次节点查询的范围；单节点读完不等于全流程已读完。
- `node_page_has_more` 与 `history_has_more`：分别指示两套分页。继续节点页时使用 `node_cursor`；继续历史页时使用 `cursor`，不能互换。已读完的页仍使用该页请求的游标，避免另一套分页反复从头开始。

终态或调试开关关闭时，仅在仍有后续页时返回 `next_actions=[get_debug_session]`，两套分页均到末尾则为 `[]`。这只是本次查询的结束提示，不证明客户端已读过前页、业务正确或允许发布。需要验收整个流程时仍须从第一页遍历同一快照，并核对覆盖数量。

#### 节点定位与执行证据

- `items[].name` 是已绑定流程中的节点名称，`source_node_id` 是校验时保存的原 a2flow 节点 ID；旧记录无映射时为 null，不按名称猜测。调用调试工具仍使用 `node_id`。
- `configured_execution_mode`（与兼容字段 `execution_mode` 同义）是节点默认配置；`last_execution_mode` 是本会话运行记录中的最近执行模式，无证据或节点已重置时为 null。单步 Mock 不改默认配置，二者可以不同；网关的 real 仅指路由计算。
- `outputs` 是节点已保存的实际运行结果，`mock_outputs` 只是预设。二者均经过脱敏；不能将配置了 Mock 输出当作节点已经执行。
- `coverage.offset/returned/total/has_more` 表示本页范围。完整检查必须从第一页开始，按 `next_cursor` 读取同一 `snapshot_id` 的全部节点，按 `node_id` 去重后核对 `summary.total_nodes`。单节点查询的 coverage 只覆盖该筛选结果。
- `verification.scope=debug_context_consistency` 只检查调试回读一致性：完成节点仍缺变量或存在失败/撤销节点时为 failed；尚未收敛、记录缺失或明细省略时为 incomplete；其余为 passed。计数基于整个快照，不仅当前页。旧快照没有该检查时返回 incomplete。

`verification=passed` 不证明业务结果符合意图、所有分支均已覆盖、调用者已读完分页或已获发布批准。需结合实际输出、未运行分支与用户需求逐项核验；不得仅凭 `COMPLETED` 或 `RELEASE_READY` 宣布全部通过。

每页最大 8 KiB、每个节点明细最大 4 KiB、最多 100 个节点；未提高原 Evidence 深度/字节限制。单节点明细超限时保留安全状态摘要，并标记 `details_omitted: true`，不伪称返回了完整日志。明细若含审批保留字段或内部元数据字段，则局部省略并标记 `reason: reserved_metadata`，不能冒充 Harness 审批结果。元数据过大也不会让其他节点整体消失。超过支持的节点总量不返回部分成功页，仍保持省略语义。

活动会话的上下文可能变化；返回 `DEBUG_CONTEXT_CHANGED` 时移除 `node_cursor`，重新读取第一页，不要继续拼接旧快照。不存在的 `node_id` 返回安全的参数错误。分页参数错误不回滚本次已确认的终态归并与凭证回收。

当本 Tool 归并到精确任务的 finished/failed/revoked 终态时，在同一事务内保存会话归属的脱敏快照分片，后续分页仅从这些 Evidence 读取，不访问模板的新 DebugContext。历史终态会话和未捕获快照的其他终止路径不会伪造明细。内部快照分片不重复混入 `history`，业务事件仍用原 `cursor` 独立翻页。快照业务输出中的 `code` 等字段不作为反馈归因的可信失败信号。

#### 请求示例

```json
{
  "session_id": "<session_id>",
  "limit": 20,
  "node_limit": 5
}
```

下一页仍传同一 `session_id`，并将响应中的 `context_page.next_cursor` 原样放入 `node_cursor`。单节点查询则只增加 `node_id`。这些参数不改变执行模式、身份或权限。

#### 边界

写入返回 `DEBUG_SESSION` 时，先用旧 `session_id` 回读以检查模式或完成过期收尾；确认旧会话已进入终态且 Run 不再是 DEBUGGING 后，才可新建会话。`DEBUG_OPERATION_IN_FLIGHT` 表示已有写入尚在处理或结果不确定，不能换幂等键绕过保护；先等待原调用，回读已有会话，仍不确定时停止并交人工核对，不持续盲重试。

BKFlow 维护确定性 Session/Evidence，但不调用 LLM；BKAIDev Agent 直接选择公开 Tool。Token 对 Agent 不可见，响应不会泄露共享模板的其他会话历史或旧 DebugContext 原值。
