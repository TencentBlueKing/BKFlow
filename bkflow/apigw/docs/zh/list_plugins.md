### 查询空间可用插件列表

#### 接口说明

查询指定空间下可用的插件列表，支持按类型过滤、关键词搜索和分页。

#### 请求方法

GET

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 否 | 模糊搜索 code 或 name |
| plugin_type | string | 否 | 按类型过滤，可选值: component, remote_plugin, uniform_api |
| without_detail | bool | 否 | 默认 true，只返回摘要信息；false 返回完整 schema |
| scope_type | string | 否 | scope 类型 |
| scope_id | string | 否 | scope ID |
| limit | int | 否 | 分页大小，默认 100，最大 200 |
| offset | int | 否 | 分页偏移，默认 0 |

#### 响应参数

| 参数 | 类型 | 说明 |
|------|------|------|
| result | bool | 请求是否成功 |
| code | int | 错误码，0 为成功 |
| count | int | 插件总数 |
| data | array | 插件列表 |
| data[].code | string | 插件 code |
| data[].name | string | 插件名称 |
| data[].plugin_type | string | 插件类型 |
| data[].version | string | 插件版本 |
| data[].description | string | 插件描述 |
| data[].group_name | string | 分组名称 |
| data[].inputs | array | 输入参数列表（without_detail=false 时返回） |
| data[].outputs | array | 输出参数列表（without_detail=false 时返回） |

#### 请求示例

```bash
curl -X GET 'http://{host}/space/1/list_plugins/?plugin_type=component&keyword=脚本&limit=10'
```

#### 响应示例

```json
{
    "result": true,
    "code": 0,
    "count": 1,
    "data": [
        {
            "code": "job_fast_execute_script",
            "name": "快速执行脚本",
            "plugin_type": "component",
            "version": "v1.0.0",
            "description": "",
            "group_name": "作业平台(JOB)"
        }
    ]
}
```
