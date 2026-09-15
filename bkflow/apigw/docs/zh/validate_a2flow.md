### 租户访问约束

开启多租户时，全租户应用必须通过 `X-Bk-Tenant-Id` 指定本次请求租户；单租户应用可省略该头，使用 JWT 中已认证的应用租户，显式传入时必须一致。本次请求租户必须与资源所属空间租户一致；同一个全租户应用应在各租户分别创建空间。原有应用与空间/模板绑定仍需满足。若 JWT 包含已认证用户，其租户也必须一致。缺少或不匹配时拒绝请求。

应用态接口不要求额外用户身份。SDK 用户态接口仍要求已认证用户，平台管理员和空间管理员同样不能跨租户。关闭多租户模式时保持单租户行为。

### 预校验 a2flow v2 流程定义

#### 接口说明

对 a2flow v2 工作流定义做 dry-run 校验，不创建模板，返回结构化的校验结果。

#### 请求方法

POST

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| a2flow | object | 是 | a2flow v2 JSON 定义 |
| scope_type | string | 否 | scope 类型 |
| scope_value | string | 否 | scope 值 |

#### 响应参数

| 参数 | 类型 | 说明 |
|------|------|------|
| result | bool | 请求是否成功 |
| code | int | 错误码 |
| data.valid | bool | 流程是否合法 |
| data.version | string | a2flow 版本 |
| data.node_count | int | 节点数量 |
| data.plugin_codes | array | 使用的插件 code 列表 |
| errors | array | 校验失败时的错误列表 |

#### 请求示例

```bash
curl -X POST 'http://{host}/space/1/validate_a2flow/' \
  -H 'Content-Type: application/json' \
  -d '{"a2flow": {"version": "2.0", "name": "测试", "nodes": [...]}}'
```

#### 响应示例（成功）

```json
{
    "result": true,
    "code": 0,
    "data": {
        "valid": true,
        "version": "2.0",
        "node_count": 3,
        "plugin_codes": ["job_fast_execute_script", "bk_notify"]
    }
}
```

#### 响应示例（失败）

```json
{
    "result": false,
    "code": 400,
    "errors": [
        {
            "type": "UNKNOWN_PLUGIN",
            "node_id": "n1",
            "field": "code",
            "value": "invalid_plugin",
            "message": "未知的插件 code: invalid_plugin"
        }
    ]
}
```
