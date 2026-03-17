from rest_framework import serializers

from bkflow.statistics.models import DailyStatisticsSummary


class StatisticsOverviewSerializer(serializers.Serializer):
    total_templates = serializers.IntegerField()
    total_tasks = serializers.IntegerField()
    total_tasks_finished = serializers.IntegerField()
    total_tasks_failed = serializers.IntegerField()
    total_nodes_executed = serializers.IntegerField()
    avg_task_elapsed_time = serializers.FloatField()
    success_rate = serializers.FloatField()


class TaskTrendSerializer(serializers.Serializer):
    date = serializers.DateField()
    task_created_count = serializers.IntegerField()
    task_finished_count = serializers.IntegerField()
    task_success_count = serializers.IntegerField()
    task_failed_count = serializers.IntegerField()
    task_revoked_count = serializers.IntegerField()
    node_executed_count = serializers.IntegerField()
    avg_task_elapsed_time = serializers.FloatField()


class PluginRankingSerializer(serializers.Serializer):
    component_code = serializers.CharField()
    version = serializers.CharField()
    is_remote = serializers.BooleanField()
    execution_count = serializers.IntegerField()
    success_count = serializers.IntegerField()
    failed_count = serializers.IntegerField()
    success_rate = serializers.FloatField()
    avg_elapsed_time = serializers.FloatField()


class TemplateRankingSerializer(serializers.Serializer):
    template_id = serializers.IntegerField()
    template_name = serializers.CharField()
    space_id = serializers.IntegerField()
    task_count = serializers.IntegerField()
    task_success_count = serializers.IntegerField()
    task_failed_count = serializers.IntegerField()


class SpaceRankingSerializer(serializers.Serializer):
    space_id = serializers.IntegerField()
    scope_type = serializers.CharField()
    scope_value = serializers.CharField()
    total_templates = serializers.IntegerField()
    total_tasks = serializers.IntegerField()
    total_nodes_executed = serializers.IntegerField()
    success_rate = serializers.FloatField()


class FailureAnalysisSerializer(serializers.Serializer):
    component_code = serializers.CharField()
    version = serializers.CharField()
    is_remote = serializers.BooleanField()
    failed_count = serializers.IntegerField()
    total_count = serializers.IntegerField()
    failure_rate = serializers.FloatField()
    avg_elapsed_time = serializers.FloatField()


class DailyStatisticsSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyStatisticsSummary
        fields = [
            "date",
            "space_id",
            "scope_type",
            "scope_value",
            "task_created_count",
            "task_finished_count",
            "task_success_count",
            "task_failed_count",
            "task_revoked_count",
            "node_executed_count",
            "node_success_count",
            "node_failed_count",
            "avg_task_elapsed_time",
            "max_task_elapsed_time",
        ]
        read_only_fields = fields


class DateRangeParamSerializer(serializers.Serializer):
    date_start = serializers.DateField(required=False)
    date_end = serializers.DateField(required=False)
    date_range = serializers.ChoiceField(
        choices=["7d", "14d", "30d", "90d"],
        required=False,
    )
    scope_type = serializers.CharField(required=False, default="")
    scope_value = serializers.CharField(required=False, default="")

    def validate(self, attrs):
        if not attrs.get("date_start") and not attrs.get("date_range"):
            raise serializers.ValidationError("date_start/date_end 或 date_range 至少提供一个")
        return attrs
