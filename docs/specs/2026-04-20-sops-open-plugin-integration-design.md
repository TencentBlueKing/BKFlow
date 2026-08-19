# 标准运维开放插件生态接入 BKFlow 设计

> **Date:** 2026-04-20
> **Status:** Draft
> **Scope:** 本设计描述如何让 BKFlow 以 API 插件方式接入标准运维的内置插件和第三方插件生态。
> **Related:** [BKFlow 设计模式与方案](../../.ai/docs/specs/design-patterns.md)

## 1. 背景

当前 BKFlow 已有三类插件消费能力：

- 内置组件插件（`component`）
- 蓝鲸标准远程插件（`remote_plugin`）
- API 插件（`uniform_api`）

标准运维已有一套更完整的插件生态，既包括内置插件，也包括第三方插件。此前如果希望 BKFlow 直接复用标准运维插件，常见思路是让 BKFlow 直接兼容标准运维插件运行时或上下文语义。但这条路线会让 BKFlow 直接承担标准运维的插件上下文转换、运行模型差异和版本治理复杂度。

本设计选择另一条路线：

- 标准运维对外提供通用的“开放插件目录 + 执行网关”
- BKFlow 不直接对接标准运维插件运行时
- BKFlow 只把标准运维当成一个 API 插件来源，通过现有 `uniform_api` 体系消费

这样可以将标准运维插件生态的异构性收敛在标准运维侧，将 BKFlow 侧保持为统一的插件消费方和治理方。

## 2. 目标与非目标

### 2.1 目标

1. 让 BKFlow 能够使用标准运维的内置插件和第三方插件生态。
2. BKFlow 侧不新增第四种插件运行时，继续复用 `uniform_api` 作为执行壳。
3. 标准运维对外接口命名保持通用，不引入 `bkflow` 语义。
4. 支持同步、轮询、回调三种执行模式。
5. 支持插件业务版本管理，而不只是 `uniform_api` 包装器版本。
6. 为所有插件类型建立统一的本地插件配置快照能力。
7. 通过空间级插件管理控制开放情况，新来源默认关闭，存量空间迁移默认开启。

### 2.2 非目标

1. 不让 BKFlow 直接兼容标准运维插件运行时协议。
2. 不在一期引入标准运维 `project` 语义适配，运行时先只传 BKFlow 原生上下文。
3. 不为标准运维插件单独发明新的 BKFlow 插件类型。
4. 不在迁移中自动将存量模板升级到最新插件版本。

## 3. 关键设计决策

1. BKFlow 将标准运维视为一个 API 插件来源，而不是特殊插件类型。
2. 标准运维对外提供通用的开放插件目录与执行接口，返回体兼容 BKFlow `uniform_api` 消费协议。
3. 标准运维开放插件调用必须在标准运维侧独立 worker 域执行，不与存量任务 worker 混跑。
4. BKFlow 侧新增通用的“开放插件来源 + 空间级插件管理”能力。
5. 一期 BKFlow 到标准运维只传 BKFlow 原生上下文，标准运维负责内部上下文转换。
6. 必须区分 `wrapper_version` 和 `plugin_version`，后者作为业务插件版本的一等概念。
7. BKFlow 必须本地保留插件引用快照与 schema 快照，即使某个插件版本失效，历史模板和任务仍可回看。

## 4. 整体架构

### 4.1 架构边界

整体架构分为两侧：

- BKFlow：开放插件来源消费方、空间治理方、模板与任务编排方
- 标准运维：开放插件目录提供方、执行适配方、上下文转换方、版本治理方

BKFlow 不直接对接标准运维插件服务，也不理解标准运维插件的内部运行差异。所有标准运维侧差异都被收敛在标准运维开放插件层中。

### 4.2 高层数据流

```text
BKFlow 配置开放插件来源
    ↓
BKFlow 读取标准运维开放插件目录
    ↓
空间管理员在 BKFlow 空间级插件管理中控制开放状态
    ↓
用户在模板中按普通 API 插件方式选择标准运维开放插件
    ↓
任务运行时由 BKFlow 走 uniform_api 执行链路
    ↓
标准运维开放执行层接收请求并转调内部插件
    ↓
同步返回 / 轮询查询 / 回调 BKFlow
```

## 5. 标准运维侧设计

### 5.1 对外语义：开放插件目录与执行网关

标准运维对外接口不应带 `bkflow` 语义，而应保持为通用开放层，例如：

- `GET /open-plugins/categories`
- `GET /open-plugins`
- `GET /open-plugins/{plugin_id}`
- `POST /open-plugin-runs`
- `GET /open-plugin-runs/status`
- `GET /open-plugin-runs/{run_id}`

这些接口的命名表达“开放插件目录”和“开放插件运行”，而不是“专门给 BKFlow 用的接口”。  
BKFlow 只是它的一个消费者。

该开放层与标准运维现有面向任务编排、任务查询、任务启动的 APIGW 接口不是同一套语义：

- 现有 APIGW 任务接口继续服务标准运维自身的流程与任务管理
- 本设计新增的开放插件目录与执行网关仅承载“开放插件消费协议”
- 两者可以复用统一网关基础设施，但不应复用为同一资源语义

### 5.2 内部对象模型

标准运维侧需要将内置插件和第三方插件统一抽象成开放对象：

- `OpenPluginDefinition`
  - 统一表示一个被开放给外部消费者的插件定义
- `OpenPluginMetaAdapter`
  - 负责把标准运维内部插件元数据转成开放插件元数据
- `OpenPluginExecutionAdapter`
  - 负责把外部执行请求转成标准运维内部插件调用
- `OpenPluginRun`
  - 表示一次开放插件执行实例

该抽象必须同时适用于：

- 标准运维内置插件
- 标准运维第三方插件

### 5.3 开放插件目录协议

#### 分类接口

分类接口用于向 BKFlow 提供插件分类。  
第一阶段不应只粗分为“内置插件 / 第三方插件”两档，而应尽量透传标准运维内部已有的 `group/category` 分类体系，避免用户在 BKFlow 中面对过粗分类导致选择体验恶化。

来源类型“标准运维内置插件 / 标准运维第三方插件”应作为别名或标签展示，而不应替代分类本身。

#### 列表接口

列表接口需要返回：

- 稳定唯一的 `plugin_id`
- 插件名称
- 来源别名
- 默认版本
- 最新版本
- 可用版本列表概况
- 详情接口定位信息

这里的 `plugin_id` 不应简单复用内部裸 `code`，但也不建议在 BKFlow 内部把命名空间直接拼成 `builtin::code` 一类值。

设计约束：

- 对外 `plugin_id` 作为不透明、URL-safe 的稳定标识使用
- 标准运维侧应同时提供可读的 `plugin_code` 与 `plugin_source`
- BKFlow 内部持久化时，应拆分保存 `plugin_source`、`plugin_code`、`plugin_id`
- 统计、聚合、展示尽量基于拆分字段而不是拼接后的单字符串

#### 详情接口

详情接口必须支持按业务插件版本取 schema，例如：

- `GET /open-plugins/{plugin_id}?version=1.2.0`

返回内容至少包括：

- `plugin_id`
- `plugin_code`
- `plugin_source`
- `plugin_version`
- `name`
- `description`
- `inputs`
- `outputs`
- `dispatch url`
- 轮询或回调所需的元数据

### 5.4 `uniform_api` 协议升级：v4.0.0

现有 `uniform_api v3.0.0` 支持的是包装器版本能力，不支持“业务插件版本”治理。  
因此本方案不能只复用现有协议语义，而必须引入一版面向开放插件来源的协议升级。建议记为 `uniform_api v4.0.0`。

对 BKFlow 而言，`uniform_api v4.0.0` 既是协议版本名，也是节点配置中 `wrapper_version = "v4.0.0"` 的取值，两者一一对应。

#### 5.4.1 升级目标

`uniform_api v4.0.0` 需要支持：

- API 插件业务版本声明
- 按版本获取 detail meta
- 执行请求透传 `plugin_version`
- polling/callback 基于统一 `run_id` 工作
- 保持对现有 v2.0.0 / v3.0.0 来源的兼容

#### 5.4.2 协议变更清单

##### list_meta

现有 `list_meta_api` 中的 `version` 字段语义是 `uniform_api` 包装器版本，不是业务插件版本。  
升级后，列表项需要补充：

- `wrapper_version`
- `default_version`
- `latest_version`
- `versions`
- `meta_url_template` 或支持按 version 查询的 `meta_url`

最小示例：

```json
{
  "result": true,
  "message": "",
  "data": {
    "total": 1,
    "apis": [
      {
        "id": "open_plugin_001",
        "name": "JOB 执行作业",
        "plugin_source": "builtin",
        "plugin_code": "job_execute_task",
        "wrapper_version": "v4.0.0",
        "default_version": "1.2.0",
        "latest_version": "1.3.0",
        "versions": ["1.2.0", "1.3.0"],
        "meta_url_template": "https://bk-sops.example/open-plugins/open_plugin_001?version={version}"
      }
    ]
  }
}
```

##### detail_meta

detail_meta 需要支持按版本查询，例如：

- `GET {meta_url}?version=1.2.0`

同一插件不同版本的：

- inputs schema
- outputs schema
- dispatch url
- polling/callback 元数据

都允许不同。

最小示例：

```json
{
  "result": true,
  "message": "",
  "data": {
    "id": "open_plugin_001",
    "name": "JOB 执行作业",
    "plugin_source": "builtin",
    "plugin_code": "job_execute_task",
    "plugin_version": "1.2.0",
    "wrapper_version": "v4.0.0",
    "url": "https://bk-sops.example/open-plugin-runs",
    "methods": ["POST"],
    "inputs": [],
    "outputs": [],
    "polling": {
      "url": "https://bk-sops.example/open-plugin-runs/status",
      "task_tag_key": "open_plugin_run_id",
      "success_tag": {
        "key": "status",
        "value": "SUCCEEDED",
        "data_key": "data.outputs"
      },
      "fail_tag": {
        "key": "status",
        "value": "FAILED",
        "msg_key": "data.error_message"
      },
      "running_tag": {
        "key": "status",
        "value": "RUNNING"
      }
    }
  }
}
```

##### execute

执行请求体必须显式透传：

- `plugin_id`
- `plugin_version`
- `client_request_id`
- `callback_url`
- `callback_token`
- `timeout_seconds`
- `inputs`
- `context`

##### polling / callback

polling 与 callback 必须围绕统一的 `open_plugin_run_id` 运转：

- 触发响应返回 `open_plugin_run_id`
- polling 默认以 `open_plugin_run_id` 作为 `task_tag`
- callback 必须至少回带 `open_plugin_run_id`

#### 5.4.3 向后兼容策略

- 已有 `uniform_api v2.0.0 / v3.0.0` 来源继续可用
- 如果来源不声明业务版本能力，BKFlow 将其按“单版本插件”处理
- 对标准运维开放插件来源，要求最低支持 `uniform_api v4.0.0`

### 5.5 执行协议

标准运维对外统一暴露执行主入口：

- `POST /open-plugin-runs`

请求至少包含：

- `plugin_id`
- `plugin_version`
- `client_request_id`
- `callback_url`
- `callback_token`
- `timeout_seconds`
- `inputs`
- `context`

其中 `context` 是 BKFlow 原生上下文，不包含标准运维专属高风险语义。

`client_request_id` 是幂等键，必须由 BKFlow 为单次节点触发生成，推荐基于：

- `task_id`
- `node_id`
- `retry_no`

组合生成。

其中 `retry_no` 应表达“本次实际触发意图的序号”：

- 同一触发意图内的超时重试、重复提交，应复用同一个 `client_request_id`
- 若业务语义是“真正再触发一次新的开放插件执行”，则必须递增 `retry_no`
- 幂等策略只负责识别“是否同一次触发意图”，不主动替调用方推断意图

`callback_url` 与 `callback_token` 必须由 BKFlow 在每次 execute 时动态下发，不应假定为标准运维侧固定配置。

这里需要显式说明一条约定：

- 对 BKFlow 而言，标准运维开放插件共享同一条 execute 入口 URL `/open-plugin-runs`
- APIGW 侧只需要注册一条对应资源
- 具体调用哪个开放插件，由请求体中的 `plugin_id + plugin_version` 决定
- 限流、监控、审计等聚合维度不应只按 path 统计，而应结合请求体字段做插件粒度分析

### 5.6 轮询、回调与 ID 映射

#### 5.6.1 统一 polling 映射

为与现有 BKFlow `uniform_api polling` 语义对齐，标准运维开放层默认采用统一 polling 方案：

- 触发响应中返回 `open_plugin_run_id`
- `uniform_api_plugin_polling.task_tag_key = "open_plugin_run_id"`
- `polling.url = /open-plugin-runs/status` 或等价兼容查询入口
- BKFlow 继续按现有 `uniform_api` 协议，将 `task_tag=open_plugin_run_id` 作为 query 参数附加到 polling 请求中

即：

- BKFlow 不直接轮询真实插件状态
- BKFlow 只轮询标准运维开放运行态
- 上述 `polling` 配置由标准运维开放层在 detail_meta 中固定填充，BKFlow 仍按现有 detail_meta 协议读取，不新增绕过 detail_meta 的硬编码
- 若标准运维同时提供 `GET /open-plugin-runs/{run_id}` 形式的通用查询接口，可作为排障或通用开放能力存在，但不应直接作为 BKFlow `polling.url` 示例
- 无论采用兼容 polling 入口还是通用查询入口，标准运维侧都必须校验调用方接入凭证与 `open_plugin_run_id` 的归属关系，不允许跨接入方查询其他来源创建的运行实例

#### 5.6.2 回调映射与双向存储

为支持回调、排障、取消、重放等场景，必须同时保存两侧映射：

标准运维侧至少保存：

- `open_plugin_run_id`
- `bkflow_node_id`
- `callback_url`
- `callback_token`
- `client_request_id`

BKFlow 侧至少保存：

- `task_id`
- `node_id`
- `plugin_id`
- `plugin_version`
- `open_plugin_run_id`
- `client_request_id`

只有这样，标准运维在执行完成后才能稳定回调 BKFlow，而 BKFlow 也能在任务详情、排障与后续扩展场景中找到对应开放执行实例。

#### 5.6.3 幂等要求

`POST /open-plugin-runs` 必须按 `client_request_id` 保证幂等：

- 同一 `client_request_id` 的重复请求，不允许创建多个 `open_plugin_run_id`
- 网络超时重试时，标准运维应返回已存在的执行实例

#### 5.6.4 回调鉴权语义

`callback_token` 不能只是“形式上传”，必须具备明确鉴权语义：

- `callback_token` 由 BKFlow 在每次 execute 时现签现发
- token 至少绑定 `task_id`、`node_id`、`client_request_id`、过期时间等上下文
- 标准运维在回调 BKFlow 节点接口时必须回带该 token
- BKFlow 回调入口必须校验 token 的签名、有效期和与当前节点映射关系是否一致
- token 过期、签名非法或映射不匹配时，BKFlow 应拒绝该回调，并由标准运维按约定重试或最终交由轮询/节点超时兜底

建议补充的实现约束：

- token TTL 应不短于该节点执行超时窗口，并额外预留网络与调度容差
- BKFlow 至少应结合 `client_request_id` 与节点映射关系做重放拒绝或幂等消费
- 如果节点已经进入终态，再收到合法回调时，应按“节点已终态”进行幂等处理，不再产生新的状态副作用
- 标准运维开放层应维护 `callback_url` 域白名单，对不在白名单内的 `callback_url` 拒绝执行

是否进一步做一次性消费或 nonce 级重放保护，可在实现阶段根据现有回调基础设施落细，但不能省略签发与校验本身。

### 5.7 运行态统一抽象与 BKFlow 状态映射

标准运维需要将内置插件和第三方插件的差异统一抽象成开放运行态，例如：

- `CREATED`
- `RUNNING`
- `WAITING_CALLBACK`
- `SUCCEEDED`
- `FAILED`

对 BKFlow 暴露的执行语义统一为：

- 同步完成
- 轮询中
- 等待回调

BKFlow 不应感知标准运维内部真实插件是如何实现这些状态的。

建议明确运行态映射表：

| 标准运维开放态 | BKFlow 行为 | 说明 |
|---|---|---|
| `CREATED` | 进入 schedule | 已创建运行实例，尚未终态 |
| `RUNNING` | 继续轮询 | 仍由 BKFlow 按 polling 配置查询 |
| `WAITING_CALLBACK` | 停止轮询，等待回调 | BKFlow 节点保持 schedule 状态 |
| `SUCCEEDED` | `finish_schedule()` | 节点结束 |
| `FAILED` | 节点失败 | 写入错误信息 |

超时治理建议：

- 标准运维侧可在内部超时后主动回调失败
- BKFlow 侧仍保留节点级 timeout 作为最终兜底

取消治理建议：

- BKFlow 侧若发生节点取消、任务暂停后强制结束等动作，应支持 best-effort 通知标准运维取消对应 `open_plugin_run_id`
- 标准运维开放层建议补充取消接口或内部取消能力
- 若标准运维取消失败，不应阻塞 BKFlow 本地状态流转，但必须记录审计与排障信息

### 5.8 部署与执行隔离

标准运维开放插件调用必须进入独立 worker 域，而不是与标准运维存量任务执行 worker 混跑。

建议新增独立执行域，例如：

- `open_plugin_dispatch`
- `open_plugin_polling`
- `open_plugin_callback`

建议部署独立 worker 组，例如：

- `sops-open-plugin-worker`

隔离原则按“调用来源”划分，而不是按“插件类型”划分。  
无论是标准运维内置插件还是第三方插件，只要它是通过开放插件层暴露给 BKFlow 的调用，都优先由开放插件 worker 域承接。

部署约束进一步明确为：

- 开放插件 worker 与标准运维现有任务 worker 共享同一套标准运维应用代码与依赖镜像
- 标准运维内置插件由开放插件 worker 直接调用内部实现
- 标准运维第三方插件仍通过既有插件服务调用，不要求在开放插件 worker 中加载第三方插件代码包
- 一期不做业务插件版本级进程隔离，多版本差异由开放目录、schema 和执行适配层管理

## 6. BKFlow 侧设计

### 6.1 开放插件来源

BKFlow 侧新增通用“开放插件来源”概念，不将标准运维硬编码为唯一特殊来源。

每个来源至少包含：

- `source_key`
- `display_name`
- `category_api`
- `list_meta_api`
- `detail_meta_api` 路由规则
- 认证配置
- 来源别名

标准运维是该能力的一个实例，而不是例外。

BKFlow 不应在每次列表展示或服务端校验时都直连来源接口。
因此开放插件来源除远端配置外，还应配套本地目录索引，用于：

- 列表展示与空间开关查询
- 模板保存、创建任务、启动任务时的服务端校验
- 目录变更后对失效插件的判定与标记

### 6.2 空间级插件管理

BKFlow 需要引入独立的空间级插件管理能力，用于控制 API 插件开放情况。  
这层能力不应简单复用只控制画布展示的 `space_plugin_config`。

与现有能力的边界明确如下：

- 现有 `space_plugin_config`
  - 继续保留
  - 仅用于内置插件展示过滤
  - 不承担开放插件执行治理
- 新的开放插件管理能力
  - 与 `space_plugin_config` 并存
  - 专门控制开放插件来源下的 API 插件是否可配置、可执行
  - 需要同时作用于展示层和服务端校验层

空间级插件管理至少支持：

- 按空间查看该来源下的开放插件列表
- 单个插件开启/关闭
- 一键全开
- 以统一的 `enabled` 状态同时控制该插件在当前空间下是否可配置、可执行

一期控制粒度明确为：

- 以 `plugin_id` 为粒度进行空间开放控制
- 不在一期引入 `(plugin_id, plugin_version)` 级开关
- 某插件已开放后，其可选版本由来源返回的 `available_versions` 决定

服务端必须在以下环节做校验，而不只是前端隐藏：

- 查询空间可用插件列表
- 保存模板
- 创建任务
- 启动任务

建议新增独立存储，例如：

- `SpaceOpenPluginAvailability`
  - `space_id`
  - `source_key`
  - `plugin_id`
  - `enabled`
  - `create_time`
  - `update_time`

同时建议新增来源目录本地索引，例如：

- `OpenPluginCatalogIndex`
  - `source_key`
  - `plugin_id`
  - `plugin_source`
  - `plugin_code`
  - `display_name`
  - `default_version`
  - `latest_version`
  - `available_versions`
  - `status`
  - `last_sync_time`

### 6.3 默认开放策略

- 新接入来源时，插件默认全关闭
- 存量空间迁移时，默认全开启

这样可兼顾：

- 新来源按保守原则引入
- 存量空间升级不出现“原有能力突然全部不可用”
- “一键全开”仅作用于当前已发现的插件，不改变后续目录变更的默认策略

迁移落库规则建议明确为：

- 为存量空间扫描来源下当前可发现的全部 `plugin_id`
- 在 `SpaceOpenPluginAvailability` 中批量写入 `enabled=true`
- 后续新增插件默认不自动写入为开启

#### 6.3.1 目录变更同步策略

来源目录并非一次性静态数据，后续变更策略应明确：

- 来源后续新增插件：
  - 写入 `OpenPluginCatalogIndex`
  - 对所有空间默认视为 `enabled=false`
- 来源下线插件：
  - 保留 `SpaceOpenPluginAvailability` 历史记录
  - 在目录索引中将插件状态标记为 `unavailable`
  - 模板与任务按快照继续回看，但不可继续新用
- 来源更名但 `plugin_id` 不变：
  - 视为同一插件的元数据更新
- 来源改变 `plugin_id`：
  - 视为新插件，不做自动继承开启状态

#### 6.3.2 目录本地索引与同步策略

为避免展示、校验和执行前检查都强依赖远端接口，BKFlow 需要维护来源目录本地索引：

- 通过定时全量同步或带缓存的拉取刷新 `OpenPluginCatalogIndex`
- 远端短时不可用时，允许基于最近一次成功同步结果继续进行展示和只读判断
- 对模板保存、创建任务、启动任务等强校验动作，应优先使用本地索引判断插件与版本是否仍可用
- 对需要最新 schema 的场景，再按需访问远端 detail_meta

### 6.4 用户体验

一期用户在 BKFlow 中仍然按普通 API 插件方式使用标准运维开放插件：

- 选择分类
- 选择插件
- 动态渲染表单
- 保存模板
- 创建并执行任务

不新增新的插件类型。  
来源信息通过插件别名体现，例如：

- `[标准运维内置插件] xxx`
- `[标准运维第三方插件] xxx`

### 6.5 执行链路

BKFlow 运行时继续复用 `uniform_api` 执行链路，但对标准运维开放插件来源应使用升级后的 `uniform_api v4.0.0` 协议，不新增“标准运维插件专属执行器”。

任务运行时：

- 发送用户填写的业务参数
- 附带 BKFlow 原生上下文
- 接收同步、轮询或回调结果

一期上下文仅包括：

- `space_id`
- `scope_type`
- `scope_value`
- `operator`
- `task_id`
- `task_name`
- 以及必要的节点运行信息

如果后续验证 BKFlow 原生上下文不足以支撑标准运维内部映射，再补充更强语义。

### 6.6 上下文不足的回退策略

一期明确不从 BKFlow 运行时透传标准运维 `project` 语义，但标准运维内置插件中存在大量依赖 `project` 的场景。  
因此必须补一套回退策略，避免工程链路打通后实际插件大面积执行失败。

第一阶段建议采用组合策略：

1. 标准运维开放来源支持来源级或插件级 `default_project_id` 配置
   - 该配置存在于标准运维开放层，不由 BKFlow 运行时传入
2. 对强依赖 `project` 且无默认映射能力的插件，不纳入一期开放白名单
3. BKFlow 与标准运维联调验收时，显式区分：
   - 可直接开放的插件
   - 依赖 `default_project_id` 才能开放的插件
   - 一期不开放的插件

若无法满足上述前提，应将“覆盖范围受 `project` 语义限制”作为一期范围约束，而不是对用户宣称全量内置插件可用。

同时需要明确一个非目标边界：

- 一期不透传用户级凭证或用户级委托身份
- 用户在标准运维侧的鉴权能力，由开放层与接入方凭证体系整体约定，不在本设计范围内单独解决
- 若某些内置插件或第三方插件强依赖用户级凭证，应纳入“一期不开放”白名单

### 6.7 与现有三类插件的关系

| 类型 | 运行时 | 发现方式 | 是否新增类型 |
|---|---|---|---|
| `component` | BKFlow 内置 | ComponentLibrary / DB | 否 |
| `remote_plugin` | 蓝鲸标准远程插件协议 | BKPlugin + 插件服务 | 否 |
| `uniform_api`（普通） | HTTP API 协议 | 来源 meta APIs | 否 |
| `uniform_api`（标准运维开放来源） | HTTP API 协议 + 标准运维开放层 | 标准运维开放目录 | 否 |

结论：

- 标准运维开放插件在 BKFlow 中仍属于 `uniform_api` 来源实例
- 因此不需要新增第四种插件类型

## 7. 版本管理设计

### 7.1 两类版本分离

必须区分两类版本：

- `wrapper_version`
  - 表示 BKFlow `uniform_api` 组件版本，例如 `v4.0.0`
- `plugin_version`
  - 表示标准运维开放插件自身业务版本

这两者不能混用。  
当前 BKFlow `uniform_api` 已支持的是前者，而本设计新增的是后者的一等治理能力。

对标准运维开放插件来源而言，`uniform_api v4.0.0` 与节点中的 `wrapper_version = "v4.0.0"` 是同一件事在协议与持久化层的两种表达，不应分叉解释。

### 7.2 标准运维开放协议的多版本能力

标准运维开放目录需要支持：

- 声明默认版本
- 声明最新版本
- 返回可用版本列表
- 按指定版本获取插件详情 schema

执行接口也必须显式带上 `plugin_version`，以保证实际运行版本与模板选择版本一致。

### 7.3 BKFlow 节点中的插件版本

BKFlow 节点配置中需要明确保存：

- `plugin_type`
- `plugin_source`
- `plugin_code` 或 `plugin_id`
- `plugin_version`
- `wrapper_code`
- `wrapper_version`
- `plugin_display_name`

该能力应尽量统一适用于所有插件类型，而不只针对 API 插件。

## 8. 插件快照设计

### 8.1 快照目标

BKFlow 本地必须保留插件引用快照与 schema 快照，以支持：

- 历史模板回看
- 历史任务回看
- 插件版本失效后的可解释性

### 8.2 快照内容

每个节点至少保留两层信息：

#### 插件引用快照

- `plugin_type`
- `plugin_source`
- `plugin_code` 或 `plugin_id`
- `plugin_version`
- `wrapper_code`
- `wrapper_version`

#### 插件 schema 快照

- `name`
- `group_name`
- `description`
- `inputs`
- `outputs`
- 来源别名
- `version_note`
- `schema_protocol_version`

其中：

- `schema_protocol_version` 由 BKFlow 在写入模板/任务快照时负责填充
- 该字段表示“BKFlow 插件 schema 快照渲染协议版本”，而不是业务插件版本
- 一期建议采用稳定字符串版本值，例如 `bkflow_plugin_schema_snapshot/v1`
- 新版 BKFlow 渲染历史快照时，必须优先按快照中记录的 `schema_protocol_version` 做兼容渲染与只读展示，不得在读取时强制升级快照结构

### 8.3 失效版本行为

当某个插件版本失效时：

- 历史模板和任务仍然可以查看该版本的快照配置
- 不允许继续基于该失效版本修改并保存模板
- 不允许基于该失效版本新建任务
- 用户只能切换到当前可用版本

这意味着系统至少要区分两类版本状态：

- `available`
- `unavailable`

### 8.4 快照写入时机与现有快照关系

插件快照不建议引入与模板快照、任务快照并列的第四套独立快照对象，而应嵌入现有快照体系：

- 模板保存或发布时
  - 在模板 `pipeline_tree` 快照中写入插件引用快照和 schema 快照
- 任务创建时
  - 从模板快照复制到 `TaskSnapshot`
  - 同时固化到 `TaskExecutionSnapshot`

这样可以保证：

- 模板视图与任务视图看到的是同一份插件快照语义
- 任务执行时不再依赖运行期去重新拉取插件 schema

### 8.5 失效版本的升级辅助

失效版本处理不能只做到“禁止修改”，还需要提供升级辅助能力：

- UI 在发现 `unavailable` 版本时，必须展示当前可用版本列表
- UI 应尽量展示目标版本与当前快照之间的字段差异
- 支持用户将节点切换到指定可用版本，再决定是否手动修正参数

系统不自动迁移业务参数，但必须提供足够的升级辅助，避免用户在失效版本上完全卡死。

## 9. 端到端数据流

### 9.1 来源接入

BKFlow 平台先配置标准运维开放插件来源，对接其开放插件目录接口。

### 9.2 空间开放

来源配置完成后，空间级插件管理中出现该来源下的插件。  
新来源默认全部关闭，空间管理员可逐个开启或一键全开。  
存量空间迁移后默认开启。

### 9.3 模板配置

用户按普通 API 插件方式：

- 选择分类
- 选择插件
- 选择业务插件版本
- 填写参数
- 保存模板

### 9.4 任务执行

任务运行时，BKFlow 通过 `uniform_api` 组件发起执行请求，携带：

- 用户填写的业务参数
- BKFlow 原生上下文
- 选中的 `plugin_version`

### 9.5 异步回传

- 同步模式：直接返回结果
- 轮询模式：按开放运行态查询接口继续轮询
- 回调模式：标准运维在内部执行完成后，使用 BKFlow 在本次 execute 中动态下发的 `callback_url` 与 `callback_token` 回调 BKFlow 节点接口

## 10. 异常处理

### 10.1 目录异常

- 分类接口失败
- 列表接口失败
- 详情接口失败

处理要求：

- 仅影响该来源
- 不影响 BKFlow 其它插件来源
- UI 明确提示来源不可用

### 10.2 版本异常

- 指定版本不存在
- 版本已下线
- 返回的版本列表为空

处理要求：

- 模板编辑态标记版本失效
- 新建任务时拒绝使用失效版本
- 历史模板与任务继续只读回看快照

### 10.3 快照异常

- 老模板缺少插件 schema 快照
- 迁移不完整导致快照缺失

处理要求：

- 至少允许展示基础引用信息
- 明确提示快照不完整
- 禁止继续在缺少快照的旧版本上进行编辑保存
- 如果来源当前仍能返回该版本 schema，可提供一次性“补拉并修复快照”能力

### 10.4 输出体异常

开放插件的 `outputs` 可能非常大，尤其第三方插件可能返回长日志或批量结果。
因此标准运维开放层与 BKFlow 回调/轮询协议应明确输出体大小边界：

- 对单次 polling / callback 返回体设置上限
- 超出上限时允许截断非关键大字段，或改为外部存储引用
- 截断行为必须在结果中显式标记，避免用户误以为拿到的是完整输出

## 11. 迁移与升级策略

### 11.1 协议升级策略

采用兼容升级，不做硬切：

- 对端若支持多版本协议，则走完整版本治理逻辑
- 对端若暂不支持多版本协议，则退化成单版本插件处理

对标准运维开放插件来源而言：

- 目录与执行协议最低要求为 `uniform_api v4.0.0`
- BKFlow 自身仍需兼容旧版普通 API 插件来源

### 11.2 存量模板迁移

迁移时只做：

- 补齐 `plugin_version`
- 补齐插件引用快照
- 补齐 schema 快照

对于历史上没有 `plugin_version` 的节点：

- 优先取来源返回的 `default_version`
- 若来源不支持多版本，则写入逻辑单版本标识

迁移时不做：

- 自动升级到最新业务插件版本
- 重写用户业务参数

### 11.3 存量任务迁移

任务侧遵循执行快照优先原则：

- 已创建任务以执行快照为准
- 不受后续插件目录变更影响
- 历史任务始终可以回看当时执行配置

### 11.4 模板与任务的治理边界

- 模板受当前版本可用性治理
- 任务受创建时执行快照保护

这是版本治理中的一个明确边界，不可混淆。

## 12. 测试与验收

### 12.1 标准运维侧验收

至少验证：

- 目录接口可稳定返回分类、列表、详情
- 内置插件和第三方插件都能统一暴露
- 可声明多个业务版本
- 执行支持同步、轮询、回调三种模式
- 开放插件调用运行在独立 worker 域
- 不影响标准运维原有任务执行链路

### 12.2 BKFlow 侧验收

至少验证：

- 可配置开放插件来源
- 可在空间级插件管理中控制开放状态
- 新来源默认关闭，存量空间迁移默认开启
- 模板节点能保存业务插件版本
- 模板和任务能保留插件快照
- 失效版本可回看但不可继续新用

### 12.3 联调验收

至少覆盖：

- 正常链路：接入来源、开启插件、保存模板、创建任务、执行成功
- 异步链路：同步、轮询、回调三种模式
- 版本链路：版本选择、版本下线、历史模板回看、切换新版本
- 异常链路：目录失败、执行失败、回调失败、版本失效、快照缺失

### 12.4 关键验收补充

必须额外覆盖：

- `client_request_id` 幂等：BKFlow 重试不会在标准运维侧生成重复执行
- `open_plugin_run_id ↔ bkflow_node_id` 映射：轮询、回调、排障都可追踪
- `WAITING_CALLBACK` 态：BKFlow 不继续轮询，而是稳定等待回调
- `callback_token` 鉴权：过期、非法签名、映射不一致的回调都会被拒绝
- 强依赖 `project` 的插件：按白名单或 `default_project_id` 策略验收

### 12.5 回归验收

必须验证：

- 现有普通 API 插件能力不受影响
- 现有 `uniform_api v3.0.0` 的同步、轮询、回调能力不回退
- 现有非标准运维来源的 API 插件无需改造即可继续工作
- 模板快照、任务快照和节点配置快照相关能力保持兼容

## 13. 风险与后续关注点

1. 标准运维开放层是否能稳定抽象内置插件与第三方插件的多版本 schema。
2. 业务插件版本语义接入后，BKFlow 现有插件查询协议是否需要统一上提为“全插件统一版本协议”。
3. 插件快照能力若只先覆盖 API 插件，后续统一推广到其它插件类型时可能产生二次迁移成本，因此建议一期就按全插件统一抽象设计。
4. 一期运行时只传 BKFlow 原生上下文，如果标准运维内部映射证明不够，需要在后续迭代中补充更强语义，但应保持与项目级“可信语义设计范式”一致。
5. BKFlow 现有按 `plugin_code` 聚合的统计口径，在接入开放插件来源后需要扩展到至少 `(plugin_source, plugin_code, plugin_version)` 维度，避免不同来源同 code 或同 code 跨版本出现统计混淆。

## 14. 实施阶段建议

### 14.1 P0：协议与最小闭环

必须先完成，否则方案无法落地：

1. 标准运维开放目录与执行网关最小实现
2. `uniform_api v4.0.0` 协议升级
3. `open_plugin_run_id ↔ bkflow_node_id` 映射与幂等机制
4. 标准运维开放插件独立 worker 域

### 14.2 P1：BKFlow 消费与治理

在 P0 完成后推进：

1. BKFlow 开放插件来源配置
2. BKFlow 空间级插件管理
3. 模板保存、创建任务、启动任务的服务端治理校验
4. 存量空间迁移默认开启

### 14.3 P2：版本治理与快照增强

在 P1 可用后推进：

1. BKFlow 业务插件版本治理
2. 模板/任务插件快照补强
3. 失效版本展示与升级辅助
4. 存量模板与任务版本补齐迁移

### 14.4 MVP 范围

若需要先落一个最小可上线版本，建议 MVP 范围为：

- P0 全量能力
- P1 中与可上线闭环直接相关的子集：
  - BKFlow 来源接入
  - 空间级插件管理
  - 模板保存、创建任务、启动任务的服务端治理校验
  - 存量空间迁移默认开启
- 同步 / 轮询 / 回调闭环
- 一期插件白名单

MVP 需要具备 `plugin_version` 的协议透传与节点持久化能力，因为这属于 `uniform_api v4.0.0` 的基础协议要求；但不要求同时交付完整的版本治理 UI 与失效版本升级辅助。

以下能力可在 MVP 之后增强：

- 业务版本治理 UI
- 更细的版本差异展示
- 失效版本升级辅助 UI
- 更强的标准运维上下文映射能力
