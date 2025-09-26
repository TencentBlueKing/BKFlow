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
from copy import deepcopy

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from pipeline.validators import validate_pipeline_tree
from rest_framework import serializers
from webhook.signals import event_broadcast_signal

from bkflow.bk_plugin.models import BKPluginAuthorization
from bkflow.constants import (
    TemplateOperationSource,
    TemplateOperationType,
    WebhookEventType,
    WebhookScopeType,
)
from bkflow.permission.models import TEMPLATE_PERMISSION_TYPE, Token
from bkflow.space.models import Space
from bkflow.template.models import (
    Template,
    TemplateMockData,
    TemplateMockScheme,
    TemplateOperationRecord,
    TemplateSnapshot,
    Trigger,
)
from bkflow.template.serializers.trigger import TriggerSerializer
from bkflow.template.utils import send_callback

logger = logging.getLogger("root")


class AdminTemplateSerializer(serializers.ModelSerializer):
    create_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S%z")
    update_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S%z")

    class Meta:
        model = Template
        fields = (
            "id",
            "name",
            "creator",
            "create_at",
            "updated_by",
            "update_at",
            "snapshot_id",
            "scope_type",
            "scope_value",
            "source",
            "is_enabled",
            "notify_config",
            "version",
            "space_id",
            "subprocess_info",
        )


class TemplateSerializer(serializers.ModelSerializer):
    pipeline_tree = serializers.JSONField(required=True)

    snapshot_id = serializers.IntegerField(help_text=_("快照ID"), required=False, read_only=True)
    notify_config = serializers.JSONField(help_text=_("配置"), required=False)
    version = serializers.CharField(help_text=_("版本"), read_only=True)
    desc = serializers.CharField(help_text=_("流程说明"), required=False, allow_blank=True)
    triggers = TriggerSerializer(many=True, required=True, allow_null=True)
    subprocess_info = serializers.JSONField(help_text=_("子流程信息"), read_only=True)

    def validate_space_id(self, space_id):
        if not Space.objects.filter(id=space_id).exists():
            raise serializers.ValidationError(_("创建失败，对应的空间不存在"))

        return space_id

    def validate_pipeline_tree(self, pipeline_tree):
        # 校验树的合法性

        try:
            validate_pipeline_tree(pipeline_tree, cycle_tolerate=True)
        except Exception as e:
            logger.exception("CreateTemplateSerializer pipeline validate error, err = {}".format(e))
            raise serializers.ValidationError(_("参数校验失败，pipeline校验不通过, err={}".format(e)))

        return pipeline_tree

    def validate_triggers(self, triggers):
        periodic_triggers = [trigger for trigger in triggers if trigger.get("type") == Trigger.TYPE_PERIODIC]
        if len(periodic_triggers) > 1:
            raise serializers.ValidationError(_("参数校验失败，该流程只允许有一个定时触发器！"))
        return triggers

    @transaction.atomic()
    def create(self, validated_data):
        pipeline_tree = validated_data.pop("pipeline_tree", None)
        snapshot = TemplateSnapshot.create_snapshot(pipeline_tree)
        validated_data["snapshot_id"] = snapshot.id
        template = super().create(validated_data)

        snapshot.template_id = template.id
        snapshot.save(update_fields=["template_id"])

        event_broadcast_signal.send(
            sender=WebhookEventType.TEMPLATE_CREATE.value,
            scopes=[(WebhookScopeType.SPACE.value, str(template.space_id))],
            extra_info={"template_id": template.id},
        )
        return template

    @transaction.atomic()
    def update(self, instance, validated_data):
        # TODO: 需要校验哪些字段是不可以更新的
        pipeline_tree = validated_data.pop("pipeline_tree", None)
        # 检查新建任务的流程中是否有未二次授权的蓝鲸插件
        try:
            exist_code_list = [
                node["component"]["data"]["plugin_code"]["value"]
                for node in pipeline_tree["activities"].values()
                if node["type"] == "ServiceActivity" and node["component"].get("data", {}).get("plugin_code")
            ]
            BKPluginAuthorization.objects.batch_check_authorization(exist_code_list, str(instance.space_id))
        except Exception as e:
            logger.exception("TemplateSerializer update error, err = {}".format(e))
            raise serializers.ValidationError(detail={"msg": ("更新失败,{}".format(e))})
        pre_pipeline_tree = instance.pipeline_tree
        instance_copy = deepcopy(instance)
        # 批量修改流程绑定的触发器:
        try:
            Trigger.objects.compare_constants(
                pre_pipeline_tree.get("constants", {}),
                pipeline_tree.get("constants", {}),
                validated_data.get("triggers"),
            )
            Trigger.objects.batch_modify_triggers(instance, validated_data["triggers"])
            snapshot = TemplateSnapshot.create_snapshot(pipeline_tree)
            instance.snapshot_id = snapshot.id
            snapshot.template_id = instance.id
            snapshot.save(update_fields=["template_id"])
            instance = super().update(instance, validated_data)
        except Exception as e:
            logger.exception("Triggers update or create failed,{}".format(e))
            instance.update_snapshot(pre_pipeline_tree)
            instance = instance_copy
            instance.save()
            raise serializers.ValidationError(detail={"msg": ("更新失败,{}".format(e))})

        send_callback(instance.space_id, "template", instance.build_callback_data(operate_type="update"))
        event_broadcast_signal.send(
            sender=WebhookEventType.TEMPLATE_UPDATE.value,
            scopes=[(WebhookScopeType.SPACE.value, str(instance.space_id))],
            extra_info={"template_id": instance.id},
        )
        return instance

    def get_current_user_auth(self, instance):
        if (self.context["request"].user.is_superuser and settings.BLOCK_ADMIN_PERMISSION is False) or getattr(
            self.context["request"], "is_space_superuser", False
        ):
            return TEMPLATE_PERMISSION_TYPE
        username = self.context["request"].user.username
        permissions = Token.objects.filter(
            space_id=instance.space_id,
            user=username,
            resource_id=instance.id,
            resource_type="TEMPLATE",
            expired_time__gte=timezone.now(),
        ).values_list("permission_type", flat=True)
        return permissions

    def to_representation(self, instance):
        data = super().to_representation(instance)
        triggers = Trigger.objects.filter(template_id=instance.id)
        data["triggers"] = TriggerSerializer(triggers, many=True).data
        data["auth"] = self.get_current_user_auth(instance)
        return data

    class Meta:
        model = Template
        fields = "__all__"
        read_only_fields = ("id", "space_id", "snapshot_id")


class DrawPipelineSerializer(serializers.Serializer):
    pipeline_tree = serializers.JSONField(help_text=_("pipeline tree"), required=True)
    canvas_width = serializers.IntegerField(help_text=_("画布宽度"), required=False)


class TemplateOperationRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateOperationRecord
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["operate_type_name"] = TemplateOperationType[instance.operate_type].value if instance.operate_type else ""
        data["operate_source_name"] = (
            TemplateOperationSource[instance.operate_source].value if instance.operate_source else ""
        )
        return data


class TemplateBatchDeleteSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"), required=True)
    template_ids = serializers.ListField(help_text=_("模板ID列表"), required=False, child=serializers.IntegerField())
    is_full = serializers.BooleanField(help_text=_("是否全量删除"), required=False, default=False)


class TemplateMockDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateMockData
        fields = "__all__"
        read_only_fields = ("id", "space_id", "template_id")


class TemplateMockSchemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateMockScheme
        fields = "__all__"


class TemplateMockDataListSerializer(serializers.Serializer):
    result = serializers.BooleanField(help_text="请求结果")
    message = serializers.CharField(help_text="请求结果失败时返回信息", default="")
    data = TemplateMockDataSerializer(many=True, help_text="mock数据列表", default=[])


class TemplateMockCreateNodeDataSerializer(serializers.Serializer):
    name = serializers.CharField(help_text=_("mock数据名称"), required=True)
    data = serializers.JSONField(help_text=_("mock数据"), required=True)
    is_default = serializers.BooleanField(help_text=_("是否为默认mock数据"), required=False, default=False)
    id = serializers.IntegerField(help_text=_("mock数据ID"), required=False)


class TemplateMockDataBatchCreateSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"), required=True)
    template_id = serializers.IntegerField(help_text=_("模板ID"), required=True)
    data = serializers.DictField(
        child=TemplateMockCreateNodeDataSerializer(many=True, help_text=_("mock数据列表"), required=True)
    )


class TemplateMockDataQuerySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"), required=True)
    template_id = serializers.IntegerField(help_text=_("模板ID"), required=True)
    node_id = serializers.CharField(help_text=_("节点ID"), required=False)


class TemplateRelatedResourceSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"), required=True)
    template_id = serializers.IntegerField(help_text=_("模板ID"), required=True)


class PreviewTaskTreeSerializer(serializers.Serializer):
    appoint_node_ids = serializers.ListSerializer(
        child=serializers.CharField(help_text=_("节点ID")), help_text=_("包含的节点ID列表"), default=[]
    )
    is_all_nodes = serializers.BooleanField(required=False, default=False, help_text=_("preview是否需要过滤节点"))


class TemplateCopySerializer(serializers.Serializer):
    template_id = serializers.IntegerField(help_text=_("模板ID"), required=True)
    space_id = serializers.IntegerField(help_text=_("空间ID"), required=True)
    copy_subprocess = serializers.BooleanField(help_text=_("是否复制子流程"), required=False, default=False)


class SimplifiedTemplateFileSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="uploaded file")
