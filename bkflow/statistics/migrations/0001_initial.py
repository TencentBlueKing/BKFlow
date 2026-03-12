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

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TemplateNodeStatistics",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("component_code", models.CharField(db_index=True, max_length=255, verbose_name="组件编码")),
                ("version", models.CharField(default="legacy", max_length=255, verbose_name="插件版本")),
                ("is_remote", models.BooleanField(default=False, verbose_name="是否第三方插件")),
                ("template_id", models.BigIntegerField(db_index=True, verbose_name="模板ID")),
                ("space_id", models.BigIntegerField(db_index=True, verbose_name="空间ID")),
                (
                    "scope_type",
                    models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name="范围类型"),
                ),
                (
                    "scope_value",
                    models.CharField(blank=True, db_index=True, max_length=255, null=True, verbose_name="范围值"),
                ),
                ("node_id", models.CharField(max_length=64, verbose_name="节点ID")),
                ("node_name", models.CharField(blank=True, max_length=255, null=True, verbose_name="节点名称")),
                ("is_sub", models.BooleanField(default=False, verbose_name="是否子流程引用")),
                ("subprocess_stack", models.TextField(default="[]", verbose_name="子流程堆栈")),
                (
                    "template_creator",
                    models.CharField(blank=True, max_length=255, null=True, verbose_name="模板创建者"),
                ),
                ("template_create_time", models.DateTimeField(null=True, verbose_name="模板创建时间")),
                ("template_update_time", models.DateTimeField(null=True, verbose_name="模板更新时间")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="记录创建时间")),
            ],
            options={
                "verbose_name": "模板节点统计",
                "verbose_name_plural": "模板节点统计",
            },
        ),
        migrations.CreateModel(
            name="TemplateStatistics",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("template_id", models.BigIntegerField(db_index=True, unique=True, verbose_name="模板ID")),
                ("space_id", models.BigIntegerField(db_index=True, verbose_name="空间ID")),
                (
                    "scope_type",
                    models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name="范围类型"),
                ),
                (
                    "scope_value",
                    models.CharField(blank=True, db_index=True, max_length=255, null=True, verbose_name="范围值"),
                ),
                ("atom_total", models.IntegerField(default=0, verbose_name="标准插件节点总数")),
                ("subprocess_total", models.IntegerField(default=0, verbose_name="子流程节点总数")),
                ("gateways_total", models.IntegerField(default=0, verbose_name="网关节点总数")),
                ("input_count", models.IntegerField(default=0, verbose_name="输入变量数")),
                ("output_count", models.IntegerField(default=0, verbose_name="输出变量数")),
                ("template_name", models.CharField(blank=True, max_length=255, null=True, verbose_name="模板名称")),
                (
                    "template_creator",
                    models.CharField(blank=True, max_length=255, null=True, verbose_name="模板创建者"),
                ),
                ("template_create_time", models.DateTimeField(db_index=True, null=True, verbose_name="模板创建时间")),
                ("template_update_time", models.DateTimeField(null=True, verbose_name="模板更新时间")),
                ("is_enabled", models.BooleanField(default=True, verbose_name="是否启用")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="记录创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="记录更新时间")),
            ],
            options={
                "verbose_name": "模板统计",
                "verbose_name_plural": "模板统计",
            },
        ),
        migrations.CreateModel(
            name="TaskflowStatistics",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("task_id", models.BigIntegerField(db_index=True, unique=True, verbose_name="任务ID")),
                ("instance_id", models.CharField(db_index=True, max_length=64, verbose_name="Pipeline实例ID")),
                (
                    "template_id",
                    models.BigIntegerField(blank=True, db_index=True, null=True, verbose_name="关联模板ID"),
                ),
                ("space_id", models.BigIntegerField(db_index=True, verbose_name="空间ID")),
                (
                    "scope_type",
                    models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name="范围类型"),
                ),
                (
                    "scope_value",
                    models.CharField(blank=True, db_index=True, max_length=255, null=True, verbose_name="范围值"),
                ),
                (
                    "engine_id",
                    models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name="Engine标识"),
                ),
                ("atom_total", models.IntegerField(default=0, verbose_name="标准插件节点总数")),
                ("subprocess_total", models.IntegerField(default=0, verbose_name="子流程节点总数")),
                ("gateways_total", models.IntegerField(default=0, verbose_name="网关节点总数")),
                ("node_total", models.IntegerField(default=0, verbose_name="总节点数")),
                ("executed_node_count", models.IntegerField(default=0, verbose_name="执行节点数")),
                ("failed_node_count", models.IntegerField(default=0, verbose_name="失败节点数")),
                ("retry_node_count", models.IntegerField(default=0, verbose_name="重试节点数")),
                ("creator", models.CharField(blank=True, max_length=128, verbose_name="创建者")),
                ("executor", models.CharField(blank=True, max_length=128, verbose_name="执行者")),
                ("create_time", models.DateTimeField(db_index=True, verbose_name="创建时间")),
                ("start_time", models.DateTimeField(blank=True, null=True, verbose_name="启动时间")),
                ("finish_time", models.DateTimeField(blank=True, null=True, verbose_name="结束时间")),
                ("elapsed_time", models.IntegerField(blank=True, null=True, verbose_name="执行耗时(秒)")),
                (
                    "create_method",
                    models.CharField(db_index=True, default="API", max_length=32, verbose_name="创建方式"),
                ),
                (
                    "trigger_method",
                    models.CharField(db_index=True, default="manual", max_length=32, verbose_name="触发方式"),
                ),
                ("is_started", models.BooleanField(default=False, verbose_name="是否已启动")),
                ("is_finished", models.BooleanField(default=False, verbose_name="是否已完成")),
                ("is_success", models.BooleanField(db_index=True, default=False, verbose_name="是否成功")),
                ("final_state", models.CharField(db_index=True, default="", max_length=32, verbose_name="最终状态")),
                (
                    "app_code",
                    models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name="调用方应用"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="记录创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="记录更新时间")),
            ],
            options={
                "verbose_name": "任务统计",
                "verbose_name_plural": "任务统计",
            },
        ),
        migrations.CreateModel(
            name="TaskflowExecutedNodeStatistics",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("component_code", models.CharField(db_index=True, max_length=255, verbose_name="组件编码")),
                ("version", models.CharField(default="legacy", max_length=255, verbose_name="插件版本")),
                ("is_remote", models.BooleanField(default=False, verbose_name="是否第三方插件")),
                ("task_id", models.BigIntegerField(db_index=True, verbose_name="任务ID")),
                ("instance_id", models.CharField(db_index=True, max_length=64, verbose_name="Pipeline实例ID")),
                ("template_id", models.BigIntegerField(blank=True, db_index=True, null=True, verbose_name="关联模板ID")),
                ("space_id", models.BigIntegerField(db_index=True, verbose_name="空间ID")),
                ("scope_type", models.CharField(blank=True, max_length=64, null=True, verbose_name="范围类型")),
                ("scope_value", models.CharField(blank=True, max_length=255, null=True, verbose_name="范围值")),
                (
                    "engine_id",
                    models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name="Engine标识"),
                ),
                ("node_id", models.CharField(db_index=True, max_length=64, verbose_name="节点ID")),
                ("node_name", models.CharField(blank=True, max_length=255, null=True, verbose_name="节点名称")),
                ("template_node_id", models.CharField(blank=True, max_length=64, null=True, verbose_name="模板节点ID")),
                ("is_sub", models.BooleanField(default=False, verbose_name="是否子流程引用")),
                ("subprocess_stack", models.TextField(default="[]", verbose_name="子流程堆栈")),
                ("started_time", models.DateTimeField(db_index=True, verbose_name="节点执行开始时间")),
                ("archived_time", models.DateTimeField(blank=True, null=True, verbose_name="节点执行结束时间")),
                ("elapsed_time", models.IntegerField(blank=True, null=True, verbose_name="节点执行耗时(秒)")),
                ("status", models.BooleanField(default=False, verbose_name="是否执行成功")),
                ("state", models.CharField(db_index=True, default="", max_length=32, verbose_name="节点状态")),
                ("is_skip", models.BooleanField(default=False, verbose_name="是否跳过")),
                ("is_retry", models.BooleanField(default=False, verbose_name="是否重试记录")),
                ("retry_count", models.IntegerField(default=0, verbose_name="重试次数")),
                ("is_timeout", models.BooleanField(default=False, verbose_name="是否超时")),
                (
                    "error_code",
                    models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name="错误码"),
                ),
                ("loop_count", models.IntegerField(default=1, verbose_name="循环次数")),
                ("task_create_time", models.DateTimeField(db_index=True, verbose_name="任务创建时间")),
                ("task_start_time", models.DateTimeField(blank=True, null=True, verbose_name="任务启动时间")),
                ("task_finish_time", models.DateTimeField(blank=True, null=True, verbose_name="任务结束时间")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="记录创建时间")),
            ],
            options={
                "verbose_name": "节点执行统计",
                "verbose_name_plural": "节点执行统计",
            },
        ),
        migrations.CreateModel(
            name="DailyStatisticsSummary",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("date", models.DateField(db_index=True, verbose_name="统计日期")),
                ("space_id", models.BigIntegerField(db_index=True, verbose_name="空间ID")),
                ("scope_type", models.CharField(blank=True, max_length=64, null=True, verbose_name="范围类型")),
                ("scope_value", models.CharField(blank=True, max_length=255, null=True, verbose_name="范围值")),
                ("task_created_count", models.IntegerField(default=0, verbose_name="创建任务数")),
                ("task_started_count", models.IntegerField(default=0, verbose_name="启动任务数")),
                ("task_finished_count", models.IntegerField(default=0, verbose_name="完成任务数")),
                ("task_success_count", models.IntegerField(default=0, verbose_name="成功任务数")),
                ("task_failed_count", models.IntegerField(default=0, verbose_name="失败任务数")),
                ("task_revoked_count", models.IntegerField(default=0, verbose_name="撤销任务数")),
                ("node_executed_count", models.IntegerField(default=0, verbose_name="执行节点数")),
                ("node_success_count", models.IntegerField(default=0, verbose_name="成功节点数")),
                ("node_failed_count", models.IntegerField(default=0, verbose_name="失败节点数")),
                ("node_retry_count", models.IntegerField(default=0, verbose_name="重试节点数")),
                ("avg_task_elapsed_time", models.FloatField(default=0, verbose_name="平均任务耗时(秒)")),
                ("max_task_elapsed_time", models.IntegerField(default=0, verbose_name="最大任务耗时(秒)")),
                ("total_task_elapsed_time", models.BigIntegerField(default=0, verbose_name="总任务耗时(秒)")),
                ("template_created_count", models.IntegerField(default=0, verbose_name="创建模板数")),
                ("template_updated_count", models.IntegerField(default=0, verbose_name="更新模板数")),
                ("active_template_count", models.IntegerField(default=0, verbose_name="活跃模板数")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="记录创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="记录更新时间")),
            ],
            options={
                "verbose_name": "每日统计汇总",
                "verbose_name_plural": "每日统计汇总",
                "unique_together": {("date", "space_id", "scope_type", "scope_value")},
            },
        ),
        migrations.CreateModel(
            name="PluginExecutionSummary",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("period_type", models.CharField(db_index=True, max_length=16, verbose_name="周期类型")),
                ("period_start", models.DateField(db_index=True, verbose_name="周期开始日期")),
                ("space_id", models.BigIntegerField(db_index=True, verbose_name="空间ID")),
                ("component_code", models.CharField(db_index=True, max_length=255, verbose_name="组件编码")),
                ("version", models.CharField(default="legacy", max_length=255, verbose_name="插件版本")),
                ("is_remote", models.BooleanField(default=False, verbose_name="是否第三方插件")),
                ("execution_count", models.IntegerField(default=0, verbose_name="执行次数")),
                ("success_count", models.IntegerField(default=0, verbose_name="成功次数")),
                ("failed_count", models.IntegerField(default=0, verbose_name="失败次数")),
                ("retry_count", models.IntegerField(default=0, verbose_name="重试次数")),
                ("timeout_count", models.IntegerField(default=0, verbose_name="超时次数")),
                ("avg_elapsed_time", models.FloatField(default=0, verbose_name="平均耗时(秒)")),
                ("max_elapsed_time", models.IntegerField(default=0, verbose_name="最大耗时(秒)")),
                ("min_elapsed_time", models.IntegerField(default=0, verbose_name="最小耗时(秒)")),
                ("p95_elapsed_time", models.IntegerField(default=0, verbose_name="P95耗时(秒)")),
                ("template_reference_count", models.IntegerField(default=0, verbose_name="模板引用数")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="记录创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="记录更新时间")),
            ],
            options={
                "verbose_name": "插件执行汇总",
                "verbose_name_plural": "插件执行汇总",
                "unique_together": {("period_type", "period_start", "space_id", "component_code", "version")},
            },
        ),
        migrations.AddIndex(
            model_name="templatenodestatistics",
            index=models.Index(fields=["space_id", "component_code"], name="stats_space_component_idx"),
        ),
        migrations.AddIndex(
            model_name="templatenodestatistics",
            index=models.Index(fields=["template_id", "node_id"], name="stats_tpl_node_idx"),
        ),
        migrations.AddIndex(
            model_name="templatestatistics",
            index=models.Index(fields=["space_id", "template_create_time"], name="stats_tpl_space_time_idx"),
        ),
        migrations.AddIndex(
            model_name="taskflowstatistics",
            index=models.Index(fields=["space_id", "create_time"], name="stats_task_space_time_idx"),
        ),
        migrations.AddIndex(
            model_name="taskflowstatistics",
            index=models.Index(fields=["template_id", "create_time"], name="stats_task_tpl_time_idx"),
        ),
        migrations.AddIndex(
            model_name="taskflowstatistics",
            index=models.Index(fields=["engine_id", "create_time"], name="stats_task_engine_time_idx"),
        ),
        migrations.AddIndex(
            model_name="taskflowexecutednodestatistics",
            index=models.Index(fields=["space_id", "component_code", "started_time"], name="stats_node_space_comp_idx"),
        ),
        migrations.AddIndex(
            model_name="taskflowexecutednodestatistics",
            index=models.Index(fields=["task_id", "node_id"], name="stats_node_task_idx"),
        ),
        migrations.AddIndex(
            model_name="taskflowexecutednodestatistics",
            index=models.Index(fields=["component_code", "status", "started_time"], name="stats_node_comp_status_idx"),
        ),
        migrations.AddIndex(
            model_name="taskflowexecutednodestatistics",
            index=models.Index(fields=["engine_id", "started_time"], name="stats_node_engine_time_idx"),
        ),
        migrations.AddIndex(
            model_name="dailystatisticssummary",
            index=models.Index(fields=["space_id", "date"], name="stats_daily_space_date_idx"),
        ),
        migrations.AddIndex(
            model_name="pluginexecutionsummary",
            index=models.Index(
                fields=["space_id", "component_code", "period_start"], name="stats_plugin_space_comp_idx"
            ),
        ),
    ]
