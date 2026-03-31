# a2flow v2.0 AI-Friendly 协议优化设计

## 概述

对 a2flow 协议进行 AI 友好方向的升级，核心目标：

1. **降低 AI 生成流程的认知负担和 token 消耗**
2. **统一三种插件类型的协议差异**，让 AI 不感知底层包装
3. **用 pipeline_converter 的两阶段架构重构工程实现**，支持协议版本演进
4. **为后续 MCP 工具链 / 向量知识库提供设计蓝图**（本次不实现）

### 背景

- PR #632 / #655 引入了 a2flow v1.0 协议（扁平数组 + 独立 Link），已合入 master
- PR #589 引入了 pipeline_converter 框架（JSON → Pydantic DataModel → pipeline_tree），代码已在 master
- 本次在两者基础上取长补短：a2flow 的简洁协议 + pipeline_converter 的可扩展架构

### 设计范围

| 层面 | 本次范围 |
|---|---|
| 协议层 | 实现 — 重新设计 a2flow v2.0 输入格式 |
| 工程层 | 实现 — 用 pipeline_converter 架构重构转换器 |
| 插件统一层 | 实现 — 在转换器中屏蔽三种插件类型的包装差异 |
| MCP 工具层 | 仅设计 — 留作后续迭代 |
| 向量知识库 | 仅设计 — 留作后续迭代 |

---

## 1. 协议格式

### 1.1 顶层结构

```json
{
  "version": "2.0",
  "name": "流程名称",
  "desc": "流程描述",
  "nodes": [ ... ],
  "variables": [ ... ]
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `version` | string | 否 | `"2.0"` | 协议版本，用于路由到对应的转换器 |
| `name` | string | 是 | — | 模板名称 |
| `desc` | string | 否 | `""` | 模板描述 |
| `nodes` | array | 是 | — | 节点数组，不能为空 |
| `variables` | array | 否 | `[]` | 全局变量数组 |

### 1.2 与 v1.0 的关键差异

| 维度 | v1.0（当前） | v2.0（本次） |
|---|---|---|
| 顶层结构 | 扁平数组 | 结构化对象 `{name, nodes, variables}` |
| 拓扑连接 | 独立 `Link` 元素 | 节点内嵌 `next` 字段 |
| StartEvent / EndEvent | 必须显式声明 | 可省略，自动注入 |
| `type` 字段 | 必须声明 | 缺省为 `"Activity"` |
| 分支条件 | `conditions` 中通过 `target` 指向目标 | `conditions` 与 `next` 按位置一一对应 |
| 默认分支 | Link 上标 `is_default` | `default_next` 字段 |
| 插件类型 | 仅支持内置插件 | 统一支持三种插件，自动识别包装 |
| 版本字段 | 无 | 顶层 `version` 用于协议路由 |

### 1.3 节点类型

#### StartEvent（可省略）

```json
{"type": "StartEvent", "id": "start", "name": "开始", "next": "n1"}
```

如果 `nodes` 数组中没有 StartEvent，转换器自动注入一个，`id` 为 `"start"`，`next` 指向 `nodes[0]`。

#### EndEvent（可省略）

```json
{"type": "EndEvent", "id": "end", "name": "结束"}
```

如果 `nodes` 数组中没有 EndEvent，转换器自动注入一个，`id` 为 `"end"`。任何节点可用 `"next": "end"` 指向它。`"start"` 和 `"end"` 为保留 ID。

#### Activity（type 可省略）

```json
{
  "id": "n1",
  "name": "执行脚本",
  "code": "job_fast_execute_script",
  "data": {"script_content": "echo ${ip}", "timeout": 600},
  "next": "n2"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | string | 否 | 缺省为 `"Activity"` |
| `id` | string | 是 | 节点标识，在整个流程内唯一 |
| `name` | string | 是 | 显示名称 |
| `code` | string | 是 | 插件标识（统一的业务 code，非底层包装 code） |
| `data` | dict | 否 | 扁平 key-value 字典，引用变量用 `${变量名}` |
| `next` | string | 是 | 下一个节点 ID |
| `stage_name` | string | 否 | 步骤名，默认同 `name` |
| `plugin_type` | string | 否 | 插件类型消歧，见"插件统一层"章节 |

#### ParallelGateway

```json
{"type": "ParallelGateway", "id": "pg1", "name": "并行", "next": ["n2", "n3"]}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | 是 | 节点标识 |
| `name` | string | 是 | 显示名称 |
| `next` | array[string] | 是 | 并行分支的首个节点 ID 列表 |
| `converge_gateway_id` | string | 否 | 对应的汇聚网关 ID，省略时自动推断 |

#### ConditionalParallelGateway

```json
{
  "type": "ConditionalParallelGateway", "id": "cpg1", "name": "条件并行",
  "next": ["n2", "n3"],
  "conditions": [
    {"evaluate": "${env} == 'prod'"},
    {"evaluate": "${env} == 'test'"}
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | 是 | 节点标识 |
| `name` | string | 是 | 显示名称 |
| `next` | array[string] | 是 | 分支目标节点 ID 列表 |
| `conditions` | array[object] | 是 | 条件数组，与 `next` 按位置一一对应 |
| `converge_gateway_id` | string | 否 | 省略时自动推断 |

#### ExclusiveGateway

```json
{
  "type": "ExclusiveGateway", "id": "eg1", "name": "判断",
  "next": ["n2", "n3"],
  "conditions": [
    {"evaluate": "${status} == 'pass'"},
    {"evaluate": "${status} != 'pass'"}
  ],
  "default_next": "n3"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | 是 | 节点标识 |
| `name` | string | 是 | 显示名称 |
| `next` | array[string] | 是 | 分支目标节点 ID 列表 |
| `conditions` | array[object] | 是 | 条件数组，与 `next` 按位置一一对应 |
| `default_next` | string | 否 | 默认分支节点 ID，必须是 `next` 中的某一个 |

#### ConvergeGateway

```json
{"type": "ConvergeGateway", "id": "cg1", "name": "汇聚", "next": "n4"}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | 是 | 节点标识 |
| `name` | string | 是 | 显示名称 |
| `next` | string | 是 | 汇聚后的下一个节点 ID |

### 1.4 变量定义

```json
{
  "key": "${ip}",
  "name": "服务器IP",
  "value": "",
  "source_type": "custom",
  "custom_type": "input",
  "description": "目标服务器",
  "show_type": "show"
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `key` | string | 是 | — | 变量引用键，格式 `${变量名}` |
| `name` | string | 否 | `""` | 变量显示名称 |
| `value` | any | 否 | `""` | 默认值 |
| `source_type` | string | 否 | `"custom"` | `custom` / `component_outputs` / `system` |
| `custom_type` | string | 否 | `"input"` | `input` / `textarea` |
| `description` | string | 否 | `""` | 变量描述 |
| `show_type` | string | 否 | `"show"` | `show` / `hide` |

### 1.5 完整示例

简单线性流程（最简形式）：

```json
{
  "version": "2.0",
  "name": "简单流程",
  "nodes": [
    {"id": "n1", "name": "执行脚本", "code": "job_fast_execute_script",
     "data": {"script_content": "echo hello"}, "next": "end"}
  ]
}
```

含并行网关和排他网关的完整流程：

```json
{
  "version": "2.0",
  "name": "运维流程",
  "nodes": [
    {"id": "n1", "name": "审批确认", "code": "pause_node",
     "data": {"description": "确认执行？"}, "next": "pg1"},
    {"type": "ParallelGateway", "id": "pg1", "name": "并行执行", "next": ["n2", "n3"]},
    {"id": "n2", "name": "任务A", "code": "job_fast_execute_script",
     "data": {"script_content": "echo A"}, "next": "cg1"},
    {"id": "n3", "name": "任务B", "code": "job_fast_execute_script",
     "data": {"script_content": "echo B"}, "next": "cg1"},
    {"type": "ConvergeGateway", "id": "cg1", "name": "汇聚", "next": "eg1"},
    {"type": "ExclusiveGateway", "id": "eg1", "name": "结果判断",
     "next": ["n4", "n5"],
     "conditions": [
       {"evaluate": "${result} == 'success'"},
       {"evaluate": "${result} != 'success'"}
     ],
     "default_next": "n5"},
    {"id": "n4", "name": "成功通知", "code": "bk_notify",
     "data": {"title": "成功", "content": "执行完成"}, "next": "end"},
    {"id": "n5", "name": "失败处理", "code": "job_fast_execute_script",
     "data": {"script_content": "echo 回滚..."}, "next": "end"}
  ],
  "variables": [
    {"key": "${result}", "name": "执行结果", "value": "success", "description": "success/fail"}
  ]
}
```

混合三种插件类型：

```json
{
  "version": "2.0",
  "name": "混合插件流程",
  "nodes": [
    {"id": "n1", "name": "HTTP请求", "code": "bk_http_request",
     "data": {"url": "http://api.example.com"}, "next": "n2"},
    {"id": "n2", "name": "自定义处理", "code": "my_custom_plugin",
     "plugin_type": "remote_plugin",
     "data": {"param1": "hello"}, "next": "n3"},
    {"id": "n3", "name": "执行标准运维", "code": "sops_execute",
     "plugin_type": "uniform_api",
     "data": {"biz_id": 123, "template_id": 456}, "next": "end"}
  ]
}
```

---

## 2. 插件统一层

### 2.1 问题

BKFlow 的三种插件类型在 pipeline_tree 中有不同的 component 结构：

| | 内置插件 | 蓝鲸标准插件 | API 插件 |
|---|---|---|---|
| `component.code` | 实际 code | `"remote_plugin"` | `"uniform_api"` |
| `component.version` | ComponentModel 版本 | `"1.0.0"` | `"v2.0.0"` / `"v3.0.0"` |
| 真正的插件标识 | code 本身 | `data.plugin_code.value` | `api_meta.id` |
| 额外元数据 | 无 | 无 | `api_meta: {id, name, meta_url, api_key, category}` |

AI 不应该关心这些包装差异。

### 2.2 设计

**a2flow 协议层**：AI 只写 `code`（真正的插件标识）+ `data`（业务参数），三种类型写法一致。

**转换器层**：`ActivityNodeConverter` 负责识别插件类型并生成正确的 pipeline_tree 结构。

**识别逻辑**：

```
plugin_type 已指定？
├── 是 → 在对应注册表中查找，未找到则报 UNKNOWN_PLUGIN_CODE
└── 否 → 自动识别
    ├── 查 ComponentModel (status=1) → 命中 → 内置插件
    ├── 查 BKPlugin 注册表 → 命中 → 蓝鲸标准插件
    ├── 查空间 uniform_api 配置 → 命中 → API 插件
    ├── 多个注册表同时命中 → 报 AMBIGUOUS_PLUGIN_CODE，提示指定 plugin_type
    └── 都未命中 → 报 UNKNOWN_PLUGIN_CODE
```

**转换输出**：

| 识别为 | pipeline_tree 中的 component 结构 |
|---|---|
| 内置插件 | `{code: 原始code, version: 自动查询最新, data: {key: {hook: false, value: val}}}` |
| 蓝鲸标准插件 | `{code: "remote_plugin", version: "1.0.0", data: {plugin_code: {hook: false, value: 原始code}, plugin_version: {hook: false, value: 查询版本}, ...业务参数}}` |
| API 插件 | `{code: "uniform_api", version: 查询版本, data: {uniform_api_plugin_url: ..., ...}, api_meta: {id: 原始code, ...}}` |

### 2.3 DataModel

```python
class ResolvedPlugin(BaseModel):
    """插件类型识别后的中间表示"""
    plugin_type: str          # "component" | "remote_plugin" | "uniform_api"
    original_code: str        # AI 写的 code
    wrapper_code: str         # pipeline_tree 中的 component.code
    wrapper_version: str      # pipeline_tree 中的 component.version
    api_meta: Optional[dict]  # API 插件专用
```

### 2.4 `plugin_type` 消歧字段

| 值 | 含义 |
|---|---|
| `"component"` | 内置插件 |
| `"remote_plugin"` | 蓝鲸标准插件 |
| `"uniform_api"` | API 插件 |

该字段可选。当多个注册表中存在同名 code 时，必须指定以消歧。AI 从知识库或工具获取的插件信息中包含 `plugin_type`，生成时直接带上即可避免冲突。

---

## 3. 工程架构

### 3.1 两阶段转换流水线

```
a2flow JSON → [阶段 1] → Pydantic DataModel → [阶段 2] → pipeline_tree (dict)
```

- **阶段 1**：协议解析、类型校验、隐式注入、插件识别、converge 推断
- **阶段 2**：DataModel → pipeline_tree 格式转换（复用现有 pipeline_converter）

### 3.2 协议版本路由

同一个 API endpoint 支持多版本，通过 `version` 字段路由：

```
POST /space/{space_id}/create_template_with_a2flow/
         │
    version 字段路由
    ┌──────────┬──────────┐
    │ v1.0     │ v2.0     │  (未来 v3.0+ ...)
    │ 扁平数组  │ nodes +  │
    │ + Link   │ next     │
    └──────────┴──────────┘
         │          │
         ▼          ▼
    各自的 a2flow_v1/   a2flow_v2/ converter 集合
         │          │
         ▼          ▼
    共享的 Pipeline DataModel
         │
         ▼
    共享的 data_model_to_web_pipeline/ 阶段 2
```

### 3.3 模块结构

```
bkflow/pipeline_converter/
├── constants.py                        # NodeTypes, DataTypes, A2FlowVersions 枚举
├── data_models.py                      # 共享 Pydantic DataModel（复用+扩展）
├── hub.py                              # ConverterHub 注册中心
├── validators/
│   ├── base.py                         # BaseValidator
│   └── node.py                         # NodeTypeValidator, JsonNodeTypeValidator
├── converters/
│   ├── base.py                         # BaseConverter, BaseBiConverter 等基类
│   ├── a2flow_v1/                      # v1.0 转换器集合（迁移现有 a2flow.py）
│   │   ├── __init__.py
│   │   ├── pipeline.py                 # A2FlowV1PipelineConverter（入口）
│   │   ├── node.py
│   │   └── gateway.py
│   ├── a2flow_v2/                      # v2.0 转换器集合（本次新增）
│   │   ├── __init__.py
│   │   ├── pipeline.py                 # A2FlowV2PipelineConverter（入口）
│   │   ├── node.py                     # StartNode, EndNode, ActivityNode 转换
│   │   ├── gateway.py                  # 网关转换 + converge 推断
│   │   ├── variable.py                 # 变量转换
│   │   └── plugin_resolver.py          # 插件类型识别与包装
│   ├── json_to_data_model/             # 原 pipeline_converter 的 JSON 转换（保留）
│   │   └── ...
│   └── data_model_to_web_pipeline/     # 共享阶段 2（复用现有）
│       ├── pipeline.py
│       ├── node.py
│       ├── gateway.py
│       └── component.py
└── file_handlers/
    └── ...
```

### 3.4 阶段 1 核心流程（A2FlowV2PipelineConverter）

```python
class A2FlowV2PipelineConverter:
    def convert(self) -> Pipeline:
        # 1. 解析输入为 A2FlowPipeline DataModel（Pydantic 校验）
        a2flow_pipeline = A2FlowPipeline(**self.source_data)

        # 2. 隐式注入 StartEvent / EndEvent
        nodes = self._inject_start_end_if_missing(a2flow_pipeline.nodes)

        # 3. 批量识别插件类型
        plugin_map = PluginResolver(self.space_id).resolve_batch(
            [n for n in nodes if n.type == "Activity"]
        )

        # 4. 转换为 Pipeline DataModel 的节点列表
        pipeline_nodes = []
        for node in nodes:
            converter = self._get_node_converter(node.type)
            pipeline_nodes.append(converter(node, plugin_map).convert())

        # 5. 从 next 字段生成 Flow 连接
        # 6. 自动推断 converge_gateway_id
        # 7. 转换变量
        # 8. 组装 Pipeline DataModel
        return Pipeline(...)
```

### 3.5 API 层

View 函数简化为编排逻辑，不包含任何转换细节：

```python
def create_template_with_a2flow(request, space_id):
    # 1. Serializer 校验
    ser = CreateTemplateWithA2FlowSerializer(data=data)
    ser.is_valid(raise_exception=True)

    # 2. 根据 version 路由到对应 converter
    version = validated_data.get("version", "2.0")
    converter_name = A2FLOW_VERSION_MAP[version]

    # 3. 阶段 1: a2flow → DataModel
    a2flow_converter = ConverterHub.get_converter_cls(
        DataTypes.A2FLOW.value, DataTypes.DATA_MODEL.value, converter_name
    )
    pipeline_model = a2flow_converter(a2flow_data, space_id=space_id).convert()

    # 4. 阶段 2: DataModel → pipeline_tree
    tree_converter = ConverterHub.get_converter_cls(
        DataTypes.DATA_MODEL.value, DataTypes.WEB_PIPELINE.value, "PipelineConverter"
    )
    pipeline_tree = tree_converter(pipeline_model).convert()

    # 5. 排版 + 替换 ID + 创建模板
    draw_pipeline(pipeline_tree)
    replace_pipeline_tree_node_ids(pipeline_tree, OperateType.CREATE_TEMPLATE.value)
    template = Template.objects.create(...)
    return {"result": True, "data": template.to_json()}
```

### 3.6 Pydantic DataModel

**a2flow v2.0 协议层 DataModel（阶段 1 入口）：**

```python
class A2FlowNode(BaseModel):
    id: str
    name: str = ""
    type: str = "Activity"
    next: Union[str, List[str], None] = None

class A2FlowActivity(A2FlowNode):
    type: str = "Activity"
    code: str
    data: Dict[str, Any] = {}
    stage_name: Optional[str] = None
    plugin_type: Optional[str] = None  # 消歧字段

class A2FlowExclusiveGateway(A2FlowNode):
    type: str = "ExclusiveGateway"
    next: List[str]
    conditions: List[dict]
    default_next: Optional[str] = None

class A2FlowVariable(BaseModel):
    key: str
    name: str = ""
    value: Any = ""
    source_type: str = "custom"
    custom_type: str = "input"
    description: str = ""
    show_type: str = "show"

class A2FlowPipeline(BaseModel):
    version: str = "2.0"
    name: str
    desc: str = ""
    nodes: List[A2FlowNode]
    variables: List[A2FlowVariable] = []
```

**共享 Pipeline DataModel（阶段 1 输出 / 阶段 2 输入）：**

复用现有 `data_models.py` 中的 `Pipeline`, `Node`, `ComponentNode`, `Flow`, `Constant` 等，必要时扩展字段。

---

## 4. 错误处理

### 4.1 分层校验

| 层级 | 职责 | 时机 |
|---|---|---|
| Serializer | 顶层字段类型（name 必填、nodes 非空、version 合法） | 请求进入 |
| Pydantic DataModel | 字段类型、必填/可选、枚举值 | 阶段 1 解析 |
| Converter 逻辑 | 业务规则（next 引用合法、conditions 数量匹配等） | 阶段 1 转换 |
| Pipeline Schema | pipeline_tree 结构完整性 | 阶段 2 完成后 |

### 4.2 结构化错误信息

错误信息面向 AI Agent 设计，可定位、可操作：

```json
{
  "result": false,
  "errors": [
    {
      "type": "INVALID_REFERENCE",
      "node_id": "n2",
      "field": "next",
      "value": "n99",
      "message": "节点 'n2' 的 next 引用了未定义的节点 'n99'",
      "hint": "可用的节点 ID: start, n1, n3, cg1, end"
    }
  ]
}
```

### 4.3 错误类型枚举

| 错误类型 | 触发条件 |
|---|---|
| `MISSING_REQUIRED_FIELD` | 必填字段缺失（如 Activity 无 code） |
| `INVALID_REFERENCE` | next 引用了不存在的节点 ID |
| `DUPLICATE_NODE_ID` | 多个节点使用相同 id |
| `CONDITIONS_MISMATCH` | conditions 数量与 next 分支数不一致 |
| `INVALID_DEFAULT_NEXT` | default_next 不在 next 数组中 |
| `UNKNOWN_PLUGIN_CODE` | code 在所有插件注册表中查不到 |
| `AMBIGUOUS_PLUGIN_CODE` | code 在多个注册表中同时存在，需指定 plugin_type |
| `CONVERGE_INFER_FAILED` | 无法自动推断 converge_gateway_id |
| `UNSUPPORTED_VERSION` | 不支持的协议版本号 |
| `RESERVED_ID_CONFLICT` | 使用了保留 ID（start/end）但类型不匹配 |

---

## 5. MCP 工具层设计（本次不实现）

### 5.1 目标

让 AI Agent 在生成流程前能"发现"可用插件及其参数，降低编造参数名的概率。

### 5.2 推荐方案：向量知识库优先 + MCP 工具补充

**向量知识库**（优先实现）：
- 定期同步三种插件的 code、name、description、参数 schema 到向量数据库
- AI 通过 RAG 检索获取上下文，无需额外 API 调用
- 适合模糊语义匹配（"需要一个通知的步骤" → 找到 `bk_notify`）
- 不适合空间级可用性校验

**MCP 工具**（后续补充）：
- `list_plugin_codes(space_id, keyword)` — 按空间查询可用插件列表
- `get_plugin_schema(space_id, code)` — 查询插件参数 schema
- `validate_a2flow(a2flow_json)` — 预校验流程定义
- 适合精确查询和空间感知场景

### 5.3 统一查询接口

无论向量知识库还是 MCP 工具，插件数据源统一，返回格式统一：

```json
{
  "code": "my_custom_plugin",
  "name": "自定义插件",
  "plugin_type": "remote_plugin",
  "description": "自定义的脚本处理插件",
  "fields": [
    {"key": "param1", "name": "参数1", "type": "string", "required": true},
    {"key": "param2", "name": "参数2", "type": "int", "required": false, "default": 10}
  ]
}
```

AI 从知识库拿到 `plugin_type` 后，生成时直接带上，避免 code 冲突。

### 5.4 AI Agent 目标工作流

```
用户需求 → Agent 理解意图
  → RAG 检索知识库，发现候选插件（含 code、plugin_type、schema）
  → 生成 a2flow v2.0 JSON（code + plugin_type + data）
  → 调用 create_template_with_a2flow 创建模板
  → 如有结构化错误，自我修正后重试
```

---

## 6. 版本演进路线

| 版本 | 协议特征 | 状态 |
|---|---|---|
| 1.0 | 扁平数组 + 独立 Link + 显式 Start/End | 已合入，保留兼容 |
| 2.0 | 结构化 `{nodes, variables}` + `next` + 隐式注入 + 插件统一 | 本次实现 |
| 3.0+ | 可能的方向：子流程引用、循环结构、动态参数绑定等 | 预留 |

---

## 7. Token 效率对比

以 5 活动节点 + 1 并行网关流程为例：

| 维度 | v1.0 | v2.0 |
|---|---|---|
| StartEvent/EndEvent | 2 个完整节点声明 | 省略 |
| Link 元素 | 7 个独立 Link | 0（内嵌 next） |
| type 声明 | 每个节点都要 | Activity 可省略 |
| 估算节省 | 基准 | ~35-40% 输出 token |
