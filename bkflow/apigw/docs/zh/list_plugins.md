### 查询空间可用插件列表

#### 接口说明

查询指定空间下可用的插件列表，支持按类型过滤、关键词搜索和分页。

当 `plugin_type=uniform_api` 时：`wrapper_version=v4.0.0` 的开放插件只返回已对当前空间准入且已开启的目录项；存量 V2/V3 API 插件仍按原远端 `meta_url` 列表返回，不受目录开启状态影响。

#### 请求方法

GET

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 否 | 模糊搜索 code 或 name |
| plugin_type | string | 否 | 按类型过滤，可选值: component, remote_plugin, uniform_api |
| plugin_source | string | 否 | 开放插件来源类型，仅过滤 `uniform_api v4.0.0` 目录项 |
| with_detail | bool | 否 | 默认 false，只返回摘要信息；true 返回完整 schema |
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
| data[].inputs | array | 输入参数列表（with_detail=true 时返回） |
| data[].outputs | array | 输出参数列表（with_detail=true 时返回） |

`uniform_api v4.0.0` 开放插件额外受两层准入控制：来源必须已对当前空间准入，插件必须已在当前空间开启；未准入或未开启的 V4 插件不会出现在列表中。存量 V2/V3 不走这套开关。

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
