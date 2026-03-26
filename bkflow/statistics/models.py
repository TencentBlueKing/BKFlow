"""运营统计数据模型

数据分为两层：
- 明细层：TaskflowStatistics（任务）、TaskflowExecutedNodeStatistics（节点）、
          TemplateStatistics（模板）、TemplateNodeStatistics（模板节点）
- 汇总层：DailyStatisticsSummary（每日汇总）、PluginExecutionSummary（插件执行汇总）

所有模型通过 StatisticsDBRouter 路由到独立的 statistics 数据库（或 default）。
"""

from django.db import models


class StatisticsBaseModel(models.Model):
    class Meta:
        abstract = True
        app_label = "statistics"


class TaskflowStatistics(StatisticsBaseModel):
    """任务统计明细，记录每个任务的基本信息、节点构成和执行状态"""

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
    """已执行节点统计明细，记录每个插件节点的执行结果、耗时和重试信息"""

    id = models.BigAutoField(primary_key=True)
    task_id = models.BigIntegerField("任务ID", db_index=True)
    space_id = models.BigIntegerField("空间ID", db_index=True)
    engine_id = models.CharField("Engine标识", max_length=64, default="")

    component_code = models.CharField("组件编码", max_length=255, db_index=True)
    component_name = models.CharField("组件名称", max_length=255, default="")
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
    """模板统计，记录模板的节点构成和元信息"""

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
    """模板节点统计，记录模板中每个插件节点的编码、版本和在子流程中的位置"""

    id = models.BigAutoField(primary_key=True)
    component_code = models.CharField("组件编码", max_length=255, db_index=True)
    component_name = models.CharField("组件名称", max_length=255, default="")
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
    """每日统计汇总，按空间和范围聚合任务和节点的执行概况"""

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
    """插件执行汇总，按周期（日/周/月）聚合各插件的执行次数、成功率和耗时"""

    id = models.BigAutoField(primary_key=True)
    period_type = models.CharField("周期类型", max_length=16, db_index=True)
    period_start = models.DateField("周期开始日期", db_index=True)
    space_id = models.BigIntegerField("空间ID", db_index=True)

    component_code = models.CharField("组件编码", max_length=255, db_index=True)
    component_name = models.CharField("组件名称", max_length=255, default="")
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
