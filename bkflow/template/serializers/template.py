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

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from pipeline.validators import validate_pipeline_tree
from rest_framework import serializers
from webhook.signals import event_broadcast_signal

from bkflow.bk_plugin.models import BKPluginAuthorization
from bkflow.constants import (
    MAX_LEN_OF_TEMPLATE_NAME,
    TemplateOperationSource,
    TemplateOperationType,
    WebhookEventType,
    WebhookScopeType,
)
from bkflow.permission.models import TEMPLATE_PERMISSION_TYPE, Token
from bkflow.pipeline_web.preview_base import PipelineTemplateWebPreviewer
from bkflow.space.configs import FlowVersioning, TemplateTriggerConfig
from bkflow.space.models import Space, SpaceConfig
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
from bkflow.utils.pipeline import replace_subprocess_version
from bkflow.utils.version import bump_custom

logger = logging.getLogger("root")


class BaseTemplateSerializer(serializers.ModelSerializer):
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
            "version",
            "space_id",
        )


class AdminTemplateSerializer(BaseTemplateSerializer):
    class Meta(BaseTemplateSerializer.Meta):
        fields = BaseTemplateSerializer.Meta.fields + (
            "notify_config",
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

    def validate_triggers(self, triggers):
        request = self.context.get("request")
        if request.method == "POST":
            space_id = self.initial_data.get("space_id")
        else:
            space_id = self.instance.space_id
        periodic_triggers = [trigger for trigger in triggers if trigger.get("type") == Trigger.TYPE_PERIODIC]
        if len(periodic_triggers) > 1 and SpaceConfig.get_config(space_id, TemplateTriggerConfig.name) == "false":
            raise serializers.ValidationError(_("参数校验失败，该流程只允许有一个定时触发器！"))
        return triggers

    def validate_pipeline_tree(self, pipeline_tree):
        # 校验树的合法性

        try:
            validate_pipeline_tree(pipeline_tree, cycle_tolerate=True)
        except Exception as e:
            logger.exception("CreateTemplateSerializer pipeline validate error, err = {}".format(e))
            raise serializers.ValidationError(_("参数校验失败，pipeline校验不通过, err={}".format(e)))

        if self.context["request"].method == "POST":
            space_id = self.initial_data.get("space_id")
            scope_type = self.initial_data.get("scope_type")
            scope_value = self.initial_data.get("scope_value")
        else:
            space_id = getattr(self.instance, "space_id", None)
            scope_type = getattr(self.instance, "scope_type", None)
            scope_value = getattr(self.instance, "scope_value", None)

        template_id = getattr(self.instance, "id", None)
        data = PipelineTemplateWebPreviewer.is_circular_reference(
            pipeline_tree, template_id, space_id, scope_type, scope_value
        )
        if data["has_cycle"]:
            raise serializers.ValidationError(
                _(f"更新失败，子流程节点【{data['node_name']}】引用的模板 {data['template_id']} 与当前流程存在循环引用")
            )

        return pipeline_tree

    @transaction.atomic()
    def create(self, validated_data):
        pipeline_tree = validated_data.pop("pipeline_tree", None)
        username = self.context["request"].user.username
        if SpaceConfig.get_config(space_id=validated_data["space_id"], config_name=FlowVersioning.name) == "true":
            snapshot = TemplateSnapshot.create_draft_snapshot(pipeline_tree, username)
        else:
            snapshot = TemplateSnapshot.create_snapshot(pipeline_tree, username, "1.0.0")
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
        username = self.context["request"].user.username
        if SpaceConfig.get_config(space_id=instance.space_id, config_name=FlowVersioning.name) == "true":
            instance.update_draft_snapshot(pipeline_tree, username)
        else:
            if instance.snapshot_version is None:
                current_version = "1.0.0"
            else:
                current_version = bump_custom(instance.snapshot_version)
            snapshot = TemplateSnapshot.create_snapshot(pipeline_tree, username, current_version)
            instance.snapshot_id = snapshot.id
            snapshot.template_id = instance.id
            snapshot.save(update_fields=["template_id"])
        instance = super().update(instance, validated_data)
        # 批量修改流程绑定的触发器:
        try:
            Trigger.objects.compare_constants(
                pre_pipeline_tree.get("constants", {}),
                pipeline_tree.get("constants", {}),
                validated_data.get("triggers"),
            )
            Trigger.objects.batch_modify_triggers(instance, validated_data["triggers"])
        except Exception as e:
            logger.exception("Triggers update or create failed,{}".format(e))
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
            Q(resource_id=f"{instance.scope_type}_{instance.scope_value}", resource_type="SCOPE")
            | Q(resource_id=instance.id, resource_type="TEMPLATE"),
            space_id=instance.space_id,
            user=username,
            expired_time__gte=timezone.now(),
        ).values_list("permission_type", flat=True)
        return list(set(permissions))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        triggers = Trigger.objects.filter(template_id=instance.id)
        data["triggers"] = TriggerSerializer(triggers, many=True).data
        data["auth"] = self.get_current_user_auth(instance)
        pipeline_tree = instance.pipeline_tree
        if SpaceConfig.get_config(space_id=instance.space_id, config_name=FlowVersioning.name) == "true":
            pipeline_tree = replace_subprocess_version(pipeline_tree)
        data["pipeline_tree"] = pipeline_tree
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
        exclude = ["extra_info"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["operate_type_name"] = TemplateOperationType[instance.operate_type].value if instance.operate_type else ""
        data["operate_source_name"] = (
            TemplateOperationSource[instance.operate_source].value if instance.operate_source else ""
        )
        if instance.operate_type == TemplateOperationType.release.name:
            data["version"] = instance.extra_info.get("version")
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
    version = serializers.CharField(help_text=_("版本号"), required=False)


class TemplateCopySerializer(serializers.Serializer):
    template_id = serializers.IntegerField(help_text=_("模板ID"), required=True)
    name = serializers.CharField(help_text=_("模版名称"), max_length=MAX_LEN_OF_TEMPLATE_NAME, required=False)
    desc = serializers.CharField(help_text=_("描述"), max_length=256, required=False, allow_blank=True)
    space_id = serializers.IntegerField(help_text=_("空间ID"), required=True)
    copy_subprocess = serializers.BooleanField(help_text=_("是否复制子流程"), required=False, default=False)


class TemplateReleaseSerializer(serializers.Serializer):
    version = serializers.CharField(help_text=_("版本号"), required=True)
    desc = serializers.CharField(help_text=_("描述"), required=False, allow_blank=True)


class TemplateSnapshotSerializer(serializers.ModelSerializer):
    create_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S%z")
    update_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S%z")

    class Meta:
        model = TemplateSnapshot
        fields = [
            "id",
            "create_time",
            "update_time",
            "version",
            "template_id",
            "desc",
            "draft",
            "creator",
            "operator",
            "md5sum",
        ]
