### 创建或更新流程草稿

#### 接口说明

只接受已经校验通过的 `run_id`、`revision_id` 和精确 `plan_hash`。首次有效修订创建 Harness 管理的模板草稿，后续有效修订原位更新同一模板。MCP-visible Tool 名为 `create_workflow_draft`。

P0 只能到达 `DRAFT_READY`。`auto_release` 即使传入 true 也会被忽略。禁止发布、创建任务和真实执行。

创建前会重新 Resolve Schema、复算 `plan_hash`，并比较 validator/converter fingerprint；变化时返回 `VALIDATION_STALE`，必须重新 `validate_workflow`。

#### 请求方法

POST `/space/{space_id}/harness/create_workflow_draft/`

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| run_id | string | 是 | 已有生成运行 |
| revision_id | string | 是 | 已接受修订 |
| plan_hash / expected_plan_hash | string | 是 | 必须与存储修订一致 |
| idempotency_key | string | 是 | 重试返回同一模板 |

#### 请求示例

```json
{
  "run_id": "00000000-0000-0000-0000-000000000001",
  "revision_id": "00000000-0000-0000-0000-000000000002",
  "expected_plan_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "idempotency_key": "draft-demo-1"
}
```

#### 返回结果

成功状态为 `DRAFT_READY`。`artifact_refs` 只含 `template_id` 与草稿快照引用。相同幂等键重试返回同一资源。

#### 响应示例

```json
{
  "ok": true,
  "run_id": "00000000-0000-0000-0000-000000000001",
  "revision_id": "00000000-0000-0000-0000-000000000002",
  "plan_hash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "status": "DRAFT_READY",
  "summary": "draft ready",
  "artifact_refs": [
    {"type": "template_id", "value": 1},
    {"type": "snapshot_ref", "value": "draft"}
  ],
  "errors": [],
  "next_actions": [],
  "correlation_id": "00000000-0000-0000-0000-000000000099"
}
```
