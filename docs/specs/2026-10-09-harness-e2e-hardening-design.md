# Harness E2E 修复与接入检查

## 本次边界

BKAIDev Agent 负责 LLM 推理和工具选择，BKFlow Harness 提供确定性能力，不调用 LLM。维持现有 15 个 MCP Tool：没有新增协议查询 Tool，也没有改成只调用一个总入口。业务知识库与编排协议分离；忽略知识库仍可完成检索能力、读取插件 Schema、校验、创建草稿。

## 修复设计

| 发现 | 本次处理 | 不做的事情 |
|---|---|---|
| Agent 把插件 code 当节点 type，发送画布结构 | validate_workflow 网关 Schema 展开 a2flow 字段及合法结构示例；增加静态错误码与字段路径 | 不猜测、自动改写节点身份 |
| 修复时误删 credential_ref | 缺少字段明确提示，无凭证仍传 null；绑定数量不匹配单独诊断 | 不向模型暴露凭证 |
| 复杂调试上下文整体超限 | 兼容 context，补 context_page 摘要、节点分页与单节点读取 | 不提高原 Evidence 安全预算 |
| 调试结束后无法继续翻页 | 在精确任务终态归并事务中持久化脱敏快照分片，终态只读本 Session 的 Evidence | 不复用模板后续调试上下文；不伪造旧会话快照 |
| JSON 配置被文本必填阻断 | Admin 条件表单；保存前验证 Harness 可信绑定及存储类型 | 不改模型、不新增迁移、不自动开门禁 |

节点页使用会话 id + 脱敏快照哈希 + 偏移量构造游标。游标不是权限，读取始终先验证会话归属。实时状态变化则要求从第一页重新读，避免将多个时刻的节点结果拼成一个快照。单节点明细超限显式标记，不妨碍其他节点读取。持久化分片与终态转换原子提交，并从普通事件历史分页中排除，避免重复占用 Agent 上下文。

摘要状态直接来自既有 DebugNodeState 定义，包含 waiting/paused。响应预算包含最终网关包装深度；审批保留字段和内部元数据仅导致对应节点明细/上下文的安全省略，不绕过网关保护。分页游标过期不会撤销已经观测到的终态；持久化分片失败则回滚整次终态事务。快照记录仅用于展示，不作为反馈系统的 typed failure evidence，避免业务结果中的 code 字段污染知识归因。

## 环境接入预检（配置人员）

1. **确认身份**：读取目标 BKFlow Space 的 `app_code`，与 BKAIDev Agent 实际用于 MCP 的应用身份一致。不能用显示名称替代应用标识。`HARNESS_APP_SPACE_FORBIDDEN` 应修正应用/空间选择，不应删除权限检查。
2. **确认网关**：MCP 指向本次部署的 backend/stage；应用鉴权、用户鉴权、资源授权保持开启；当前应用已获所需 MCP 资源权限，OAuth 用户已完成授权。OAuth 不替代可信部署绑定。
3. **录入可信绑定**：由管理员在目标 Space 的 `harness_deployment` 中选择 JSON 类型，填写下例所有字段。`text_value` 留空，无需 `{}` 占位。该配置不是模型入参，不允许 Agent 指定应用、用户、Scope 或策略。
4. **分层开门禁**：最小草稿 E2E 只开启 `harness_enabled`。需要 Mock 调试时另行确认开启 `harness_debug_enabled`。真实单步、真实全局调试、发布、执行开关均独立审批，保持默认关闭。本清单不授予开启权限。
5. **核对可用能力**：Search 的引用原样传 Schema Tool；每个 Activity 保留对应 binding，包括无凭证时的 null。不要让模型从引用中解码、拼接身份。
6. **分级验收**：协议样例校验 → 草稿画布核对 → Agent 自主四工具闭环 → 单步 Mock → 全局 Mock → 复杂结果多页读取。真实操作须另有明确授权。

可信绑定示例（仅示意，必须由接入方确定真实值）：

```json
{
  "platform_key": "bkaidev",
  "allowed_scope_types": [],
  "scope_type": null,
  "scope_value": null,
  "target_environment": "stag",
  "risk_policy_version": "your-approved-policy-version",
  "mcp_contract_version": "1.4.0"
}
```

有 Scope 的平台应将 `scope_type` 加入 `allowed_scope_types` 并设置匹配的 `scope_value`；不能用无 Scope 示例规避资源范围。空对象不是有效部署绑定。表单校验仅校验配置结构，不代表资源授权、用户权限或下游连通性已验证。

## 发布后待验收

代码和网关资源/文档必须成套更新，BKAIDev 侧刷新 MCP Tool Schema 缓存后确认可见展开的 a2flow 和三个节点读取参数。新建对话，避免旧提示和旧 Schema 缓存影响结果；先执行仅草稿测试，再在授权范围内执行 Mock 调试。

本地回归不代表云端验收。BKAIDev 的 ask_user_question 回传表现仍需平台原始消息证据，不能归为已确认平台缺陷；知识库 Embedding 授权按用户要求暂不处理。
