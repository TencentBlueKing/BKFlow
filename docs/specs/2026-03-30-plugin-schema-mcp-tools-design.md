# 插件查询与 Schema 发现 APIGW 接口设计

## 概述

为 AI Agent 提供插件发现和参数 schema 查询能力，降低 AI 生成 a2flow 流程时编造参数的概率。蓝鲸生态下所有网关接口可配置为 MCP 工具，因此直接实现为标准 APIGW 接口。

### 背景

- a2flow v2 协议已实现（`feat/optimize_a2flow` 分支），AI 可通过 `create_template_with_a2flow` 接口创建流程模板
- 但 AI 在生成流程前，缺乏"发现可用插件"和"查询参数 schema"的能力
- 原设计 spec（`docs/specs/2026-03-30-a2flow-v2-ai-friendly-protocol-design.md`）第 5 章规划了 MCP 工具层，本次落地实现

### 设计范围

| 接口 | 说明 | HTTP 方法 |
|---|---|---|
| `list_plugins` | 查询空间可用插件列表（支持搜索、过滤、详略控制） | GET |
| `get_plugin_schema` | 查询单个插件的完整参数 schema | GET |
| `validate_a2flow` | 预校验 a2flow v2 流程定义（dry-run，不创建模板） | POST |

---

## 1. API Endpoints

### 1.1 list_plugins — 查询空间可用插件列表

```
GET /space/{space_id}/list_plugins/
```

**请求参数（Query Params）：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `keyword` | string | 否 | — | 模糊搜索，匹配 code 或 name |
| `plugin_type` | string | 否 | — | 按类型过滤：`component` / `remote_plugin` / `uniform_api` |
| `without_detail` | bool | 否 | `true` | `false` 时返回完整 inputs/outputs schema |
| `scope_type` | string | 否 | — | 空间下 scope 类型（用于 SpacePluginConfig 过滤） |
| `scope_id` | string | 否 | — | 空间下 scope ID |
| `limit` | int | 否 | `100` | 分页大小，上限 200 |
| `offset` | int | 否 | `0` | 分页偏移 |

**响应（without_detail=true，摘要模式，默认）：**

```json
{
  "result": true,
  "data": [
    {
      "code": "job_fast_execute_script",
      "name": "快速执行脚本",
      "plugin_type": "component",
      "version": "v1.0.0",
      "description": "在目标机器上执行脚本",
      "group_name": "作业平台(JOB)"
    },
    {
      "code": "my_custom_plugin",
      "name": "自定义插件",
      "plugin_type": "remote_plugin",
      "version": "1.2.0",
      "description": "自定义的脚本处理插件",
      "group_name": ""
    }
  ],
  "count": 42,
  "code": 0
}
```

响应格式与 `get_template_list` 一致：`data`（数组） + `count`（总数） + `code` + `result` 并列。

**响应（without_detail=false，完整模式）：**

`data` 中每个元素额外包含 `inputs` 和 `outputs`：

```json
{
  "code": "job_fast_execute_script",
  "name": "快速执行脚本",
  "plugin_type": "component",
  "version": "v1.0.0",
  "description": "在目标机器上执行脚本",
  "group_name": "作业平台(JOB)",
  "inputs": [
    {"key": "script_content", "name": "脚本内容", "type": "string", "required": true, "description": ""},
    {"key": "timeout", "name": "超时时间", "type": "int", "required": false, "description": "", "default": 600}
  ],
  "outputs": [
    {"key": "_result", "name": "执行结果", "type": "bool", "description": ""}
  ]
}
```

**分页机制：** 由于 `list_plugins` 需要聚合三种来源到内存列表，不能直接复用 `paginate_list_data`（该函数依赖 queryset）。实现时先合并全部结果到 Python list，然后手动切片 `[offset:offset+limit]`，`count` 为合并后的总条数。`limit` 上限为 200，与 `paginate_list_data` 一致。

**AI Agent 推荐调用流程：**

1. `list_plugins(space_id, keyword=..., without_detail=true)` — 轻量发现候选插件
2. `get_plugin_schema(space_id, code=...)` — 对感兴趣的插件查完整 schema
3. 生成 a2flow v2 JSON
4. `validate_a2flow(a2flow_json)` — 可选预校验
5. `create_template_with_a2flow(a2flow_json)` — 创建模板

### 1.2 get_plugin_schema — 查询单个插件详情

```
GET /space/{space_id}/get_plugin_schema/
```

**请求参数（Query Params）：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `code` | string | 是 | — | 插件 code |
| `version` | string | 否 | — | 指定版本，不传取最新。仅对 component 类型生效；remote_plugin / uniform_api 忽略此参数 |
| `plugin_type` | string | 否 | — | 消歧用，多注册表同名时必传 |
| `scope_type` | string | 否 | — | uniform_api 凭证解析用 |
| `scope_id` | string | 否 | — | 同上 |

**响应：**

```json
{
  "result": true,
  "data": {
    "code": "my_custom_plugin",
    "name": "自定义插件",
    "plugin_type": "remote_plugin",
    "version": "1.2.0",
    "description": "自定义的脚本处理插件",
    "group_name": "",
    "inputs": [
      {"key": "param1", "name": "参数1", "type": "string", "required": true, "description": "主要参数"},
      {"key": "param2", "name": "参数2", "type": "int", "required": false, "description": "", "default": 10}
    ],
    "outputs": [
      {"key": "result_data", "name": "结果数据", "type": "string", "description": ""}
    ]
  },
  "code": 0
}
```

**错误响应（插件不存在）：**

```json
{
  "result": false,
  "message": "未找到插件 code 'xxx'",
  "code": 400,
  "data": null
}
```

**错误响应（code 歧义）：**

```json
{
  "result": false,
  "message": "插件 code 'xxx' 在多个注册表中同时存在，请指定 plugin_type 参数消歧",
  "code": 400,
  "data": null
}
```

### 1.3 validate_a2flow — 预校验 a2flow v2 流程定义

```
POST /space/{space_id}/validate_a2flow/
```

**请求体：** 与 `create_template_with_a2flow` v2 格式一致，只校验不创建模板。

```json
{
  "a2flow": {
    "version": "2.0",
    "name": "测试流程",
    "nodes": [
      {"id": "n1", "name": "执行脚本", "code": "job_fast_execute_script",
       "data": {"script_content": "echo hello"}, "next": "end"}
    ],
    "variables": []
  },
  "scope_type": "project",
  "scope_value": "1"
}

```

注意：与 `create_template_with_a2flow` 一致使用 `scope_value`（非 `scope_id`）。

**成功响应：**

```json
{
  "result": true,
  "data": {
    "valid": true,
    "version": "2.0",
    "node_count": 1,
    "plugin_codes": ["job_fast_execute_script"]
  },
  "code": 0
}
```

**失败响应：** 复用 a2flow v2 结构化错误格式。View 层直接返回错误 dict（不抛异常），确保 `errors` 字段不被 `@return_json_response` 吞掉。

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
  ],
  "code": 400
}
```

---

## 2. plugin_type 命名映射

### 2.1 背景

项目中存在两套 plugin_type 命名体系：

| 体系 | 枚举位置 | 内置 | 蓝鲸标准 | API |
|---|---|---|---|---|
| a2flow v2 协议 | `A2FlowPluginType` | `component` | `remote_plugin` | `uniform_api` |
| 内部 plugin 模块 | `PluginType` | `component` | `blueking` | `uniform_api` |

### 2.2 决策

**对外统一使用 a2flow v2 的命名**（`remote_plugin`），因为：

1. 与 a2flow v2 协议中 `plugin_type` 消歧字段一致，AI Agent 只需学一套名字
2. `remote_plugin` 比 `blueking` 语义更清晰（描述的是"远程执行的插件"）
3. MCP 工具的主要消费者是 AI Agent，应优先对齐 AI 可见的协议

### 2.3 映射常量

在 `PluginSchemaService` 中定义映射，隔离外部命名和内部命名的差异：

```python
EXTERNAL_PLUGIN_TYPE_MAP = {
    "component": "component",
    "remote_plugin": "blueking",
    "uniform_api": "uniform_api",
}

INTERNAL_TO_EXTERNAL_PLUGIN_TYPE_MAP = {v: k for k, v in EXTERNAL_PLUGIN_TYPE_MAP.items()}
```

外部接口只暴露 `component` / `remote_plugin` / `uniform_api`，内部查询时转换为对应的内部标识。

---

## 3. 统一 Schema 格式

### 3.1 统一输出结构

无论插件类型，所有插件统一映射为：

```python
{
    "code": str,           # 插件标识
    "name": str,           # 显示名称
    "plugin_type": str,    # "component" | "remote_plugin" | "uniform_api"
    "version": str,        # 版本号
    "description": str,    # 描述
    "group_name": str,     # 分组名（内置插件有，其他为空字符串）
    "inputs": [            # without_detail=true 时不返回此字段
        {
            "key": str,
            "name": str,
            "type": str,       # "string" / "int" / "bool" / "object" / "array" 等
            "required": bool,
            "description": str,
            "default": Any,    # 可选，有默认值时才出现
            "schema": dict,    # 可选，复杂类型的嵌套 JSON Schema
        }
    ],
    "outputs": [           # without_detail=true 时不返回此字段
        {
            "key": str,
            "name": str,
            "type": str,
            "description": str,
            "schema": dict,    # 可选
        }
    ]
}
```

### 3.2 三种插件类型的字段映射

| 统一字段 | component (内置) | remote_plugin (蓝鲸标准) | uniform_api (API) |
|---|---|---|---|
| `code` | `ComponentModel.code` | `BKPlugin.code` | `api_item["id"]` |
| `name` | `ComponentModel.name`（split 取插件名部分） | `BKPlugin.name` | `api_item["name"]` |
| `description` | `component_cls.desc` | `BKPlugin.introduction` | `meta["desc"]` |
| `version` | `ComponentModel.version` | `get_meta().versions` 最新版 | `meta.get("version", "")` |
| `group_name` | `ComponentModel.name`（split 取分组名部分） | `""` | `api_item.get("category", "")` |
| `inputs` | `component_cls.inputs_format()` | `get_meta().data` 中的 inputs | `meta["inputs"]` |
| `outputs` | `component_cls.outputs_format()` | `get_meta().data` 中的 outputs | `meta.get("outputs", [])` |

### 3.3 Schema 数据源说明

**内置插件 (component)：**

- `inputs_format()` 和 `outputs_format()` 来自 bamboo-pipeline 的 `ComponentLibrary.get_component_class(code, version)`
- 返回 `[{key, name, type, required, schema}]` 格式，直接可用
- `outputs_format()` 默认包含系统字段 `_result`、`_loop`、`_inner_loop`，保留在输出中
- 排除 wrapper code：`remote_plugin`、`uniform_api`、`subprocess_plugin`
- `version` 参数直接传给 `get_component_class`，支持指定版本查询

**蓝鲸标准插件 (remote_plugin)：**

- 列表来自 `BKPlugin` 本地 DB 模型
- Schema 来自 `PluginServiceApiClient(code).get_meta()` 远程调用
- meta 返回内容由插件服务定义，提取可用的 inputs/outputs 字段
- 远程调用失败时：`get_plugin_schema` 报错返回；`list_plugins` 中该插件返回空 schema 并在日志记录错误
- `version` 参数不适用（版本由插件服务管理），查询时忽略

**API 插件 (uniform_api)：**

- 列表来自 SpaceConfig → `UniformAPIConfigHandler` 处理后的 `meta_apis` URL 的 GET 请求
- Schema 来自各 API 的 `meta_url` 返回值中的 `inputs` 字段
- `inputs` 已是结构化格式 `{key, name, type, required, desc}`，与目标格式最接近
- 必须通过 `UniformAPIConfigHandler` 处理配置（兼容 v1/v2 schema），不直接读取原始配置
- `version` 参数不适用，查询时忽略

---

## 4. Service Layer 架构

### 4.1 模块位置

```
bkflow/plugin/services/
├── __init__.py
└── plugin_schema_service.py       # PluginSchemaService — 插件列表与 schema 查询
```

`validate_a2flow` 逻辑直接放在 view 函数中（与 `create_template_with_a2flow` 模式一致），不放入 `PluginSchemaService`，因为它与插件查询无共享逻辑。

### 4.2 PluginSchemaService

```python
class PluginSchemaService:
    """统一查询三种插件类型的信息和参数 schema"""

    def __init__(self, space_id, username=None, scope_type=None, scope_id=None):
        self.space_id = space_id
        self.username = username
        self.scope_type = scope_type
        self.scope_id = scope_id

    def list_plugins(self, keyword=None, plugin_type=None, without_detail=True):
        """
        查询空间可用插件列表，聚合三种来源。

        :param keyword: 模糊搜索 code 或 name
        :param plugin_type: 按类型过滤
        :param without_detail: True 只返回摘要，False 返回完整 schema
        :return: (plugins_list, total_count)
        """
        ...

    def get_plugin_schema(self, code, version=None, plugin_type=None):
        """
        查询单个插件的完整 schema。

        :param code: 插件 code
        :param version: 指定版本（仅 component 生效），不传取最新
        :param plugin_type: 消歧用
        :return: 统一格式的插件信息 dict
        :raises: ValueError（插件不存在或 code 歧义）
        """
        ...
```

### 4.3 内部方法划分

```python
class PluginSchemaService:
    # === 公共方法 ===
    def list_plugins(...)
    def get_plugin_schema(...)

    # === 列表查询（各类型） ===
    def _list_component_plugins(self, keyword=None):
        """查询内置插件列表，应用 SpacePluginConfig 过滤"""
        ...

    def _list_remote_plugins(self, keyword=None):
        """查询蓝鲸标准插件列表，应用 BKPluginAuthorization 过滤"""
        ...

    def _list_uniform_api_plugins(self, keyword=None):
        """查询 API 插件列表，从 SpaceConfig + UniformAPIConfigHandler 获取"""
        ...

    # === Schema 提取（各类型） ===
    def _get_component_schema(self, code, version=None):
        """从 ComponentLibrary 提取 inputs_format / outputs_format"""
        ...

    def _get_remote_plugin_schema(self, code):
        """从 PluginServiceApiClient.get_meta() 提取 schema"""
        ...

    def _get_uniform_api_schema(self, code):
        """从 meta_url 提取 schema"""
        ...

    # === 格式转换 ===
    @staticmethod
    def _normalize_plugin_info(raw, plugin_type, with_detail=False):
        """将各类型的原始数据转换为统一格式"""
        ...
```

### 4.4 空间级插件可见性过滤

各类型的过滤规则与现有 `ComponentModelSetViewSet` 和 `BluekingPluginHandler` 保持一致：

| 插件类型 | 过滤规则 |
|---|---|
| component | 排除 wrapper code → 排除 `settings.SPACE_PLUGIN_LIST` 中未授权的 → 应用 `SpacePluginConfig` 的 allow/deny list |
| remote_plugin | 按 `BKPluginAuthorization` 过滤（`status=authorized` + white_list 包含当前 space_id 或 `*`） |
| uniform_api | 空间的 `UniformApiConfig` 配置本身决定了可用的 API 列表 |

### 4.5 list_plugins 中 schema 查询的并发策略

`without_detail=false` 时，remote_plugin 和 uniform_api 的 schema 需要远程调用。使用 `concurrent.futures.ThreadPoolExecutor`：

- `max_workers=5` — 控制并发度，避免瞬间大量外发请求
- 单个 schema 查询失败不影响其他插件 — 失败的返回空 inputs/outputs 并记录日志
- 配合缓存（见第 5 章），大多数请求走缓存不触发远程调用

---

## 5. 缓存策略

### 5.1 缓存范围

使用 Django cache framework，对远程调用结果做短时缓存。

| 缓存数据 | Cache Key | TTL | 说明 |
|---|---|---|---|
| uniform_api 列表 | `plugin_list:uniform_api:{space_id}` | 5 分钟 | 一次 `meta_apis` GET 请求的结果 |
| remote_plugin schema | `plugin_schema:remote_plugin:{code}` | 5 分钟 | `get_meta()` 的完整返回值（全局，不区分 space） |
| uniform_api schema | `plugin_schema:uniform_api:{space_id}:{code}` | 5 分钟 | 单个 API 的 `meta_url` 返回值（区分 space） |
| component schema | 不缓存 | — | 本地 `ComponentLibrary` 内存调用，无 IO 成本 |

remote_plugin 的 cache key 不含 `space_id`，因为插件 schema 是全局的，不随空间变化。

### 5.2 缓存实现

```python
from django.core.cache import cache

PLUGIN_SCHEMA_CACHE_TTL = 300  # 5 分钟

def _get_cached_or_fetch(cache_key, fetch_fn):
    """从缓存获取，未命中则调用 fetch_fn 并缓存结果"""
    result = cache.get(cache_key)
    if result is not None:
        return result
    result = fetch_fn()
    cache.set(cache_key, result, PLUGIN_SCHEMA_CACHE_TTL)
    return result
```

### 5.3 失效策略

- 不做主动失效，依赖 TTL 自然过期
- 插件 schema 变更频率低（通常天级别），5 分钟延迟可接受
- `list_plugins(without_detail=true)` 对 remote_plugin 不触发远程调用（BKPlugin 在本地 DB），不需要 schema 缓存
- `list_plugins(without_detail=false)` 中远程类型的 schema 查询使用 ThreadPoolExecutor 并发 + 缓存

---

## 6. 文件结构

### 6.1 新增文件

```
bkflow/plugin/services/
├── __init__.py
└── plugin_schema_service.py         # PluginSchemaService 服务层

bkflow/apigw/views/
├── list_plugins.py                  # list_plugins APIGW view
├── get_plugin_schema.py             # get_plugin_schema APIGW view
└── validate_a2flow.py               # validate_a2flow APIGW view

bkflow/apigw/serializers/
└── plugin.py                        # ListPluginsSerializer, GetPluginSchemaSerializer, ValidateA2FlowSerializer

bkflow/apigw/docs/zh/
├── list_plugins.md                  # API 文档
├── get_plugin_schema.md             # API 文档
└── validate_a2flow.md               # API 文档

tests/interface/plugin/services/
└── test_plugin_schema_service.py    # 服务层测试

tests/interface/apigw/
├── test_list_plugins.py             # View 层测试
├── test_get_plugin_schema.py        # View 层测试
└── test_validate_a2flow.py          # View 层测试
```

### 6.2 修改文件

```
bkflow/apigw/urls.py                # 注册三个新 URL pattern
```

### 6.3 URL 注册

```python
# bkflow/apigw/urls.py 新增
url(r"^space/(?P<space_id>\d+)/list_plugins/$", list_plugins),
url(r"^space/(?P<space_id>\d+)/get_plugin_schema/$", get_plugin_schema),
url(r"^space/(?P<space_id>\d+)/validate_a2flow/$", validate_a2flow),
```

---

## 7. 权限与装饰器

三个 view 遵循现有 APIGW 模式：

```python
@login_exempt
@csrf_exempt
@require_GET  # 或 @require_POST（validate_a2flow）
@apigw_require
@check_jwt_and_space
@return_json_response
def list_plugins(request, space_id):
    ...
```

权限由 `@apigw_require` + `@check_jwt_and_space` 控制：
- 请求方的 `app_code` 必须与 space 绑定的 `app_code` 一致
- 不需要额外的用户级鉴权（与 `get_template_list` 等只读接口一致）

---

## 8. 错误处理

### 8.1 错误码

使用现有 `err_code` 体系（`bkflow/utils/err_code.py`）：

| 场景 | 使用的 err_code |
|---|---|
| 成功 | `err_code.SUCCESS.code`（0） |
| 参数校验失败 / 插件不存在 / code 歧义 | `err_code.VALIDATION_ERROR.code`（400） |
| 远程调用失败等内部错误 | `err_code.ERROR.code`（500） |

### 8.2 list_plugins 错误处理

| 错误场景 | 处理方式 |
|---|---|
| 参数校验失败 | `@return_json_response` 捕获 `ValidationError`，返回 `{result: false, message: ..., code: 400}` |
| 远程插件 schema 查询失败 | 该插件返回空 inputs/outputs，不影响其他插件，日志记录错误 |
| 空间不存在 / 无权限 | `@check_jwt_and_space` 拦截，返回 HTTP 403 |

### 8.3 get_plugin_schema 错误处理

| 错误场景 | 处理方式 |
|---|---|
| code 不存在 | `{result: false, message: "未找到插件 code 'xxx'", code: 400, data: null}` |
| code 歧义 | `{result: false, message: "...请指定 plugin_type 参数消歧", code: 400, data: null}` |
| 远程 schema 查询失败 | `{result: false, message: "查询插件 schema 失败: ...", code: 500, data: null}` |

### 8.4 validate_a2flow 错误处理

与 `create_template_with_a2flow` 完全一致的模式 — view 函数直接返回错误 dict（不抛异常），确保 `errors` 字段结构被保留：

| 错误场景 | 返回格式 |
|---|---|
| Serializer 校验失败 | `{result: false, errors: [...], code: 400}` |
| Pydantic 校验失败 | `{result: false, errors: [{type: "MISSING_REQUIRED_FIELD", ...}], code: 400}` |
| A2FlowValidationError | `{result: false, errors: [...], code: 400}` |
| A2FlowConvertError | `{result: false, errors: [{type, node_id, field, value, message, hint}], code: 400}` |

---

## 9. 测试策略

### 9.1 服务层测试（test_plugin_schema_service.py）

需要 mock 的外部依赖：
- `ComponentModel.objects` — 内置插件 DB 查询
- `ComponentLibrary.get_component_class()` — 组件类获取
- `BKPlugin.objects` — 蓝鲸插件 DB 查询
- `BKPluginAuthorization.objects` — 授权查询
- `PluginServiceApiClient.get_meta()` — 远程插件 meta
- `SpaceConfig.get_config()` — 空间配置
- `UniformAPIClient.request()` — API 插件远程调用
- `Credential.objects` — 凭证查询
- `django.core.cache` — 缓存

测试用例：
- `test_list_component_plugins` — 内置插件列表 + SpacePluginConfig 过滤
- `test_list_remote_plugins` — 蓝鲸插件列表 + 授权过滤
- `test_list_uniform_api_plugins` — API 插件列表
- `test_list_plugins_keyword_filter` — keyword 模糊搜索 code 和 name
- `test_list_plugins_plugin_type_filter` — 按 plugin_type 过滤
- `test_list_plugins_with_detail` — without_detail=false，含 schema
- `test_list_plugins_without_detail` — without_detail=true，不含 schema
- `test_get_component_schema` — 内置插件 schema 提取
- `test_get_component_schema_with_version` — 指定版本查询
- `test_get_remote_plugin_schema` — 蓝鲸插件 schema 提取
- `test_get_uniform_api_schema` — API 插件 schema 提取
- `test_get_plugin_schema_not_found` — 插件不存在
- `test_get_plugin_schema_ambiguous` — code 歧义
- `test_cache_hit` — 缓存命中不触发远程调用
- `test_cache_miss` — 缓存未命中触发远程调用并写入缓存
- `test_remote_schema_failure_graceful` — 远程 schema 失败时优雅降级

### 9.2 View 层测试

`list_plugins` / `get_plugin_schema` view 测试：
- 参数校验（必填/选填/类型）
- 装饰器链正常工作（mock request 对象）
- 正确调用 PluginSchemaService 并返回标准格式

`validate_a2flow` view 测试：
- 参数校验
- 合法流程校验通过（`test_validate_a2flow_valid`）
- 非法流程返回结构化错误（`test_validate_a2flow_invalid`）
- 走与 `create_template_with_a2flow` 相同的校验路径，直接组装响应

---

## 10. AI Agent 工作流示例

```
用户需求："帮我创建一个流程，先执行脚本，然后发通知"

Agent 执行流程：
1. list_plugins(space_id=1, keyword="脚本", without_detail=true)
   → 发现 job_fast_execute_script (component)

2. list_plugins(space_id=1, keyword="通知", without_detail=true)
   → 发现 bk_notify (component)

3. get_plugin_schema(space_id=1, code="job_fast_execute_script")
   → 获取 inputs: script_content, timeout, ...

4. get_plugin_schema(space_id=1, code="bk_notify")
   → 获取 inputs: title, content, ...

5. 生成 a2flow v2 JSON:
   {
     "version": "2.0",
     "name": "执行脚本并通知",
     "nodes": [
       {"id": "n1", "name": "执行脚本", "code": "job_fast_execute_script",
        "data": {"script_content": "echo hello"}, "next": "n2"},
       {"id": "n2", "name": "发通知", "code": "bk_notify",
        "data": {"title": "完成", "content": "脚本已执行"}, "next": "end"}
     ]
   }

6. validate_a2flow(space_id=1, a2flow_json) → {"valid": true, "version": "2.0"}

7. create_template_with_a2flow(a2flow_json) → 创建模板
```
