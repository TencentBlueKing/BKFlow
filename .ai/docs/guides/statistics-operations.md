# 运营统计数据回填与验证指南

## 概述

统计模块的数据分为两层：

- **明细层**：由信号处理器实时写入，包括 `TaskflowStatistics`、`TaskflowExecutedNodeStatistics`、`TemplateStatistics`、`TemplateNodeStatistics`
- **汇总层**：由 Celery Beat 定时任务聚合明细数据写入，包括 `DailyStatisticsSummary`、`PluginExecutionSummary`

回填时必须先填充明细层，再生成汇总层。

## 回填命令

### 管理命令

```bash
python manage.py backfill_statistics --type <type> [options]
```

| 参数 | 说明 |
|------|------|
| `--type` | `all` / `template` / `task` / `summary` |
| `--space-id` | 指定空间 ID，仅回填该空间（可选） |
| `--date-start` | 汇总回填开始日期，仅 `summary` 类型生效（默认近 30 天） |
| `--date-end` | 汇总回填结束日期，仅 `summary` 类型生效（默认昨天） |
| `--batch-size` | 每批处理数量（默认 100） |
| `--parallel` | 使用 Celery 异步执行（注意：异步模式不回填已完成任务的节点执行数据） |

### 分模块部署

**第一步：engine 模块上回填任务数据**

```bash
python manage.py backfill_statistics --type task
```

遍历所有 `TaskInstance`，已完成的任务同时回填 `TaskflowStatistics` 和 `TaskflowExecutedNodeStatistics`。

**第二步：interface 模块上回填模板数据**

```bash
python manage.py backfill_statistics --type template
```

遍历所有 `Template`，回填 `TemplateStatistics` 和 `TemplateNodeStatistics`。

**第三步：任意模块上回填汇总数据**

```bash
python manage.py backfill_statistics --type summary --date-start 2024-01-01 --date-end 2026-03-25
```

基于明细数据按天聚合生成 `DailyStatisticsSummary` 和 `PluginExecutionSummary`。

### 单模块部署

一条命令全覆盖：

```bash
python manage.py backfill_statistics --type all --date-start 2024-01-01 --date-end 2026-03-25
```

内部按 template → task → summary 顺序依次执行。

## 手动触发汇总任务

在 Django Shell 中同步执行，便于观察输出和排错：

```python
from bkflow.statistics.tasks.summary_tasks import generate_daily_summary_task, generate_plugin_summary_task

# 每日统计汇总 — 指定日期，不传默认汇总昨天
generate_daily_summary_task.apply(kwargs={"target_date": "2026-03-25"})

# 插件使用统计 — 按天汇总
generate_plugin_summary_task.apply(kwargs={"period_type": "day", "target_date": "2026-03-25"})
```

## 验证数据是否正确

```python
from bkflow.statistics.models import (
    TaskflowStatistics,
    TaskflowExecutedNodeStatistics,
    TemplateStatistics,
    TemplateNodeStatistics,
    DailyStatisticsSummary,
    PluginExecutionSummary,
)

# 明细层
print("TaskflowStatistics:", TaskflowStatistics.objects.count())
print("TaskflowExecutedNodeStatistics:", TaskflowExecutedNodeStatistics.objects.count())
print("TemplateStatistics:", TemplateStatistics.objects.count())
print("TemplateNodeStatistics:", TemplateNodeStatistics.objects.count())

# 汇总层
print("DailyStatisticsSummary:", DailyStatisticsSummary.objects.count())
print("PluginExecutionSummary:", PluginExecutionSummary.objects.count())
```

## 幂等性

所有回填操作都是幂等的，可以安全重复执行：

- `TaskflowStatistics`：`update_or_create(task_id=...)`
- `TaskflowExecutedNodeStatistics`：事务内 `delete` + `bulk_create`
- `TemplateStatistics`：`update_or_create(template_id=...)`
- `TemplateNodeStatistics`：`delete` + `bulk_create`
- `DailyStatisticsSummary`：`update_or_create`（date + space_id + scope 联合唯一）
- `PluginExecutionSummary`：`update_or_create`（period + space_id + component 联合唯一）

## 定时任务调度

汇总任务由 Celery Beat 自动调度，无需手动干预：

| 任务 | 调度时间 | 说明 |
|------|----------|------|
| `generate_daily_summary_task` | 每天 02:00 | 汇总前一天各空间的任务执行概况 |
| `generate_plugin_summary_task` (day) | 每天 02:30 | 汇总前一天各插件的执行统计 |
| `generate_plugin_summary_task` (week) | 每周一 03:00 | 汇总上周各插件的执行统计 |
| `clean_expired_statistics_task` | 每天 04:00 | 清理过期的明细和汇总数据 |
