from datetime import date, datetime
from datetime import timezone as datetime_timezone

import pytest
from django.utils import timezone

from bkflow.statistics.models import (
    PluginExecutionSummary,
    TaskflowExecutedNodeStatistics,
)
from bkflow.statistics.tasks.summary_tasks import _generate_plugin_summary


@pytest.mark.django_db
@pytest.mark.parametrize(
    "started_time, expected_period_start",
    [
        (datetime(2026, 9, 9, 15, 59, 59, tzinfo=datetime_timezone.utc), date(2026, 9, 9)),
        (datetime(2026, 9, 9, 16, 0, 0, tzinfo=datetime_timezone.utc), date(2026, 9, 10)),
    ],
)
def test_generate_plugin_summary_keeps_plugin_source_dimension(started_time, expected_period_start):
    """本地日期跨日的前后均保留插件来源维度，不依赖 CI 执行时刻。"""
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

    with timezone.override("Asia/Shanghai"):
        _generate_plugin_summary("day", timezone.localdate(started_time))

    summaries = PluginExecutionSummary.objects.filter(
        period_type="day",
        period_start=expected_period_start,
        space_id=100,
        component_code="job_execute",
        version="1.0.0",
    ).order_by("plugin_source")

    assert summaries.count() == 2
    assert list(summaries.values_list("plugin_source", "execution_count", "failed_count")) == [
        ("builtin", 1, 0),
        ("third_party", 1, 1),
    ]
