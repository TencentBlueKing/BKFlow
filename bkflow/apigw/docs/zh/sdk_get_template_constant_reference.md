### 资源描述

变量引用统计（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 接口参数

| 字段          | 类型   | 必选 | 描述                    |
|-------------|------|----|-----------------------|
| pipeline_tree | dict | 是  | 流程树，包含 constants 字段 |

### pipeline_tree 说明

pipeline_tree 需要包含以下结构：
- `constants`: 流程中定义的全局变量
- `activities`: 流程中的活动节点
- `gateways`: 流程中的网关节点

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "pipeline_tree": {
        "constants": {
            "var1": {
                "key": "var1",
                "name": "变量1",
                "value": "value1"
            }
        },
        "activities": {},
        "gateways": {},
        "flows": {}
    }
}
```

### 返回结果示例

```json
{
    "defined": {
        "var1": {
            "activities": ["node1", "node2"],
            "conditions": [],
            "constants": []
        }
    },
    "nodefined": {
        "${undefined_var}": {
            "activities": ["node3"],
            "conditions": [],
            "constants": []
        }
    }
}
```

### 返回结果参数说明

| 字段       | 类型   | 描述                    |
|----------|------|-----------------------|
| defined  | dict | 已定义的变量及其引用位置          |
| nodefined | dict | 未定义的变量及其引用位置          |

#### defined[node_key] 和 nodefined[node_key] 字段说明

| 字段        | 类型     | 描述                    |
|-----------|--------|-----------------------|
| activities | list | 引用该变量的活动节点ID列表        |
| conditions | list | 引用该变量的条件节点ID列表        |
| constants  | list | 引用该变量的其他常量ID列表        |


