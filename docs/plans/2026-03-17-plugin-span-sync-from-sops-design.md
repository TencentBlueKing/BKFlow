# Plugin Span 增强 — 从 bk-sops 同步实现

> **Date:** 2026-03-17
> **Related:** [原始设计文档](./2026-01-29-plugin-span-construction.md)

## 背景

bk-flow 在 2026-01 实现了节点调用 Span 构建能力（PR #593）。之后 bk-sops 在此基础上进行了多轮迭代（2026-01-30 ~ 2026-02-09，共 9 个 commit），修复了 span 层级、命名、输出清理等问题。本次任务将这些增强同步回 bk-flow。

## bk-sops 增强点总结

| # | 增强项 | 影响 |
|---|--------|------|
| 1 | **Span 层级修复**：预生成 `plugin_span_id` + `_CustomSpan` 子类 | 修复 execute/schedule method span 与 plugin span 的父子关系 |
| 2 | **Execution Span 层**：`create_execution_span()` | 为所有插件 span 提供统一的根 span |
| 3 | **Span 输出清理**：`clean_plugin_span_outputs()` | 防止内部 `_plugin_span_*` 属性污染任务输出 |
| 4 | **Span 属性精简** | 移除冗余 `plugin.success`/`plugin.error`，仅保留 OTel Status |
| 5 | **`propagate_attributes()` 幂等优化** | 避免重复添加 SpanProcessor 导致 CPU 开销 |
| 6 | **命名及其他**：`.plugin.` 命名空间、early return guard、日志精简 | 改善一致性和可维护性 |

## 适配原则

- 使用 `settings.PLATFORM_CODE`（bk-flow 约定），不使用 bk-sops 的 `settings.APP_CODE`
- 保留 bk-flow 独有的 `custom_span_attributes` 能力
- 保留 Mock 模式逻辑
- 使用 `space_id` 替代 bk-sops 的 `project_id` 领域概念

## 实施方案：按文件分层移植

### Phase 1 — `bkflow/utils/trace.py` 核心能力增强

**新增组件：**

1. `_CustomSpan(SDKSpan)` — 绕过 SDK `__new__` 检查的子类
2. `_generate_span_id()` — 生成 64 位随机 span_id
3. `create_execution_span()` — 创建 `{platform}.execution` 根 span
4. `_create_span_with_custom_id()` — 使用预定 span_id 创建 span
5. `clean_plugin_span_outputs()` — 清理 `data.outputs` 中的 span 内部属性

**新增常量：**

- `PLUGIN_SPAN_ID_KEY = "_plugin_span_id"`
- `PLUGIN_SPAN_ENDED_KEY`（从 base.py 迁入）
- `PLUGIN_SCHEDULE_COUNT_KEY`（从 base.py 迁入）
- `PLUGIN_SPAN_OUTPUT_KEYS`（所有 span output key 列表）

**更新函数：**

- `start_plugin_span()` — 增加预生成 `plugin_span_id` 并保存到 `data.outputs`
- `end_plugin_span()` — 使用 `_create_span_with_custom_id()` 创建 span（带回退）；移除冗余属性；增加前置 `ENABLE_OTEL_TRACE` 检查
- `plugin_method_span()` — 新增 `plugin_span_id` 参数；增加 disabled-trace early return；span 名称改为 `{platform}.plugin.{name}.{method}`；移除冗余属性和日志
- `propagate_attributes()` — 增加幂等检测
- `AttributeInjectionSpanProcessor` — 新增 `set_attributes()` 方法

### Phase 2 — `bkflow/pipeline_plugins/components/collections/base.py` 插件基类适配

**变更：**

1. `PLUGIN_SPAN_ENDED_KEY` 和 `PLUGIN_SCHEDULE_COUNT_KEY` 改为从 `trace.py` 导入
2. `_get_span_name()` — 名称格式改为 `{platform}.plugin.{plugin_name}`
3. `_get_trace_context(self, data, parent_data)` — 增加 `data` 参数，返回 `plugin_span_id`
4. `_end_plugin_span()` — 结束后调用 `clean_plugin_span_outputs(data)`
5. `execute()` / `schedule()` — 传入 `plugin_span_id` 参数给 `plugin_method_span()`

**保留不变：**

- `custom_span_attributes` 合并逻辑
- Mock 模式逻辑
- `plugin_name` 类属性方式（不采用 bk-sops 的自动驼峰转换）

### Phase 3 — `bkflow/task/operations.py` 任务启动适配

**变更：**

1. `start()` 中用 `create_execution_span()` 替换直接获取外部 trace context
2. 移除 `_external_trace_context` 相关逻辑

**保留不变：**

- `trace_task_operation` 装饰器（操作级 span 仍有意义）

## 改造后的数据流

```
外部请求 (带 Trace Context)
    ↓
trace_task_operation("start") 创建操作 span
    ↓
create_execution_span() 创建 execution span (立即结束)
    ↓ 返回 (trace_id, execution_span_id)
注入到 Pipeline Data (_trace_id, _parent_span_id)
    ↓
节点执行 BKFlowBaseService.execute()
    ↓ _start_plugin_span() → 预生成 plugin_span_id
    ↓ plugin_method_span(plugin_span_id=...) → execute method span
    ↓
节点调度 BKFlowBaseService.schedule()
    ↓ plugin_method_span(plugin_span_id=...) → schedule method span
    ↓
_end_plugin_span() → 用预生成 span_id 创建 plugin span
    ↓
clean_plugin_span_outputs() → 清理内部属性
```

## 改造后的 Span 层级

```
bkflow.task.start (操作 span)
  └── bkflow.execution (execution span, 立即结束)
        └── bkflow.plugin.{name} (plugin span, 用预生成 span_id)
              ├── bkflow.plugin.{name}.execute (method span)
              └── bkflow.plugin.{name}.schedule (method span)
```

## 涉及文件

| 文件 | 变更类型 |
|------|----------|
| `bkflow/utils/trace.py` | 新增函数 + 更新函数 |
| `bkflow/pipeline_plugins/components/collections/base.py` | 更新导入 + 更新方法 |
| `bkflow/task/operations.py` | 更新 `start()` 方法 |
| `tests/engine/utils/test_trace.py` | 新增测试 + 更新测试 |
| `tests/engine/task/test_bkflow_base_plugin_service.py` | 更新测试 |
| `tests/engine/task/test_task_operations.py` | 更新测试 |

## bk-sops 相关 Commits

| Hash | Date | Message |
|------|------|---------|
| `178a60ee95` | 2026-01-30 | feat: 构建节点执行的Span |
| `4368403ab6` | 2026-01-30 | refactor: 修复import的问题 |
| `8b8df64352` | 2026-02-02 | refactor: 修复python版本兼容的问题 |
| `65842b2e05` | 2026-02-02 | refactor: plugin execute和schedule 的span名称格式修改 |
| `db4c2523b8` | 2026-02-04 | refactor: 修复内置插件span名称不对的问题 & span层级问题修复 |
| `dac8c9c4fc` | 2026-02-09 | refactor: 修复execute和schedule的父span不对的问题 |
| `cf4f84799c` | 2026-02-09 | refactor: approve插件补充调用finish_schedule |
| `59fa41056d` | 2026-02-09 | refactor: 调整span属性的内容 |
| `6e67741cd9` | 2026-02-09 | refactor: 流程结束后, 流程output清理span相关的内置属性 |
