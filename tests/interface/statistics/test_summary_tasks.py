from datetime import date

from django.test import TestCase
from django.utils import timezone

from bkflow.statistics.models import PluginExecutionSummary, TaskflowExecutedNodeStatistics
from bkflow.statistics.tasks.summary_tasks import _generate_plugin_summary


class TestGeneratePluginSummary(TestCase):
    def test_generate_plugin_summary_keeps_plugin_source_dimension(self):
        started_time = timezone.now()

        TaskflowExecutedNodeStatistics.objects.create(
            task_id=1,
            space_id=100,
            component_code="job_execute",
            plugin_source="builtin",
            version="1.0.0",
            plugin_type="uniform_api",
            node_id="node_1",
            started_time=started_time,
            status=True,
            state="FINISHED",
        )
        TaskflowExecutedNodeStatistics.objects.create(
            task_id=2,
            space_id=100,
            component_code="job_execute",
            plugin_source="third_party",
            version="1.0.0",
            plugin_type="uniform_api",
            node_id="node_2",
            started_time=started_time,
            status=False,
            state="FAILED",
        )

        _generate_plugin_summary("day", started_time.date())

        summaries = PluginExecutionSummary.objects.filter(
            period_type="day",
            period_start=started_time.date(),
            space_id=100,
            component_code="job_execute",
            version="1.0.0",
        ).order_by("plugin_source")

        assert summaries.count() == 2
        assert list(summaries.values_list("plugin_source", "execution_count", "failed_count")) == [
            ("builtin", 1, 0),
            ("third_party", 1, 1),
        ]
