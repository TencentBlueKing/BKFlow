# BKFlow 插件体系架构

> 本文档描述 BKFlow 的插件设计、调用协议和执行架构。
> 适用于理解插件开发规范、调试插件执行问题、以及扩展新插件类型。

## 架构概览

BKFlow 的插件体系建立在三层框架之上：

```
┌─────────────────────────────────────────────────────────┐
│  BKFlow Application Layer                               │
│  ┌───────────────────────────────────────────────────┐  │
│  │ BKFlowBaseService (模板方法 + Span 追踪)          │  │
│  │   ├── ApproveService                              │  │
│  │   ├── UniformAPIService                           │  │
│  │   ├── HttpRequestService                          │  │
│  │   ├── PauseService                                │  │
│  │   └── ...                                         │  │
│  └───────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  pipeline Framework Layer                               │
│  ┌──────────────────┐  ┌────────────────────────────┐  │
│  │ Service (ABC)     │  │ Component (注册/发现)      │  │
│  │ ServiceActivity   │  │ ComponentMeta (元类注册)   │  │
│  └──────────────────┘  └────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  bamboo_engine Layer                                    │
│  ┌──────────────────┐  ┌────────────────────────────┐  │
│  │ Engine (调度核心) │  │ BambooDjangoRuntime (桥接) │  │
│  │ Handler (节点处理)│  │ ScheduleType / State       │  │
│  └──────────────────┘  └────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**职责划分：**

| 层级 | 职责 |
|------|------|
| **bamboo_engine** | 流程引擎核心：进程管理、状态机、调度循环、回调分发 |
| **pipeline** | 插件协议定义：Service 基类、Component 注册、ServiceActivity 适配、ScheduleType 推导 |
| **BKFlow** | 业务插件实现：BKFlowBaseService 模板方法、Span 追踪、Mock 模式、具体插件逻辑 |

## 插件组成协议

每个插件由一对类组成：**Service**（执行逻辑）和 **Component**（注册元数据）。

### Service 类

继承 `BKFlowBaseService`，实现业务逻辑：

```python
class ApproveService(BKFlowBaseService):
    plugin_name = "approve"           # Span 名称标识
    __need_schedule__ = True          # 声明需要调度
    # interval = StaticIntervalGenerator(0)  # 不设置 = CALLBACK 类型

    def plugin_execute(self, data, parent_data):
        """同步执行阶段，发起外部调用"""
        ...
        return True  # 成功

    def plugin_schedule(self, data, parent_data, callback_data=None):
        """调度/回调阶段，处理异步结果"""
        ...
        self.finish_schedule()  # 标记调度完成（必须！）
        return True
```

### Component 类

声明插件元数据，通过 `ComponentMeta` 元类自动注册到全局 `ComponentLibrary`：

```python
class ApproveComponent(Component):
    name = _("审批")                    # 显示名称
    code = "bk_approve"                # 唯一标识
    bound_service = ApproveService     # 绑定的 Service 类
    version = "v1.0"                   # 版本号
    form = "...approve/v1_0.js"        # 前端表单路径
```

注册发生在模块导入时，`ComponentMeta.__new__` 自动调用
`ComponentLibrary.register_component(code, version, cls)`。

## 插件生命周期

### 整体调用流程

```
用户发起任务启动
    │
    ▼
TaskOperation.start()
    ├── 构建 root_pipeline_data（TaskContext → parent_data）
    ├── 创建 execution span（注入 _trace_id, _parent_span_id）
    └── bamboo_engine_api.run_pipeline()
         │
         ▼
    Engine 遍历流程节点
         │
         ▼
    ServiceActivityHandler.execute()
    ├── runtime.get_service(code, version) → ServiceWrapper
    ├── service.execute(data, root_pipeline_data)
    │   └── BKFlowBaseService.execute()    ← 模板方法
    │       ├── _start_plugin_span()       ← 记录 Span 起始
    │       ├── plugin_method_span("execute")
    │       │   └── plugin_execute()       ← 子类实现
    │       └── 判断是否需要 schedule
    │
    ├── [need_schedule=True] → 创建 Schedule 对象
    │   └── 等待轮询或回调
    │
    └── [need_schedule=False] → 节点完成
         └── _end_plugin_span(success=True)

回调到达 / 轮询触发
    │
    ▼
ServiceActivityHandler.schedule()
    ├── service.schedule(data, root_pipeline_data, callback_data)
    │   └── BKFlowBaseService.schedule()   ← 模板方法
    │       ├── plugin_method_span("schedule")
    │       │   └── plugin_schedule()      ← 子类实现
    │       └── 判断 schedule 是否结束
    │           ├── [失败] → _end_plugin_span(success=False)
    │           └── [finish_schedule() 已调用] → _end_plugin_span(success=True)
    │
    └── 引擎根据 ScheduleType 决定后续行为
```

### execute 阶段

由 `BKFlowBaseService.execute()` 模板方法驱动：

1. 检查 Mock 模式 → 走 `mock_execute()` 短路
2. 调用 `_start_plugin_span()` 记录插件 Span 起始信息
3. 在 `plugin_method_span("execute")` 上下文内执行 `plugin_execute()`
4. 根据返回值决定后续：
   - `False` → 执行失败，立即结束插件 Span
   - `True` 且无需 schedule → 执行成功，立即结束插件 Span
   - `True` 且需要 schedule → 插件 Span 保持开启，等待 schedule 完成

### schedule 阶段

由 `BKFlowBaseService.schedule()` 模板方法驱动：

1. 检查 Mock 模式
2. 在 `plugin_method_span("schedule")` 上下文内执行 `plugin_schedule()`
3. 根据返回值和 `is_schedule_finished()` 决定：
   - `False` → 调度失败，结束插件 Span
   - `True` 且 `is_schedule_finished()` → 调度完成，结束插件 Span
   - `True` 且非 `is_schedule_finished()` → 中间状态，继续等待下次调度

## 调度类型（ScheduleType）

插件通过类属性声明调度行为，`pipeline.eri.imp.service.ServiceWrapper.schedule_type()` 推导调度类型：

```
need_schedule() == False  ──→  None（无需调度）
       │ True
       ▼
interval is not None  ────→  POLL（轮询）
       │ None
       ▼
multi_callback_enabled()
  False ──→  CALLBACK（单次回调）
  True  ──→  MULTIPLE_CALLBACK（多次回调）
```

### 三种调度类型的引擎行为

| 类型 | 触发方式 | 完成条件 | 引擎行为 |
|------|---------|---------|---------|
| **POLL** | 引擎定时触发 | `schedule()` 返回 True 且 `is_schedule_done()` 为 True | 持续轮询直到完成或失败 |
| **CALLBACK** | 外部 HTTP 回调触发 | `schedule()` 返回 True（引擎自动完成） | **回调成功即完成，不检查 `is_schedule_done()`** |
| **MULTIPLE_CALLBACK** | 外部 HTTP 回调触发（可多次） | `schedule()` 返回 True 且 `is_schedule_done()` 为 True | 支持多次回调，直到插件声明完成 |

> **关键区别：** 对于 CALLBACK 类型，bamboo_engine 在 `schedule()` 返回 True 时直接
> 调用 `_finish_schedule()` 完成节点，不检查 `is_schedule_done()`。但 BKFlow 的
> `BKFlowBaseService.schedule()` 依赖 `is_schedule_finished()` 来触发 `_end_plugin_span()`，
> 因此 **CALLBACK 类型插件也必须调用 `self.finish_schedule()`**，否则插件 Span 不会被创建。

### 各插件调度配置一览

| 插件 | `__need_schedule__` | `interval` | 推导类型 | `finish_schedule()` 时机 |
|------|---------------------|------------|---------|-------------------------|
| approve | True | 无 | CALLBACK | 审批结果回调后 |
| pause | True | 无 | CALLBACK | 收到回调数据后 |
| subprocess_plugin | True | 无 | CALLBACK | 收到子流程结果后（调度开头即调用） |
| http | True | `StaticIntervalGenerator(0)` | POLL | HTTP 请求成功后 |
| sleep_time | True | `StaticIntervalGenerator(0)` | POLL | 定时到达后 |
| uniform_api v2/v3 | True | `StepIntervalGenerator(0)` | POLL | 终态成功路径（trigger/polling/callback 三种子模式） |
| remote_plugin | 动态设置 | `StepIntervalGenerator()` | POLL | 远程插件状态为 SUCCESS 时 |

## 数据流

### parent_data 的构建

`parent_data`（即 `root_pipeline_data`）在任务启动时构建，作为所有节点的共享上下文：

```
TaskOperation.start()
    │
    ├── get_pipeline_context(task_instance)
    │   └── get_task_context(task_instance)
    │       └── TaskContext(task_instance).__dict__
    │           ├── task_id          ← TaskInstance.id
    │           ├── task_space_id    ← TaskInstance.space_id
    │           ├── task_scope_type  ← TaskInstance.scope_type
    │           ├── task_scope_value ← TaskInstance.scope_value
    │           ├── executor         ← TaskInstance.executor
    │           ├── operator         ← TaskInstance.executor
    │           ├── task_name        ← TaskInstance.name
    │           ├── task_start_time  ← 当前时间
    │           ├── is_mock          ← create_method == "MOCK"
    │           └── [custom_context] ← extra_info.custom_context 展开
    │
    ├── 注入 trace context（ENABLE_OTEL_TRACE 时）
    │   ├── _trace_id          ← execution span 的 trace_id
    │   └── _parent_span_id    ← execution span 的 span_id
    │
    └── bamboo_engine_api.run_pipeline(root_pipeline_data=...)
```

### data 对象（节点私有数据）

每个节点有独立的 `data` 对象，由插件 Component 的输入输出定义：

- `data.inputs`：节点输入参数（来自用户配置 + 流程变量渲染）
- `data.outputs`：节点输出参数（插件运行时写入）

### callback_data 的传递链路

```
外部系统 HTTP POST → bkflow/interface/views.callback
    → 解密 token → 提取 node_id, callback_data
    → TaskNodeOperation.callback(data=callback_data)
    → bamboo_engine_api.callback(node_id, version, data)
    → Engine.callback → runtime.set_callback_data(data_id)
    → Engine.schedule → runtime.get_callback_data(data_id)
    → ServiceActivityHandler.schedule(callback_data=...)
    → ServiceWrapper.schedule(callback_data.data)
    → BKFlowBaseService.schedule(callback_data=...)
    → plugin_schedule(data, parent_data, callback_data)
```

## Span 追踪体系

### Span 层级结构

```
bkflow.task.start                          ← 任务操作 Span
  └── bkflow.execution                     ← 执行级根 Span（立即结束，仅作 parent）
       ├── bkflow.plugin.approve           ← 插件 Span（覆盖完整生命周期）
       │    ├── bkflow.plugin.approve.execute   ← 方法 Span
       │    └── bkflow.plugin.approve.schedule  ← 方法 Span
       ├── bkflow.plugin.notify            ← 另一个插件
       │    └── bkflow.plugin.notify.execute
       └── bkflow.plugin.uniform_api
            ├── bkflow.plugin.uniform_api.execute
            ├── bkflow.plugin.uniform_api.schedule  (schedule_count=1)
            └── bkflow.plugin.uniform_api.schedule  (schedule_count=2)
```

### Span 创建机制

插件 Span 采用"延迟创建"策略，适配跨进程、跨 schedule 调用的场景：

```
execute() 阶段：
  start_plugin_span() ──→ 仅记录元信息到 data.outputs
    ├── _plugin_span_start_time_ns  ← 开始时间
    ├── _plugin_span_name           ← "bkflow.plugin.{plugin_name}"
    ├── _plugin_span_trace_id       ← 继承的 trace_id
    ├── _plugin_span_parent_span_id ← execution span 的 span_id
    ├── _plugin_span_id             ← 预生成的 span_id（随机 64bit）
    └── _plugin_span_attributes     ← 序列化的属性

  plugin_method_span("execute") ──→ 立即创建并结束
    parent = plugin_span_id（优先）或 parent_span_id（fallback）

schedule() 阶段（可能跨进程）：
  plugin_method_span("schedule") ──→ 立即创建并结束
    parent = plugin_span_id（从 data.outputs 恢复）

完成时：
  end_plugin_span() ──→ 用预生成的 plugin_span_id 创建实际 Span
    ├── _create_span_with_custom_id()  ← 使用 _CustomSpan 精确还原 span_id
    └── fallback: tracer.start_span()  ← SDK 默认方式（span_id 不匹配但不丢失）
```

**为什么延迟创建？**
因为插件 Span 的生命周期可能跨多个 celery 任务（execute 在一个 worker，schedule 在另一个 worker），
无法在内存中保持一个打开的 Span 对象。通过 `data.outputs` 持久化元信息，在最终 `end_plugin_span()`
时一次性创建完整 Span。

### 插件开发者的 Span 契约

基类 `BKFlowBaseService` 自动处理 Span 的创建和结束，插件开发者只需：

1. 设置 `plugin_name` 类属性
2. 可选覆盖 `_get_span_attributes()` 添加自定义属性
3. **在 `plugin_schedule()` 的最终成功路径上调用 `self.finish_schedule()`**
4. 可选设置 `enable_plugin_span = False` 禁用追踪

## 插件开发规范

### 最小实现模板

**仅 execute（同步插件）：**

```python
class MyService(BKFlowBaseService):
    plugin_name = "my_plugin"

    def plugin_execute(self, data, parent_data):
        result = do_something(data.get_one_of_inputs("param"))
        data.set_outputs("result", result)
        return True

class MyComponent(Component):
    name = "我的插件"
    code = "my_plugin"
    bound_service = MyService
    version = "v1.0"
```

**execute + 轮询（POLL）：**

```python
class MyPollingService(BKFlowBaseService):
    plugin_name = "my_polling"
    __need_schedule__ = True
    interval = StaticIntervalGenerator(10)  # 每 10 秒轮询

    def plugin_execute(self, data, parent_data):
        task_id = submit_async_task()
        data.set_outputs("remote_task_id", task_id)
        return True

    def plugin_schedule(self, data, parent_data, callback_data=None):
        status = check_task_status(data.get_one_of_outputs("remote_task_id"))
        if status == "running":
            return True  # 继续轮询，不调用 finish_schedule
        if status == "success":
            self.finish_schedule()
            return True
        data.set_outputs("ex_data", f"Task failed: {status}")
        return False
```

**execute + 回调（CALLBACK）：**

```python
class MyCallbackService(BKFlowBaseService):
    plugin_name = "my_callback"
    __need_schedule__ = True
    # 不设置 interval → CALLBACK 类型

    def plugin_execute(self, data, parent_data):
        callback_url = get_node_callback_url(
            space_id, task_id, self.id, self.version
        )
        register_webhook(callback_url)
        return True

    def plugin_schedule(self, data, parent_data, callback_data=None):
        result = callback_data.get("result")
        if result == "success":
            self.finish_schedule()  # 必须调用！
            return True
        data.set_outputs("ex_data", "Callback failed")
        return False
```

### finish_schedule() 调用规则

| 场景 | 是否调用 `finish_schedule()` | 说明 |
|------|------------------------------|------|
| 插件最终成功 | **必须调用** | 触发基类结束插件 Span |
| 插件最终失败（return False） | 不调用 | 基类通过 `not result` 分支处理 |
| 中间轮询状态（POLL 继续等待） | 不调用 | 插件尚未完成 |
| 回调但需继续等待（MULTIPLE_CALLBACK） | 不调用 | 等待后续回调 |

> **核心规则：所有 `plugin_schedule()` 返回 True 且代表"插件已完成"的路径，
> 都必须在 return 前调用 `self.finish_schedule()`。**
>
> 不遵守此规则会导致：
> - 插件 Span 缺失（Span 层级断裂）
> - POLL/MULTIPLE_CALLBACK 类型的插件节点无法正常完成

### 子类可覆盖的扩展点

| 方法 | 用途 | 默认行为 |
|------|------|---------|
| `plugin_execute(data, parent_data)` | 执行逻辑 | 空实现 |
| `plugin_schedule(data, parent_data, callback_data)` | 调度逻辑 | 空实现 |
| `_get_span_name()` | 自定义 Span 名称 | `{PLATFORM_CODE}.plugin.{plugin_name}` |
| `_get_span_attributes(data, parent_data)` | 自定义 Span 属性 | space_id, task_id, node_id |
| `inputs_format()` / `outputs_format()` | 输入输出 schema | 空列表 |

### Mock 模式

当 `parent_data.is_mock == True` 且节点在 mock 列表中时，基类自动切换到 mock 路径：

- `mock_execute()`：直接从预置数据读取输出，如需 schedule 则改用 2 秒轮询
- `mock_schedule()`：直接从预置数据读取输出，调用 `finish_schedule()`

Mock 模式下不创建任何 Span。

## 轮询间隔策略

### StaticIntervalGenerator

固定间隔轮询：

```python
interval = StaticIntervalGenerator(10)  # 每 10 秒
```

### StepIntervalGenerator

渐进式间隔，适用于长时间轮询任务（如 uniform_api）：

```
前 30 次: init_interval（默认 10s）
第 31 次起: min((count - 25)², max_interval)
```

参数：
- `init_interval`：初始间隔（默认 10s）
- `max_interval`：最大间隔（默认 600s）
- `max_count`：最大轮询次数（默认 200 次），超过后 `reach_limit()` 返回 True
- `fix_interval`：固定间隔（设置后忽略渐进策略）

## BambooDjangoRuntime 桥接层

`BambooDjangoRuntime` 是 pipeline 框架提供的 `EngineRuntimeInterface` 实现，
组合了多个 Mixin（Task、Schedule、State、Node、Process、Context 等），
负责在 bamboo_engine 和 Django ORM 之间进行桥接：

- **获取 Service 实例**：`get_service(code, version)` → `ComponentLibrary` 查找 → 实例化
- **状态管理**：`set_state()` / `get_state()` → 数据库状态记录
- **调度管理**：`schedule()` → Celery 任务分发
- **回调数据**：`set_callback_data()` / `get_callback_data()` → 数据库持久化
- **执行数据**：`set_execution_data()` / `get_execution_data()` → 节点输入输出持久化

## 相关文件索引

### 核心文件

| 文件 | 说明 |
|------|------|
| `bkflow/pipeline_plugins/components/collections/base.py` | BKFlowBaseService 基类 + StepIntervalGenerator |
| `bkflow/utils/trace.py` | Span 创建/结束工具函数 |
| `bkflow/task/operations.py` | TaskOperation（任务启动、trace context 注入） |
| `bkflow/task/context.py` | TaskContext（parent_data 构建） |
| `bkflow/utils/context.py` | TaskContext 类定义 |
| `bkflow/interface/views.py` | 回调入口（HTTP → callback） |
| `config/default.py` | PIPELINE_INSTANCE_CONTEXT 配置 |

### 插件实现

| 插件 | 路径 |
|------|------|
| 审批 | `bkflow/pipeline_plugins/components/collections/approve/v1_0.py` |
| 暂停 | `bkflow/pipeline_plugins/components/collections/pause/legacy.py` |
| 定时 | `bkflow/pipeline_plugins/components/collections/sleep_time/legacy.py` |
| HTTP 请求 | `bkflow/pipeline_plugins/components/collections/http/v1_0.py` |
| 统一 API v2 | `bkflow/pipeline_plugins/components/collections/uniform_api/v2_0_0.py` |
| 统一 API v3 | `bkflow/pipeline_plugins/components/collections/uniform_api/v3_0_0.py` |
| 远程插件 | `bkflow/pipeline_plugins/components/collections/remote_plugin/v1_0_0.py` |
| 子流程 | `bkflow/pipeline_plugins/components/collections/subprocess_plugin/v1_0_0.py` |
| 通知 | `bkflow/pipeline_plugins/components/collections/notify/v1_0.py` |
| 变量赋值 | `bkflow/pipeline_plugins/components/collections/value_assign/v1_0_0.py` |
| 展示 | `bkflow/pipeline_plugins/components/collections/display/v1_0.py` |
| DMN 决策 | `bkflow/pipeline_plugins/components/collections/dmn_plugin/v1_0_0.py` |
| Python 脚本 | `bkflow/pipeline_plugins/components/collections/python_code/v1_0_0.py` |

### 框架文件（依赖包）

| 文件 | 说明 |
|------|------|
| `pipeline/core/flow/activity/service_activity.py` | Service 基类、finish_schedule()、need_schedule() |
| `pipeline/eri/imp/service.py` | ServiceWrapper、schedule_type() 推导 |
| `pipeline/eri/runtime.py` | BambooDjangoRuntime |
| `pipeline/component_framework/base.py` | ComponentMeta 元类注册 |
| `bamboo_engine/handlers/service_activity.py` | ServiceActivityHandler（execute/schedule 处理） |
| `bamboo_engine/engine.py` | Engine（调度核心、回调处理） |
| `bamboo_engine/eri/models/runtime.py` | ScheduleType 枚举 |
