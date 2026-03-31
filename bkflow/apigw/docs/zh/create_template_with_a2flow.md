### 资源描述

导入简化流程 JSON 并创建模板。支持两种协议格式：

- **v1（数组格式）**：`a2flow` 字段为 JSON 数组，需配合顶层 `name` 字段
- **v2（对象格式）**：`a2flow` 字段为 JSON 对象，`name` 在 `a2flow` 内部，AI Agent 推荐使用

接口自动根据 `a2flow` 字段的类型（数组 / 对象）路由到对应的转换器。

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |
| access_token  | string | 否  | 用户或应用 access_token，详情参考 AccessToken API                     |

---

## v2 协议（推荐）

适用于 AI Agent / LLM 生成流程，token 更省、结构更简洁。

#### 接口参数

| 字段           | 类型     | 必选 | 描述                                |
|--------------|--------|----|-----------------------------------|
| a2flow       | object | 是  | a2flow v2 JSON 对象（详见下方结构）         |
| creator      | string | 否  | 创建人                               |
| scope_type   | string | 否  | 流程范围类型，与 scope_value 必须同时填写或同时不填写 |
| scope_value  | string | 否  | 流程范围值，与 scope_type 必须同时填写或同时不填写   |
| auto_release | bool   | 否  | 是否自动发布，默认为 false                  |

#### a2flow 对象结构

| 字段        | 类型     | 必选 | 描述                          |
|-----------|--------|----|-----------------------------|
| version   | string | 否  | 协议版本，默认 `"2.0"`             |
| name      | string | 是  | 流程名称                        |
| desc      | string | 否  | 流程描述                        |
| nodes     | list   | 是  | 节点数组（不能为空）                  |
| variables | list   | 否  | 全局变量数组                      |

#### 节点结构（nodes 数组元素）

| 字段                  | 类型          | 必选    | 描述                                                      |
|---------------------|-------------|-------|---------------------------------------------------------|
| id                  | string      | 是     | 节点唯一 ID                                                 |
| name                | string      | 否     | 节点显示名称                                                  |
| type                | string      | 否     | 节点类型，默认 `"Activity"`；可选值见下表                              |
| code                | string      | Activity 是 | 插件 code                                                 |
| data                | object      | 否     | 插件参数，扁平 `{"key": value}` 格式                             |
| next                | string/list | 非 EndEvent 是 | 下一个节点 ID（Activity/ConvergeGateway 为字符串，分支网关为数组）         |
| plugin_type         | string      | 否     | 插件类型提示：`component` / `remote_plugin` / `uniform_api`    |
| conditions          | list        | ExclusiveGateway 是 | 条件数组 `[{"evaluate": "表达式"}]`，与 next 数组一一对应              |
| default_next        | string      | 否     | ExclusiveGateway 默认分支目标 ID                               |
| converge_gateway_id | string      | 否     | 手动指定汇聚网关 ID，不填时自动推断                                     |
| stage_name          | string      | 否     | 步骤名称，默认与 name 相同                                        |

#### 节点类型

| type                        | 说明     | next 类型 |
|-----------------------------|--------|---------|
| Activity（默认）                | 活动节点   | string  |
| StartEvent                  | 开始事件   | string  |
| EndEvent                    | 结束事件   | 无       |
| ParallelGateway             | 并行网关   | list    |
| ConditionalParallelGateway  | 条件并行网关 | list    |
| ExclusiveGateway            | 排他网关   | list    |
| ConvergeGateway             | 汇聚网关   | string  |

**隐式注入**：若 nodes 中没有 StartEvent / EndEvent，转换器会自动注入。

#### 变量结构（variables 数组元素）

| 字段          | 类型     | 必选 | 描述                                          |
|-------------|--------|----|---------------------------------------------|
| key         | string | 是  | 变量引用键，格式 `${变量名}`                           |
| name        | string | 否  | 变量显示名称                                      |
| value       | any    | 否  | 默认值                                         |
| source_type | string | 否  | `custom`（默认） / `component_outputs` / `system` |
| custom_type | string | 否  | `input`（默认） / `textarea`                     |
| description | string | 否  | 变量描述                                        |
| show_type   | string | 否  | `show`（默认） / `hide`                          |

#### v2 请求示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "a2flow": {
        "version": "2.0",
        "name": "示例流程-v2",
        "desc": "并行执行后条件判断",
        "nodes": [
            {"id": "n1", "name": "人工确认", "code": "pause_node", "data": {"description": "确认参数"}, "next": "pg1"},
            {"type": "ParallelGateway", "id": "pg1", "name": "并行", "next": ["n2", "n3"]},
            {"id": "n2", "name": "任务A", "code": "job_fast_execute_script", "data": {"script_content": "echo A"}, "next": "cg1"},
            {"id": "n3", "name": "任务B", "code": "job_fast_execute_script", "data": {"script_content": "echo B"}, "next": "cg1"},
            {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚", "next": "eg1"},
            {"type": "ExclusiveGateway", "id": "eg1", "name": "判断", "next": ["n4", "n5"], "conditions": [{"evaluate": "${result} == 'success'"}, {"evaluate": "${result} != 'success'"}], "default_next": "n5"},
            {"id": "n4", "name": "成功通知", "code": "bk_notify", "data": {"bk_notify_title": "成功"}, "next": "cg2"},
            {"id": "n5", "name": "失败处理", "code": "bk_notify", "data": {"bk_notify_title": "失败"}, "next": "cg2"},
            {"type": "ConvergeGateway", "id": "cg2", "name": "条件汇聚", "next": "end"}
        ],
        "variables": [
            {"key": "${result}", "name": "执行结果", "value": "success"}
        ]
    }
}
```

#### v2 错误响应格式

v2 协议返回结构化错误数组，便于 AI Agent 解析和修复：

```json
{
    "result": false,
    "errors": [
        {
            "type": "INVALID_REFERENCE",
            "node_id": "n1",
            "field": "next",
            "value": "nonexistent",
            "message": "节点 'n1' 的 next 引用了未定义的节点 'nonexistent'",
            "hint": "可用的节点 ID: ['cg1', 'end', 'n1', 'n2', 'start']"
        }
    ],
    "code": 1
}
```

错误类型枚举：

| type                     | 说明            |
|--------------------------|---------------|
| MISSING_REQUIRED_FIELD   | 缺少必填字段        |
| INVALID_REFERENCE        | 引用了不存在的节点     |
| DUPLICATE_NODE_ID        | 节点 ID 重复      |
| CONDITIONS_MISMATCH      | conditions 数量与 next 不匹配 |
| INVALID_DEFAULT_NEXT     | default_next 不在 next 中 |
| UNKNOWN_PLUGIN_CODE      | 未找到插件 code    |
| AMBIGUOUS_PLUGIN_CODE    | 多个注册表匹配，需指定 plugin_type |
| CONVERGE_INFER_FAILED    | 无法自动推断汇聚网关    |
| UNSUPPORTED_VERSION      | 不支持的协议版本      |
| RESERVED_ID_CONFLICT     | 保留 ID 与节点类型冲突 |

---

## v1 协议（兼容）

#### 接口参数

| 字段           | 类型     | 必选 | 描述                                |
|--------------|--------|----|-----------------------------------|
| name         | string | 是  | 模板名称                              |
| a2flow       | list   | 是  | 简化流程 JSON 数组                      |
| creator      | string | 否  | 创建人                               |
| desc         | string | 否  | 模板描述                              |
| scope_type   | string | 否  | 流程范围类型，与 scope_value 必须同时填写或同时不填写 |
| scope_value  | string | 否  | 流程范围值，与 scope_type 必须同时填写或同时不填写   |
| auto_release | bool   | 否  | 是否自动发布，默认为 false                  |

---

a2flow 数组中支持以下 10 种组件类型，输出顺序建议为：流程名称 → StartEvent → Activity/Gateway 节点 → EndEvent → 所有 Link → 所有 Variable。

#### 流程名称

必须包含，用于标识流程。

```json
{"type": "name", "value": "流程名称"}
```

---

#### StartEvent

开始节点。每个流程有且仅有一个，ID 固定为 `start`。

```json
{"type": "StartEvent", "id": "start", "name": "流程开始"}
```

---

#### EndEvent

结束节点。每个流程有且仅有一个，ID 固定为 `end`。

```json
{"type": "EndEvent", "id": "end", "name": "流程结束"}
```

---

#### Activity

活动节点（插件节点）。

```json
{"type": "Activity", "id": "n1", "name": "执行脚本", "code": "job_fast_execute_script", "data": {"script_content": "echo hello"}}
```

| 字段       | 必填 | 说明                                    |
|----------|----|---------------------------------------|
| id       | 是  | `n1`, `n2`, `n3` ... 按序递增             |
| name     | 是  | 节点显示名称                                |
| code     | 是  | 插件 code（如 `job_fast_execute_script`、`pause_node`、`bk_notify` 等） |
| data     | 否  | 扁平化键值对 `{"key": "value"}`，引用变量用 `${变量名}`；仅填写需要的参数 |
| stage_name | 否 | 步骤名称，默认与 name 相同                     |

---

#### ParallelGateway

并行网关。所有分支都会执行，汇聚时等待全部完成。**必须**与 ConvergeGateway 配对使用。

```json
{"type": "ParallelGateway", "id": "pg1", "name": "并行分发"}
```

| 字段                  | 必填 | 说明                                |
|---------------------|----|-----------------------------------|
| id                  | 是  | `pg1`, `pg2` ... 按序递增             |
| name                | 是  | 网关显示名称                            |
| converge_gateway_id | 否  | 对应汇聚网关 ID，不填时自动推断                 |

---

#### ConditionalParallelGateway

条件并行网关。会执行所有满足条件的分支。**必须**与 ConvergeGateway 配对使用。

```json
{"type": "ConditionalParallelGateway", "id": "cpg1", "name": "条件并行", "conditions": [{"evaluate": "${env}=='prod'", "target": "n1"}, {"evaluate": "${env}=='test'", "target": "n2"}]}
```

| 字段                  | 必填 | 说明                                |
|---------------------|----|-----------------------------------|
| id                  | 是  | 按序递增                              |
| name                | 是  | 网关显示名称                            |
| conditions          | 否  | 条件数组，每项含 `evaluate`（条件表达式）和 `target`（目标节点 ID） |
| converge_gateway_id | 否  | 对应汇聚网关 ID，不填时自动推断                 |

---

#### ExclusiveGateway

排他网关。只会执行一个满足条件的分支，多个条件同时满足时会报错。

```json
{"type": "ExclusiveGateway", "id": "eg1", "name": "条件判断", "conditions": [{"evaluate": "${status}=='pass'", "target": "n2"}, {"evaluate": "${status}!='pass'", "target": "n3"}]}
```

| 字段       | 必填 | 说明                                    |
|----------|----|---------------------------------------|
| id       | 是  | `eg1`, `eg2` ... 按序递增                 |
| name     | 是  | 网关显示名称                                |
| conditions | 否 | 条件数组，每项含 `evaluate`（条件表达式）和 `target`（目标节点 ID） |

- 条件分支必须覆盖所有可能情况
- 建议设置 `is_default` 默认分支处理未匹配情况（在 Link 上标记）
- **必须**与 ConvergeGateway 配对使用

---

#### ConvergeGateway

汇聚网关。与 ParallelGateway / ExclusiveGateway / ConditionalParallelGateway 配对使用。

```json
{"type": "ConvergeGateway", "id": "cg1", "name": "汇聚"}
```

| 字段   | 必填 | 说明                    |
|------|----|---------------------|
| id   | 是  | `cg1`, `cg2` ... 按序递增 |
| name | 是  | 网关显示名称              |

---

#### Link

连接线。所有节点必须通过 Link 连通。

```json
{"type": "Link", "source": "start", "target": "n1"}
{"type": "Link", "source": "eg1", "target": "n3", "is_default": true}
```

| 字段       | 必填 | 说明                            |
|----------|----|-------------------------------|
| source   | 是  | 源节点 ID                        |
| target   | 是  | 目标节点 ID                       |
| is_default | 否 | 设为 `true` 表示排他网关的默认分支，当所有条件都不满足时走此分支 |

---

#### Variable

全局变量定义。无变量则不输出。

```json
{"type": "Variable", "key": "${ip}", "name": "目标服务器IP", "value": "", "source_type": "custom", "custom_type": "input", "description": "执行脚本的目标服务器IP"}
```

| 字段          | 必填 | 说明                                          |
|-------------|----|---------------------------------------------|
| key         | 是  | 变量引用键，格式 `${变量名}`                           |
| name        | 否  | 变量显示名称                                      |
| value       | 否  | 默认值（可为空）                                    |
| source_type | 否  | `custom`（自定义，默认） / `component_outputs` / `system` |
| custom_type | 否  | `input`（单行输入，默认） / `textarea`（多行输入），仅 source_type 为 custom 时有效 |
| description | 否  | 变量描述                                        |
| show_type   | 否  | `show`（显示，默认） / `hide`（隐藏）                  |

---

### 请求参数示例

以下示例覆盖所有支持的节点类型：name、StartEvent、EndEvent、Activity（含 data）、ParallelGateway、ExclusiveGateway（含 conditions）、ConvergeGateway、Link（含 is_default）、Variable。

流程结构：开始 → 审批确认 → 并行执行（任务A / 任务B） → 汇聚 → 条件判断 → 成功通知 / 失败处理 → 汇聚 → 结束

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "示例流程-全类型演示",
    "desc": "覆盖所有节点类型的示例流程",
    "auto_release": false,
    "a2flow": [
        {"type": "name", "value": "示例流程-全类型演示"},
        {"type": "StartEvent", "id": "start", "name": "开始"},
        {"type": "Activity", "id": "n1", "name": "人工确认", "code": "pause_node", "data": {"description": "参数确认：\n目标: ${target}\n操作人: ${operator}\n\n确认无误后点击继续。"}},
        {"type": "ParallelGateway", "id": "pg1", "name": "并行执行"},
        {"type": "Activity", "id": "n2", "name": "任务A", "code": "job_fast_execute_script", "data": {"script_content": "#!/bin/bash\necho 'Task A: ${target}'"}},
        {"type": "Activity", "id": "n3", "name": "任务B", "code": "job_fast_execute_script", "data": {"script_content": "#!/bin/bash\necho 'Task B: ${target}'"}},
        {"type": "ConvergeGateway", "id": "cg1", "name": "并行汇聚"},
        {"type": "ExclusiveGateway", "id": "eg1", "name": "结果判断", "conditions": [
            {"evaluate": "${result}=='success'", "target": "n4"},
            {"evaluate": "${result}!='success'", "target": "n5"}
        ]},
        {"type": "Activity", "id": "n4", "name": "成功通知", "code": "bk_notify", "data": {"bk_notify_title": "执行成功", "bk_notify_content": "目标 ${target} 处理完成", "bk_receiver": "${operator}", "bk_msg_type": "weixin"}},
        {"type": "Activity", "id": "n5", "name": "失败处理", "code": "job_fast_execute_script", "data": {"script_content": "#!/bin/bash\necho '执行失败，开始回滚...'"}},
        {"type": "Activity", "id": "n6", "name": "失败通知", "code": "bk_notify", "data": {"bk_notify_title": "执行失败", "bk_notify_content": "目标 ${target} 处理失败，已回滚", "bk_receiver": "${operator}", "bk_msg_type": "weixin"}},
        {"type": "ConvergeGateway", "id": "cg2", "name": "条件汇聚"},
        {"type": "EndEvent", "id": "end", "name": "结束"},
        {"type": "Link", "source": "start", "target": "n1"},
        {"type": "Link", "source": "n1", "target": "pg1"},
        {"type": "Link", "source": "pg1", "target": "n2"},
        {"type": "Link", "source": "pg1", "target": "n3"},
        {"type": "Link", "source": "n2", "target": "cg1"},
        {"type": "Link", "source": "n3", "target": "cg1"},
        {"type": "Link", "source": "cg1", "target": "eg1"},
        {"type": "Link", "source": "eg1", "target": "n4"},
        {"type": "Link", "source": "eg1", "target": "n5", "is_default": true},
        {"type": "Link", "source": "n4", "target": "cg2"},
        {"type": "Link", "source": "n5", "target": "n6"},
        {"type": "Link", "source": "n6", "target": "cg2"},
        {"type": "Link", "source": "cg2", "target": "end"},
        {"type": "Variable", "key": "${target}", "name": "操作目标", "value": "", "source_type": "custom", "custom_type": "input", "description": "操作的目标对象"},
        {"type": "Variable", "key": "${operator}", "name": "操作人", "value": "", "source_type": "custom", "custom_type": "input", "description": "执行操作的负责人"},
        {"type": "Variable", "key": "${result}", "name": "执行结果", "value": "success", "source_type": "custom", "custom_type": "input", "description": "执行结果，success/fail"}
    ]
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": 3,
        "space_id": "1",
        "name": "消息展示",
        "desc": "通过简化流程 JSON 创建的模板",
        "notify_config": {},
        "scope_type": null,
        "scope_value": null,
        "source": null,
        "version": null,
        "is_enabled": true,
        "bk_app_code": null,
        "extra_info": {},
        "creator": "",
        "create_at": "2026-03-13T06:59:38.890Z",
        "update_at": "2026-03-13T06:59:38.890Z",
        "updated_by": "",
        "pipeline_tree": {
            "activities": {
                "n1": {
                    "id": "n1",
                    "name": "消息展示",
                    "type": "ServiceActivity",
                    "incoming": ["lb"],
                    "outgoing": "l7",
                    "stage_name": "消息展示",
                    "component": {
                        "code": "bk_display",
                        "version": "v1.0",
                        "data": {}
                    },
                    "auto_retry": {
                        "enable": false,
                        "interval": 0,
                        "times": 1
                    },
                    "timeout_config": {
                        "action": "forced_fail",
                        "enable": false,
                        "seconds": 10
                    },
                    "error_ignorable": false,
                    "retryable": true,
                    "skippable": true,
                    "optional": true,
                    "labels": [],
                    "loop": null
                }
            },
            "gateways": {},
            "flows": {
                "lb": {
                    "id": "lb",
                    "is_default": false,
                    "source": "n4",
                    "target": "n1"
                },
                "l7": {
                    "id": "l7",
                    "is_default": false,
                    "source": "n1",
                    "target": "nb"
                }
            },
            "start_event": {
                "id": "n4",
                "name": "开始",
                "type": "EmptyStartEvent",
                "incoming": "",
                "outgoing": "lb",
                "labels": []
            },
            "end_event": {
                "id": "nb",
                "name": "结束",
                "type": "EmptyEndEvent",
                "incoming": ["l7"],
                "outgoing": "",
                "labels": []
            },
            "constants": {},
            "outputs": []
        }
    },
    "code": 0,
    "trace_id": "xxxxxxxxx"
}
```

### 返回结果参数说明

| 字段       | 类型     | 描述                    |
|----------|--------|-----------------------|
| result   | bool   | 返回结果，true为成功，false为失败 |
| code     | int    | 返回码，0表示成功，其他值表示失败     |
| message  | string | 错误信息                  |
| data     | dict   | 返回数据                  |
| trace_id | string | open telemetry trace_id |

#### data[item]

| 字段            | 类型     | 描述       |
|---------------|--------|----------|
| id            | int    | 流程ID     |
| space_id      | string | 流程所属空间ID |
| name          | string | 流程名称     |
| desc          | string | 流程描述     |
| notify_config | dict   | 通知配置     |
| scope_type    | string | 流程范围类型   |
| scope_value   | string | 流程范围ID   |
| source        | string | 流程来源     |
| version       | string | 流程版本     |
| is_enabled    | bool   | 流程是否启用   |
| bk_app_code   | string | 绑定的应用编码  |
| extra_info    | dict   | 流程扩展信息   |
| creator       | string | 流程创建者    |
| create_at     | string | 流程创建时间   |
| update_at     | string | 流程更新时间   |
| updated_by    | string | 流程更新者    |
| pipeline_tree | dict   | 流程树详情    |
