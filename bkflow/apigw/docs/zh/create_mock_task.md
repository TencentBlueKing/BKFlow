### 资源描述

创建 mock 任务

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |


#### 接口参数

| 字段          | 类型     | 必选 | 描述                                                                                                                                                              |
|-------------|--------|----|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| template_id | int    | 是  | 模板id                                                                                                                                                            |
| name        | string | 是  | 任务名                                                                                                                                                             |
| creator     | string | 是  | 创建者                                                                                                                                                             |
| description | string | 否  | 描述                                                                                                                                                              |
| constants   | dict   | 否  | 任务启动参数                                                                                                                                                          |
| credentials | dict   | 否  | 凭证字典，用于传递API调用所需的凭证信息，详见下方说明                                                                                                                              |
| mock_data   | dict   | 否  | mock 数据，包含 nodes（mock 任务使用 mock 执行的节点)，outputs（可选参数，mock 执行对应节点的节点输出)，mock_data_ids（mock 执行对应节点使用的 mock 数据 id，如果 outputs 没有传参，则会自动将创建任务时对应的 mock 数据 作为 outputs） |

### credentials 参数说明

`credentials` 参数用于在创建任务时传递 API 调用所需的凭证信息。该参数是一个字典类型，字典的 key 为凭证的标识名称，value 为 base64 编码的 JSON 字符串。

**凭证格式要求：**
- key：凭证的标识名称
- value：base64 编码的 JSON 字符串，解码后必须是一个包含 `bk_app_code` 和 `bk_app_secret` 字段的字典对象

**对于API插件凭证使用优先级：**
1. 如果任务创建时传入了 `credentials` 参数，且凭证 key 与空间配置中的 `api_gateway_credential_name` 匹配，则优先使用用户传入的凭证
2. 如果用户未提供凭证或凭证 key 不匹配，则使用空间配置中的 `credential` 配置

**凭证示例：**
```json
{
    "credentials": {
        "my_credential": "eyJia19hcHBfY29kZSI6ICJteV9hcHAiLCAiYmtfYXBwX3NlY3JldCI6ICJteV9zZWNyZXQifQ=="
    }
}
```

其中，base64 解码后的内容为：
```json
{
    "bk_app_code": "my_app",
    "bk_app_secret": "my_secret"
}
```

**注意事项：**
- 凭证信息会被存储在任务的 `extra_info.custom_context.credentials` 中，供流程执行时使用
- 凭证信息仅用于统一 API 插件（uniform_api）的 API 调用认证
- 如果空间配置中设置了 `api_gateway_credential_name` 为字典格式（支持按 scope 配置不同凭证），系统会根据任务的 scope_type 和 scope_value 匹配对应的凭证名称

### pipeline_tree 版本说明

创建 mock 任务时，系统会自动选择使用的流程版本：

1. **优先使用草稿版本**：如果当前模板存在草稿版本的流程（`draft=True`），则使用草稿版本的 `pipeline_tree` 创建调试任务
2. **使用最新发布版本**：如果当前模板没有草稿版本，则使用最新发布版本的 `pipeline_tree` 创建调试任务

这样可以确保在调试时优先使用最新的未发布修改，如果没有草稿版本则使用已发布的稳定版本。

### 请求参数示例

基础请求参数示例：
```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "空间名",
    "template_id": 4,
    "creator": "创建者",
    "mock_data": {
        "nodes": [
            "nd7927122ef6310eb309c2c8d3f70c23"
        ],
        "outputs": {
            "nd7927122ef6310eb309c2c8d3f70c23": {
                "callback_data": "abc"
            }
        },
        "mock_data_ids": {
            "nd7927122ef6310eb309c2c8d3f70c23": 1
        }
    }
}
```

带凭证的请求参数示例：
```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "空间名",
    "template_id": 4,
    "creator": "创建者",
    "credentials": {
        "my_credential": "eyJia19hcHBfY29kZSI6ICJteV9hcHAiLCAiYmtfYXBwX3NlY3JldCI6ICJteV9zZWNyZXQifQ=="
    },
    "mock_data": {
        "nodes": [
            "nd7927122ef6310eb309c2c8d3f70c23"
        ],
        "outputs": {
            "nd7927122ef6310eb309c2c8d3f70c23": {
                "callback_data": "abc"
            }
        },
        "mock_data_ids": {
            "nd7927122ef6310eb309c2c8d3f70c23": 1
        }
    }
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": 10,
        "space_id": 1,
        "scope_type": null,
        "scope_value": null,
        "instance_id": "6e15e7cf27ab3129878cdd9b95fff006",
        "template_id": 4,
        "name": "default_taskflow_instance",
        "creator": "",
        "create_time": "2023-04-23T21:10:06.826644+08:00",
        "create_method": "MOCK",
        "executor": "",
        "start_time": null,
        "finish_time": null,
        "description": "",
        "is_started": false,
        "is_finished": false,
        "is_revoked": false,
        "is_deleted": false,
        "is_expired": false,
        "snapshot_id": 3,
        "execution_snapshot_id": 8,
        "tree_info_id": null,
        "extra_info": {}
        },
    "code": "0",
    "message": ""
}

```
### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |

#### data[item]

| 字段                    | 类型     | 描述       |
|-----------------------|--------|----------|
| id                    | int    | 任务ID     |
| space_id              | int    | 空间ID     |
| scope_type            | string | 任务范围类型   |
| scope_value           | string | 任务范围值    |
| instance_id           | string | 实例ID     |
| template_id           | int    | 模板ID     |
| name                  | string | 任务名称     |
| creator               | string | 创建者      |
| create_time           | string | 创建时间     |
| executor              | string | 执行者      |
| start_time            | string | 开始时间     |
| finish_time           | string | 结束时间     |
| description           | string | 描述       |
| is_started            | bool   | 是否已开始    |
| is_finished           | bool   | 是否已完成    |
| is_revoked            | bool   | 是否已撤销    |
| is_deleted            | bool   | 是否已删除    |
| is_expired            | bool   | 是否已过期    |
| snapshot_id           | int    | 快照ID     |
| execution_snapshot_id | int    | 执行快照ID   |
| tree_info_id          | int    | 任务拓扑信息ID |
| extra_info            | dict   | 任务额外信息   |
