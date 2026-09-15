### 租户访问约束

开启多租户时，全租户应用必须通过 `X-Bk-Tenant-Id` 指定本次请求租户；单租户应用可省略该头，使用 JWT 中已认证的应用租户，显式传入时必须一致。本次请求租户必须与资源所属空间租户一致；同一个全租户应用应在各租户分别创建空间。原有应用与空间/模板绑定仍需满足。若 JWT 包含已认证用户，其租户也必须一致。缺少或不匹配时拒绝请求。

应用态接口不要求额外用户身份。SDK 用户态接口仍要求已认证用户，平台管理员和空间管理员同样不能跨租户。关闭多租户模式时保持单租户行为。

### 资源描述

配置流程调试节点 mock（SDK接口）

### HTTP Header 参数说明

| 参数名称 | 参数类型 | 必须 | 参数说明 |
| --- | --- | --- | --- |
| HTTP_BKFLOW_TOKEN | string | 是 | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 申请，权限类型为 `MOCK` |

### 接口参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| space_id | int | 是 | 空间ID |
| template_id | int | 是 | 流程模板ID |
| node_id | string | 是 | 节点ID |
| enable | bool | 否 | 是否开启 mock |
| mock_result | string | 否 | mock 结果，`success` 或 `fail` |
| mock_outputs | dict | 否 | mock 输出 |
| mock_error | string | 否 | mock 失败信息 |

分支网关和条件并行网关不支持 Mock。对这两类节点调用本接口会返回“条件网关不支持 Mock”。

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
