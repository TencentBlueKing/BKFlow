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
import datetime
import logging
from copy import deepcopy

from django.db import models, transaction
from django.utils.translation import ugettext_lazy as _
from pipeline.core.constants import PE
from pipeline.parser.utils import replace_all_id

from bkflow.constants import TemplateOperationSource, TemplateOperationType
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.contrib.operation_record.models import BaseOperateRecord
from bkflow.exceptions import APIResponseError, NotFoundError, ValidationError
from bkflow.utils.canvas import OperateType
from bkflow.utils.md5 import compute_pipeline_md5
from bkflow.utils.models import CommonModel, CommonSnapshot
from bkflow.utils.pipeline import replace_pipeline_tree_node_ids

logger = logging.getLogger("root")


class TemplateManager(models.Manager):
    def copy_template(self, template_id, space_id, operator, name=None, desc=None, copy_subprocess=False, version=None):
        """
        复制流程模版 snapshot 深拷贝复制 其他浅拷贝复制 其他关联资源如 mock 数据、决策表数据等暂不拷贝
        暂不支持拷贝带决策表插件的流程
        """
        template = self.get(id=template_id, space_id=space_id)
        # 复制逻辑 snapshot 需要深拷贝
        template_pipeline_tree = template.get_pipeline_tree_by_version(version)
        for node in template_pipeline_tree["activities"].values():
            if node["type"] == "SubProcess":
                if copy_subprocess:
                    new_sub_template = self.copy_template(
                        node["template_id"], space_id, operator, copy_subprocess=True, version=node["version"]
                    )
                    node["template_id"] = new_sub_template.id
                    node["version"] = new_sub_template.version
                else:
                    continue
            elif node["component"]["code"] == "dmn_plugin":
                raise ValidationError("流程中存在决策节点 暂不支持拷贝")
        template.pk = None
        template.name = name or f"Copy {template.name}"
        template.desc = desc or template.desc

        copyed_pipeline_tree = deepcopy(template_pipeline_tree)
        pe_maps = replace_all_id(copyed_pipeline_tree)
        replace_pipeline_tree_node_ids(copyed_pipeline_tree, OperateType.CREATE_TEMPLATE.value, pe_maps[PE.activities])

        # 拷贝流程并替换节点 避免 id 重叠
        with transaction.atomic():
            # 开启事务 确保都创建成功
            copyed_snapshot = TemplateSnapshot.create_snapshot(copyed_pipeline_tree)
            template.snapshot_id = copyed_snapshot.id
            template.updated_by = operator
            template.creator = operator
            template.save()
            copyed_snapshot.template_id = template.id
            copyed_snapshot.save(update_fields=["template_id"])
        return template


class Template(CommonModel):
    """
    字段说明:
    notify_type : 通知类型存储的是一个列表
    notify_receivers : {'receiver_group': ['Maintainers'], 'more_receiver': 'username1,username2'}
    snapshot_id : 因为在新的流程中，一个版本对应一个流程，对应修改都是原地修改
    """

    id = models.BigAutoField(_("模版ID"), primary_key=True)
    space_id = models.IntegerField(_("空间ID"))
    snapshot_id = models.BigIntegerField(_("模板对应的数据ID"))
    name = models.CharField(_("模版名称"), max_length=128)
    desc = models.CharField(_("描述"), max_length=256, null=True, blank=True)
    notify_config = models.JSONField(_("流程事件通知配置"), default=dict)
    scope_type = models.CharField(_("流程范围类型"), max_length=128, null=True, blank=True)
    scope_value = models.CharField(_("流程范围"), max_length=128, null=True, blank=True)
    source = models.CharField(_("来源"), max_length=32, null=True, blank=True, help_text=_("第三方系统对应的资源ID"))
    is_enabled = models.BooleanField(_("是否启用"), default=True)
    extra_info = models.JSONField(_("额外的扩展信息"), default=dict)

    objects = TemplateManager()

    class Meta:
        verbose_name = _("流程模板")
        verbose_name_plural = _("流程模板信息表")
        index_together = ["space_id", "scope_type", "scope_value"]

    def to_json(self, with_pipeline_tree=True):
        result = {
            "id": self.id,
            "space_id": self.space_id,
            "name": self.name,
            "desc": self.desc,
            "notify_config": self.notify_config,
            "scope_type": self.scope_type,
            "scope_value": self.scope_value,
            "source": self.source,
            "version": self.version,
            "is_enabled": self.is_enabled,
            "extra_info": self.extra_info,
            "creator": self.creator,
            "create_at": self.create_at,
            "update_at": self.update_at,
            "updated_by": self.updated_by,
        }
        if with_pipeline_tree:
            result["pipeline_tree"] = self.pipeline_tree
        return result

    @classmethod
    def exists(cls, template_id):
        return cls.objects.filter(id=template_id).exists()

    @property
    def snapshot(self):
        return TemplateSnapshot.objects.get(id=self.snapshot_id)

    @property
    def pipeline_tree(self):
        return self.snapshot.data

    def build_callback_data(self, operate_type):
        return {"type": "template", "data": {"id": self.id, "operate_type": operate_type}}

    def update_snapshot(self, pipeline_tree):
        if self.snapshot.has_change(pipeline_tree):
            try:
                TemplateSnapshot.objects.filter(id=self.snapshot_id).update(
                    data=pipeline_tree, md5sum=compute_pipeline_md5(pipeline_tree), create_time=datetime.datetime.now()
                )
            except Exception as e:
                logger.error("[Template->update_snapshot] update snapshot error, error = {}".format(e))

    def create_flow(self, username) -> int:
        """
        根据模板创建flow
        """
        return

    def get_pipeline_tree_by_version(self, version=None):
        if not version:
            return self.pipeline_tree
        return TemplateSnapshot.objects.filter(md5sum=version).order_by("-id").first().data

    @property
    def version(self):
        return self.snapshot.md5sum

    @property
    def subprocess_info(self):
        subprocess_info = TemplateReference.objects.filter(root_template_id=self.id).values(
            "subprocess_template_id", "subprocess_node_id", "version", "always_use_latest"
        )
        info = []
        if not subprocess_info:
            return info

        temp_current_versions = {
            item.id: item
            for item in Template.objects.filter(
                id__in=[int(item["subprocess_template_id"]) for item in subprocess_info]
            )
        }

        for item in subprocess_info:
            item["expired"] = (
                False
                if item["version"] is None
                or int(item["subprocess_template_id"]) not in temp_current_versions
                or item["always_use_latest"]
                else (item["version"] != temp_current_versions[int(item["subprocess_template_id"])].version)
            )
            item["subprocess_template_name"] = temp_current_versions[int(item["subprocess_template_id"])].name
            info.append(item)

        return info

    def outputs(self, version=None):
        data = self.get_pipeline_tree_by_version(version)

        if "constants" not in data:
            return {}

        outputs_key = data["outputs"]
        outputs = {}
        for key in outputs_key:
            if key in data["constants"]:
                outputs[key] = data["constants"][key]
        return outputs


class TemplateSnapshot(CommonSnapshot):
    """
    默认模板快照
    """

    template_id = models.BigIntegerField(help_text=_("模板ID"), null=True)

    class Meta:
        verbose_name = _("模板快照")
        verbose_name_plural = _("模板快照表")
        ordering = ["-id"]

    @classmethod
    def create_snapshot(cls, pipeline_tree):
        return cls.objects.create(data=pipeline_tree, md5sum=compute_pipeline_md5(pipeline_tree))


class TemplateOperationRecord(BaseOperateRecord):
    """模版操作记录"""

    operate_type = models.CharField(
        _("操作类型"), choices=[(_type.name, _type.value) for _type in TemplateOperationType], max_length=64
    )
    operate_source = models.CharField(
        _("操作来源"), choices=[(_source.name, _source.value) for _source in TemplateOperationSource], max_length=64
    )

    class Meta:
        verbose_name = _("模版操作记录")
        verbose_name_plural = _("模版操作记录")
        indexes = [models.Index(fields=["instance_id"])]
        ordering = ["-id"]


class TemplateMockDataManager(models.Manager):
    def batch_create(self, operator: str, space_id: int, template_id: int, mock_data: dict, *args, **kwargs):
        objs = [
            TemplateMockData(
                space_id=space_id,
                template_id=template_id,
                node_id=node_id,
                data=data["data"],
                is_default=data["is_default"],
                operator=operator,
                name=data["name"],
            )
            for node_id, mock_data_list in mock_data.items()
            for data in mock_data_list
        ]
        self.bulk_create(objs)
        return self.filter(space_id=space_id, template_id=template_id)

    def batch_update(self, operator: str, space_id: int, template_id: int, mock_data: dict, *args, **kwargs):
        existing_ones = self.filter(space_id=space_id, template_id=template_id)
        mock_data_mappings = {data.id: data for data in existing_ones}

        flatten_mock_data = (
            (node_id, data) for node_id, mock_data_list in mock_data.items() for data in mock_data_list
        )

        # 根据是否有 id 来判断是新增数据还是更新数据
        update_ones = []
        update_ids = []
        new_ones = []

        for node_id, data in flatten_mock_data:
            if "id" in data:
                data_id = data.pop("id")
                update_ids.append(data_id)
                mock_data_obj = mock_data_mappings[data_id]
                mock_data_obj.name = data["name"]
                mock_data_obj.data = data["data"]
                mock_data_obj.is_default = data["is_default"]
                mock_data_obj.operator = operator
                mock_data_obj.node_id = node_id
                update_ones.append(mock_data_obj)
            else:
                new_ones.append(
                    TemplateMockData(
                        space_id=space_id,
                        template_id=template_id,
                        node_id=node_id,
                        data=data["data"],
                        is_default=data["is_default"],
                        operator=operator,
                        name=data["name"],
                    )
                )

        remove_ids = set(mock_data_mappings.keys()) - set(update_ids)
        try:
            with transaction.atomic():
                self.bulk_update(update_ones, ["name", "data", "is_default", "operator", "update_at", "node_id"])
                self.bulk_create(new_ones)
                self.filter(id__in=remove_ids).delete()
        except Exception as e:
            logger.exception(f"[TemplateMockDataManager] mock data batch update failed: {e}")
            raise e
        return self.filter(space_id=space_id, template_id=template_id)


class TemplateMockData(models.Model):
    name = models.CharField("Mock Data Name", max_length=128)
    space_id = models.IntegerField("Space ID")
    template_id = models.BigIntegerField("Template ID")
    node_id = models.CharField("Node ID", max_length=33)
    data = models.JSONField("Mock Data")
    is_default = models.BooleanField("Is Default", default=False)
    extra_info = models.JSONField("Extra Info", null=True, blank=True)
    operator = models.CharField("operator", max_length=32, null=True, blank=True)
    create_at = models.DateTimeField(_("创建时间"), auto_now_add=True, db_index=True)
    update_at = models.DateTimeField(_("更新时间"), auto_now=True)

    objects = TemplateMockDataManager()

    class Meta:
        verbose_name = "Template Mock Data"
        verbose_name_plural = "Template Mock Data"
        ordering = ["-id"]
        index_together = ["space_id", "template_id", "node_id"]


class TemplateMockScheme(models.Model):
    space_id = models.IntegerField("Space ID")
    template_id = models.BigIntegerField("Template ID")
    data = models.JSONField("Mock Scheme Data")
    operator = models.CharField("operator", max_length=32, null=True, blank=True)
    create_at = models.DateTimeField(_("创建时间"), auto_now_add=True, db_index=True)
    update_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = "Template Mock Scheme"
        verbose_name_plural = "Template Mock Scheme"
        ordering = ["-id"]
        index_together = ["space_id", "template_id"]


class BaseTriggerHandler:
    """触发器操作基类"""

    def create(self, trigger, template):
        raise NotImplementedError

    def update(self, trigger, data, template):
        raise NotImplementedError


class PeriodicTriggerHandler(BaseTriggerHandler):
    """定时触发器处理器"""

    def create(self, trigger, template):
        client = TaskComponentClient(space_id=trigger.space_id)
        data = {
            "name": template.name,
            "trigger_id": trigger.id,
            "template_id": trigger.template_id,
            "cron": trigger.config.get("cron"),
            "config": {
                "space_id": trigger.space_id,
                "pipeline_tree": template.pipeline_tree,
                "constants": trigger.config.get("constants"),
                "scope_type": template.scope_type,
                "scope_value": template.scope_value,
            },
            "creator": template.creator,
            "extra_info": {"notify_config": template.notify_config},
        }
        result = client.create_periodic_task(data=data)
        if not result.get("result"):
            raise APIResponseError(f"create periodic_task error: {result.get('message')}")

    def update(self, trigger, data, template):
        client = TaskComponentClient(space_id=trigger.space_id)
        update_data = {
            "name": template.name,
            "trigger_id": trigger.id,
            "cron": data["config"].get("cron"),
            "config": {
                "space_id": trigger.space_id,
                "pipeline_tree": template.pipeline_tree,
                "constants": data["config"].get("constants"),
                "scope_type": template.scope_type,
                "scope_value": template.scope_value,
            },
            "extra_info": {"notify_config": template.notify_config},
            "is_enabled": trigger.is_enabled,
        }
        result = client.update_periodic_task(data=update_data)
        if not result.get("result"):
            raise APIResponseError(f"update periodic_task error: {result.get('message')}")


class TriggerManager(models.Manager):
    def create_trigger(self, data, template):
        config = {
            "space_id": data.get("space_id"),
            "pipeline_tree": template.pipeline_tree,
            "scope_type": template.scope_type,
            "scope_value": template.scope_value,
        }
        data["config"] = {**data["config"], **config}
        with transaction.atomic():
            trigger = Trigger.objects.create(**data)
            handler = self._get_handler(trigger.type)
            handler.create(trigger, template)
        return trigger

    def update_trigger(self, trigger, data, template):
        config = {
            "pipeline_tree": template.pipeline_tree,
            "scope_type": template.scope_type,
            "scope_value": template.scope_value,
        }
        data["config"] = {**data["config"], **config}
        with transaction.atomic():
            for field, value in data.items():
                setattr(trigger, field, value)
            trigger.save()
            handler = self._get_handler(trigger.type)
            handler.update(trigger, data, template)
        return trigger

    def batch_delete_by_ids(self, space_id, trigger_ids, is_full=False):
        client = TaskComponentClient(space_id=space_id)
        if is_full:
            trigger_ids = self.filter(space_id=space_id).values_list("id", flat=True)
        result = client.batch_delete_periodic_task(data={"trigger_ids": list(trigger_ids)})
        if not result.get("result"):
            raise APIResponseError(f"delete periodic_task error: {result.get('message')}")
        self.filter(id__in=list(trigger_ids)).delete()

    def _get_handler(self, trigger_type):
        handlers = {
            Trigger.TYPE_PERIODIC: PeriodicTriggerHandler(),
        }
        handler = handlers.get(trigger_type)
        if not handler:
            raise NotFoundError(f"TriggerHandler with trigger type {trigger_type} not found")
        return handler

    def compare_constants(self, pre_constants_dict, input_constants_dict, triggers):
        """比较模板的新增常量和传入的常量，返回差异"""

        if not triggers:
            return
        pre_constants = {
            constant for constant in pre_constants_dict if pre_constants_dict[constant].get("show_type") == "show"
        }
        input_constants = {
            constant for constant in input_constants_dict if input_constants_dict[constant].get("show_type") == "show"
        }
        new_constants = input_constants - pre_constants
        for index, trigger in enumerate(triggers):
            trigger_constants = {constant for constant in trigger.get("config", {}).get("constants", {})}
            if new_constants - trigger_constants:
                cron_config = " ".join([value for time, value in trigger.get("config", {}).get("cron").items()])
                raise ValidationError(
                    f"该流程下的触发器 #{index}:{cron_config} 有以下新增参数未填写：{', '.join(new_constants - trigger_constants)}"
                )

    def batch_modify_triggers(self, template, triggers):
        """批量更新、创建和删除单个流程下的多个触发器"""

        input_trigger_ids = [trigger.get("id") for trigger in triggers if trigger.get("id")]
        exist_triggers = self.filter(template_id=template.id)

        # 根据入参中触发器的id集合和数据库中存在的触发器id集合，筛选出待更新、待创建和待删除的触发器id列表
        exist_triggers_dict = {trigger.id: trigger for trigger in exist_triggers}
        exist_trigger_ids = exist_triggers_dict.keys()
        to_update_trigger_ids = list(set(input_trigger_ids) & set(exist_trigger_ids))
        to_delete_trigger_ids = list(set(exist_trigger_ids) - set(input_trigger_ids))
        to_update_triggers = [
            trigger for trigger in triggers if trigger.get("id") and trigger.get("id") in to_update_trigger_ids
        ]
        # 没有携带id或为空则视为创建
        to_create_triggers = [trigger for trigger in triggers if not trigger.get("id")]

        for update_instance in to_update_triggers:
            trigger = exist_triggers_dict[update_instance.get("id")]
            self.update_trigger(trigger, update_instance, template)

        for create_instance in to_create_triggers:
            self.create_trigger(create_instance, template)

        # 批量删除触发器以及其对应的周期任务
        if to_delete_trigger_ids:
            self.batch_delete_by_ids(template.space_id, to_delete_trigger_ids)


class Trigger(CommonModel):
    # 定义触发器类型选项
    TYPE_PERIODIC = "periodic"
    TYPE_MANUAL = "manual"
    TYPE_REMOTE = "remote"

    TYPE_CHOICES = [
        (TYPE_PERIODIC, "定时"),  # 定时
        (TYPE_REMOTE, "远程"),  # 远程
    ]

    space_id = models.IntegerField(help_text="Space ID")
    template_id = models.IntegerField(help_text="Related template ID", db_index=True)
    is_enabled = models.BooleanField(default=True, help_text="Indicates whether the trigger is enabled")
    name = models.CharField(max_length=100)
    config = models.JSONField(help_text="Configuration for the trigger")
    type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default=TYPE_PERIODIC, help_text="Type of the trigger"  # 设置默认触发类型
    )

    objects = TriggerManager()

    class Meta:
        indexes = [
            models.Index(fields=["space_id", "template_id"]),
        ]


class TemplateReference(models.Model):
    """
    流程模板引用关系：直接引用
    """

    root_template_id = models.CharField(_("主流程模板ID"), max_length=32, db_index=True)
    subprocess_template_id = models.CharField(_("子流程模板ID"), max_length=32, null=False, db_index=True)
    subprocess_node_id = models.CharField(_("子流程节点 ID"), max_length=32, null=False)
    version = models.CharField(_("快照字符串的md5"), max_length=32, null=False)
    always_use_latest = models.BooleanField(_("是否永远使用最新版本"), default=False)
