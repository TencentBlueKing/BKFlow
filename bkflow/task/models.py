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
import json
import logging

from bamboo_engine import states
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django_celery_beat.models import CrontabSchedule as DjangoCeleryBeatCrontabSchedule
from django_celery_beat.models import PeriodicTask as DjangoCeleryBeatPeriodicTask
from pipeline.contrib.periodic_task.djcelery.models import *  # noqa
from pipeline.core.constants import PE
from pipeline.engine.utils import calculate_elapsed_time
from pipeline.eri.models import Schedule as DBSchedule
from pipeline.eri.runtime import BambooDjangoRuntime
from pipeline.models import CompressJSONField
from pipeline.parser.utils import replace_all_id
from pipeline.utils.uniqid import node_uniqid, uniqid

from bkflow.constants import (
    MAX_LEN_OF_TASK_NAME,
    TaskOperationSource,
    TaskOperationType,
    TaskTriggerMethod,
)
from bkflow.contrib.operation_record.models import BaseOperateRecord
from bkflow.pipeline_plugins.components.collections.subprocess_plugin.converter import (
    PipelineTreeSubprocessConverter,
)
from bkflow.task.auto_retry import AutoRetryNodeStrategyCreator
from bkflow.task.utils import parse_node_timeout_configs
from bkflow.utils.models import CommonSnapshot, CommonSnapshotManager

logger = logging.getLogger("root")


class TaskTreeInfo(models.Model):
    id = models.BigAutoField(primary_key=True)
    data = CompressJSONField(null=True, blank=True)


class TaskSnapshot(CommonSnapshot):
    objects = CommonSnapshotManager()

    class Meta:
        verbose_name = "模板快照"
        verbose_name_plural = "模板快照"
        ordering = ["-id"]


class TaskExecutionSnapshot(CommonSnapshot):
    objects = CommonSnapshotManager()

    class Meta:
        verbose_name = "任务执行快照"
        verbose_name_plural = "任务执行快照"
        ordering = ["-id"]


class TaskInstanceManager(models.Manager):
    def set_finished(self, instance_id: str):
        self.filter(instance_id=instance_id).update(finish_time=timezone.now(), is_finished=True)

    def set_revoked(self, instance_id: str):
        self.filter(instance_id=instance_id).update(finish_time=timezone.now(), is_revoked=True)

    @staticmethod
    def inject_template_node_id(pipeline_tree: dict):
        """
        pipeline 注入原始模板节点 ID
        """
        for act_id, act in pipeline_tree[PE.activities].items():
            act["template_node_id"] = act["template_node_id"] = act.get("template_node_id") or act_id

    def create_instance(self, *args, **kwargs):
        """
        创建任务实例
        """
        pipeline_tree = kwargs.pop("pipeline_tree")
        space_id = kwargs.pop("space_id")
        mock_data = kwargs.pop("mock_data", {})
        instance_id = node_uniqid()
        pipeline_tree["id"] = instance_id
        with transaction.atomic():
            snapshot = TaskSnapshot.objects.get_or_create_snapshot(pipeline_tree)
            self.inject_template_node_id(pipeline_tree)
            converter = PipelineTreeSubprocessConverter(pipeline_tree)
            converter.convert()
            node_mappings = replace_all_id(pipeline_tree)
            execution_snapshot = TaskExecutionSnapshot.objects.create_snapshot(pipeline_tree)
            instance = self.create(
                space_id=space_id,
                instance_id=instance_id,
                snapshot_id=snapshot.id,
                execution_snapshot_id=execution_snapshot.id,
                **kwargs,
            )
            # create task mock data
            if kwargs.get("create_method") == "MOCK":
                new_mock_data = {}
                act_mappings = node_mappings[PE.activities]
                new_mock_data["nodes"] = [act_mappings[node_id] for node_id in mock_data.get("nodes", [])]
                new_mock_data["outputs"] = {
                    act_mappings[node_id]: outputs for node_id, outputs in mock_data.get("outputs", {}).items()
                }
                TaskMockData.objects.create(
                    taskflow_id=instance.id, data=new_mock_data, mock_data_ids=mock_data.get("mock_data_ids", {})
                )
            # create auto retry strategy
            arn_creator = AutoRetryNodeStrategyCreator(taskflow_id=instance.id, root_pipeline_id=instance.instance_id)
            arn_creator.batch_create_strategy(pipeline_tree)
            # create node timeout configs
            TimeoutNodeConfig.objects.batch_create_node_timeout_config(
                taskflow_id=instance.id,
                root_pipeline_id=instance.instance_id,
                pipeline_tree=pipeline_tree,
            )

        return instance


class TaskInstance(models.Model):
    """
    任务实例
    """

    CREATE_METHODS = (("API", "API"), ("MOCK", "MOCK"))

    id = models.BigAutoField(primary_key=True)
    space_id = models.IntegerField("空间ID", db_index=True)
    scope_type = models.CharField("空间域类型", max_length=128, null=True, blank=True)
    scope_value = models.CharField("空间域值", max_length=128, null=True, blank=True)
    instance_id = models.CharField("实例ID", max_length=33, unique=True, db_index=True)
    template_id = models.BigIntegerField(verbose_name="流程模版ID", null=True, blank=True, db_index=True)
    name = models.CharField("实例名称", max_length=MAX_LEN_OF_TASK_NAME, default="default_taskflow_instance")
    creator = models.CharField("创建者", max_length=32, blank=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)
    create_method = models.CharField("创建方式", choices=CREATE_METHODS, default="API", max_length=32)
    trigger_method = models.CharField("触发方式", default="manual", max_length=32)
    executor = models.CharField("执行者", max_length=32, blank=True)
    start_time = models.DateTimeField("启动时间", null=True, blank=True)
    finish_time = models.DateTimeField("结束时间", null=True, blank=True)
    description = models.TextField("描述", blank=True)
    is_started = models.BooleanField("是否已经启动", default=False)
    is_finished = models.BooleanField("是否已经完成", default=False)
    is_revoked = models.BooleanField("是否已经撤销", default=False)
    is_deleted = models.BooleanField("是否已经删除", default=False, help_text="表示当前实例是否删除")
    is_expired = models.BooleanField("是否已经过期", default=False, help_text="运行时被定期清理即为过期")
    snapshot_id = models.BigIntegerField(verbose_name="实例结构数据ID", null=True, blank=True, db_index=True)
    execution_snapshot_id = models.BigIntegerField(verbose_name="用于实例执行的结构数据ID", null=True, blank=True, db_index=True)
    tree_info_id = models.BigIntegerField(verbose_name="提前计算好的一些流程结构数据ID", null=True, blank=True, db_index=True)
    extra_info = models.JSONField(verbose_name="额外信息", default=dict)

    objects = TaskInstanceManager()

    class Meta:
        verbose_name = "任务实例"
        verbose_name_plural = "任务实例"
        index_together = [("space_id", "scope_type", "scope_value")]
        ordering = ["-create_time"]

    def delete(self, real_delete=False):
        if real_delete:
            return super().delete()
        setattr(self, "is_deleted", True)
        self.save(update_fields=["is_deleted"])

    @property
    def snapshot(self):
        return TaskSnapshot.objects.filter(id=self.snapshot_id).first()

    @property
    def data(self):
        return self.snapshot.data

    @property
    def pipeline_tree(self):
        return self.execution_data

    @property
    def tree_info(self):
        return TaskTreeInfo.objects.filter(id=self.tree_info_id).first()

    @property
    def execution_snapshot(self):
        return TaskExecutionSnapshot.objects.filter(id=self.execution_snapshot_id).first()

    @property
    def execution_data(self):
        return self.execution_snapshot.data if self.execution_snapshot else None

    @property
    def node_id_set(self):
        if not self.tree_info_id:
            self.calculate_tree_info()
        return set(TaskTreeInfo.objects.get(id=self.tree_info_id).data["node_id_set"])

    @property
    def elapsed_time(self):
        return calculate_elapsed_time(self.start_time, self.finish_time)

    def set_execution_data(self, data):
        try:
            execution_snapshot = TaskExecutionSnapshot.objects.get(id=self.execution_snapshot_id)
        except TaskExecutionSnapshot.DoesNotExist:
            execution_snapshot = TaskExecutionSnapshot.objects.create_snapshot(data=data)
        self.execution_snapshot_id = execution_snapshot.id
        self.save(update_fields=["execution_snapshot_id"])

    def _replace_id(self, exec_data):
        replace_all_id(exec_data)
        activities = exec_data[PE.activities]
        for act_id, act in list(activities.items()):
            if act[PE.type] == PE.SubProcess:
                self._replace_id(act["pipeline"])
                act["pipeline"]["id"] = act_id

    def clone(self, creator, **kwargs):
        name = kwargs.get("name") or timezone.localtime(timezone.now()).strftime("clone%Y%m%d%H%m%S")
        instance_id = node_uniqid()

        exec_data = self.execution_data
        self._replace_id(exec_data)
        # replace root id
        exec_data["id"] = instance_id
        new_snapshot = TaskSnapshot.objects.create_snapshot(exec_data)

        return self.__class__.objects.create(
            space_id=self.space_id,
            scope_type=self.scope_type,
            scope_value=self.scope_value,
            instance_id=instance_id,
            template_id=self.template_id,
            name=name,
            creator=creator,
            description=self.description,
            snapshot_id=self.snapshot_id,
            execution_snapshot_id=new_snapshot.id,
            extra_info=self.extra_info,
        )

    def _get_node_id_set(self, node_id_set, data):
        node_id_set.add(data[PE.start_event]["id"])
        node_id_set.add(data[PE.end_event]["id"])
        for gid in data[PE.gateways]:
            node_id_set.add(gid)
        for aid, act_data in list(data[PE.activities].items()):
            node_id_set.add(aid)
            if act_data[PE.type] == PE.SubProcess:
                self._get_node_id_set(node_id_set, act_data["pipeline"])

    def calculate_tree_info(self):
        node_id_set = set()
        if self.execution_data is None:
            return

        # get node id set
        self._get_node_id_set(node_id_set, self.execution_data)

        tree_info_data = {"node_id_set": list(node_id_set)}
        if self.tree_info_id:
            TaskTreeInfo.objects.filter(id=self.tree_info_id).update(data=tree_info_data)
        else:
            tree_info = TaskTreeInfo.objects.create(data=tree_info_data)
            self.tree_info_id = tree_info.id
            self.save(update_fields=["tree_info_id"])

    def has_node(self, node_id):
        return node_id in self.node_id_set

    def get_notify_info(self):
        notify_config = self.extra_info.get("notify_config", {})
        receivers = [self.executor] if self.executor else []
        more_receivers = notify_config.get("notify_receivers", {}).get("more_receiver")
        if more_receivers:
            receivers.extend([receiver for receiver in more_receivers.split(",") if receiver != self.executor])
        return {
            "types": notify_config.get("notify_type") or {"success": [], "fail": []},
            "receivers": receivers,
            "format": notify_config.get("notify_format") or {"title": "", "content": ""},
        }

    def change_parent_task_node_state_to_running(self):
        if not self.trigger_method == TaskTriggerMethod.subprocess.name:
            logger.info("taskflow[id=%s] is not child taskflow, cannot change parent task node state to running")
            return

        with transaction.atomic():
            record = TaskFlowRelation.objects.filter(task_id=self.id).first()
            if not record:
                return
            info = record.extra_info
            parent_node_id, parent_node_version = info["node_id"], info["node_version"]
            runtime = BambooDjangoRuntime()
            node_state = runtime.get_state(parent_node_id)
            if node_state.name != states.FAILED or node_state.version != parent_node_version:
                return
            schedule = runtime.get_schedule_with_node_and_version(parent_node_id, parent_node_version)
            DBSchedule.objects.filter(id=schedule.id).update(expired=False)
            # FAILED 状态需要转换为 READY 之后才能转换为 RUNNING
            runtime.set_state(
                node_id=parent_node_id, version=parent_node_version, to_state=states.READY, clear_archived_time=True
            )
            runtime.set_state(node_id=parent_node_id, version=parent_node_version, to_state=states.RUNNING)
            data_outputs = runtime.get_execution_data_outputs(parent_node_id)
            data_outputs.pop("ex_data", None)
            runtime.set_execution_data_outputs(parent_node_id, data_outputs)

            # 仅当父流程的节点状态为失败时，才需要唤醒父流程的节点
            parent_task_id = TaskFlowRelation.objects.filter(task_id=self.id).first().parent_task_id
            parent_task = TaskInstance.objects.get(id=parent_task_id)
            parent_task.change_parent_task_node_state_to_running()


class AutoRetryNodeStrategy(models.Model):
    taskflow_id = models.BigIntegerField(verbose_name="taskflow id")
    root_pipeline_id = models.CharField(verbose_name="root pipeline id", max_length=64)
    node_id = models.CharField(verbose_name="task node id", max_length=64, primary_key=True)
    retry_times = models.IntegerField(verbose_name="retry times", default=0)
    max_retry_times = models.IntegerField(verbose_name="retry times", default=5)
    interval = models.IntegerField(verbose_name="retry interval", default=0)

    class Meta:
        verbose_name = "节点自动重试策略 AutoRetryNodeStrategy"
        verbose_name_plural = "节点自动重试策略 AutoRetryNodeStrategy"
        index_together = [("root_pipeline_id", "node_id")]


class TimeoutNodeConfigManager(models.Manager):
    NODE_TIMEOUT_CONFIG_BATCH_CREAT_COUNT = 500

    def batch_create_node_timeout_config(self, taskflow_id: int, root_pipeline_id: str, pipeline_tree: dict):
        """批量创建节点超时配置"""

        config_parse_result = parse_node_timeout_configs(pipeline_tree)
        # 这里忽略解析失败的情况，保证即使解析失败也能正常创建任务
        if not config_parse_result["result"]:
            logger.error(
                f'[batch_create_node_timeout_config] parse node timeout config failed: {config_parse_result["result"]}'
            )
            return
        configs = config_parse_result["data"] or []
        config_objs = [
            TimeoutNodeConfig(
                task_id=taskflow_id,
                action=config["action"],
                root_pipeline_id=root_pipeline_id,
                node_id=config["node_id"],
                timeout=config["timeout"],
            )
            for config in configs
        ]
        self.bulk_create(config_objs, batch_size=self.NODE_TIMEOUT_CONFIG_BATCH_CREAT_COUNT)


class TimeoutNodeConfig(models.Model):
    ACTION_TYPE = (("forced_fail", "强制失败"), ("forced_fail_and_skip", "强制失败并跳过"))
    task_id = models.BigIntegerField(verbose_name="taskflow id")
    root_pipeline_id = models.CharField(verbose_name="root pipeline id", max_length=64)
    action = models.CharField(verbose_name="action", choices=ACTION_TYPE, max_length=32)
    node_id = models.CharField(verbose_name="task node id", max_length=64, primary_key=True)
    timeout = models.IntegerField(verbose_name="node timeout time")

    objects = TimeoutNodeConfigManager()

    class Meta:
        verbose_name = "节点超时配置 TimeoutNodeConfig"
        verbose_name_plural = "节点超时配置 TimeoutNodeConfig"
        index_together = [("root_pipeline_id", "node_id")]


class TimeoutNodesRecord(models.Model):
    id = models.BigAutoField(verbose_name="ID", primary_key=True)
    timeout_nodes = models.TextField(verbose_name="超时节点信息")

    class Meta:
        verbose_name = "超时节点数据记录 TimeoutNodesRecord"
        verbose_name_plural = "超时节点数据记录 TimeoutNodesRecord"


class TaskOperationRecord(BaseOperateRecord):
    """任务操作记录"""

    node_id = models.CharField(verbose_name="节点 ID", max_length=128, default="", null=True, blank=True)
    operate_type = models.CharField(
        _("操作类型"), choices=[(_type.name, _type.value) for _type in TaskOperationType], max_length=64
    )
    operate_source = models.CharField(
        _("操作来源"), choices=[(_source.name, _source.value) for _source in TaskOperationSource], max_length=64
    )

    class Meta:
        verbose_name = "任务操作记录 TaskOperationRecord"
        verbose_name_plural = "任务操作记录 TaskOperationRecord"
        indexes = [models.Index(fields=["instance_id", "node_id"])]
        ordering = ["-id"]


class TaskMockData(models.Model):
    id = models.BigAutoField(verbose_name="ID", primary_key=True)
    taskflow_id = models.BigIntegerField(verbose_name="taskflow id", db_index=True)
    data = models.JSONField(verbose_name="task mock data")
    mock_data_ids = models.JSONField(verbose_name="task mock data ids", default=dict)
    create_time = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "任务Mock数据 TaskMockData"
        verbose_name_plural = "任务Mock数据 TaskMockData"

    def to_json(self):
        return {
            "id": self.id,
            "taskflow_id": self.taskflow_id,
            "data": self.data,
            "mock_data_ids": self.mock_data_ids,
            "create_time": self.create_time,
        }


class EngineSpaceConfigValueType(models.TextChoices):
    TEXT = "TEXT", _("文本")
    JSON = "JSON", _("JSON")


class EngineSpaceConfig(models.Model):
    interface_config_id = models.BigIntegerField(unique=True, verbose_name="交互模块配置id")
    name = models.CharField(max_length=255, verbose_name="配置名称")
    desc = models.TextField(null=True, blank=True, verbose_name="描述")
    is_public = models.BooleanField(default=True, verbose_name="是否公开")
    value_type = models.CharField(
        max_length=10,
        choices=EngineSpaceConfigValueType.choices,
        default=EngineSpaceConfigValueType.TEXT,
    )
    is_mix_type = models.BooleanField(default=False, verbose_name="是否混合类型")

    text_value = models.CharField(_("配置值"), max_length=128, default="")
    json_value = models.JSONField(_("配置值(JSON)"), default=dict, blank=True)

    space_id = models.BigIntegerField(null=False, verbose_name="空间id")

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "value_type": self.value_type,
            "value": self.text_value,
            "json_value": self.json_value,
            "interface_config_id": self.interface_config_id,
        }

    @classmethod
    def get_space_var(cls, space_id):
        qs = cls.objects.filter(space_id=space_id, name="engine_space_config")
        if not qs.exists():
            return {}
        instance = qs.first()
        return instance.json_value


def default_cron():
    return {
        "minute": "0",
        "hour": "*",
        "day_of_week": "*",
        "day_of_month": "*",
        "month_of_year": "*",
    }


class PeriodicTaskManager(models.Manager):
    def create_task(self, name, template_id, trigger_id, cron, config, creator, extra_info=None, is_enabled=True):
        with transaction.atomic():
            periodic_task = self.create(
                name=name,
                template_id=template_id,
                trigger_id=trigger_id,
                cron=cron,
                config=config,
                creator=creator,
                extra_info=extra_info,
            )

            schedule, _ = DjangoCeleryBeatCrontabSchedule.objects.get_or_create(
                minute=cron.get("minute", "0"),
                hour=cron.get("hour", "*"),
                day_of_week=cron.get("day_of_week", "*"),
                day_of_month=cron.get("day_of_month", "*"),
                month_of_year=cron.get("month_of_year", "*"),
                timezone=timezone.pytz.timezone(settings.TIME_ZONE) or "Asia/Shanghai",
            )
            _ = schedule.schedule  # noqa
            celery_task = DjangoCeleryBeatPeriodicTask.objects.create(
                crontab=schedule,
                name=uniqid(),
                task="bkflow.task.celery.tasks.bkflow_periodic_task_start",
                enabled=is_enabled,
                kwargs=json.dumps({"periodic_task_id": periodic_task.id}),
            )
            periodic_task.celery_task = celery_task
            periodic_task.save()
        return periodic_task


class PeriodicTask(models.Model):
    name = models.CharField(_("周期任务名称"), max_length=64)
    template_id = models.IntegerField(_("关联流程模板 ID"), db_index=True)
    trigger_id = models.IntegerField(_("关联触发器 ID"), db_index=True)
    cron = models.JSONField(_("调度策略"), default=default_cron)
    celery_task = models.ForeignKey(
        DjangoCeleryBeatPeriodicTask,
        related_name="periodic_task",
        verbose_name=_("celery 周期任务实例"),
        null=True,
        on_delete=models.SET_NULL,
    )
    config = models.JSONField(help_text="流程相关信息")
    total_run_count = models.PositiveIntegerField(_("执行次数"), default=0)
    last_run_at = models.DateTimeField(_("上次运行时间"), null=True)
    creator = models.CharField(_("创建者"), max_length=32, default="")
    extra_info = models.JSONField(verbose_name=_("额外信息"), null=True)

    objects = PeriodicTaskManager()

    class Meta:
        verbose_name = _("周期任务")
        verbose_name_plural = _("周期任务")

    def __unicode__(self):
        return "{name}({id})".format(name=self.name, id=self.id)

    @property
    def enabled(self):
        return self.celery_task.enabled

    def delete(self, using=None, keep_parents=False):
        self.celery_task.delete()
        return super().delete(using, keep_parents)

    def set_enabled(self, enabled):
        """修改celery任务开启状态"""
        self.celery_task.enabled = enabled
        self.celery_task.save()

    def modify_cron(self, cron, must_disabled=True):
        """修改celery周期任务周期计划"""
        schedule, _ = DjangoCeleryBeatCrontabSchedule.objects.get_or_create(
            minute=cron.get("minute", "0"),
            hour=cron.get("hour", "*"),
            day_of_week=cron.get("day_of_week", "*"),
            day_of_month=cron.get("day_of_month", "*"),
            month_of_year=cron.get("month_of_year", "*"),
            timezone=timezone.pytz.timezone(settings.TIME_ZONE) or "Asia/Shanghai",
        )
        _ = schedule.schedule  # noqa
        self.cron = schedule.__str__()
        if must_disabled and self.enabled:
            with transaction.atomic():
                self.set_enabled(False)
                self.celery_task.crontab = schedule
                self.celery_task.save()
                self.set_enabled(True)
            return
        else:
            self.celery_task.crontab = schedule
            self.celery_task.save()
        self.save()


class TaskFlowRelation(models.Model):
    id = models.BigAutoField(verbose_name="ID", primary_key=True)
    task_id = models.BigIntegerField(verbose_name=_("任务ID"), db_index=True)
    parent_task_id = models.BigIntegerField(verbose_name=_("父任务ID"), db_index=True)
    root_task_id = models.BigIntegerField(verbose_name=_("根任务ID"), db_index=True)
    create_time = models.DateTimeField(verbose_name=_("创建时间"), auto_now_add=True)
    extra_info = models.JSONField(verbose_name=_("额外信息"), null=True)

    class Meta:
        verbose_name = verbose_name_plural = _("任务关系")
