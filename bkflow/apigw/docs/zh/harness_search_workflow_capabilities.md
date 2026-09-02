### 检索流程构建能力

#### 接口说明

在已授权空间内检索用于构建流程的第三方插件/API 能力摘要。返回轻量卡片，不含完整 Schema。MCP-visible Tool 名为 `search_workflow_capabilities`。

P0 只暴露 4 个控制 Tool。本接口不是业务插件执行入口。

#### 可信字段与不可信字段

- 可信：APIGW JWT 应用、JWT 用户、路由 `space_id`、服务端非公开 Harness 部署绑定。
- 不可信：请求体中的 `platform_key`、`platform_app`、`actor`、`space_id`、`scope_*`、`target_environment`。这些字段会被忽略，不能作为授权依据。

#### 请求方法

POST `/space/{space_id}/harness/search_workflow_capabilities/`

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 能力检索词 |
| top_k | int | 否 | 默认 10，最大 20 |
| client_context.conversation_ref | string | 否 | 不透明会话引用，禁止放密钥 |
| client_context.agent_release | string | 否 | Agent 发布版本 |

#### 请求示例

```json
{
  "query": "重启服务",
  "top_k": 10
}
```

#### 返回结果

统一 Envelope：`ok`、`run_id`、`revision_id`、`plan_hash`、`status`、`summary`、`artifact_refs`、`errors`、`next_actions`、`correlation_id`。

`artifact_refs` 中的 `capability_card` 只含 `capability_ref`、名称、摘要、精确版本、`schema_hash`、风险和匹配词，不含 inputs/outputs 全量 Schema。

#### 响应示例

```json
{
  "ok": true,
  "run_id": null,
  "revision_id": null,
  "plan_hash": null,
  "status": "INTENT_CAPTURED",
  "summary": "found 1 capability card",
  "artifact_refs": [
    {
      "type": "capability_card",
      "value": {
        "capability_ref": "cap_v1_example_not_a_secret",
        "name": "重启服务",
        "summary": "重启指定主机上的服务",
        "resolved_version": "1.0.0",
        "schema_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "risk_level": "low",
        "matched_terms": ["重启"]
      }
    }
  ],
  "errors": [],
  "next_actions": ["get_plugin_schema"],
  "correlation_id": "00000000-0000-0000-0000-000000000099"
}
```
