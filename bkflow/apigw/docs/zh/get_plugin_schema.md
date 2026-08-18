### 查询单个插件参数 Schema

#### 接口说明

查询指定插件的完整参数 schema（inputs 和 outputs）。

查询 `uniform_api v4.0.0` 开放插件时，插件来源必须已对当前空间准入，且插件必须已在当前空间开启。存量 V2/V3 仍按原远端 `meta_url` 查询。

#### 请求方法

GET

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 否 | 插件 code，与 `plugin_id` 至少传一个 |
| plugin_id | string | 否 | 开放插件 ID，传入后优先作为 `code` 使用，便于查询 `uniform_api v4.0.0` 开放插件 |
| version | string | 否 | 插件版本，不传取最新 |
| plugin_version | string | 否 | 开放插件业务版本，传入后优先作为 `version` 使用 |
| plugin_source | string | 否 | 开放插件来源类型，查询 V4 开放插件时可消歧 |
| source_key | string | 否 | 开放插件来源标识，同 `plugin_id` 存在多个来源时用于消歧 |
| plugin_type | string | 否 | 消歧用，可选值: component, remote_plugin, uniform_api |
| scope_type | string | 否 | scope 类型 |
| scope_id | string | 否 | scope ID |

#### 响应参数

| 参数 | 类型 | 说明 |
|------|------|------|
| result | bool | 请求是否成功 |
| code | int | 错误码，0 为成功 |
| data | object | 插件详细信息 |
| data.code | string | 插件 code |
| data.name | string | 插件名称 |
| data.plugin_type | string | 插件类型 |
| data.version | string | 插件版本 |
| data.description | string | 插件描述 |
| data.plugin_source | string | 开放插件来源类型，仅 `uniform_api v4.0.0` 返回，如 `builtin` / `third_party` |
| data.plugin_code | string | 来源侧插件编码，仅 `uniform_api v4.0.0` 返回 |
| data.wrapper_version | string | BKFlow 包装器版本，仅 `uniform_api v4.0.0` 返回 |
| data.inputs | array | 输入参数列表 |
| data.inputs[].key | string | 参数标识 |
| data.inputs[].name | string | 参数名称 |
| data.inputs[].type | string | 参数类型 |
| data.inputs[].required | bool | 是否必填 |
| data.inputs[].description | string | 参数描述 |
| data.outputs | array | 输出参数列表 |

`uniform_api v4.0.0` 开放插件若来源未准入、插件不可用或插件未开启，将返回失败信息，不返回 schema。存量 V2/V3 不套用这套校验。

#### 请求示例

```bash
curl -X GET 'http://{host}/space/1/get_plugin_schema/?code=job_fast_execute_script&plugin_type=component'
```

开放插件示例：

```bash
curl -X GET 'http://{host}/space/1/get_plugin_schema/?plugin_id=open_plugin_001&plugin_version=1.2.0&plugin_type=uniform_api&source_key=source-b'
```

#### 响应示例

```json
{
    "result": true,
    "code": 0,
    "data": {
        "code": "job_fast_execute_script",
        "name": "快速执行脚本",
        "plugin_type": "component",
        "version": "v1.0.0",
        "description": "执行脚本",
        "inputs": [
            {
                "key": "script_content",
                "name": "脚本内容",
                "type": "string",
                "required": true,
                "description": ""
            }
        ],
        "outputs": [
            {
                "key": "_result",
                "name": "执行结果",
                "type": "bool",
                "description": ""
            }
        ]
    }
}
```

开放插件响应示例：

```json
{
    "result": true,
    "code": 0,
    "data": {
        "code": "open_plugin_001",
        "name": "JOB 执行作业",
        "plugin_type": "uniform_api",
        "version": "1.2.0",
        "plugin_source": "builtin",
        "plugin_code": "job_execute_task",
        "wrapper_version": "v4.0.0",
        "description": "执行标准运维作业",
        "inputs": [],
        "outputs": []
    }
}
```
