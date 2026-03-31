### 查询单个插件参数 Schema

#### 接口说明

查询指定插件的完整参数 schema（inputs 和 outputs）。

#### 请求方法

GET

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 插件 code |
| version | string | 否 | 插件版本，不传取最新 |
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
| data.inputs | array | 输入参数列表 |
| data.inputs[].key | string | 参数标识 |
| data.inputs[].name | string | 参数名称 |
| data.inputs[].type | string | 参数类型 |
| data.inputs[].required | bool | 是否必填 |
| data.inputs[].description | string | 参数描述 |
| data.outputs | array | 输出参数列表 |

#### 请求示例

```bash
curl -X GET 'http://{host}/space/1/get_plugin_schema/?code=job_fast_execute_script&plugin_type=component'
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
