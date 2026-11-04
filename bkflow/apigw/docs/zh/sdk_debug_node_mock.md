### 租户访问约束

开启多租户时，全租户应用必须通过 `X-Bk-Tenant-Id` 指定本次请求租户；单租户应用可省略该头，使用 JWT 中已认证的应用租户，显式传入时必须一致。本次请求租户必须与资源所属空间租户一致；同一个全租户应用应在各租户分别创建空间。原有应用与空间/模板绑定仍需满足。若 JWT 包含已认证用户，其租户也必须一致。缺少或不匹配时拒绝请求。

应用态接口不要求额外用户身份。SDK 用户态接口仍要求已认证用户，平台管理员和空间管理员同样不能跨租户。关闭多租户模式时保持单租户行为。

### 资源描述

配置流程调试节点 mock（SDK接口）

### HTTP Header 参数说明

| 参数名称         | 参数类型 | 必须 | 参数说明 |
|--------------| --- | --- | --- |
| BKFLOW-TOKEN | string | 是 | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 申请，权限类型为 `MOCK` |

### 接口参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| space_id | int | 是 | 空间ID |
| template_id | int | 是 | 流程模板ID |
| node_id | string | 是 | 节点ID |
| enable | bool | 否 | 是否开启 mock；从 mock 切回 real 时重置本节点结果并删除其绑定的产出变量 |
| mock_result | string | 否 | mock 结果，`success` 或 `fail` |
| mock_outputs | dict | 否 | mock 输出 |
| mock_error | string | 否 | mock 失败信息 |

分支网关和条件并行网关不支持 Mock。对这两类节点调用本接口会返回“条件网关不支持 Mock”。

### 取消 Mock

- `enable=false` 且当前节点为 `mock` 时，切回 `real`，同时将当前节点态和 `debug_snapshot.nodes` 中对应结果重置为 `not_run`，清空执行输入、输出、耗时、错误及日志引用。该结果行的 `execution_mode` 同步为 `real`，保留配置输入及 Mock 预设。
- 从 `global_vars` 删除当前草稿中由该节点绑定的全部产出变量，包括不在最新 `mock_outputs` 中的旧值；不恢复上一次全局调试的值。其他节点的结果、产出变量以及无关的手动输入保持不变，不级联重置下游。
- 未开启 Mock 时重复关闭不会再次清理。调试运行中禁止配置或取消 Mock；取消的模式、结果和变量变更在同一事务内完成。没有历史快照时不补造快照。
- 下游默认真实单步沿用依赖检查：缺少这些变量时，`debug_context` 返回 `can_step=false` 和 `missing_vars`，执行请求返回“依赖未满足”。上游重新产出后恢复可执行。显式 `input_overrides` 仍沿用原有覆盖规则，普通单步不要自动携带旧覆盖值。
- 保存成功的 Mock 预设仍会立即回写对应全局变量；仅取消 Mock 时触发上述清理。前端取消成功后应重新读取 `debug_context`，刷新节点结果和下游可执行状态。
- 无需数据库迁移或存量回填，仅在取消操作时生效。滚动发布时，所有 Interface 实例更新完成后行为才一致。

### 请求参数示例

```json
{
  "space_id": 1,
  "template_id": 100,
  "node_id": "node1",
  "enable": true,
  "mock_result": "success",
  "mock_outputs": {
    "k": "v"
  }
}
```

取消时传入 `{"space_id": 1, "template_id": 100, "node_id": "node1", "enable": false}`。

### 返回数据说明

| data 字段 | 类型 | 描述 |
| --- | --- | --- |
| node_id | string | 节点 ID |
| execution_mode | string | 当前模式，取消成功后为 `real` |
| updated_global_vars | dict | 操作后的完整调试全局变量，已删除的产出键不再出现 |
