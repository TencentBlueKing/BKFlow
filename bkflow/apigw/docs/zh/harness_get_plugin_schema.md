### 获取精确能力 Schema

#### 接口说明

按 `capability_ref` 在可信空间内加载完整 Schema，并核对精确版本与 `schema_hash`。MCP-visible Tool 名为 `get_plugin_schema`。

业务插件 Schema 只用于生成和校验，不代表 Agent 获得直接执行权限。

#### 可信字段与不可信字段

身份、空间、Scope 和环境只能来自网关与服务端部署绑定。禁止用裸 plugin code 代替 `capability_ref`。

#### 请求方法

POST `/space/{space_id}/harness/get_plugin_schema/`

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| capability_ref | string | 是 | 不透明能力引用 |
| expected_schema_hash | string | 否 | 乐观哈希，漂移时返回 SCHEMA_DRIFT |

#### 请求示例

```json
{
  "capability_ref": "cap_v1_example_not_a_secret"
}
```

#### 返回结果

成功时 `artifact_refs` 含 `resolved_schema`：`capability_ref`、`resolved_version`、`schema_hash`、inputs/outputs。漂移、越权或不存在时返回类型化错误，需要重新搜索并选择。

#### 响应示例

```json
{
  "ok": true,
  "run_id": null,
  "revision_id": null,
  "plan_hash": null,
  "status": "PLANNING",
  "summary": "schema resolved",
  "artifact_refs": [
    {
      "type": "resolved_schema",
      "value": {
        "capability_ref": "cap_v1_example_not_a_secret",
        "resolved_version": "1.0.0",
        "schema_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "inputs": {"type": "object", "properties": {"host": {"type": "string"}}},
        "outputs": {"type": "object"}
      }
    }
  ],
  "errors": [],
  "next_actions": ["validate_workflow"],
  "correlation_id": "00000000-0000-0000-0000-000000000099"
}
```
