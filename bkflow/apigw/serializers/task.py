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
from django.utils.translation import ugettext_lazy as _
from pipeline.exceptions import PipelineException
from rest_framework import serializers

from bkflow.constants import MAX_LEN_OF_TASK_NAME, USER_NAME_MAX_LENGTH
from bkflow.pipeline_web.parser.validator import validate_web_pipeline_tree
from bkflow.template.models import TemplateMockData
from bkflow.utils.strings import standardize_pipeline_node_name


class CreateTaskSerializer(serializers.Serializer):
    template_id = serializers.IntegerField(help_text=_("模版ID"))
    name = serializers.CharField(help_text=_("任务名"), max_length=MAX_LEN_OF_TASK_NAME, required=False)
    creator = serializers.CharField(help_text=_("创建者"), max_length=USER_NAME_MAX_LENGTH, required=True)
    description = serializers.CharField(help_text=_("任务描述"), required=False)
    constants = serializers.JSONField(help_text=_("任务启动参数"), required=False, default={})


class TaskMockDataSerializer(serializers.Serializer):
    nodes = serializers.ListSerializer(help_text=_("要 Mock 执行的节点 ID 列表"), child=serializers.CharField(), default=[])
    outputs = serializers.JSONField(help_text=_('节点 Mock 输出, 形如{"node_id": {"output1": "output_value1"}}'), default={})
    mock_data_ids = serializers.JSONField(
        help_text=_("节点 Mock 数据，当 outputs 为空时会提取对应 mock_data_ids 设置 outputs，否则仅记录作用"), default={}
    )


class CreateMockTaskBaseSerializer(serializers.Serializer):
    name = serializers.CharField(help_text=_("任务名"), max_length=MAX_LEN_OF_TASK_NAME, required=True)
    creator = serializers.CharField(help_text=_("创建者"), max_length=USER_NAME_MAX_LENGTH, required=True)
    mock_data = TaskMockDataSerializer(help_text=_("Mock 数据"), default=TaskMockDataSerializer())
    description = serializers.CharField(help_text=_("任务描述"), required=False)
    constants = serializers.JSONField(help_text=_("任务启动参数"), default={})


class CreateMockTaskWithPipelineTreeSerializer(CreateMockTaskBaseSerializer):
    pipeline_tree = serializers.JSONField(help_text=_("任务树"), required=True)
    include_node_ids = serializers.ListField(
        child=serializers.CharField(allow_blank=False), help_text=_("包含的节点ID列表"), required=False
    )


class CreateMockTaskWithTemplateIdSerializer(CreateMockTaskBaseSerializer):
    template_id = serializers.IntegerField(help_text=_("模版ID"))

    def validate(self, attrs):
        if attrs["mock_data"]["mock_data_ids"] and not attrs["mock_data"]["outputs"]:
            mock_data = TemplateMockData.objects.filter(
                template_id=attrs["template_id"], id__in=list(attrs["mock_data"]["mock_data_ids"].values())
            ).values("id", "data")
            mock_data = {item["id"]: item["data"] for item in mock_data}
            outputs = {}
            for node_id, mock_data_id in attrs["mock_data"]["mock_data_ids"].items():
                if node_id not in attrs["mock_data"].get("nodes"):
                    continue
                if mock_data_id not in mock_data:
                    raise serializers.ValidationError(
                        f"mock data of node {node_id} with mock_data_id {mock_data_id} not found"
                    )
                outputs[node_id] = mock_data[mock_data_id]
            attrs["mock_data"]["outputs"] = outputs
        return attrs


class CreateTaskWithoutTemplateSerializer(serializers.Serializer):
    name = serializers.CharField(help_text=_("任务名"), max_length=MAX_LEN_OF_TASK_NAME, required=False)
    creator = serializers.CharField(help_text=_("创建者"), max_length=USER_NAME_MAX_LENGTH, required=True)
    scope_type = serializers.CharField(help_text=_("任务范围类型"), max_length=128, required=False)
    scope_value = serializers.CharField(help_text=_("任务范围值"), max_length=128, required=False)
    description = serializers.CharField(help_text=_("任务描述"), required=False)
    constants = serializers.JSONField(help_text=_("任务启动参数"), required=False, default={})
    pipeline_tree = serializers.JSONField(help_text=_("任务树"), required=True)
    notify_config = serializers.JSONField(help_text=_("通知配置"), required=False, default={})


class PipelineTreeSerializer(serializers.Serializer):
    pipeline_tree = serializers.JSONField(help_text=_("任务树"), required=True)

    def validate_pipeline_tree(self, pipeline_tree):
        try:
            standardize_pipeline_node_name(pipeline_tree)
            validate_web_pipeline_tree(pipeline_tree)
        except PipelineException as e:
            raise serializers.ValidationError(str(e))


class GetTaskListSerializer(serializers.Serializer):
    scope_type = serializers.CharField(help_text=_("流程范围类型"), max_length=128, required=False)
    scope_value = serializers.CharField(help_text=_("流程范围值"), max_length=128, required=False)
    offset = serializers.IntegerField(help_text=_("偏移量"), required=False, default=0)
    limit = serializers.IntegerField(help_text=_("返回数量"), required=False, default=100)
    create_at_start = serializers.DateTimeField(help_text=_("创建时间开始"), required=False)
    create_at_end = serializers.DateTimeField(help_text=_("创建时间结束"), required=False)
    creator = serializers.CharField(help_text=_("创建者"), max_length=USER_NAME_MAX_LENGTH, required=False)
    name = serializers.CharField(help_text=_("任务名"), max_length=MAX_LEN_OF_TASK_NAME, required=False)
    id = serializers.IntegerField(help_text=_("任务ID"), required=False)
    executor = serializers.CharField(help_text=_("执行者"), max_length=USER_NAME_MAX_LENGTH, required=False)
    template_id = serializers.IntegerField(help_text=_("流程ID"), required=False)


class GetTasksStatesSerializer(serializers.Serializer):
    task_ids = serializers.ListField(required=True, child=serializers.IntegerField())


class OperateTaskSerializer(serializers.Serializer):
    operator = serializers.CharField(help_text=_("操作人"), max_length=USER_NAME_MAX_LENGTH, required=True)


class OperateTaskNodeSerializer(serializers.Serializer):
    operator = serializers.CharField(help_text=_("操作人"), max_length=USER_NAME_MAX_LENGTH, required=True)


class GetTaskNodeDetailSerializer(serializers.Serializer):
    loop = serializers.IntegerField(help_text=_("循环次数"), required=False)
    component_code = serializers.CharField(help_text=_("组件code"), max_length=128, required=False)
