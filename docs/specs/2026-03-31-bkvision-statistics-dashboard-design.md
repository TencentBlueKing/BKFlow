# BK-Vision 运营统计仪表盘对接设计

> 日期：2026-03-31
> 状态：Draft

## 1. 背景

BKFlow 在 [PR #636](https://github.com/TencentBlueKing/BKFlow/pull/636) 中新增了 `bkflow.statistics` 运营统计模块，包含 6 张统计数据表。现在需要将这些数据接入 BK-Vision 可视化平台，配置面向管理员和空间负责人的仪表盘，并最终通过 iframe 嵌入 BKFlow 前端。

## 2. 目标

1. **后端**：集成 `django-bkvision` SDK，配置网关权限，提供仪表盘 UID 给前端
2. **BK-Vision 配置**：设计并配置两个仪表盘（系统级 + 空间级），直连统计数据库
3. **前端需求文档**：输出前端对接方案和接口说明，交给前端开发实现

## 3. 整体架构

```
┌─────────────────────────────────────────────────┐
│                   BKFlow 前端                     │
│  ┌──────────────┐     ┌──────────────────────┐  │
│  │ 系统管理页面   │     │ 空间页面              │  │
│  │ (admin)      │     │ (space)              │  │
│  │  ┌────────┐  │     │  ┌────────────────┐  │  │
│  │  │ iframe │  │     │  │    iframe       │  │  │
│  │  │ 系统   │  │     │  │ 空间仪表盘      │  │  │
│  │  │ 仪表盘 │  │     │  │ ?space_id=xxx  │  │  │
│  │  └────────┘  │     │  └────────────────┘  │  │
│  └──────────────┘     └──────────────────────┘  │
│         │                       │                │
│         ▼                       ▼                │
│  django-bkvision SDK (认证 + API 代理)            │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│              BK-Vision 平台                       │
│  ┌──────────────┐     ┌──────────────────────┐  │
│  │ 系统仪表盘    │     │ 空间仪表盘            │  │
│  │ (16 panels)  │     │ (10 panels)          │  │
│  └──────┬───────┘     └──────────┬───────────┘  │
│         └────────────┬───────────┘               │
│                      ▼                           │
│              SQL 直连数据库                        │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│         Statistics 数据库 (MySQL)                  │
│  statistics_taskflowstatistics                    │
│  statistics_taskflowexecutednodestatistics         │
│  statistics_templatestatistics                     │
│  statistics_templatenodestatistics                 │
│  statistics_dailystatisticssummary                 │
│  statistics_pluginexecutionsummary                 │
└─────────────────────────────────────────────────┘
```

## 4. 数据表概览

| 表名 | 粒度 | 关键维度 | 关键指标 |
|------|------|---------|---------|
| `statistics_taskflowstatistics` | 每任务一行 | space_id, scope, template_id, final_state, engine_id, create_method, trigger_method | elapsed_time, atom_total, subprocess_total |
| `statistics_taskflowexecutednodestatistics` | 每执行节点一行 | space_id, component_code, plugin_type, status, state | elapsed_time, retry_count, is_skip |
| `statistics_templatestatistics` | 每模板一行 | space_id, scope, is_enabled | atom_total, subprocess_total, template_update_time |
| `statistics_templatenodestatistics` | 模板中每插件节点一行 | space_id, component_code, plugin_type, template_id | is_sub, node_name |
| `statistics_dailystatisticssummary` | 每天每空间每scope一行 | date, space_id, scope | task_*_count, node_*_count, avg/max_task_elapsed_time |
| `statistics_pluginexecutionsummary` | 按周期每插件一行 | period_type, period_start, space_id, component_code | execution/success/failed_count, avg/max_elapsed_time |

## 5. 后端对接设计

### 5.1 安装 django-bkvision SDK

**requirements.txt** 新增：

```
django-bkvision>=0.1.0
```

> 注：部署前确认 PyPI 上最新版本并锁定。

### 5.2 Django 配置

**config/default.py** — `INSTALLED_APPS` 新增：

```python
INSTALLED_APPS += (
    'django_bkvision',
)
```

**urls.py**（项目根）新增路由：

```python
path('bkvision/', include('django_bkvision.urls')),
```

### 5.3 环境变量

**env.py** 新增：

```python
# BK-Vision 对接配置
BKAPP_BKVISION_APIGW_URL = os.getenv("BKAPP_BKVISION_APIGW_URL", "")
BKAPP_BKVISION_BASE_URL = os.getenv("BKAPP_BKVISION_BASE_URL", "")
BKAPP_BKVISION_SYSTEM_DASHBOARD_UID = os.getenv("BKAPP_BKVISION_SYSTEM_DASHBOARD_UID", "")
BKAPP_BKVISION_SPACE_DASHBOARD_UID = os.getenv("BKAPP_BKVISION_SPACE_DASHBOARD_UID", "")
```

### 5.4 Context Processor 注入前端配置

**bkflow/interface/context_processors.py** 的 `bkflow_settings` 函数新增：

```python
ctx = {
    # ... 现有字段 ...
    "BKVISION_SYSTEM_DASHBOARD_UID": env.BKAPP_BKVISION_SYSTEM_DASHBOARD_UID,
    "BKVISION_SPACE_DASHBOARD_UID": env.BKAPP_BKVISION_SPACE_DASHBOARD_UID,
    "BKVISION_BASE_URL": env.BKAPP_BKVISION_BASE_URL,
}
```

前端通过 `window.BKVISION_*` 全局变量获取配置，拼装 iframe URL。

### 5.5 网关权限

在蓝鲸 API 网关管理页面申请 `bk-vision` 接口权限，绑定 BKFlow 的 `app_code`。

## 6. 前端对接需求（供前端开发参考）

### 6.1 新增页面

| 页面 | 路由 | 位置 | 说明 |
|------|------|------|------|
| 系统运营统计 | `/bkflow_engine_admin/statistics/` | 系统管理侧边栏新增"运营统计"菜单项 | iframe 嵌入系统仪表盘 |
| 空间运营统计 | 空间路由下新增 `statistics/` | 空间侧边栏新增"运营统计"菜单项 | iframe 嵌入空间仪表盘，传 `space_id` 变量 |

### 6.2 嵌入方式

使用 BK-Vision iframe 方式嵌入，参考 [前端嵌入开发指引](https://iwiki.woa.com/p/4015849400)。

**系统仪表盘 iframe URL 拼装：**

```
{BKVISION_BASE_URL}/share/{BKVISION_SYSTEM_DASHBOARD_UID}/?date_start=xxx&date_end=xxx
```

**空间仪表盘 iframe URL 拼装：**

```
{BKVISION_BASE_URL}/share/{BKVISION_SPACE_DASHBOARD_UID}/?space_id={spaceId}&date_start=xxx&date_end=xxx
```

### 6.3 权限控制

- 系统运营统计页面：复用现有的 admin 路由 `meta: { admin: true }` 鉴权
- 空间运营统计页面：复用现有的 `hasStatisticsPerm`（Vuex 中已有占位）

### 6.4 i18n

在 `frontend/src/config/i18n/cn.js` 和 `en.js` 中新增：

```javascript
// cn.js
'运营统计': '运营统计',

// en.js
'运营统计': 'Operations Statistics',
```

## 7. BK-Vision 仪表盘设计

### 7.1 数据源配置

在 BK-Vision 平台创建 MySQL 数据源，连接 BKFlow 的统计数据库：

- **类型**：MySQL
- **连接信息**：使用 `STATISTICS_DB_HOST/PORT/NAME/USER/PASSWORD` 对应的数据库。如果统计表在 default 数据库中，则连接 default 数据库。

### 7.2 SQL 约定

**日期过滤规则**：

- 对 `DateField` 列（`date`、`period_start`）：使用 `BETWEEN $date_start AND $date_end`
- 对 `DateTimeField` 列（`create_time`、`started_time`）：使用 `>= $date_start AND < DATE_ADD($date_end, INTERVAL 1 DAY)`，避免 date 类型变量被解释为 `00:00:00` 而丢失当天数据

**除零保护**：所有比率计算使用 `NULLIF(divisor, 0)` 防止除零错误。

**变量语法**：以下 SQL 使用 `$variable_name` 占位符，实际配置时需按 BK-Vision 平台的变量语法替换（可能是 `${variable}`、`{{variable}}` 等）。

### 7.3 系统仪表盘（管理员视角）

**仪表盘名称**：BKFlow 系统运营统计

**变量配置：**

| 变量名 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `date_start` | 日期 | 开始日期 | 30天前 |
| `date_end` | 日期 | 结束日期 | 今天 |
| `engine_id` | 下拉（可选） | 引擎实例筛选，仅影响 Panel 16（引擎实例负载），单引擎部署可隐藏 | 全部 |

**布局：**

```
Row 1:  [卡片×6] — 平台概览 KPI
Row 2:  [任务执行趋势] — 全宽折线图
Row 3:  [任务状态分布 | 创建方式分布 | 触发方式分布] — 三个饼图
Row 4:  [任务耗时分布 | 任务复杂度分析] — 两个柱状图
Row 5:  [空间排行 Top 10] — 全宽表格
Row 6:  [插件使用排行 | 插件耗时排行 | 插件类型分布] — 柱状图 + 柱状图 + 饼图
Row 7:  [插件耗时趋势] — 全宽折线图
Row 8:  [插件失败分析 | 节点重试分析] — 两个表格
Row 9:  [模板活跃度 | 插件模板覆盖度] — 表格 + 柱状图
Row 10: [引擎实例负载分布] — 柱状图
```

#### Panel 1 — 平台概览（数字卡片 × 6）

| 卡片 | 指标 | SQL |
|------|------|-----|
| 总任务数 | COUNT | `SELECT COUNT(*) FROM statistics_taskflowstatistics WHERE create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)` |
| 任务成功率 | % | `SELECT ROUND(SUM(final_state='FINISHED')/NULLIF(COUNT(*),0)*100, 1) FROM statistics_taskflowstatistics WHERE is_finished=1 AND create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)` |
| 总模板数 | COUNT | `SELECT COUNT(*) FROM statistics_templatestatistics WHERE is_enabled=1` |
| 节点执行总数 | COUNT | `SELECT COUNT(*) FROM statistics_taskflowexecutednodestatistics WHERE started_time >= $date_start AND started_time < DATE_ADD($date_end, INTERVAL 1 DAY)` |
| 平均任务耗时(min) | AVG | `SELECT ROUND(AVG(elapsed_time)/60, 1) FROM statistics_taskflowstatistics WHERE elapsed_time IS NOT NULL AND create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)` |
| 活跃空间数 | DISTINCT | `SELECT COUNT(DISTINCT space_id) FROM statistics_taskflowstatistics WHERE create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)` |

#### Panel 2 — 任务执行趋势（多折线图）

- **X 轴**：date | **Y 轴**：创建数、完成数、成功数、失败数、撤销数

```sql
SELECT
  date,
  SUM(task_created_count) AS created,
  SUM(task_finished_count) AS finished,
  SUM(task_success_count) AS success,
  SUM(task_failed_count) AS failed,
  SUM(task_revoked_count) AS revoked
FROM statistics_dailystatisticssummary
WHERE date BETWEEN $date_start AND $date_end
GROUP BY date
ORDER BY date
```

#### Panel 3 — 任务状态分布（饼图）

```sql
SELECT final_state, COUNT(*) AS cnt
FROM statistics_taskflowstatistics
WHERE create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)
GROUP BY final_state
```

#### Panel 4a — 创建方式分布（饼图）

```sql
SELECT create_method, COUNT(*) AS cnt
FROM statistics_taskflowstatistics
WHERE create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)
GROUP BY create_method
```

#### Panel 4b — 触发方式分布（饼图）

```sql
SELECT trigger_method, COUNT(*) AS cnt
FROM statistics_taskflowstatistics
WHERE create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)
GROUP BY trigger_method
```

#### Panel 5 — 任务耗时分布（柱状图）

- **X 轴**：耗时区间 | **Y 轴**：任务数

```sql
SELECT
  CASE
    WHEN elapsed_time < 60 THEN '<1min'
    WHEN elapsed_time < 300 THEN '1-5min'
    WHEN elapsed_time < 1800 THEN '5-30min'
    WHEN elapsed_time < 3600 THEN '30-60min'
    ELSE '>60min'
  END AS duration_bucket,
  COUNT(*) AS cnt
FROM statistics_taskflowstatistics
WHERE elapsed_time IS NOT NULL
  AND create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)
GROUP BY duration_bucket
ORDER BY MIN(elapsed_time)
```

#### Panel 6 — 任务复杂度分析（柱状图）

- **X 轴**：复杂度区间 | **Y 轴**：任务数

```sql
SELECT
  CASE
    WHEN (atom_total + subprocess_total) <= 5 THEN '简单(≤5)'
    WHEN (atom_total + subprocess_total) <= 15 THEN '中等(6-15)'
    WHEN (atom_total + subprocess_total) <= 30 THEN '复杂(16-30)'
    ELSE '超复杂(>30)'
  END AS complexity,
  COUNT(*) AS cnt
FROM statistics_taskflowstatistics
WHERE create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)
GROUP BY complexity
```

#### Panel 7 — 空间排行 Top 10（表格）

```sql
SELECT
  t.space_id,
  t.task_cnt,
  t.success_cnt,
  ROUND(t.success_cnt / NULLIF(t.finished_cnt, 0) * 100, 1) AS success_rate,
  COALESCE(tpl.tpl_cnt, 0) AS tpl_cnt,
  COALESCE(n.node_cnt, 0) AS node_cnt
FROM (
  SELECT space_id,
    COUNT(*) AS task_cnt,
    SUM(is_finished) AS finished_cnt,
    SUM(final_state='FINISHED') AS success_cnt
  FROM statistics_taskflowstatistics
  WHERE create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)
  GROUP BY space_id
) t
LEFT JOIN (
  SELECT space_id, COUNT(*) AS tpl_cnt
  FROM statistics_templatestatistics WHERE is_enabled=1
  GROUP BY space_id
) tpl ON t.space_id = tpl.space_id
LEFT JOIN (
  SELECT space_id, COUNT(*) AS node_cnt
  FROM statistics_taskflowexecutednodestatistics
  WHERE started_time >= $date_start AND started_time < DATE_ADD($date_end, INTERVAL 1 DAY)
  GROUP BY space_id
) n ON t.space_id = n.space_id
ORDER BY t.task_cnt DESC
LIMIT 10
```

#### Panel 8 — 插件使用排行 Top 15（横向柱状图）

- **Y 轴**：插件名称 | **X 轴**：执行次数

```sql
SELECT
  COALESCE(NULLIF(component_name, ''), component_code) AS plugin_name,
  component_code,
  plugin_type,
  SUM(execution_count) AS exec_cnt,
  SUM(success_count) AS success_cnt,
  SUM(failed_count) AS failed_cnt,
  ROUND(SUM(success_count)/NULLIF(SUM(execution_count),0)*100, 1) AS success_rate
FROM statistics_pluginexecutionsummary
WHERE period_type='day' AND period_start BETWEEN $date_start AND $date_end
GROUP BY component_code, component_name, plugin_type
ORDER BY exec_cnt DESC
LIMIT 15
```

#### Panel 9 — 插件耗时排行 Top 15（横向柱状图）

- **Y 轴**：插件名称 | **X 轴**：平均耗时（秒）

```sql
SELECT
  COALESCE(NULLIF(component_name, ''), component_code) AS plugin_name,
  plugin_type,
  ROUND(SUM(avg_elapsed_time * execution_count) / NULLIF(SUM(execution_count), 0), 1) AS avg_elapsed,
  MAX(max_elapsed_time) AS max_elapsed,
  SUM(execution_count) AS total_exec
FROM statistics_pluginexecutionsummary
WHERE period_type='day' AND period_start BETWEEN $date_start AND $date_end
GROUP BY component_code, component_name, plugin_type
HAVING SUM(execution_count) > 10
ORDER BY avg_elapsed DESC
LIMIT 15
```

#### Panel 10 — 插件类型分布（饼图）

```sql
SELECT plugin_type, COUNT(*) AS cnt
FROM statistics_taskflowexecutednodestatistics
WHERE started_time >= $date_start AND started_time < DATE_ADD($date_end, INTERVAL 1 DAY)
GROUP BY plugin_type
```

#### Panel 11 — 插件耗时趋势（多折线图，Top 5 插件）

- **X 轴**：日期 | **Y 轴**：平均耗时（秒）| **系列**：Top 5 插件

```sql
SELECT
  p.period_start AS date,
  COALESCE(NULLIF(p.component_name, ''), p.component_code) AS plugin_name,
  p.avg_elapsed_time
FROM statistics_pluginexecutionsummary p
INNER JOIN (
  SELECT component_code
  FROM statistics_pluginexecutionsummary
  WHERE period_type='day' AND period_start BETWEEN $date_start AND $date_end
  GROUP BY component_code
  ORDER BY SUM(execution_count) DESC
  LIMIT 5
) top5 ON p.component_code = top5.component_code
WHERE p.period_type='day'
  AND p.period_start BETWEEN $date_start AND $date_end
ORDER BY date, plugin_name
```

#### Panel 12 — 插件失败分析 Top 10（表格）

```sql
SELECT
  COALESCE(NULLIF(component_name, ''), component_code) AS plugin_name,
  plugin_type,
  SUM(execution_count) AS total,
  SUM(failed_count) AS failed,
  ROUND(SUM(failed_count)/NULLIF(SUM(execution_count),0)*100, 1) AS failure_rate,
  ROUND(SUM(avg_elapsed_time * execution_count) / NULLIF(SUM(execution_count), 0), 1) AS avg_elapsed
FROM statistics_pluginexecutionsummary
WHERE period_type='day' AND period_start BETWEEN $date_start AND $date_end
GROUP BY component_code, component_name, plugin_type
HAVING SUM(execution_count) > 10
ORDER BY failure_rate DESC
LIMIT 10
```

#### Panel 13 — 节点重试分析 Top 10（表格）

```sql
SELECT
  COALESCE(NULLIF(component_name, ''), component_code) AS plugin_name,
  plugin_type,
  COUNT(*) AS total_nodes,
  SUM(retry_count > 0) AS retried_nodes,
  ROUND(SUM(retry_count > 0)/NULLIF(COUNT(*),0)*100, 1) AS retry_rate,
  ROUND(AVG(retry_count), 1) AS avg_retry_count
FROM statistics_taskflowexecutednodestatistics
WHERE started_time >= $date_start AND started_time < DATE_ADD($date_end, INTERVAL 1 DAY)
GROUP BY component_code, component_name, plugin_type
HAVING COUNT(*) > 10
ORDER BY retry_rate DESC
LIMIT 10
```

#### Panel 14 — 模板活跃度 Top 20（表格）

```sql
SELECT
  template_id, template_name, space_id,
  atom_total, subprocess_total,
  is_enabled,
  template_update_time
FROM statistics_templatestatistics
ORDER BY template_update_time DESC
LIMIT 20
```

#### Panel 15 — 插件模板覆盖度 Top 15（横向柱状图）

- **Y 轴**：插件名称 | **X 轴**：被引用模板数

```sql
SELECT
  COALESCE(NULLIF(component_name, ''), component_code) AS plugin_name,
  plugin_type,
  COUNT(DISTINCT template_id) AS template_cnt,
  COUNT(*) AS node_cnt
FROM statistics_templatenodestatistics
GROUP BY component_code, component_name, plugin_type
ORDER BY template_cnt DESC
LIMIT 15
```

#### Panel 16 — 引擎实例负载分布（分组柱状图）

- **X 轴**：engine_id | **Y 轴**：任务数 + 节点执行数（双系列）

```sql
SELECT
  t.engine_id,
  t.task_cnt,
  COALESCE(n.node_cnt, 0) AS node_cnt
FROM (
  SELECT engine_id, COUNT(*) AS task_cnt
  FROM statistics_taskflowstatistics
  WHERE create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)
  GROUP BY engine_id
) t
LEFT JOIN (
  SELECT engine_id, COUNT(*) AS node_cnt
  FROM statistics_taskflowexecutednodestatistics
  WHERE started_time >= $date_start AND started_time < DATE_ADD($date_end, INTERVAL 1 DAY)
  GROUP BY engine_id
) n ON t.engine_id = n.engine_id
ORDER BY t.task_cnt DESC
```

---

### 7.4 空间仪表盘（空间负责人视角）

**仪表盘名称**：BKFlow 空间运营统计

**变量配置：**

| 变量名 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `space_id` | 数字（必填） | 空间 ID，前端 iframe URL 参数传入 | — |
| `date_start` | 日期 | 开始日期 | 30天前 |
| `date_end` | 日期 | 结束日期 | 今天 |
| `scope_type` | 下拉（可选） | 范围类型筛选 | 全部 |
| `scope_value` | 下拉（可选） | 范围值筛选，联动 scope_type | 全部 |

**布局：**

```
Row 1: [卡片×6] — 空间概览 KPI
Row 2: [任务执行趋势] — 全宽折线图
Row 3: [任务状态分布 | 任务耗时分布] — 饼图 + 柱状图
Row 4: [模板排行 Top 10] — 全宽表格
Row 5: [插件使用排行 | 插件耗时排行] — 两个横向柱状图
Row 6: [插件失败分析 | 节点重试分析] — 两个表格
Row 7: [模板插件构成] — 全宽表格
```

> 以下 SQL 均带 `space_id = $space_id` 过滤。
>
> **scope 过滤规则**：当 `$scope_type` 非空时，对含有 `scope_type`/`scope_value` 列的表追加条件 `AND scope_type = $scope_type AND scope_value = $scope_value`。适用的表：`statistics_taskflowstatistics`、`statistics_dailystatisticssummary`、`statistics_templatestatistics`、`statistics_templatenodestatistics`。**不适用**的表（无 scope 列）：`statistics_taskflowexecutednodestatistics`、`statistics_pluginexecutionsummary`。

#### Panel 1 — 空间概览（数字卡片 × 6）

| 卡片 | 指标 | SQL |
|------|------|-----|
| 任务总数 | COUNT | `SELECT COUNT(*) FROM statistics_taskflowstatistics WHERE space_id=$space_id AND create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)` |
| 任务成功率 | % | `SELECT ROUND(SUM(final_state='FINISHED')/NULLIF(COUNT(*),0)*100, 1) FROM statistics_taskflowstatistics WHERE space_id=$space_id AND is_finished=1 AND create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)` |
| 模板总数 | COUNT | `SELECT COUNT(*) FROM statistics_templatestatistics WHERE space_id=$space_id AND is_enabled=1` |
| 节点执行数 | COUNT | `SELECT COUNT(*) FROM statistics_taskflowexecutednodestatistics WHERE space_id=$space_id AND started_time >= $date_start AND started_time < DATE_ADD($date_end, INTERVAL 1 DAY)` |
| 平均任务耗时(min) | AVG | `SELECT ROUND(AVG(elapsed_time)/60, 1) FROM statistics_taskflowstatistics WHERE space_id=$space_id AND elapsed_time IS NOT NULL AND create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)` |
| 失败任务数 | COUNT | `SELECT COUNT(*) FROM statistics_taskflowstatistics WHERE space_id=$space_id AND is_finished=1 AND final_state!='FINISHED' AND create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)` |

#### Panel 2 — 任务执行趋势（多折线图）

```sql
SELECT
  date,
  SUM(task_created_count) AS created,
  SUM(task_finished_count) AS finished,
  SUM(task_success_count) AS success,
  SUM(task_failed_count) AS failed,
  SUM(task_revoked_count) AS revoked
FROM statistics_dailystatisticssummary
WHERE space_id = $space_id
  AND date BETWEEN $date_start AND $date_end
GROUP BY date
ORDER BY date
```

#### Panel 3 — 任务状态分布（饼图）

```sql
SELECT final_state, COUNT(*) AS cnt
FROM statistics_taskflowstatistics
WHERE space_id = $space_id
  AND create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)
GROUP BY final_state
```

#### Panel 4 — 任务耗时分布（柱状图）

```sql
SELECT
  CASE
    WHEN elapsed_time < 60 THEN '<1min'
    WHEN elapsed_time < 300 THEN '1-5min'
    WHEN elapsed_time < 1800 THEN '5-30min'
    WHEN elapsed_time < 3600 THEN '30-60min'
    ELSE '>60min'
  END AS duration_bucket,
  COUNT(*) AS cnt
FROM statistics_taskflowstatistics
WHERE space_id = $space_id AND elapsed_time IS NOT NULL
  AND create_time >= $date_start AND create_time < DATE_ADD($date_end, INTERVAL 1 DAY)
GROUP BY duration_bucket
ORDER BY MIN(elapsed_time)
```

#### Panel 5 — 模板排行 Top 10（表格）

> 注：仅统计关联了模板的任务（`template_id IS NOT NULL`）。

```sql
SELECT
  ts.template_id,
  ts.template_name,
  COUNT(tf.id) AS task_count,
  SUM(tf.final_state = 'FINISHED') AS success_count,
  SUM(tf.is_finished = 1 AND tf.final_state != 'FINISHED') AS failed_count,
  ROUND(SUM(tf.final_state = 'FINISHED') / NULLIF(SUM(tf.is_finished), 0) * 100, 1) AS success_rate
FROM statistics_taskflowstatistics tf
JOIN statistics_templatestatistics ts ON tf.template_id = ts.template_id
WHERE tf.space_id = $space_id
  AND tf.create_time >= $date_start AND tf.create_time < DATE_ADD($date_end, INTERVAL 1 DAY)
GROUP BY ts.template_id, ts.template_name
ORDER BY task_count DESC
LIMIT 10
```

#### Panel 6 — 插件使用排行 Top 10（横向柱状图）

```sql
SELECT
  COALESCE(NULLIF(component_name, ''), component_code) AS plugin_name,
  plugin_type,
  SUM(execution_count) AS exec_cnt,
  SUM(failed_count) AS failed_cnt,
  ROUND(SUM(success_count)/NULLIF(SUM(execution_count),0)*100, 1) AS success_rate
FROM statistics_pluginexecutionsummary
WHERE space_id = $space_id AND period_type='day'
  AND period_start BETWEEN $date_start AND $date_end
GROUP BY component_code, component_name, plugin_type
ORDER BY exec_cnt DESC
LIMIT 10
```

#### Panel 7 — 插件耗时排行 Top 10（横向柱状图）

```sql
SELECT
  COALESCE(NULLIF(component_name, ''), component_code) AS plugin_name,
  plugin_type,
  ROUND(SUM(avg_elapsed_time * execution_count) / NULLIF(SUM(execution_count), 0), 1) AS avg_elapsed,
  MAX(max_elapsed_time) AS max_elapsed,
  SUM(execution_count) AS total_exec
FROM statistics_pluginexecutionsummary
WHERE space_id = $space_id AND period_type='day'
  AND period_start BETWEEN $date_start AND $date_end
GROUP BY component_code, component_name, plugin_type
HAVING SUM(execution_count) > 5
ORDER BY avg_elapsed DESC
LIMIT 10
```

#### Panel 8 — 插件失败分析 Top 10（表格）

```sql
SELECT
  COALESCE(NULLIF(component_name, ''), component_code) AS plugin_name,
  plugin_type,
  SUM(execution_count) AS total,
  SUM(failed_count) AS failed,
  ROUND(SUM(failed_count)/NULLIF(SUM(execution_count),0)*100, 1) AS failure_rate
FROM statistics_pluginexecutionsummary
WHERE space_id = $space_id AND period_type='day'
  AND period_start BETWEEN $date_start AND $date_end
GROUP BY component_code, component_name, plugin_type
HAVING SUM(execution_count) > 5
ORDER BY failure_rate DESC
LIMIT 10
```

#### Panel 9 — 模板插件构成 Top 20（表格）

```sql
SELECT
  ts.template_name,
  ts.template_id,
  ts.atom_total,
  ts.subprocess_total,
  ts.gateways_total,
  GROUP_CONCAT(DISTINCT tn.component_code ORDER BY tn.component_code SEPARATOR ', ') AS plugins_used,
  COUNT(DISTINCT tn.component_code) AS plugin_variety
FROM statistics_templatestatistics ts
LEFT JOIN statistics_templatenodestatistics tn ON ts.template_id = tn.template_id
WHERE ts.space_id = $space_id AND ts.is_enabled = 1
GROUP BY ts.template_id, ts.template_name, ts.atom_total, ts.subprocess_total, ts.gateways_total
ORDER BY ts.atom_total DESC
LIMIT 20
```

#### Panel 10 — 节点重试分析 Top 10（表格）

```sql
SELECT
  COALESCE(NULLIF(component_name, ''), component_code) AS plugin_name,
  plugin_type,
  COUNT(*) AS total_nodes,
  SUM(retry_count > 0) AS retried_nodes,
  ROUND(SUM(retry_count > 0)/NULLIF(COUNT(*),0)*100, 1) AS retry_rate,
  ROUND(AVG(retry_count), 1) AS avg_retry
FROM statistics_taskflowexecutednodestatistics
WHERE space_id = $space_id
  AND started_time >= $date_start AND started_time < DATE_ADD($date_end, INTERVAL 1 DAY)
GROUP BY component_code, component_name, plugin_type
HAVING COUNT(*) > 5
ORDER BY retry_rate DESC
LIMIT 10
```

## 8. BK-Vision 配置步骤

### 8.1 创建空间

在 BK-Vision 平台创建名为 `BKFlow` 的工作空间。

### 8.2 配置数据源

添加 MySQL 数据源，连接 BKFlow 统计数据库（`STATISTICS_DB_*` 环境变量对应的库）。

### 8.3 创建图表

按照第 7 节的 Panel 设计，逐个创建图表，配置 SQL 查询和图表类型。

### 8.4 组装仪表盘

1. 创建"系统运营统计"仪表盘，添加变量 `date_start`、`date_end`、`engine_id`，按 Row 布局添加 16 个 Panel
2. 创建"空间运营统计"仪表盘，添加变量 `space_id`、`date_start`、`date_end`、`scope_type`、`scope_value`，按 Row 布局添加 10 个 Panel

### 8.5 创建分享链接

1. 在"嵌入管理"中为两个仪表盘分别创建分享链接
2. 绑定 BKFlow 的蓝鲸应用 `app_code`
3. 发布分享链接
4. 将生成的 UID 配置到 BKFlow 环境变量 `BKAPP_BKVISION_SYSTEM_DASHBOARD_UID` 和 `BKAPP_BKVISION_SPACE_DASHBOARD_UID`

## 9. 实现范围

### 本次实现（后端 + BK-Vision 配置）

- [x] 安装 `django-bkvision` SDK
- [x] 配置 `INSTALLED_APPS`、URL 路由、环境变量
- [x] `context_processors.py` 注入 BK-Vision 配置
- [x] 在 BK-Vision 平台配置数据源、图表、两个仪表盘
- [x] 创建并发布分享链接
- [x] 输出前端对接需求文档

### 后续由前端开发实现

- [ ] 系统管理侧边栏新增"运营统计"菜单
- [ ] 系统运营统计页面（iframe 嵌入）
- [ ] 空间侧边栏新增"运营统计"菜单
- [ ] 空间运营统计页面（iframe 嵌入，传 `space_id` 变量）
- [ ] i18n 翻译

## 10. 注意事项

### 10.1 数据新鲜度

`DailyStatisticsSummary` 和 `PluginExecutionSummary` 依赖 Celery Beat 定时任务生成（默认凌晨 2:00-3:00），因此当天的汇总数据要到次日才可用。用户如果查询包含"今天"的数据，这两张汇总表的当日数据会缺失。需要在仪表盘中通过提示或默认 `date_end` 为昨天来规避。

### 10.2 大数据量查询性能

`statistics_taskflowexecutednodestatistics` 表的数据量可能非常大（每个任务的每个节点一行）。在 BK-Vision 配置图表时，确保所有对该表的查询都走索引：

- `(space_id, component_code, started_time)` — 插件维度查询
- `(space_id, started_time)` — 空间+时间范围查询
- `(engine_id, started_time)` — 引擎维度查询

### 10.3 iframe 嵌入安全

前端嵌入 BK-Vision iframe 时需注意：

- BKFlow 的 `X-Frame-Options` / `Content-Security-Policy` 响应头不应阻止 BK-Vision 的 iframe
- BK-Vision 分享链接需绑定 BKFlow 的 `app_code`，否则会报"无权访问该视图资源"
- 分享链接必须发布后才可访问

### 10.4 空数据处理

新部署或新空间可能没有统计数据。BK-Vision 图表在查询结果为空时的展示行为由平台控制，通常显示"暂无数据"。KPI 卡片建议在 SQL 中使用 `COALESCE` 确保返回 0 而非 NULL。

### 10.5 多数据库部署

如果 BKFlow 使用独立的统计数据库（`STATISTICS_DB_*` 环境变量已配置），BK-Vision 的 MySQL 数据源必须连接到该独立库，而非 BKFlow 的 default 数据库。

## 11. 部署 Checklist

1. `pip install django-bkvision` 并加入 `requirements.txt`
2. 确认 `INSTALLED_APPS` 包含 `django_bkvision`
3. 确认 URL 路由已添加 `bkvision/`
4. 申请 `bk-vision` 网关接口权限
5. 在 BK-Vision 创建空间、数据源、图表、仪表盘
6. 发布分享链接，获取 UID
7. 配置环境变量：`BKAPP_BKVISION_APIGW_URL`、`BKAPP_BKVISION_BASE_URL`、`BKAPP_BKVISION_SYSTEM_DASHBOARD_UID`、`BKAPP_BKVISION_SPACE_DASHBOARD_UID`
8. 部署验证
