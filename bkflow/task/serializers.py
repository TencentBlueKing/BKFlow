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
import copy
import logging

import jsonschema
from pipeline.exceptions import PipelineException
from rest_framework import serializers

from bkflow.constants import TaskOperationSource, TaskOperationType
from bkflow.pipeline_web.parser.validator import validate_web_pipeline_tree
from bkflow.task.models import (
    EngineSpaceConfigValueType,
    PeriodicTask,
    TaskFlowRelation,
    TaskInstance,
    TaskOperationRecord,
)
from bkflow.task.operations import TaskNodeOperation, TaskOperation
from bkflow.utils.strings import standardize_pipeline_node_name

logger = logging.getLogger("root")

NOTIFY_CONFIG_SCHEMA = {
    "type": "object",
    "required": ["notify_type", "notify_receivers"],
    "properties": {
        "notify_type": {
            "type": "object",
            "properties": {
                "success": {"type": "array", "items": {"type": "string"}},
                "fail": {"type": "array", "items": {"type": "string"}},
            },
        },
        "notify_receivers": {
            "type": "object",
            "properties": {
                "receiver_group": {"type": "array", "items": {"type": "string"}},
                "more_receiver": {"type": "string"},
            },
        },
        "notify_format": {
            "type": "object",
            "properties": {"title": {"type": "string"}, "content": {"type": "string"}},
        },
    },
}


class CreateTaskInstanceSerializer(serializers.ModelSerializer):
    pipeline_tree = serializers.JSONField(required=True)
    constants = serializers.JSONField(required=False, default={})
    mock_data = serializers.JSONField(required=False, default={})

    def validate(self, value):
        if value.get("extra_info", {}).get("notify_config") is not None:
            try:
                notify_config = value["extra_info"]["notify_config"]
                jsonschema.validate(notify_config, NOTIFY_CONFIG_SCHEMA)
            except jsonschema.ValidationError as e:
                raise serializers.ValidationError(str(e))

        constants = value.pop("constants", {})
        pipeline_tree = value.get("pipeline_tree")
        try:
            for key, c_value in constants.items():
                if key not in pipeline_tree.get("constants", {}):
                    continue
                if pipeline_tree["constants"][key].get("is_meta", False):
                    meta = copy.deepcopy(pipeline_tree["constants"][key])
                    pipeline_tree["constants"][key]["meta"] = meta
                pipeline_tree["constants"][key]["value"] = c_value
            standardize_pipeline_node_name(pipeline_tree)
            validate_web_pipeline_tree(pipeline_tree)
        except PipelineException as e:
            msg = f"[API] create_task get invalid pipeline_tree: {e}"
            logger.exception(msg)
            raise serializers.ValidationError(str(e))

        return value

    class Meta:
        model = TaskInstance
        fields = [
            "space_id",
            "name",
            "pipeline_tree",
            "creator",
            "create_method",
            "trigger_method",
            "mock_data",
            "description",
            "template_id",
            "scope_type",
            "scope_value",
            "constants",
            "extra_info",
        ]


class TaskInstanceSerializer(serializers.ModelSerializer):
    create_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S%z")
    start_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S%z")
    finish_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S%z")

    class Meta:
        model = TaskInstance
        fields = "__all__"
        read_only_fields = (
            "id",
            "instance_id",
            "executor",
            "create_time",
            "start_time",
            "finish_time",
            "is_started",
            "is_finished",
            "is_revoked",
            "is_expired",
            "is_deleted",
            "create_method",
            "trigger_method",
            "execution_snapshot_id",
            "snapshot_id",
            "tree_info_id",
        )


class RetrieveTaskInstanceSerializer(TaskInstanceSerializer):
    pipeline_tree = serializers.SerializerMethodField()
    outputs = serializers.SerializerMethodField()

    def get_pipeline_tree(self, obj):
        return obj.pipeline_tree

    def get_outputs(self, obj):
        outputs_result = TaskNodeOperation(task_instance=obj, node_id=obj.instance_id).get_outputs()
        return [{"key": key, "value": value} for key, value in outputs_result.data.items()]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.trigger_method == "subprocess":
            task_flow_relation = TaskFlowRelation.objects.get(task_id=instance.id)
            parent_task_id = task_flow_relation.parent_task_id
            task_instance = TaskInstance.objects.get(id=parent_task_id)
            operation = TaskOperation(task_instance=task_instance).get_task_states()
            stare = operation.data.get("state") if operation.result is True else None

            representation["parent_task_info"] = {"task_id": parent_task_id, "state": stare}
        return representation


class GetTaskOperationRecordSerializer(serializers.Serializer):
    node_id = serializers.CharField(required=False)


class TaskOperationRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskOperationRecord
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["operate_type_name"] = TaskOperationType[instance.operate_type].value if instance.operate_type else ""
        data["operate_source_name"] = (
            TaskOperationSource[instance.operate_source].value if instance.operate_source else ""
        )
        return data


class NodeSnapshotQuerySerializer(serializers.Serializer):
    node_id = serializers.CharField(help_text="节点ID", required=True)


class NodeSnapshotResponseSerializer(serializers.Serializer):
    component = serializers.DictField(help_text="组件快照信息")


class EngineSpaceConfigSerializer(serializers.Serializer):
    interface_config_id = serializers.IntegerField(required=False)
    name = serializers.CharField(required=True, max_length=255)
    desc = serializers.CharField(allow_blank=True, required=False)
    is_public = serializers.BooleanField(default=True)
    value_type = serializers.ChoiceField(
        choices=[(choice.value, choice.label) for choice in EngineSpaceConfigValueType], required=True
    )
    is_mix_type = serializers.BooleanField(default=False)
    text_value = serializers.CharField(max_length=128, default="")
    json_value = serializers.JSONField(default=dict)
    space_id = serializers.IntegerField(required=True)


class GetEngineSpaceConfigSerializer(serializers.Serializer):
    interface_config_ids = serializers.ListField(required=True, child=serializers.IntegerField())
    simplified = serializers.BooleanField(required=False, default=False)


class PeriodicTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = PeriodicTask
        fields = "__all__"


class PeriodicTaskConfigSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(required=False)
    constants = serializers.JSONField(help_text="流程变量", required=False, allow_null=True)
    pipeline_tree = serializers.JSONField(help_text="流程树", required=False, allow_null=True)
    scope_type = serializers.CharField(help_text="流程所属作用域类型", required=False, allow_null=True)
    scope_value = serializers.CharField(help_text="流程所属作用域值", required=False, allow_null=True)


class CreatePeriodicTaskSerializer(serializers.Serializer):
    trigger_id = serializers.IntegerField(help_text="触发器ID", required=True)
    template_id = serializers.IntegerField(help_text="模板ID", required=True)
    name = serializers.CharField(max_length=100, help_text="名称", required=True)
    cron = serializers.JSONField(help_text="cron表达式", required=True)
    creator = serializers.CharField(max_length=100, help_text="创建人", required=True)
    config = PeriodicTaskConfigSerializer(help_text="流程相关信息", required=True)
    extra_info = serializers.JSONField(help_text="额外信息", required=False)

    def validate_trigger_id(self, value):
        if PeriodicTask.objects.filter(trigger_id=value).exists():
            raise serializers.ValidationError(f"periodic_task with trigger_id {value} already exists")
        return value


class UpdatePeriodicTaskSerializer(serializers.Serializer):
    trigger_id = serializers.IntegerField(help_text="触发器ID", required=True)
    name = serializers.CharField(max_length=100, help_text="名称", required=False)
    cron = serializers.JSONField(help_text="cron表达式", required=False)
    config = PeriodicTaskConfigSerializer(help_text="流程相关信息", required=False)
    extra_info = serializers.JSONField(help_text="额外信息", required=False)
    is_enabled = serializers.BooleanField(help_text="任务开启状态", default=True)

    def update(self, instance, validated_data):
        for field_name, field_value in validated_data.items():
            if field_name == "cron":
                instance.modify_cron(field_value)
            elif field_name == "config":
                old_config = instance.config
                for key, value in field_value.items():
                    if key not in old_config:
                        raise serializers.ValidationError(f"Invalid config key: {key}")
                    old_config[key] = value
                validated_data["config"] = old_config
            elif field_name == "is_enabled":
                instance.set_enabled(field_value)
                validated_data.pop(field_name)
                continue
            setattr(instance, field_name, field_value)
        instance.save()
        return instance

    def validate_cron(self, cron_data):
        required_fields = ["minute", "hour", "day_of_month", "month_of_year", "day_of_week"]
        if not all(field in cron_data for field in required_fields):
            raise serializers.ValidationError("Cron expression is missing required fields")
        return cron_data


class BatchDeletePeriodicTaskSerializer(serializers.Serializer):
    trigger_ids = serializers.ListField(child=serializers.IntegerField(), help_text="触发器ID列表", required=True)
