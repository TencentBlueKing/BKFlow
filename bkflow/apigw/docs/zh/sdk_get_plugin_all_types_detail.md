### 资源描述

获取插件配置详情（SDK接口，覆盖内置/远程/统一API三类插件）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称         | 参数类型   | 必须 | 参数说明                                                       |
|--------------|--------|----|------------------------------------------------------------|
| BKFLOW-TOKEN | string | 是  | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 接口申请。该 token 用于验证用户对指定空间的访问权限 |

### 接口参数

| 字段          | 类型      | 必选 | 描述                                                                                |
|-------------|---------|----|-----------------------------------------------------------------------------------|
| space_id    | string  | 是  | 空间ID                                                                              |
| template_id | string  | 是  | 模板ID                                                                              |
| plugin_type | string  | 是  | 插件类型，取值：component（内置插件）/ remote_plugin（远程插件）/ uniform_api（统一API插件） |
| plugin_code | string  | 是  | 插件code                                                                            |
| plugin_version | string  | 是  | 插件版本                                                                              |
| source_key  | string  | 否  | 统一API插件来源标识；plugin_type 为 uniform_api 时必填                                   |
| scope_type  | string  | 否  | 业务范围类型                                                                            |
| scope_value | string  | 否  | 业务范围值（scope_type 为 biz / cmdb_biz 时需为整数）                                     |

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "space_id": "1",
    "template_id": "10",
    "plugin_type": "component",
    "plugin_code": "bk_display",
    "plugin_version": "v1.0"
}
```

### 返回结果示例

```json
{
    "result": true,
    "message": "",
    "data": {
        "plugin_type": "component",
        "plugin_code": "bk_display",
        "plugin_version": "v1.0",
        "source_key": "bkflow",
        "plugin_source": "builtin",
        "protocol": "native",
        "wrapper_version": null,
        "name": "消息展示",
        "description": "本插件为仅用于消息展示的空节点",
        "inputs": [
            {
                "key": "bk_display_message",
                "name": "展示内容",
                "type": "string",
                "description": "",
                "required": true,
                "schema": {
                    "type": "string",
                    "description": "展示内容",
                    "enum": []
                }
            }
        ],
        "outputs": [
            {
                "key": "_result",
                "name": "执行结果",
                "type": "boolean",
                "description": "",
                "schema": {
                    "type": "boolean",
                    "description": "执行结果的布尔值，True or False",
                    "enum": []
                }
            },
            {
                "key": "_loop",
                "name": "循环次数",
                "type": "int",
                "description": "",
                "schema": {
                    "type": "int",
                    "description": "循环执行次数",
                    "enum": []
                }
            },
            {
                "key": "_inner_loop",
                "name": "当前流程循环次数",
                "type": "int",
                "description": "",
                "schema": {
                    "type": "int",
                    "description": "在当前流程节点循环执行次数，由父流程重新进入时会重置（仅支持新版引擎）",
                    "enum": []
                }
            }
        ],
        "credentials": [],
        "forms": {
            "input": {
                "type": "component_js",
                "key": "bk_display",
                "data": "/static/components/display/v1_0.js",
                "is_embedded": false,
                "base": ""
            },
            "output": null
        },
        "form_schema": null,
        "form_context": {
            "project": null,
            "biz_cc_id": null,
            "site_url": "/",
            "component": null,
            "variable": null,
            "template": null,
            "instance": null,
            "bk_plugin_api_host": {}
        },
        "execution_kind": "component",
        "url": null,
        "methods": [],
        "response_data_path": null,
        "polling": {},
        "callback": {},
        "credential_key": null
    }
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |

#### data 字段说明

| 字段                 | 类型       | 描述                                                        |
|--------------------|----------|-----------------------------------------------------------|
| plugin_type        | string   | 插件类型：component（内置）/ remote_plugin（远程）/ uniform_api（统一API） |
| plugin_code        | string   | 插件code                                                    |
| plugin_version     | string   | 插件版本                                                      |
| source_key         | string   | 统一API来源标识；内置/远程插件可能为空                                     |
| plugin_source      | string   | 插件来源                                                      |
| protocol           | string   | 协议                                                        |
| wrapper_version    | string   | 包装版本                                                      |
| name               | string   | 插件名称                                                      |
| description        | string   | 插件描述                                                      |
| inputs             | list     | 输入参数定义                                                    |
| outputs            | list     | 输出参数定义                                                    |
| credentials        | list     | 凭证信息列表                                                    |
| forms              | dict     | 表单定义                                                      |
| form_schema        | dict     | 表单 schema                                                 |
| form_context       | dict     | 表单上下文（project / biz_cc_id / site_url 等）                   |
| execution_kind     | string   | 执行类型（如 component）                                         |
| url                | string   | 远程插件地址（内置插件为 null）                                        |
| methods            | list     | 远程插件支持的 HTTP 方法列表（内置插件为空）                                 |
| response_data_path | string   | 响应数据提取路径                                                  |
| polling            | dict     | 轮询配置                                                      |
| callback           | dict     | 回调配置                                                      |
| credential_key     | string   | 凭证标识                                                      |

说明：
- 该接口通过 plugin_type 区分三类插件（component / remote_plugin / uniform_api），返回统一结构的原生表单详情；
- plugin_type 为 uniform_api 时必须传 source_key，否则返回参数校验错误；
