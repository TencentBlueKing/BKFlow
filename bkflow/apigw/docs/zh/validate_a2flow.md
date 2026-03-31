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
