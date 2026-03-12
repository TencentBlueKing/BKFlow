"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""

from rest_framework import serializers

from bkflow.statistics.models import (
    DailyStatisticsSummary,
    PluginExecutionSummary,
    TaskflowExecutedNodeStatistics,
    TaskflowStatistics,
    TemplateNodeStatistics,
    TemplateStatistics,
)


class TemplateNodeStatisticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateNodeStatistics
        fields = "__all__"


class TemplateStatisticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateStatistics
        fields = "__all__"


class TaskflowStatisticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskflowStatistics
        fields = "__all__"


class TaskflowExecutedNodeStatisticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskflowExecutedNodeStatistics
        fields = "__all__"


class DailyStatisticsSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyStatisticsSummary
        fields = "__all__"


class PluginExecutionSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = PluginExecutionSummary
        fields = "__all__"


class StatisticsOverviewSerializer(serializers.Serializer):
    """空间统计概览"""

    space_id = serializers.IntegerField()
    scope_type = serializers.CharField(required=False, allow_null=True)
    scope_value = serializers.CharField(required=False, allow_null=True)

    # 任务统计
    total_tasks = serializers.IntegerField()
    success_tasks = serializers.IntegerField()
    failed_tasks = serializers.IntegerField()
    success_rate = serializers.FloatField()

    # 模板统计
    total_templates = serializers.IntegerField()
    active_templates = serializers.IntegerField()

    # 节点统计
    total_nodes_executed = serializers.IntegerField()
    node_success_rate = serializers.FloatField()

    # 耗时统计
    avg_task_elapsed_time = serializers.FloatField()


class TaskTrendSerializer(serializers.Serializer):
    """任务趋势数据"""

    date = serializers.DateField()
    task_created_count = serializers.IntegerField()
    task_finished_count = serializers.IntegerField()
    task_success_count = serializers.IntegerField()
    success_rate = serializers.FloatField()


class PluginRankingSerializer(serializers.Serializer):
    """插件排行数据"""

    component_code = serializers.CharField()
    version = serializers.CharField()
    execution_count = serializers.IntegerField()
    success_count = serializers.IntegerField()
    failed_count = serializers.IntegerField()
    success_rate = serializers.FloatField()
    avg_elapsed_time = serializers.FloatField()


class TemplateRankingSerializer(serializers.Serializer):
    """模板排行数据"""

    template_id = serializers.IntegerField()
    template_name = serializers.CharField()
    task_count = serializers.IntegerField()
    success_count = serializers.IntegerField()
    success_rate = serializers.FloatField()
