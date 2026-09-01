### 校验流程并生成不可变修订

#### 接口说明

对 a2flow V2 做确定性校验：解析能力、核对绑定、校验输入、转换 pipeline tree、计算 `plan_hash`，成功则创建不可变 Revision。首次调用隐式创建 `HarnessRun`。MCP-visible Tool 名为 `validate_workflow`。

失败可以留下 run 级报告，但不能产生有效修订或草稿。修复必须生成新 Revision。

#### 请求方法

POST `/space/{space_id}/harness/validate_workflow/`

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| a2flow | object | 是 | a2flow V2 对象，不要字符串化 |
| bindings | list | 是 | 每个 Activity 节点的精确绑定 |
| idempotency_key | string | 是 | 写操作幂等键 |
| run_id | string | 否 | 首次可空，后续回传 |
| expected_plan_hash | string | 否 | 对上一版修订的乐观并发断言 |
| intent | object | 否 | 结构化意图，不进入 plan_hash 的对话措辞 |

每个 binding 必须包含 `node_id`、`capability_ref`、`schema_hash`，可选 `credential_ref`（只存引用，不传明文）。

#### 请求示例

```json
{
  "idempotency_key": "validate-demo-1",
  "a2flow": {
    "version": "2.0",
    "name": "restart-demo",
    "nodes": [
      {
        "id": "node_1",
        "name": "重启服务",
        "code": "demo_restart_service",
        "data": {"host": "example-host"},
        "next": "end"
      }
    ]
  },
  "bindings": [
    {
      "node_id": "node_1",
      "capability_ref": "cap_v1_example_not_a_secret",
      "schema_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "credential_ref": null
    }
  ]
}
```

#### 返回结果

统一 Envelope。成功状态为 `VALIDATING`，带 `revision_id` 与服务端计算的 `plan_hash`。错误含 `category`、`code`、`path`、`repairable`、`retryable`。

#### 响应示例

```json
{
  "ok": true,
  "run_id": "00000000-0000-0000-0000-000000000001",
  "revision_id": "00000000-0000-0000-0000-000000000002",
  "plan_hash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "status": "VALIDATING",
  "summary": "revision accepted",
  "artifact_refs": [
    {"type": "revision", "value": "00000000-0000-0000-0000-000000000002"}
  ],
  "errors": [],
  "next_actions": ["create_workflow_draft"],
  "correlation_id": "00000000-0000-0000-0000-000000000099"
}
```
