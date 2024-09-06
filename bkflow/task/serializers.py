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
import copy
import logging

import jsonschema
from pipeline.exceptions import PipelineException
from rest_framework import serializers

from bkflow.constants import TaskOperationSource, TaskOperationType
from bkflow.pipeline_web.parser.validator import validate_web_pipeline_tree
from bkflow.task.models import TaskInstance, TaskOperationRecord
from bkflow.task.operations import TaskNodeOperation
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


class GetTaskOperationRecordSerializer(serializers.Serializer):
    node_id = serializers.CharField(required=False)


class TaskOperationRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskOperationRecord
        fields = "__all__"

    def to_representation(self, instance):
        data = super(TaskOperationRecordSerializer, self).to_representation(instance)
        data["operate_type_name"] = TaskOperationType[instance.operate_type].value if instance.operate_type else ""
        data["operate_source_name"] = (
            TaskOperationSource[instance.operate_source].value if instance.operate_source else ""
        )
        return data


class NodeSnapshotQuerySerializer(serializers.Serializer):
    node_id = serializers.CharField(help_text="节点ID", required=True)


class NodeSnapshotResponseSerializer(serializers.Serializer):
    component = serializers.DictField(help_text="组件快照信息")
