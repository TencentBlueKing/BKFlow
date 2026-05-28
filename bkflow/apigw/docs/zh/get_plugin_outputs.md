### 资源描述

获取插件输出信息

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

#### 接口参数

| 字段             | 类型       | 必选    | 描述                     |
|----------------|----------|-------|------------------------|
| plugin_id      | string   | 是     | 插件ID，唯一标识一个插件类型        |
| plugin_version | string   | 否     | 插件版本                   |

### 请求参数示例

```json
{
    "plugin_id": "bk_plugin_example"
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "output": [
            {
                "name": "执行结果",
                "key": "_result",
                "type": "boolean",
                "schema": {
                    "type": "boolean",
                    "description": "执行结果的布尔值，True or False",
                    "enum": []
                }
            },
            {
                "name": "循环次数",
                "key": "_loop",
                "type": "int",
                "schema": {
                    "type": "int",
                    "description": "循环执行次数",
                    "enum": []
                }
            },
            {
                "name": "当前流程循环次数",
                "key": "_inner_loop",
                "type": "int",
                "schema": {
                    "type": "int",
                    "description": "在当前流程节点循环执行次数，由父流程重新进入时会重置（仅支持新版引擎）",
                    "enum": []
                }
            }
        ],
        "form": null,
        "output_form": null,
        "desc": "这是一个示例插件",
        "form_is_embedded": false,
        "group_name": "蓝鲸服务",
        "group_icon": "",
        "name": "示例插件",
        "base": "",
        "code": "test_api",
        "version": "v1.0.0",
        "is_default_version": false
    },
    "code": 0,
    "message": ""
}
```

### 返回结果参数说明

| 字段        | 类型           | 描述                    |
|-----------|--------------|-----------------------|
| result    | bool         | 返回结果，true为成功，false为失败 |
| code      | int          | 返回码，0表示成功，其他值表示失败     |
| message   | string       | 成功/错误信息               |
| data      | object/array | 插件数据                  |

#### data[item]

| 字段               | 类型      | 描述               |
|------------------|---------|------------------|
| code             |  string | 插件代码             |
| version          | string  | 插件版本             |
| name             | string  | 插件名称             |
| group_name       | string  | 插件分组名称           |
| group_icon       | string  | 插件分组图标           |
| desc             | string  | 插件描述             |
| form             | object  | 插件输入表单配置         |
| output           | object  | 插件输出配置           |
| output_form      | object  | 插件输出表单配置         |
| form_is_embedded | bool    | 表单是否嵌入           |
| base             | object  | 基础配置             |
