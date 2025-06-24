# -*- coding: utf-8 -*-
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
import logging

from django.utils.translation import ugettext_lazy as _
from pipeline.validators import validate_pipeline_tree
from rest_framework import serializers

from bkflow.constants import MAX_LEN_OF_TEMPLATE_NAME, USER_NAME_MAX_LENGTH
from bkflow.pipeline_converter.constants import NodeTypes
from bkflow.pipeline_converter.data_models import (
    ComponentNode,
    ConditionalParallelGateway,
    ConvergeGateway,
    EmptyEndNode,
    EmptyStartNode,
    ExclusiveGateway,
    ParallelGateway,
)
from bkflow.space.models import Space
from bkflow.template.models import Template

logger = logging.getLogger("root")


class TemplateBaseSerializer(serializers.Serializer):
    creator = serializers.CharField(help_text=_("创建人"), max_length=USER_NAME_MAX_LENGTH, required=False)
    name = serializers.CharField(help_text=_("模版名称"), max_length=MAX_LEN_OF_TEMPLATE_NAME, required=True)
    desc = serializers.CharField(help_text=_("描述"), max_length=256, required=False)
    scope_type = serializers.CharField(help_text=_("流程范围类型"), max_length=128, required=False)
    scope_value = serializers.CharField(help_text=_("流程范围值"), max_length=128, required=False)
    source = serializers.CharField(help_text=_("来源"), max_length=32, required=False)
    version = serializers.CharField(help_text=_("版本号"), max_length=32, required=False)
    extra_info = serializers.JSONField(help_text=_("额外扩展信息"), required=False)

    def validate_creator(self, value):
        if not value and not self.context.get("request").user.username:
            raise serializers.ValidationError(_("网关用户和creator都为空，请检查"))
        return value


class CreateTemplateSerializer(TemplateBaseSerializer):
    """
    创建模板的序列化器
    """

    notify_config = serializers.JSONField(help_text=_("通知配置"), required=False)
    source_template_id = serializers.IntegerField(help_text=_("来源的模板id"), required=False)
    pipeline_tree = serializers.JSONField(help_text=_("任务树"), required=False)

    def validate(self, attrs):

        source_template_id = attrs.get("source_template_id")
        if source_template_id:
            try:
                template = Template.objects.get(id=source_template_id, is_deleted=False)
            except Template.DoesNotExist:
                raise serializers.ValidationError(_(f"复制的源模板不存在, 请检查: {source_template_id}"))

            if template.space_id != self.context.get("space_id"):
                raise serializers.ValidationError(
                    _("只能复制同一个空间下的模板, space_id={space_id}").format(space_id=template.space_id)
                )

        pipeline_tree = attrs.get("pipeline_tree")

        if pipeline_tree:
            try:
                validate_pipeline_tree(pipeline_tree)
            except Exception as e:
                logger.exception("CreateTemplateSerializer pipeline validate error, err = {}".format(e))
                raise serializers.ValidationError(_("参数校验失败，pipeline校验不通过, err={}".format(e)))

        return attrs


class ImportTemplateSerializer(TemplateBaseSerializer):
    pipeline_data = serializers.JSONField(help_text=_("流程信息"), required=True)

    NODE_TYPE_MAPPING = {
        NodeTypes.COMPONENT.value: ComponentNode,
        NodeTypes.END_EVENT.value: EmptyEndNode,
        NodeTypes.START_EVENT.value: EmptyStartNode,
        NodeTypes.PARALLEL_GATEWAY.value: ParallelGateway,
        NodeTypes.EXCLUSIVE_GATEWAY.value: ExclusiveGateway,
        NodeTypes.CONDITIONAL_PARALLEL_GATEWAY.value: ConditionalParallelGateway,
        NodeTypes.CONVERGE_GATEWAY.value: ConvergeGateway,
    }

    def validate_pipeline_data(self, value):
        nodes = value.get("nodes")
        if not isinstance(nodes, list):
            raise serializers.ValidationError(_("nodes字段必须是列表类型"))

        for index, node in enumerate(nodes, 1):
            node_type = node.get("type")
            if not node_type:
                raise serializers.ValidationError(_(f"第 {index} 个节点缺少type字段"))

            node_class = self.NODE_TYPE_MAPPING.get(node_type)
            if not node_class:
                raise serializers.ValidationError(_("不支持的节点类型: %(type)s") % {"type": node_type})

            try:
                node_class(**node)
            except Exception as e:
                error_msg = self._format_error_message(e, index)
                logger.exception("ImportTemplateSerializer node validate error, err = {}".format(error_msg))
                raise serializers.ValidationError(error_msg)
        return value

    def _format_error_message(self, error, node_index):
        """Format detailed error message from validation exception."""
        message = f"第 {node_index} 个节点验证失败: "

        if not hasattr(error, "errors"):
            return f"{message}{str(error)}"

        missing_fields = []
        type_mismatches = []

        for err in error.errors():
            field = err["loc"][0]

            if err["type"] == "value_error.missing":
                missing_fields.append(field)
            elif err["type"].startswith("type_error."):
                type_mismatches.append(field)

        parts = []
        if missing_fields:
            parts.append(f"缺少必填字段: {', '.join(missing_fields)}")
        if type_mismatches:
            parts.append(f"字段: {', '.join(type_mismatches)}类型错误")

        return message + "; ".join(parts)


class DeleteTemplateSerializer(serializers.Serializer):
    template_id = serializers.IntegerField(help_text=_("模板ID"), required=True)
    space_id = serializers.IntegerField(help_text=_("空间ID"), required=False)

    def validate_space_id(self, space_id):
        if not Space.exists(space_id=space_id):
            raise serializers.ValidationError(_(f"校验失败，space_id={space_id}对应的空间不存在"))

        return space_id


class UpdateTemplateSerializer(serializers.Serializer):
    operator = serializers.CharField(help_text=_("更新人"), max_length=USER_NAME_MAX_LENGTH, required=False)
    name = serializers.CharField(help_text=_("模版名称"), max_length=MAX_LEN_OF_TEMPLATE_NAME, required=False)
    notify_config = serializers.JSONField(help_text=_("通知配置"), required=False)
    desc = serializers.CharField(help_text=_("描述"), max_length=256, required=False)
    scope_type = serializers.CharField(help_text=_("流程范围类型"), max_length=128, required=False)
    scope_value = serializers.CharField(help_text=_("流程范围值"), max_length=128, required=False)
    source = serializers.CharField(help_text=_("来源"), max_length=32, required=False)
    version = serializers.CharField(help_text=_("版本号"), max_length=32, required=False)
    extra_info = serializers.JSONField(help_text=_("额外扩展信息"), required=False)

    def validate(self, attrs):
        operator = attrs.get("operator")
        if not operator and not self.context.get("request").user.username:
            raise serializers.ValidationError(_("网关用户和operator都为空，请检查"))

        return attrs


class TemplateListFilterSerializer(serializers.Serializer):
    name = serializers.CharField(help_text=_("模板名称"), max_length=MAX_LEN_OF_TEMPLATE_NAME, required=False)
    creator = serializers.CharField(help_text=_("创建人"), max_length=USER_NAME_MAX_LENGTH, required=False)
    updated_by = serializers.CharField(help_text=_("更新人"), required=False)
    scope_type = serializers.CharField(help_text=_("流程范围类型"), max_length=128, required=False)
    scope_value = serializers.CharField(help_text=_("流程范围值"), max_length=128, required=False)
    create_at_start = serializers.DateTimeField(help_text=_("开始时间小于等于"), required=False)
    create_at_end = serializers.DateTimeField(help_text=_("开始时间大于等于"), required=False)
    order_by = serializers.CharField(help_text=_("排序字段"), required=False, default="-create_at")


class TemplateDetailQuerySerializer(serializers.Serializer):
    with_mock_data = serializers.BooleanField(help_text=_("是否包含 mock 数据"), required=False)
