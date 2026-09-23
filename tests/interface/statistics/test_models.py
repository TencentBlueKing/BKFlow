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
            task_id=2,
            space_id=100,
            create_time=now,
            final_state="CREATED",
        )
        with pytest.raises(Exception):
            TaskflowStatistics.objects.create(
                task_id=2,
                space_id=100,
                create_time=now,
                final_state="CREATED",
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
            date=date(2026, 1, 2),
            space_id=100,
        )
        assert summary.scope_type == ""
        assert summary.scope_value == ""


class TestTemplateNodeStatistics(TestCase):
    def test_create_node_statistics(self):
        stat = TemplateNodeStatistics.objects.create(
            component_code="bk_http",
            plugin_source="builtin",
            template_id=1,
            space_id=100,
            node_id="node_abc",
        )
        assert stat.component_code == "bk_http"
        assert stat.is_sub is False
        assert stat.plugin_source == "builtin"


class TestPluginExecutionSummary(TestCase):
    def test_create_plugin_summary(self):
        from datetime import date

        stat = PluginExecutionSummary.objects.create(
            period_type="day",
            period_start=date(2026, 1, 1),
            space_id=100,
            component_code="bk_http",
            plugin_source="builtin",
            execution_count=100,
            success_count=95,
            failed_count=5,
        )
        assert stat.execution_count == 100
        assert stat.plugin_source == "builtin"


class TestTaskflowExecutedNodeStatistics(TestCase):
    def test_create_executed_node(self):
        stat = TaskflowExecutedNodeStatistics.objects.create(
            task_id=1,
            space_id=100,
            component_code="bk_http",
            plugin_source="builtin",
            node_id="node_1",
            started_time=timezone.now(),
            status=True,
            state="FINISHED",
        )
        assert stat.status is True
        assert stat.is_retry is False
        assert stat.plugin_source == "builtin"
