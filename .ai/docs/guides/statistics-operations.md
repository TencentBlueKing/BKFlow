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

## 共享统计数据库配置

在分模块部署（engine + interface 独立进程）场景下，需要配置共享统计数据库使两个模块读写同一份统计数据。

### 环境变量

在 engine 和 interface 两个模块上都配置以下环境变量：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `STATISTICS_DB_HOST` | 统计数据库地址 | （空，不配则使用 default 库） |
| `STATISTICS_DB_PORT` | 统计数据库端口 | `3306` |
| `STATISTICS_DB_NAME` | 统计数据库名 | （空） |
| `STATISTICS_DB_USER` | 统计数据库用户名 | （空） |
| `STATISTICS_DB_PASSWORD` | 统计数据库密码 | （空） |

> **关键点**：只有同时配置了 `STATISTICS_DB_HOST` 和 `STATISTICS_DB_NAME` 时，才会在 `settings.DATABASES` 中注入 `"statistics"` 数据库，数据库路由器才会将统计模型路由到独立库。否则回退到 `default` 库。

### 验证配置是否生效

```bash
python manage.py shell -c "
from django.conf import settings
from bkflow.statistics.conf import StatisticsSettings
print('DATABASES keys:', list(settings.DATABASES.keys()))
print('get_db_alias():', StatisticsSettings.get_db_alias())
if 'statistics' in settings.DATABASES:
    db = settings.DATABASES['statistics']
    print(f'statistics DB -> {db[\"USER\"]}@{db[\"HOST\"]}:{db[\"PORT\"]}/{db[\"NAME\"]}')
else:
    print('WARNING: statistics DB 未配置，使用 default 库')
"
```

预期输出（已配置）：`get_db_alias()` 返回 `"statistics"`，连接信息指向共享库。

### 迁移

配置统计数据库后，需在对应模块上执行：

```bash
python manage.py migrate statistics --database=statistics
```

## 定时任务调度

汇总任务由 Celery Beat 自动调度，无需手动干预：

| 任务 | 调度时间 | 说明 |
|------|----------|------|
| `generate_daily_summary_task` | 每天 02:00 | 汇总前一天各空间的任务执行概况 |
| `generate_plugin_summary_task` (day) | 每天 02:30 | 汇总前一天各插件的执行统计 |
| `generate_plugin_summary_task` (week) | 每周一 03:00 | 汇总上周各插件的执行统计 |
| `clean_expired_statistics_task` | 每天 04:00 | 清理过期的明细和汇总数据 |
