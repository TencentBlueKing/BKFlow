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
import re
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _


class LabelManager(models.Manager):
    """自定义管理器，添加层级相关查询方法"""

    def check_label_ids(self, label_ids):
        if len(label_ids) != self.filter(id__in=label_ids).count():
            return False
        return True

    def get_root_labels(self, space_id=-1, label_scope=None):
        """获取指定空间、指定范围的根标签（父ID为null或-1）"""
        filters = {"parent_id__isnull": True, "space_id": space_id}
        # 兼容可能的-1存储（如果根标签存-1，需调整过滤条件为 parent_id=-1）
        # filters = Q(parent_id__isnull=True) | Q(parent_id=-1)
        if label_scope:
            filters["label_scope__contains"] = label_scope
        return self.filter(**filters).order_by("name")

    def get_sub_labels(self, parent_id, recursive=False):
        """
        获取指定父标签ID的子标签（手动过滤parent_id）
        :param parent_id: 父标签ID
        :param recursive: 是否递归查询所有子孙标签
        :return: QuerySet（非递归）或列表（递归）
        """
        if not recursive:
            # 非递归：直接过滤parent_id等于目标ID
            return self.filter(parent_id=parent_id).order_by("name")

        # 递归查询：手动遍历子标签，累计所有子孙
        sub_labels = list(self.filter(parent_id=parent_id).order_by("name"))
        for label in sub_labels:
            # 递归查询当前标签的子标签，并入结果
            sub_labels.extend(self.get_sub_labels(label.id, recursive=True))
        return sub_labels

    def get_parent_label(self, label_id):
        """通过标签ID获取其父标签（手动查询parent_id对应的记录）"""
        try:
            # 当前标签的parent_id字段存储父标签ID
            current_label = self.get(id=label_id)
            if not current_label.parent_id:  # 根标签无父标签
                return None
            # 通过parent_id查询父标签记录
            return self.get(id=current_label.parent_id)
        except self.model.DoesNotExist:
            return None

    def get_labels_map(self, label_ids):
        """通过标签ID获取其完整信息"""
        labels = Label.objects.filter(id__in=label_ids)
        labels_map = {}
        for label in labels:
            label_dict = {"id": label.id, "name": label.name, "color": label.color, "full_path": label.full_path}
            labels_map[label.id] = label_dict
        return labels_map


class Label(models.Model):
    LABEL_SCOPE_CHOICES = (
        ("task", _("任务")),
        ("template", _("模板")),
        ("common", _("通用")),
    )

    id = models.BigAutoField(_("标签ID"), primary_key=True)
    name = models.CharField(_("标签名称"), max_length=255, db_index=True, help_text="标签名称")
    creator = models.CharField(_("创建者"), max_length=255, help_text="标签创建人")
    updated_by = models.CharField(_("更新者"), max_length=255, help_text="标签更新人")
    space_id = models.IntegerField(_("空间ID"), default=-1, help_text="标签对应的空间id（默认标签时space_id=-1）")
    is_default = models.BooleanField(_("默认标签"), default=False, help_text="是否是默认标签")
    color = models.CharField(_("标签颜色"), max_length=7, default="#dcffe2", help_text="标签颜色值（如#ffffff）")
    description = models.CharField(_("标签描述"), max_length=255, blank=True, null=True, help_text="标签描述")
    label_scope = models.JSONField(
        verbose_name=_("标签范围"), default="template", help_text="标签范围（支持多选，如['task', 'common']）"
    )

    # 核心修改：用IntegerField存储父标签ID，替代外键
    parent_id = models.IntegerField(_("父标签ID"), null=True, blank=True, default=None, help_text="父标签ID（根标签填null或留空）")

    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    objects = LabelManager()

    class Meta:
        verbose_name = _("用户标签 Label")
        verbose_name_plural = _("用户标签 Label")
        # 唯一约束：同一空间、同一父ID下，标签名称不能重复
        unique_together = ("space_id", "parent_id", "name")
        ordering = ["space_id", "parent_id", "name"]

    def __str__(self):
        # 手动查询父标签名称（替代外键的self.parent.name）
        parent_label = self.get_parent_label()
        parent_name = parent_label.name if parent_label else "无"
        return f"标签：{self.name}（父标签：{parent_name}，空间：{self.space_id}）"

    def get_parent_label(self):
        """获取父标签实例（手动通过parent_id查询）"""
        if not self.parent_id:
            return None
        try:
            return Label.objects.get(id=self.parent_id)
        except Label.DoesNotExist:
            # 父标签已删除（数据不一致），返回None
            return None

    def clean(self):
        """数据验证：保持原有约束，适配手动关联"""
        # 1. 子标签的space_id必须与父标签一致（如果有父标签）
        if self.parent_id:
            parent_label = self.get_parent_label()
            if not parent_label:
                raise ValidationError(_("父标签不存在（父ID：{}）".format(self.parent_id)))
            if self.space_id != parent_label.space_id:
                raise ValidationError(_("子标签的空间ID必须与父标签一致"))
        # 2. 禁止循环引用（如A→B→C→A）
        if self.parent_id:
            current_parent_id = self.parent_id
            # 遍历所有祖先标签，检查是否包含自身ID
            while current_parent_id:
                if current_parent_id == self.id:
                    raise ValidationError(_("禁止循环引用：标签不能作为自身的祖先"))
                # 手动获取上一级父标签ID
                try:
                    ancestor = Label.objects.get(id=current_parent_id)
                    current_parent_id = ancestor.parent_id
                except Label.DoesNotExist:
                    break  # 父标签不存在，终止检查

    def save(self, *args, **kwargs):
        """保存前执行验证"""
        self.clean()
        super().save(*args, **kwargs)

    @staticmethod
    def get_label_ids_by_names(names):
        """通过标签名称列表获取对应的标签ID列表"""
        labels = [s.strip() for s in re.split(r"[,\s]+", names) if s.strip()]

        label_ids = []
        if labels:
            q_objects = Q()
            for keyword in labels:
                q_objects |= Q(name__icontains=keyword)
            label_ids = list(Label.objects.filter(q_objects).values_list("id", flat=True))

        return label_ids

    @property
    def full_path(self):
        """获取标签完整路径（手动递归查询父标签）"""
        path = [self.name]
        current_parent = self.get_parent_label()
        while current_parent:
            path.insert(0, current_parent.name)
            # 继续查询上一级父标签
            current_parent = current_parent.get_parent_label()
        return "/".join(path)

    def is_root(self):
        """判断是否为根标签（parent_id为null或无对应父标签）"""
        return not self.parent_id or not self.get_parent_label()

    def get_all_children(self, recursive=True):
        """获取所有子标签（手动过滤parent_id）"""
        return Label.objects.get_sub_labels(parent_id=self.id, recursive=recursive)


class BaseLabelRelationManager(models.Manager):
    """
    通用的标签关系管理器
    核心思想：将变化的字段名 (task_id/template_id) 抽象为 self.fk_field
    """

    def __init__(self, fk_field):
        super().__init__()
        self.fk_field = fk_field

    def set_labels(self, obj_id, label_ids):
        """
        设置对象的标签（增量更新）
        """
        # 1. 构造查询参数，例如: {"template_id": 1} 或 {"task_id": 1}
        filter_kwargs = {self.fk_field: obj_id}

        # 2. 获取已有标签
        existing_labels = self.filter(**filter_kwargs).values_list("label_id", flat=True)

        # 3. 计算差异
        existing_set = set(existing_labels)
        new_set = set(label_ids)

        add_ids = list(new_set - existing_set)
        remove_ids = list(existing_set - new_set)

        # 4. 执行删除
        if remove_ids:
            # 构造删除查询: template_id=1, label_id__in=[...]
            delete_kwargs = {self.fk_field: obj_id, "label_id__in": remove_ids}
            self.filter(**delete_kwargs).delete()

        # 5. 执行批量添加
        if add_ids:
            # 动态创建模型实例: TaskLabelRelation(task_id=1, label_id=xx)
            new_relations = [self.model(**{self.fk_field: obj_id, "label_id": label_id}) for label_id in add_ids]
            self.bulk_create(new_relations)

    def fetch_labels(self, obj_id):
        """
        获取单个对象的标签列表
        """
        filter_kwargs = {self.fk_field: obj_id}
        label_ids = self.filter(**filter_kwargs).distinct().values_list("label_id", flat=True)
        labels = Label.objects.filter(id__in=label_ids)
        labels_list_of_dicts = []

        for label in labels:
            label_dict = {
                "id": label.id,
                "name": label.name,
                "color": label.color,
            }
            label_dict["full_path"] = label.full_path
            labels_list_of_dicts.append(label_dict)

        return labels_list_of_dicts

    def fetch_objects_labels(self, obj_ids, label_fields=("name", "color")):
        """
        批量获取多个对象的标签字典
        返回格式: {obj_id: [label_dict, ...]}
        """
        # 1. 构造 __in 查询，例如 template_id__in=[1,2,3]
        filter_kwargs = {f"{self.fk_field}__in": obj_ids}
        # 2. 获取所有关系
        relations = self.filter(**filter_kwargs).values(self.fk_field, "label_id")
        if not relations:
            return {}
        # 3. 提取标签详情
        label_ids = {rel["label_id"] for rel in relations}
        labels_map = {
            label.id: {
                "id": label.id,
                **{field: getattr(label, field) for field in label_fields},
                "full_path": label.full_path,
            }
            for label in Label.objects.filter(id__in=label_ids)
        }
        # 4. 组装结果
        result = defaultdict(list)
        for rel in relations:
            oid = rel[self.fk_field]
            lid = rel["label_id"]
            if lid in labels_map:
                result[oid].append(labels_map[lid])
        return dict(result)


class TemplateLabelRelation(models.Model):
    template_id = models.IntegerField(_("模版ID"), db_index=True)
    label_id = models.IntegerField(_("标签ID"), db_index=True)

    objects = BaseLabelRelationManager(fk_field="template_id")

    class Meta:
        verbose_name = _("模版标签关系 TemplateLabelRelation")
        verbose_name_plural = _("模版标签关系 TemplateLabelRelation")
        unique_together = ("template_id", "label_id")
