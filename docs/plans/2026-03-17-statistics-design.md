# BKFlow 运营统计模块实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 BKFlow 新增运营统计模块，支持流程模板、任务执行、插件使用三个维度的数据采集、汇总和查询。

**Architecture:** 采用"明细镜像 + 预聚合"方案。各实例通过 Django Signal → Celery Task 将明细数据写入中心统计库，定时任务生成 DailyStatisticsSummary 和 PluginExecutionSummary 预聚合表。Dashboard API 查汇总表获取趋势，查明细表做排行和钻取。

**Tech Stack:** Django 3.2+, Django REST Framework, Celery, bamboo_engine, MySQL

**Test runner:**
- Interface 模块测试: `pytest tests/interface/statistics/ -v`
- Engine 模块测试: `pytest tests/engine/statistics/ -v`
- 环境变量: 参考 `tests/interface.env` 和 `tests/engine.env`

---

## Task 1: App 基础骨架 + 配置

**Files:**
- Create: `bkflow/statistics/__init__.py`
- Create: `bkflow/statistics/apps.py`
- Create: `bkflow/statistics/conf.py`
- Modify: `env.py`
- Test: `tests/interface/statistics/__init__.py`
- Test: `tests/interface/statistics/test_conf.py`
- Test: `tests/engine/statistics/__init__.py`
- Test: `tests/engine/statistics/test_conf.py`

**Step 1: 创建 app 骨架文件**

`bkflow/statistics/__init__.py`: 空文件

`bkflow/statistics/apps.py`:
```python
from django.apps import AppConfig


class StatisticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bkflow.statistics"
    label = "statistics"
    verbose_name = "统计分析"

    def ready(self):
        from bkflow.statistics.conf import StatisticsSettings

        if StatisticsSettings.is_enabled():
            from bkflow.statistics.signals.handlers import register_statistics_signals

            register_statistics_signals()
```

**Step 2: 添加环境变量配置**

在 `env.py` 末尾追加：
```python
# 运营统计配置
STATISTICS_ENABLED = bool(os.getenv("STATISTICS_ENABLED", True))
STATISTICS_INCLUDE_MOCK = bool(os.getenv("STATISTICS_INCLUDE_MOCK", False))
STATISTICS_DETAIL_RETENTION_DAYS = int(os.getenv("STATISTICS_DETAIL_RETENTION_DAYS", 90))
STATISTICS_SUMMARY_RETENTION_DAYS = int(os.getenv("STATISTICS_SUMMARY_RETENTION_DAYS", 365))
```

**Step 3: 创建配置管理类**

`bkflow/statistics/conf.py`:
```python
from django.conf import settings

import env


class StatisticsSettings:

    @classmethod
    def is_enabled(cls) -> bool:
        return getattr(env, "STATISTICS_ENABLED", True)

    @classmethod
    def get_engine_id(cls) -> str:
        bkflow_module = getattr(settings, "BKFLOW_MODULE", None)
        if bkflow_module and hasattr(bkflow_module, "code") and bkflow_module.code:
            return bkflow_module.code
        return getattr(env, "BKFLOW_MODULE_CODE", "default") or "default"

    @classmethod
    def get_db_alias(cls) -> str:
        if "statistics" in settings.DATABASES:
            return "statistics"
        return "default"

    @classmethod
    def get_module_type(cls) -> str:
        return getattr(env, "BKFLOW_MODULE_TYPE", "") or ""

    @classmethod
    def should_collect_template_stats(cls) -> bool:
        if not cls.is_enabled():
            return False
        return cls.get_module_type() in ("interface", "")

    @classmethod
    def should_collect_task_stats(cls) -> bool:
        if not cls.is_enabled():
            return False
        return cls.get_module_type() == "engine"

    @classmethod
    def include_mock_tasks(cls) -> bool:
        return getattr(env, "STATISTICS_INCLUDE_MOCK", False)

    @classmethod
    def get_detail_retention_days(cls) -> int:
        return getattr(env, "STATISTICS_DETAIL_RETENTION_DAYS", 90)

    @classmethod
    def get_summary_retention_days(cls) -> int:
        return getattr(env, "STATISTICS_SUMMARY_RETENTION_DAYS", 365)
```

**Step 4: 写配置测试**

`tests/interface/statistics/__init__.py`: 空文件
`tests/engine/statistics/__init__.py`: 空文件

`tests/interface/statistics/test_conf.py`:
```python
from unittest.mock import patch

import pytest

from bkflow.statistics.conf import StatisticsSettings


class TestStatisticsSettings:
    def test_is_enabled_default(self):
        assert StatisticsSettings.is_enabled() is True

    @patch("bkflow.statistics.conf.env")
    def test_is_enabled_false(self, mock_env):
        mock_env.STATISTICS_ENABLED = False
        assert StatisticsSettings.is_enabled() is False

    def test_get_db_alias_default(self):
        assert StatisticsSettings.get_db_alias() == "default"

    @patch("bkflow.statistics.conf.env")
    def test_should_collect_template_stats_interface(self, mock_env):
        mock_env.STATISTICS_ENABLED = True
        mock_env.BKFLOW_MODULE_TYPE = "interface"
        assert StatisticsSettings.should_collect_template_stats() is True

    @patch("bkflow.statistics.conf.env")
    def test_should_collect_task_stats_engine(self, mock_env):
        mock_env.STATISTICS_ENABLED = True
        mock_env.BKFLOW_MODULE_TYPE = "engine"
        assert StatisticsSettings.should_collect_task_stats() is True

    @patch("bkflow.statistics.conf.env")
    def test_should_collect_task_stats_interface(self, mock_env):
        mock_env.STATISTICS_ENABLED = True
        mock_env.BKFLOW_MODULE_TYPE = "interface"
        assert StatisticsSettings.should_collect_task_stats() is False

    def test_get_detail_retention_days_default(self):
        assert StatisticsSettings.get_detail_retention_days() == 90

    def test_get_summary_retention_days_default(self):
        assert StatisticsSettings.get_summary_retention_days() == 365
```

**Step 5: 运行测试**

Run: `pytest tests/interface/statistics/test_conf.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add bkflow/statistics/ tests/interface/statistics/ tests/engine/statistics/ env.py
git commit -m "feat(statistics): 新增统计模块基础骨架和配置 --story=<TAPD_ID>"
```

---

## Task 2: 数据模型

**Files:**
- Create: `bkflow/statistics/models.py`
- Test: `tests/interface/statistics/test_models.py`

**Step 1: 写模型测试**

`tests/interface/statistics/test_models.py`:
```python
import pytest
from django.test import TestCase
from django.utils import timezone

from bkflow.statistics.models import (
    DailyStatisticsSummary,
    PluginExecutionSummary,
    TaskflowExecutedNodeStatistics,
    TaskflowStatistics,
    TemplateNodeStatistics,
    TemplateStatistics,
)


class TestTaskflowStatistics(TestCase):
    def test_create_taskflow_statistics(self):
        now = timezone.now()
        stat = TaskflowStatistics.objects.create(
            task_id=1,
            space_id=100,
            scope_type="project",
            scope_value="proj_1",
            template_id=10,
            engine_id="engine_01",
            atom_total=5,
            subprocess_total=1,
            gateways_total=2,
            create_time=now,
            is_started=False,
            is_finished=False,
            final_state="CREATED",
            create_method="API",
            trigger_method="manual",
        )
        assert stat.task_id == 1
        assert stat.space_id == 100
        assert stat.final_state == "CREATED"

    def test_taskflow_statistics_unique_task_id(self):
        now = timezone.now()
        TaskflowStatistics.objects.create(
            task_id=2, space_id=100, create_time=now, final_state="CREATED",
        )
        with pytest.raises(Exception):
            TaskflowStatistics.objects.create(
                task_id=2, space_id=100, create_time=now, final_state="CREATED",
            )


class TestTemplateStatistics(TestCase):
    def test_create_template_statistics(self):
        stat = TemplateStatistics.objects.create(
            template_id=1,
            space_id=100,
            atom_total=3,
            subprocess_total=1,
            gateways_total=2,
            template_name="test_template",
            is_enabled=True,
            template_create_time=timezone.now(),
            template_update_time=timezone.now(),
        )
        assert stat.template_id == 1
        assert stat.template_name == "test_template"


class TestDailyStatisticsSummary(TestCase):
    def test_unique_together(self):
        from datetime import date

        DailyStatisticsSummary.objects.create(
            date=date(2026, 1, 1),
            space_id=100,
            scope_type="project",
            scope_value="proj_1",
        )
        with pytest.raises(Exception):
            DailyStatisticsSummary.objects.create(
                date=date(2026, 1, 1),
                space_id=100,
                scope_type="project",
                scope_value="proj_1",
            )

    def test_scope_defaults_to_empty_string(self):
        from datetime import date

        summary = DailyStatisticsSummary.objects.create(
            date=date(2026, 1, 2), space_id=100,
        )
        assert summary.scope_type == ""
        assert summary.scope_value == ""
```

**Step 2: 运行测试确认失败**

Run: `pytest tests/interface/statistics/test_models.py -v`
Expected: FAIL (models not defined yet)

**Step 3: 实现模型**

`bkflow/statistics/models.py`:
```python
from django.db import models


class StatisticsBaseModel(models.Model):
    class Meta:
        abstract = True
        app_label = "statistics"


class TaskflowStatistics(StatisticsBaseModel):
    id = models.BigAutoField(primary_key=True)
    task_id = models.BigIntegerField("任务ID", unique=True, db_index=True)
    space_id = models.BigIntegerField("空间ID", db_index=True)
    scope_type = models.CharField("范围类型", max_length=64, default="")
    scope_value = models.CharField("范围值", max_length=255, default="")
    template_id = models.BigIntegerField("关联模板ID", null=True, blank=True, db_index=True)
    engine_id = models.CharField("Engine标识", max_length=64, default="", db_index=True)

    atom_total = models.IntegerField("标准插件节点总数", default=0)
    subprocess_total = models.IntegerField("子流程节点总数", default=0)
    gateways_total = models.IntegerField("网关节点总数", default=0)

    create_time = models.DateTimeField("任务创建时间", db_index=True)
    start_time = models.DateTimeField("启动时间", null=True, blank=True)
    finish_time = models.DateTimeField("结束时间", null=True, blank=True)
    elapsed_time = models.IntegerField("执行耗时(秒)", null=True, blank=True)

    is_started = models.BooleanField("是否已启动", default=False)
    is_finished = models.BooleanField("是否已完成", default=False)
    final_state = models.CharField("最终状态", max_length=32, default="CREATED", db_index=True)

    create_method = models.CharField("创建方式", max_length=32, default="API")
    trigger_method = models.CharField("触发方式", max_length=32, default="manual")

    created_at = models.DateTimeField("记录创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("记录更新时间", auto_now=True)

    class Meta(StatisticsBaseModel.Meta):
        verbose_name = "任务统计"
        verbose_name_plural = "任务统计"
        indexes = [
            models.Index(fields=["space_id", "create_time"]),
            models.Index(fields=["template_id", "create_time"]),
            models.Index(fields=["engine_id", "create_time"]),
        ]

    def __str__(self):
        return f"Task_{self.task_id}"


class TaskflowExecutedNodeStatistics(StatisticsBaseModel):
    id = models.BigAutoField(primary_key=True)
    task_id = models.BigIntegerField("任务ID", db_index=True)
    space_id = models.BigIntegerField("空间ID", db_index=True)
    engine_id = models.CharField("Engine标识", max_length=64, default="")

    component_code = models.CharField("组件编码", max_length=255, db_index=True)
    version = models.CharField("插件版本", max_length=255, default="legacy")
    is_remote = models.BooleanField("是否第三方插件", default=False)

    node_id = models.CharField("节点ID", max_length=64)
    started_time = models.DateTimeField("执行开始时间", db_index=True)
    archived_time = models.DateTimeField("执行结束时间", null=True, blank=True)
    elapsed_time = models.IntegerField("耗时(秒)", null=True, blank=True)

    status = models.BooleanField("执行结果", default=False)
    state = models.CharField("节点状态", max_length=32, default="")
    is_skip = models.BooleanField("是否跳过", default=False)
    is_retry = models.BooleanField("是否重试记录", default=False)
    retry_count = models.IntegerField("重试次数", default=0)

    created_at = models.DateTimeField("记录创建时间", auto_now_add=True)

    class Meta(StatisticsBaseModel.Meta):
        verbose_name = "节点执行统计"
        verbose_name_plural = "节点执行统计"
        indexes = [
            models.Index(fields=["space_id", "component_code", "started_time"]),
            models.Index(fields=["task_id", "node_id"]),
            models.Index(fields=["component_code", "status", "started_time"]),
            models.Index(fields=["engine_id", "started_time"]),
        ]

    def __str__(self):
        return f"{self.component_code}_{self.task_id}_{self.node_id}"


class TemplateStatistics(StatisticsBaseModel):
    id = models.BigAutoField(primary_key=True)
    template_id = models.BigIntegerField("模板ID", unique=True, db_index=True)
    space_id = models.BigIntegerField("空间ID", db_index=True)
    scope_type = models.CharField("范围类型", max_length=64, default="")
    scope_value = models.CharField("范围值", max_length=255, default="")

    atom_total = models.IntegerField("标准插件节点总数", default=0)
    subprocess_total = models.IntegerField("子流程节点总数", default=0)
    gateways_total = models.IntegerField("网关节点总数", default=0)

    template_name = models.CharField("模板名称", max_length=255, default="")
    is_enabled = models.BooleanField("是否启用", default=True)
    template_create_time = models.DateTimeField("模板创建时间", null=True)
    template_update_time = models.DateTimeField("模板更新时间", null=True)

    created_at = models.DateTimeField("记录创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("记录更新时间", auto_now=True)

    class Meta(StatisticsBaseModel.Meta):
        verbose_name = "模板统计"
        verbose_name_plural = "模板统计"

    def __str__(self):
        return f"Template_{self.template_id}"


class TemplateNodeStatistics(StatisticsBaseModel):
    id = models.BigAutoField(primary_key=True)
    component_code = models.CharField("组件编码", max_length=255, db_index=True)
    version = models.CharField("插件版本", max_length=255, default="legacy")
    is_remote = models.BooleanField("是否第三方插件", default=False)

    template_id = models.BigIntegerField("模板ID", db_index=True)
    space_id = models.BigIntegerField("空间ID", db_index=True)
    scope_type = models.CharField("范围类型", max_length=64, default="")
    scope_value = models.CharField("范围值", max_length=255, default="")

    node_id = models.CharField("节点ID", max_length=64)
    node_name = models.CharField("节点名称", max_length=255, default="")
    is_sub = models.BooleanField("是否子流程内引用", default=False)
    subprocess_stack = models.TextField("子流程堆栈", default="[]")

    created_at = models.DateTimeField("记录创建时间", auto_now_add=True)

    class Meta(StatisticsBaseModel.Meta):
        verbose_name = "模板节点统计"
        verbose_name_plural = "模板节点统计"
        indexes = [
            models.Index(fields=["space_id", "component_code"]),
            models.Index(fields=["template_id", "node_id"]),
        ]

    def __str__(self):
        return f"{self.component_code}_{self.template_id}_{self.node_id}"


class DailyStatisticsSummary(StatisticsBaseModel):
    id = models.BigAutoField(primary_key=True)
    date = models.DateField("统计日期", db_index=True)
    space_id = models.BigIntegerField("空间ID", db_index=True)
    scope_type = models.CharField("范围类型", max_length=64, default="")
    scope_value = models.CharField("范围值", max_length=255, default="")

    task_created_count = models.IntegerField("创建任务数", default=0)
    task_finished_count = models.IntegerField("完成任务数", default=0)
    task_success_count = models.IntegerField("成功任务数", default=0)
    task_failed_count = models.IntegerField("失败任务数", default=0)
    task_revoked_count = models.IntegerField("撤销任务数", default=0)

    node_executed_count = models.IntegerField("执行节点数", default=0)
    node_success_count = models.IntegerField("成功节点数", default=0)
    node_failed_count = models.IntegerField("失败节点数", default=0)

    avg_task_elapsed_time = models.FloatField("平均任务耗时(秒)", default=0)
    max_task_elapsed_time = models.IntegerField("最大任务耗时(秒)", default=0)

    created_at = models.DateTimeField("记录创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("记录更新时间", auto_now=True)

    class Meta(StatisticsBaseModel.Meta):
        verbose_name = "每日统计汇总"
        verbose_name_plural = "每日统计汇总"
        unique_together = ["date", "space_id", "scope_type", "scope_value"]
        indexes = [
            models.Index(fields=["space_id", "date"]),
        ]

    def __str__(self):
        return f"DailySummary_{self.space_id}_{self.date}"


class PluginExecutionSummary(StatisticsBaseModel):
    id = models.BigAutoField(primary_key=True)
    period_type = models.CharField("周期类型", max_length=16, db_index=True)
    period_start = models.DateField("周期开始日期", db_index=True)
    space_id = models.BigIntegerField("空间ID", db_index=True)

    component_code = models.CharField("组件编码", max_length=255, db_index=True)
    version = models.CharField("插件版本", max_length=255, default="legacy")
    is_remote = models.BooleanField("是否第三方插件", default=False)

    execution_count = models.IntegerField("执行次数", default=0)
    success_count = models.IntegerField("成功次数", default=0)
    failed_count = models.IntegerField("失败次数", default=0)

    avg_elapsed_time = models.FloatField("平均耗时(秒)", default=0)
    max_elapsed_time = models.IntegerField("最大耗时(秒)", default=0)

    created_at = models.DateTimeField("记录创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("记录更新时间", auto_now=True)

    class Meta(StatisticsBaseModel.Meta):
        verbose_name = "插件执行汇总"
        verbose_name_plural = "插件执行汇总"
        unique_together = ["period_type", "period_start", "space_id", "component_code", "version"]
        indexes = [
            models.Index(fields=["space_id", "component_code", "period_start"]),
        ]

    def __str__(self):
        return f"PluginSummary_{self.component_code}_{self.period_type}_{self.period_start}"
```

**Step 4: 生成 migration**

Run: `python manage.py makemigrations statistics`
Expected: `0001_initial.py` created

**Step 5: 运行测试**

Run: `pytest tests/interface/statistics/test_models.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add bkflow/statistics/models.py bkflow/statistics/migrations/
git add tests/interface/statistics/test_models.py
git commit -m "feat(statistics): 新增统计数据模型 --story=<TAPD_ID>"
```

---

## Task 3: 数据库路由

**Files:**
- Create: `bkflow/statistics/db_router.py`
- Test: `tests/interface/statistics/test_db_router.py`

**Step 1: 写路由测试**

`tests/interface/statistics/test_db_router.py`:
```python
from unittest.mock import MagicMock, patch

from bkflow.statistics.db_router import StatisticsDBRouter
from bkflow.statistics.models import TaskflowStatistics, TemplateStatistics


class TestStatisticsDBRouter:
    def setup_method(self):
        self.router = StatisticsDBRouter()

    def test_db_for_read_statistics_model_fallback(self):
        result = self.router.db_for_read(TaskflowStatistics)
        assert result == "default"

    def test_db_for_write_statistics_model_fallback(self):
        result = self.router.db_for_write(TaskflowStatistics)
        assert result == "default"

    def test_db_for_read_non_statistics_model(self):
        non_stat_model = MagicMock()
        non_stat_model._meta.app_label = "task"
        result = self.router.db_for_read(non_stat_model)
        assert result is None

    def test_allow_relation_both_statistics(self):
        obj1 = MagicMock()
        obj1._meta.app_label = "statistics"
        obj2 = MagicMock()
        obj2._meta.app_label = "statistics"
        assert self.router.allow_relation(obj1, obj2) is True

    def test_allow_relation_mixed(self):
        obj1 = MagicMock()
        obj1._meta.app_label = "statistics"
        obj2 = MagicMock()
        obj2._meta.app_label = "task"
        assert self.router.allow_relation(obj1, obj2) is False

    def test_allow_migrate_statistics_to_default(self):
        assert self.router.allow_migrate("default", "statistics") is True

    def test_allow_migrate_other_app_not_to_statistics(self):
        assert self.router.allow_migrate("statistics", "task") is False
```

**Step 2: 运行测试确认失败**

Run: `pytest tests/interface/statistics/test_db_router.py -v`
Expected: FAIL

**Step 3: 实现路由**

`bkflow/statistics/db_router.py`:
```python
class StatisticsDBRouter:
    APP_LABEL = "statistics"
    DB_ALIAS = "statistics"

    def db_for_read(self, model, **hints):
        if model._meta.app_label == self.APP_LABEL:
            return self._get_db_alias()
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == self.APP_LABEL:
            return self._get_db_alias()
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if obj1._meta.app_label == self.APP_LABEL and obj2._meta.app_label == self.APP_LABEL:
            return True
        if obj1._meta.app_label == self.APP_LABEL or obj2._meta.app_label == self.APP_LABEL:
            return False
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == self.APP_LABEL:
            return db == self._get_db_alias()
        return db != self.DB_ALIAS

    def _get_db_alias(self):
        from django.conf import settings

        if self.DB_ALIAS in settings.DATABASES:
            return self.DB_ALIAS
        return "default"
```

**Step 4: 运行测试**

Run: `pytest tests/interface/statistics/test_db_router.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add bkflow/statistics/db_router.py tests/interface/statistics/test_db_router.py
git commit -m "feat(statistics): 新增统计数据库路由 --story=<TAPD_ID>"
```

---

## Task 4: 采集器基类

**Files:**
- Create: `bkflow/statistics/collectors/__init__.py`
- Create: `bkflow/statistics/collectors/base.py`
- Test: `tests/interface/statistics/test_collectors_base.py`

**Step 1: 写基类测试**

`tests/interface/statistics/test_collectors_base.py`:
```python
from bkflow.statistics.collectors.base import BaseStatisticsCollector


class TestCountPipelineTreeNodes:
    def test_simple_tree(self):
        tree = {
            "activities": {
                "act1": {"type": "ServiceActivity"},
                "act2": {"type": "ServiceActivity"},
                "act3": {"type": "SubProcess", "pipeline": {"activities": {}, "gateways": {}}},
            },
            "gateways": {"gw1": {}},
        }
        atom, sub, gw = BaseStatisticsCollector.count_pipeline_tree_nodes(tree)
        assert atom == 2
        assert sub == 1
        assert gw == 1

    def test_recursive_subprocess(self):
        tree = {
            "activities": {
                "sub1": {
                    "type": "SubProcess",
                    "pipeline": {
                        "activities": {
                            "act_inner": {"type": "ServiceActivity"},
                            "sub_inner": {
                                "type": "SubProcess",
                                "pipeline": {
                                    "activities": {"deep_act": {"type": "ServiceActivity"}},
                                    "gateways": {"deep_gw": {}},
                                },
                            },
                        },
                        "gateways": {"inner_gw": {}},
                    },
                },
            },
            "gateways": {"top_gw": {}},
        }
        atom, sub, gw = BaseStatisticsCollector.count_pipeline_tree_nodes(tree)
        assert atom == 2
        assert sub == 2
        assert gw == 3  # top_gw + inner_gw + deep_gw

    def test_empty_tree(self):
        atom, sub, gw = BaseStatisticsCollector.count_pipeline_tree_nodes({})
        assert atom == 0
        assert sub == 0
        assert gw == 0


class TestParseDatetime:
    def test_none_input(self):
        assert BaseStatisticsCollector.parse_datetime(None) is None

    def test_empty_string(self):
        assert BaseStatisticsCollector.parse_datetime("") is None

    def test_iso_format(self):
        result = BaseStatisticsCollector.parse_datetime("2026-01-15T13:00:00+08:00")
        assert result is not None

    def test_datetime_passthrough(self):
        from django.utils import timezone

        now = timezone.now()
        assert BaseStatisticsCollector.parse_datetime(now) is now
```

**Step 2: 运行测试确认失败**

Run: `pytest tests/interface/statistics/test_collectors_base.py -v`
Expected: FAIL

**Step 3: 实现基类**

`bkflow/statistics/collectors/__init__.py`:
```python
from bkflow.statistics.collectors.base import BaseStatisticsCollector  # noqa
```

`bkflow/statistics/collectors/base.py`:
```python
import logging
from abc import ABC, abstractmethod
from typing import Tuple

from bkflow.statistics.conf import StatisticsSettings

logger = logging.getLogger("celery")


class BaseStatisticsCollector(ABC):

    def __init__(self):
        self.db_alias = StatisticsSettings.get_db_alias()
        self.engine_id = StatisticsSettings.get_engine_id()

    @abstractmethod
    def collect(self):
        raise NotImplementedError

    @staticmethod
    def count_pipeline_tree_nodes(pipeline_tree: dict) -> Tuple[int, int, int]:
        activities = pipeline_tree.get("activities", {})
        gateways = pipeline_tree.get("gateways", {})

        atom_total = 0
        subprocess_total = 0
        gateways_total = len(gateways)

        for act_id, act in activities.items():
            act_type = act.get("type", "")
            if act_type == "ServiceActivity":
                atom_total += 1
            elif act_type == "SubProcess":
                subprocess_total += 1
                sub_pipeline = act.get("pipeline", {})
                if sub_pipeline:
                    sub_atom, sub_sub, sub_gw = BaseStatisticsCollector.count_pipeline_tree_nodes(sub_pipeline)
                    atom_total += sub_atom
                    subprocess_total += sub_sub
                    gateways_total += sub_gw

        return atom_total, subprocess_total, gateways_total

    @staticmethod
    def parse_datetime(time_str):
        if not time_str:
            return None
        from django.utils.dateparse import parse_datetime

        if isinstance(time_str, str):
            time_str = time_str.replace(" +", "+").replace(" -", "-")
            return parse_datetime(time_str)
        return time_str
```

**Step 4: 运行测试**

Run: `pytest tests/interface/statistics/test_collectors_base.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add bkflow/statistics/collectors/ tests/interface/statistics/test_collectors_base.py
git commit -m "feat(statistics): 新增采集器基类 --story=<TAPD_ID>"
```

---

## Task 5: 模板采集器

**Files:**
- Create: `bkflow/statistics/collectors/template_collector.py`
- Test: `tests/interface/statistics/test_template_collector.py`

**Step 1: 写模板采集器测试**

`tests/interface/statistics/test_template_collector.py`:
```python
from unittest.mock import MagicMock, PropertyMock, patch

from django.test import TestCase
from django.utils import timezone

from bkflow.statistics.collectors.template_collector import TemplateStatisticsCollector
from bkflow.statistics.models import TemplateNodeStatistics, TemplateStatistics


class TestTemplateStatisticsCollector(TestCase):
    def _make_mock_template(self, template_id=1):
        mock = MagicMock()
        mock.id = template_id
        mock.space_id = 100
        mock.scope_type = "project"
        mock.scope_value = "proj_1"
        mock.name = "test_template"
        mock.creator = "admin"
        mock.is_enabled = True
        mock.create_at = timezone.now()
        mock.update_at = timezone.now()
        mock.snapshot_id = 10
        mock.pipeline_tree = {
            "activities": {
                "act1": {
                    "type": "ServiceActivity",
                    "name": "HTTP请求",
                    "component": {"code": "bk_http_request", "version": "v1.0"},
                },
                "act2": {
                    "type": "ServiceActivity",
                    "name": "远程插件",
                    "component": {
                        "code": "remote_plugin",
                        "version": "legacy",
                        "inputs": {
                            "plugin_code": {"value": "my_plugin"},
                            "plugin_version": {"value": "1.0.0"},
                        },
                    },
                },
            },
            "gateways": {"gw1": {}},
        }
        return mock

    @patch("bkflow.statistics.collectors.template_collector.TemplateStatisticsCollector.template",
           new_callable=PropertyMock)
    def test_collect_creates_template_statistics(self, mock_template_prop):
        mock_template_prop.return_value = self._make_mock_template()
        collector = TemplateStatisticsCollector(template_id=1, snapshot_id=10)
        result = collector.collect()
        assert result is True
        assert TemplateStatistics.objects.filter(template_id=1).exists()
        stat = TemplateStatistics.objects.get(template_id=1)
        assert stat.atom_total == 2
        assert stat.gateways_total == 1

    @patch("bkflow.statistics.collectors.template_collector.TemplateStatisticsCollector.template",
           new_callable=PropertyMock)
    def test_collect_creates_node_statistics(self, mock_template_prop):
        mock_template_prop.return_value = self._make_mock_template()
        collector = TemplateStatisticsCollector(template_id=1, snapshot_id=10)
        collector.collect()
        nodes = TemplateNodeStatistics.objects.filter(template_id=1)
        assert nodes.count() == 2
        codes = set(nodes.values_list("component_code", flat=True))
        assert "bk_http_request" in codes
        assert "my_plugin" in codes

    @patch("bkflow.statistics.collectors.template_collector.TemplateStatisticsCollector.template",
           new_callable=PropertyMock)
    def test_collect_remote_plugin_extraction(self, mock_template_prop):
        mock_template_prop.return_value = self._make_mock_template()
        collector = TemplateStatisticsCollector(template_id=1, snapshot_id=10)
        collector.collect()
        remote_node = TemplateNodeStatistics.objects.get(template_id=1, is_remote=True)
        assert remote_node.component_code == "my_plugin"
        assert remote_node.version == "1.0.0"

    @patch("bkflow.statistics.collectors.template_collector.TemplateStatisticsCollector.template",
           new_callable=PropertyMock)
    def test_collect_idempotent(self, mock_template_prop):
        mock_template_prop.return_value = self._make_mock_template()
        collector = TemplateStatisticsCollector(template_id=1, snapshot_id=10)
        collector.collect()
        collector.collect()
        assert TemplateStatistics.objects.filter(template_id=1).count() == 1
        assert TemplateNodeStatistics.objects.filter(template_id=1).count() == 2
```

**Step 2: 运行测试确认失败**

Run: `pytest tests/interface/statistics/test_template_collector.py -v`
Expected: FAIL

**Step 3: 实现模板采集器**

`bkflow/statistics/collectors/template_collector.py`:
```python
import logging
from copy import deepcopy
from typing import List

import ujson as json
from django.db import transaction

from bkflow.statistics.collectors.base import BaseStatisticsCollector
from bkflow.statistics.models import TemplateNodeStatistics, TemplateStatistics

logger = logging.getLogger("celery")


class TemplateStatisticsCollector(BaseStatisticsCollector):

    def __init__(self, template_id: int, snapshot_id: int = None):
        super().__init__()
        self.template_id = template_id
        self.snapshot_id = snapshot_id
        self._template = None

    @property
    def template(self):
        if self._template is None:
            try:
                from bkflow.template.models import Template
                self._template = Template.objects.get(id=self.template_id)
            except Exception as e:
                logger.warning(f"Template {self.template_id} not found: {e}")
        return self._template

    def collect(self):
        if not self.template:
            return False
        try:
            self._collect_template_statistics()
            self._collect_node_statistics()
            return True
        except Exception as e:
            logger.exception(f"[TemplateStatisticsCollector] template_id={self.template_id} error: {e}")
            return False

    def collect_meta_only(self):
        """仅更新模板元信息（name/is_enabled），不重新采集节点"""
        if not self.template:
            return False
        try:
            TemplateStatistics.objects.using(self.db_alias).filter(
                template_id=self.template_id
            ).update(
                template_name=self.template.name,
                is_enabled=self.template.is_enabled,
                template_update_time=self.template.update_at,
            )
            return True
        except Exception as e:
            logger.exception(f"[TemplateStatisticsCollector] collect_meta_only error: {e}")
            return False

    def _collect_template_statistics(self):
        pipeline_tree = self.template.pipeline_tree or {}
        atom_total, subprocess_total, gateways_total = self.count_pipeline_tree_nodes(pipeline_tree)

        TemplateStatistics.objects.using(self.db_alias).update_or_create(
            template_id=self.template_id,
            defaults={
                "space_id": self.template.space_id,
                "scope_type": self.template.scope_type or "",
                "scope_value": self.template.scope_value or "",
                "atom_total": atom_total,
                "subprocess_total": subprocess_total,
                "gateways_total": gateways_total,
                "template_name": self.template.name,
                "is_enabled": self.template.is_enabled,
                "template_create_time": self.template.create_at,
                "template_update_time": self.template.update_at,
            },
        )

    def _collect_node_statistics(self):
        pipeline_tree = self.template.pipeline_tree or {}
        component_list = self._collect_nodes(pipeline_tree, [], False)

        with transaction.atomic(using=self.db_alias):
            TemplateNodeStatistics.objects.using(self.db_alias).filter(
                template_id=self.template_id
            ).delete()
            if component_list:
                TemplateNodeStatistics.objects.using(self.db_alias).bulk_create(
                    component_list, batch_size=100
                )

    def _collect_nodes(
        self, pipeline_tree: dict, subprocess_stack: list, is_sub: bool
    ) -> List[TemplateNodeStatistics]:
        component_list = []
        activities = pipeline_tree.get("activities", {})

        for act_id, act in activities.items():
            act_type = act.get("type", "")

            if act_type == "ServiceActivity":
                component = act.get("component", {})
                code = component.get("code", "")
                version = component.get("version", "legacy")
                is_remote = False

                if code == "remote_plugin":
                    inputs = component.get("inputs", {})
                    code = inputs.get("plugin_code", {}).get("value", code)
                    version = inputs.get("plugin_version", {}).get("value", version)
                    is_remote = True

                component_list.append(TemplateNodeStatistics(
                    component_code=code,
                    version=version,
                    is_remote=is_remote,
                    template_id=self.template_id,
                    space_id=self.template.space_id,
                    scope_type=self.template.scope_type or "",
                    scope_value=self.template.scope_value or "",
                    node_id=act_id,
                    node_name=act.get("name", ""),
                    is_sub=is_sub,
                    subprocess_stack=json.dumps(subprocess_stack),
                ))

            elif act_type == "SubProcess":
                sub_pipeline = act.get("pipeline", {})
                if sub_pipeline:
                    new_stack = deepcopy(subprocess_stack)
                    new_stack.insert(0, act_id)
                    component_list.extend(
                        self._collect_nodes(sub_pipeline, new_stack, True)
                    )

        return component_list
```

更新 `bkflow/statistics/collectors/__init__.py`:
```python
from bkflow.statistics.collectors.base import BaseStatisticsCollector  # noqa
from bkflow.statistics.collectors.template_collector import TemplateStatisticsCollector  # noqa
```

**Step 4: 运行测试**

Run: `pytest tests/interface/statistics/test_template_collector.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add bkflow/statistics/collectors/ tests/interface/statistics/test_template_collector.py
git commit -m "feat(statistics): 新增模板统计采集器 --story=<TAPD_ID>"
```

---

## Task 6: 任务采集器

**Files:**
- Create: `bkflow/statistics/collectors/task_collector.py`
- Test: `tests/engine/statistics/test_task_collector.py`

由于任务采集器依赖 `bamboo_engine` 和 `TaskInstance`，测试需要大量 mock。实现和测试参考模板采集器的模式。

**核心逻辑要点：**
- `collect_on_create`: 任务创建时写入 `TaskflowStatistics`
- `collect_on_archive`: 任务完成/撤销时更新 `TaskflowStatistics` + 写入 `TaskflowExecutedNodeStatistics`
- `final_state` 直接映射 pipeline 根节点状态
- `is_retry` 通过 bamboo_engine 状态树的 version 判断
- delete + bulk_create 在 `transaction.atomic` 中执行

**Step 1: 写任务采集器测试**（参考设计文档中的逻辑要点编写测试）

**Step 2: 运行测试确认失败**

**Step 3: 实现任务采集器**

**Step 4: 运行测试确认通过**

**Step 5: Commit**

```bash
git add bkflow/statistics/collectors/ tests/engine/statistics/
git commit -m "feat(statistics): 新增任务统计采集器 --story=<TAPD_ID>"
```

---

## Task 7: Celery 异步任务

**Files:**
- Create: `bkflow/statistics/tasks/__init__.py`
- Create: `bkflow/statistics/tasks/template_tasks.py`
- Create: `bkflow/statistics/tasks/task_tasks.py`
- Create: `bkflow/statistics/tasks/summary_tasks.py`
- Test: `tests/interface/statistics/test_tasks.py`
- Test: `tests/engine/statistics/test_tasks.py`

**核心逻辑：**
- `template_post_save_statistics_task(template_id, old_snapshot_id, new_snapshot_id)`: 对比 snapshot_id 决定全量采集还是仅更新元信息
- `task_created_statistics_task(task_id)`: 调用 `TaskStatisticsCollector.collect_on_create`
- `task_archive_statistics_task(instance_id)`: 调用 `TaskStatisticsCollector.collect_on_archive`
- `generate_daily_summary_task(target_date)`: 生成每日汇总，包含空洞补全
- `generate_plugin_summary_task(period_type, target_date)`: 生成插件汇总
- `clean_expired_statistics_task()`: 按保留策略清理所有表

所有任务均使用 `@shared_task(bind=True, ignore_result=True)`，开头检查 `StatisticsSettings.is_enabled()`。

**Step 1-5:** 按 TDD 流程实现并测试。

**Commit:**
```bash
git commit -m "feat(statistics): 新增统计 Celery 任务 --story=<TAPD_ID>"
```

---

## Task 8: 信号处理

**Files:**
- Create: `bkflow/statistics/signals/__init__.py`
- Create: `bkflow/statistics/signals/handlers.py`
- Test: `tests/interface/statistics/test_signals.py`

**核心逻辑：**

`register_statistics_signals()`:
- Interface 模块：监听 `Template.post_save`，触发时比较 `instance.snapshot_id` 与旧值，决定采集方式
- Engine 模块：监听 `TaskInstance.post_save(created=True)` + `post_set_state(root→FINISHED/REVOKED)`
- 使用 `dispatch_uid` 防止重复注册
- 全部通过 `.delay()` 异步调用，不阻塞主流程

**模板信号的变更检测：**
```python
@receiver(post_save, sender=Template, dispatch_uid="template_statistics_post_save")
def template_post_save_handler(sender, instance, created, update_fields, **kwargs):
    old_snapshot_id = getattr(instance, "_pre_save_snapshot_id", None)
    template_post_save_statistics_task.delay(
        template_id=instance.id,
        old_snapshot_id=old_snapshot_id,
        new_snapshot_id=instance.snapshot_id,
    )
```

需要在 Template.save() 前记录 `_pre_save_snapshot_id`，通过 `pre_save` 信号实现。

**Step 1-5:** 按 TDD 流程实现并测试。

**Commit:**
```bash
git commit -m "feat(statistics): 新增统计信号处理 --story=<TAPD_ID>"
```

---

## Task 9: Serializers

**Files:**
- Create: `bkflow/statistics/serializers.py`
- Test: `tests/interface/statistics/test_serializers.py`

**需要的 Serializer：**
- `StatisticsOverviewSerializer` — 概览 KPI
- `TaskTrendSerializer` — 趋势数据
- `PluginRankingSerializer` — 插件排行
- `TemplateRankingSerializer` — 模板排行
- `SpaceRankingSerializer` — 空间排行
- `FailureAnalysisSerializer` — 失败分析
- `DailyStatisticsSummarySerializer` — 每日汇总 ModelSerializer

所有 Serializer 均为只读。

**Step 1-5:** 按 TDD 流程实现并测试。

**Commit:**
```bash
git commit -m "feat(statistics): 新增统计序列化器 --story=<TAPD_ID>"
```

---

## Task 10: API Views

**Files:**
- Create: `bkflow/statistics/views.py`
- Test: `tests/interface/statistics/test_views.py`

**两套 ViewSet：**

1. `SystemStatisticsViewSet` — 系统管理员视角（全局）
   - `permission_classes = [AdminPermission | AppInternalPermission]`
   - `overview` / `space_ranking` / `plugin_ranking` / `task_trend` / `failure_analysis`

2. `SpaceStatisticsViewSet` — 空间管理员视角
   - `permission_classes = [AdminPermission | AppInternalPermission]`（后续可细化空间权限）
   - URL 中含 `space_id` 参数
   - `overview` / `task_trend` / `plugin_ranking` / `template_ranking` / `failure_analysis` / `daily_summary`

**通用逻辑抽取：**
- `_get_date_range(request)`: 支持 `date_start/date_end` 和 `date_range` 快捷参数
- `_validate_order_by(value, allowed)`: 白名单校验排序字段
- `_get_limit(request, max_val=100)`: 带上界的 limit 参数

**Step 1-5:** 按 TDD 流程实现并测试。测试使用 `APIRequestFactory` + mock 数据。

**Commit:**
```bash
git commit -m "feat(statistics): 新增统计 API 视图 --story=<TAPD_ID>"
```

---

## Task 11: URL 路由 + 项目集成

**Files:**
- Create: `bkflow/statistics/urls.py`
- Modify: `bkflow/urls.py:31-46` — 在 interface 模块 urlpatterns 中添加统计 URL
- Modify: `module_settings.py:139-158` — 在 engine INSTALLED_APPS 中添加 `bkflow.statistics`
- Modify: `module_settings.py:216-246` — 在 interface INSTALLED_APPS 中添加 `bkflow.statistics`
- Modify: `module_settings.py:168-173` — 在 engine beat_schedule 中添加统计定时任务
- Modify: `module_settings.py:284-290` — 在 interface beat_schedule 中添加统计定时任务

**Step 1: 创建 URL 配置**

`bkflow/statistics/urls.py`:
```python
from django.conf.urls import url
from django.urls import include
from rest_framework.routers import DefaultRouter

from bkflow.statistics.views import SpaceStatisticsViewSet, SystemStatisticsViewSet

router = DefaultRouter()
router.register(r"system", SystemStatisticsViewSet, basename="system_statistics")
router.register(r"spaces/(?P<space_id>\d+)", SpaceStatisticsViewSet, basename="space_statistics")

urlpatterns = [
    url(r"^", include(router.urls)),
]
```

**Step 2: 注册到 bkflow/urls.py**

在 interface urlpatterns 中添加:
```python
url(r"^api/statistics/", include("bkflow.statistics.urls")),
```

**Step 3: 添加到 INSTALLED_APPS**

在 `module_settings.py` engine 和 interface 的 INSTALLED_APPS 中都添加 `"bkflow.statistics"`。

**Step 4: 配置 beat_schedule**

Engine 模块 beat_schedule 添加:
```python
"statistics_daily_summary": {
    "task": "bkflow.statistics.tasks.summary_tasks.generate_daily_summary_task",
    "schedule": crontab(minute=30, hour=1),
},
"statistics_plugin_summary_day": {
    "task": "bkflow.statistics.tasks.summary_tasks.generate_plugin_summary_task",
    "schedule": crontab(minute=0, hour=2),
    "args": ("day",),
},
"statistics_plugin_summary_week": {
    "task": "bkflow.statistics.tasks.summary_tasks.generate_plugin_summary_task",
    "schedule": crontab(minute=0, hour=3, day_of_week=1),
    "args": ("week",),
},
"statistics_clean_expired": {
    "task": "bkflow.statistics.tasks.summary_tasks.clean_expired_statistics_task",
    "schedule": crontab(minute=0, hour=4),
},
```

**Step 5: 添加 DATABASE_ROUTERS**

在 `module_settings.py` 或 `config/default.py` 中确保：
```python
DATABASE_ROUTERS = ["bkflow.statistics.db_router.StatisticsDBRouter"]
```

**Step 6: Commit**

```bash
git commit -m "feat(statistics): 集成统计模块到项目配置 --story=<TAPD_ID>"
```

---

## Task 12: Admin 配置

**Files:**
- Create: `bkflow/statistics/admin.py`

简单注册所有模型到 Django Admin，方便运维查看数据。

**Commit:**
```bash
git commit -m "feat(statistics): 新增统计模型 Admin 配置 --story=<TAPD_ID>"
```

---

## Task 13: 回填管理命令

**Files:**
- Create: `bkflow/statistics/management/__init__.py`
- Create: `bkflow/statistics/management/commands/__init__.py`
- Create: `bkflow/statistics/management/commands/backfill_statistics.py`

**核心参数：**
- `--type template|task|summary|all`
- `--space-id <id>`
- `--days <n>` (默认 30)
- `--batch-size <n>` (默认 100)
- `--dry-run`

**逻辑：**
- template 回填: 遍历 Template.objects.all()，逐个调用 TemplateStatisticsCollector
- task 回填: 遍历当前模块 default 库的 TaskInstance，调用 TaskStatisticsCollector，自动写入 engine_id 标识
- summary 回填: 遍历指定日期范围，调用 _generate_daily_summary + _generate_plugin_summary

**多 engine 部署注意事项：**
- 各 engine 模块的 TaskInstance 存储在各自独立的数据库中
- `--type=template` 只需在 interface 模块执行一次（模板数据仅在 interface 库）
- `--type=task` 需要在**每个 engine 模块分别执行**（各自只能查到自己库中的任务）
- `--type=summary` 需在 template 和 task 回填全部完成后，在 interface 模块执行一次
- `--type=all` 不建议使用，会在非对应模块上产生无效的回填（0 条）
- 推荐执行顺序：interface 跑 template → 每个 engine 跑 task → interface 跑 summary

**Commit:**
```bash
git commit -m "feat(statistics): 新增统计数据回填管理命令 --story=<TAPD_ID>"
```

---

## Task 14: 端到端集成验证

**Step 1: 运行全部统计模块测试**

```bash
pytest tests/interface/statistics/ tests/engine/statistics/ -v
```

Expected: ALL PASS

**Step 2: 运行完整项目测试确认无回归**

```bash
bash scripts/run_interface_unit_test.sh
bash scripts/run_engine_unit_test.sh
```

Expected: ALL PASS, 无回归

**Step 3: 验证 migration**

```bash
python manage.py makemigrations --check --dry-run
```

Expected: "No changes detected"

**Step 4: Final Commit**

```bash
git commit -m "test(statistics): 补充集成测试验证 --story=<TAPD_ID>"
```

---

## 执行顺序总结

| 顺序 | Task | 依赖 |
|------|------|------|
| 1 | App 骨架 + 配置 | 无 |
| 2 | 数据模型 | Task 1 |
| 3 | 数据库路由 | Task 2 |
| 4 | 采集器基类 | Task 1 |
| 5 | 模板采集器 | Task 2, 4 |
| 6 | 任务采集器 | Task 2, 4 |
| 7 | Celery 任务 | Task 5, 6 |
| 8 | 信号处理 | Task 7 |
| 9 | Serializers | Task 2 |
| 10 | API Views | Task 2, 9 |
| 11 | URL + 集成 | Task 10 |
| 12 | Admin | Task 2 |
| 13 | 回填命令 | Task 5, 6, 7 |
| 14 | 集成验证 | All |
