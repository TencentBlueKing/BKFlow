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

from django.db import models


class StatisticsBaseModel(models.Model):
    """
    统计模型基类

    所有统计模型继承此基类，确保：
    1. 使用正确的 app_label（用于数据库路由）
    2. 统一的元信息配置
    """

    class Meta:
        abstract = True
        app_label = "statistics"

    @classmethod
    def using_db(cls):
        """获取当前模型使用的数据库"""
        from django.conf import settings

        return "statistics" if "statistics" in settings.DATABASES else "default"

    def save(self, *args, **kwargs):
        """确保保存到正确的数据库"""
        kwargs.setdefault("using", self.using_db())
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """确保从正确的数据库删除"""
        kwargs.setdefault("using", self.using_db())
        super().delete(*args, **kwargs)

    @classmethod
    def objects_using_db(cls):
        """获取使用正确数据库的 QuerySet"""
        return cls.objects.using(cls.using_db())


class TemplateNodeStatistics(StatisticsBaseModel):
    """模板中标准插件节点的引用统计"""

    id = models.BigAutoField(primary_key=True)

    # 组件信息
    component_code = models.CharField("组件编码", max_length=255, db_index=True)
    version = models.CharField("插件版本", max_length=255, default="legacy")
    is_remote = models.BooleanField("是否第三方插件", default=False)

    # 模板关联
    template_id = models.BigIntegerField("模板ID", db_index=True)

    # 平台标识
    space_id = models.BigIntegerField("空间ID", db_index=True)
    scope_type = models.CharField("范围类型", max_length=64, null=True, blank=True, db_index=True)
    scope_value = models.CharField("范围值", max_length=255, null=True, blank=True, db_index=True)

    # 节点信息
    node_id = models.CharField("节点ID", max_length=64)
    node_name = models.CharField("节点名称", max_length=255, null=True, blank=True)
    is_sub = models.BooleanField("是否子流程引用", default=False)
    subprocess_stack = models.TextField("子流程堆栈", default="[]")

    # 模板元信息
    template_creator = models.CharField("模板创建者", max_length=255, null=True, blank=True)
    template_create_time = models.DateTimeField("模板创建时间", null=True)
    template_update_time = models.DateTimeField("模板更新时间", null=True)

    # 记录时间
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


class TemplateStatistics(StatisticsBaseModel):
    """模板维度的整体统计"""

    id = models.BigAutoField(primary_key=True)

    # 模板关联
    template_id = models.BigIntegerField("模板ID", db_index=True, unique=True)

    # 平台标识
    space_id = models.BigIntegerField("空间ID", db_index=True)
    scope_type = models.CharField("范围类型", max_length=64, null=True, blank=True, db_index=True)
    scope_value = models.CharField("范围值", max_length=255, null=True, blank=True, db_index=True)

    # 节点统计
    atom_total = models.IntegerField("标准插件节点总数", default=0)
    subprocess_total = models.IntegerField("子流程节点总数", default=0)
    gateways_total = models.IntegerField("网关节点总数", default=0)

    # 变量统计
    input_count = models.IntegerField("输入变量数", default=0)
    output_count = models.IntegerField("输出变量数", default=0)

    # 模板元信息
    template_name = models.CharField("模板名称", max_length=255, null=True, blank=True)
    template_creator = models.CharField("模板创建者", max_length=255, null=True, blank=True)
    template_create_time = models.DateTimeField("模板创建时间", null=True, db_index=True)
    template_update_time = models.DateTimeField("模板更新时间", null=True)
    is_enabled = models.BooleanField("是否启用", default=True)

    # 记录时间
    created_at = models.DateTimeField("记录创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("记录更新时间", auto_now=True)

    class Meta(StatisticsBaseModel.Meta):
        verbose_name = "模板统计"
        verbose_name_plural = "模板统计"
        indexes = [
            models.Index(fields=["space_id", "template_create_time"]),
        ]

    def __str__(self):
        return f"Template_{self.template_id}"


class TaskflowStatistics(StatisticsBaseModel):
    """任务实例维度的统计"""

    id = models.BigAutoField(primary_key=True)

    # 任务关联
    task_id = models.BigIntegerField("任务ID", db_index=True, unique=True)
    instance_id = models.CharField("Pipeline实例ID", max_length=64, db_index=True)
    template_id = models.BigIntegerField("关联模板ID", null=True, blank=True, db_index=True)

    # 平台标识
    space_id = models.BigIntegerField("空间ID", db_index=True)
    scope_type = models.CharField("范围类型", max_length=64, null=True, blank=True, db_index=True)
    scope_value = models.CharField("范围值", max_length=255, null=True, blank=True, db_index=True)

    # Engine 标识（用于区分不同 Engine 模块写入的数据）
    engine_id = models.CharField("Engine标识", max_length=64, null=True, blank=True, db_index=True)

    # 节点统计
    atom_total = models.IntegerField("标准插件节点总数", default=0)
    subprocess_total = models.IntegerField("子流程节点总数", default=0)
    gateways_total = models.IntegerField("网关节点总数", default=0)
    node_total = models.IntegerField("总节点数", default=0)
    executed_node_count = models.IntegerField("执行节点数", default=0)
    failed_node_count = models.IntegerField("失败节点数", default=0)
    retry_node_count = models.IntegerField("重试节点数", default=0)

    # 执行信息
    creator = models.CharField("创建者", max_length=128, blank=True)
    executor = models.CharField("执行者", max_length=128, blank=True)
    create_time = models.DateTimeField("创建时间", db_index=True)
    start_time = models.DateTimeField("启动时间", null=True, blank=True)
    finish_time = models.DateTimeField("结束时间", null=True, blank=True)
    elapsed_time = models.IntegerField("执行耗时(秒)", null=True, blank=True)

    # 创建/触发方式
    create_method = models.CharField("创建方式", max_length=32, default="API", db_index=True)
    trigger_method = models.CharField("触发方式", max_length=32, default="manual", db_index=True)

    # 执行状态
    is_started = models.BooleanField("是否已启动", default=False)
    is_finished = models.BooleanField("是否已完成", default=False)
    is_success = models.BooleanField("是否成功", default=False, db_index=True)
    final_state = models.CharField("最终状态", max_length=32, default="", db_index=True)

    # 调用方信息
    app_code = models.CharField("调用方应用", max_length=64, null=True, blank=True, db_index=True)

    # 记录时间
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
    """任务执行过程中节点执行详情统计"""

    id = models.BigAutoField(primary_key=True)

    # 组件信息
    component_code = models.CharField("组件编码", max_length=255, db_index=True)
    version = models.CharField("插件版本", max_length=255, default="legacy")
    is_remote = models.BooleanField("是否第三方插件", default=False)

    # 任务关联
    task_id = models.BigIntegerField("任务ID", db_index=True)
    instance_id = models.CharField("Pipeline实例ID", max_length=64, db_index=True)
    template_id = models.BigIntegerField("关联模板ID", null=True, blank=True, db_index=True)

    # 平台标识
    space_id = models.BigIntegerField("空间ID", db_index=True)
    scope_type = models.CharField("范围类型", max_length=64, null=True, blank=True)
    scope_value = models.CharField("范围值", max_length=255, null=True, blank=True)

    # Engine 标识
    engine_id = models.CharField("Engine标识", max_length=64, null=True, blank=True, db_index=True)

    # 节点信息
    node_id = models.CharField("节点ID", max_length=64, db_index=True)
    node_name = models.CharField("节点名称", max_length=255, null=True, blank=True)
    template_node_id = models.CharField("模板节点ID", max_length=64, null=True, blank=True)
    is_sub = models.BooleanField("是否子流程引用", default=False)
    subprocess_stack = models.TextField("子流程堆栈", default="[]")

    # 执行信息
    started_time = models.DateTimeField("节点执行开始时间", db_index=True)
    archived_time = models.DateTimeField("节点执行结束时间", null=True, blank=True)
    elapsed_time = models.IntegerField("节点执行耗时(秒)", null=True, blank=True)

    # 执行状态
    status = models.BooleanField("是否执行成功", default=False)
    state = models.CharField("节点状态", max_length=32, default="", db_index=True)
    is_skip = models.BooleanField("是否跳过", default=False)
    is_retry = models.BooleanField("是否重试记录", default=False)
    retry_count = models.IntegerField("重试次数", default=0)
    is_timeout = models.BooleanField("是否超时", default=False)
    error_code = models.CharField("错误码", max_length=64, null=True, blank=True, db_index=True)
    loop_count = models.IntegerField("循环次数", default=1)

    # 任务实例时间（冗余，便于统计）
    task_create_time = models.DateTimeField("任务创建时间", db_index=True)
    task_start_time = models.DateTimeField("任务启动时间", null=True, blank=True)
    task_finish_time = models.DateTimeField("任务结束时间", null=True, blank=True)

    # 记录时间
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


class DailyStatisticsSummary(StatisticsBaseModel):
    """每日统计汇总（预计算）"""

    id = models.BigAutoField(primary_key=True)

    # 时间维度
    date = models.DateField("统计日期", db_index=True)

    # 空间维度
    space_id = models.BigIntegerField("空间ID", db_index=True)
    scope_type = models.CharField("范围类型", max_length=64, null=True, blank=True)
    scope_value = models.CharField("范围值", max_length=255, null=True, blank=True)

    # 任务统计
    task_created_count = models.IntegerField("创建任务数", default=0)
    task_started_count = models.IntegerField("启动任务数", default=0)
    task_finished_count = models.IntegerField("完成任务数", default=0)
    task_success_count = models.IntegerField("成功任务数", default=0)
    task_failed_count = models.IntegerField("失败任务数", default=0)
    task_revoked_count = models.IntegerField("撤销任务数", default=0)

    # 节点统计
    node_executed_count = models.IntegerField("执行节点数", default=0)
    node_success_count = models.IntegerField("成功节点数", default=0)
    node_failed_count = models.IntegerField("失败节点数", default=0)
    node_retry_count = models.IntegerField("重试节点数", default=0)

    # 耗时统计
    avg_task_elapsed_time = models.FloatField("平均任务耗时(秒)", default=0)
    max_task_elapsed_time = models.IntegerField("最大任务耗时(秒)", default=0)
    total_task_elapsed_time = models.BigIntegerField("总任务耗时(秒)", default=0)

    # 模板统计
    template_created_count = models.IntegerField("创建模板数", default=0)
    template_updated_count = models.IntegerField("更新模板数", default=0)
    active_template_count = models.IntegerField("活跃模板数", default=0)

    # 记录时间
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
    """插件执行汇总（按天/按周/按月）"""

    id = models.BigAutoField(primary_key=True)

    # 时间维度
    period_type = models.CharField("周期类型", max_length=16, db_index=True)  # day/week/month
    period_start = models.DateField("周期开始日期", db_index=True)

    # 空间维度
    space_id = models.BigIntegerField("空间ID", db_index=True)

    # 插件维度
    component_code = models.CharField("组件编码", max_length=255, db_index=True)
    version = models.CharField("插件版本", max_length=255, default="legacy")
    is_remote = models.BooleanField("是否第三方插件", default=False)

    # 执行统计
    execution_count = models.IntegerField("执行次数", default=0)
    success_count = models.IntegerField("成功次数", default=0)
    failed_count = models.IntegerField("失败次数", default=0)
    retry_count = models.IntegerField("重试次数", default=0)
    timeout_count = models.IntegerField("超时次数", default=0)

    # 耗时统计
    avg_elapsed_time = models.FloatField("平均耗时(秒)", default=0)
    max_elapsed_time = models.IntegerField("最大耗时(秒)", default=0)
    min_elapsed_time = models.IntegerField("最小耗时(秒)", default=0)
    p95_elapsed_time = models.IntegerField("P95耗时(秒)", default=0)

    # 引用统计
    template_reference_count = models.IntegerField("模板引用数", default=0)

    # 记录时间
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
