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
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from bkflow.constants import MAX_LEN_OF_TASK_NAME, USER_NAME_MAX_LENGTH


class CreateTaskSerializer(serializers.Serializer):
    template_id = serializers.IntegerField(help_text=_("模版ID"))
    name = serializers.CharField(help_text=_("任务名"), max_length=MAX_LEN_OF_TASK_NAME, required=False)
    creator = serializers.CharField(help_text=_("创建者"), max_length=USER_NAME_MAX_LENGTH, required=True)
    description = serializers.CharField(help_text=_("任务描述"), required=False)
    constants = serializers.JSONField(help_text=_("任务启动参数"), required=False, default={})


class TaskMockDataSerializer(serializers.Serializer):
    nodes = serializers.ListSerializer(
        help_text=_("要 Mock 执行的节点 ID 列表"), child=serializers.CharField(), default=[]
    )
    outputs = serializers.JSONField(
        help_text=_('节点 Mock 输出, 形如{"node_id": {"output1": "output_value1"}}'), default={}
    )


class CreateMockTaskBaseSerializer(serializers.Serializer):
    name = serializers.CharField(help_text=_("任务名"), max_length=MAX_LEN_OF_TASK_NAME, required=True)
    creator = serializers.CharField(help_text=_("创建者"), max_length=USER_NAME_MAX_LENGTH, required=True)
    mock_data = TaskMockDataSerializer(help_text=_("Mock 数据"), default=TaskMockDataSerializer())
    description = serializers.CharField(help_text=_("任务描述"), required=False)
    constants = serializers.JSONField(help_text=_("任务启动参数"), default={})


class CreateMockTaskWithPipelineTreeSerializer(CreateMockTaskBaseSerializer):
    pipeline_tree = serializers.JSONField(help_text=_("任务树"), required=True)


class CreateMockTaskWithTemplateIdSerializer(CreateMockTaskBaseSerializer):
    template_id = serializers.IntegerField(help_text=_("模版ID"))


class CreateTaskWithoutTemplateSerializer(serializers.Serializer):
    name = serializers.CharField(help_text=_("任务名"), max_length=MAX_LEN_OF_TASK_NAME, required=False)
    creator = serializers.CharField(help_text=_("创建者"), max_length=USER_NAME_MAX_LENGTH, required=True)
    scope_type = serializers.CharField(help_text=_("任务范围类型"), max_length=128, required=False)
    scope_value = serializers.CharField(help_text=_("任务范围值"), max_length=128, required=False)
    description = serializers.CharField(help_text=_("任务描述"), required=False)
    constants = serializers.JSONField(help_text=_("任务启动参数"), required=False, default={})
    pipeline_tree = serializers.JSONField(help_text=_("任务树"), required=True)


class GetTaskListSerializer(serializers.Serializer):
    scope_type = serializers.CharField(help_text=_("流程范围类型"), max_length=128, required=False)
    scope_value = serializers.CharField(help_text=_("流程范围值"), max_length=128, required=False)
    offset = serializers.IntegerField(help_text=_("偏移量"), required=False, default=0)
    limit = serializers.IntegerField(help_text=_("返回数量"), required=False, default=100)
    create_at_start = serializers.DateTimeField(help_text=_("创建时间开始"), required=False)
    create_at_end = serializers.DateTimeField(help_text=_("创建时间结束"), required=False)
    creator = serializers.CharField(help_text=_("创建者"), max_length=USER_NAME_MAX_LENGTH, required=False)
    name = serializers.CharField(help_text=_("任务名"), max_length=MAX_LEN_OF_TASK_NAME, required=False)


class OperateTaskSerializer(serializers.Serializer):
    operator = serializers.CharField(help_text=_("操作人"), max_length=USER_NAME_MAX_LENGTH, required=True)


class OperateTaskNodeSerializer(serializers.Serializer):
    operator = serializers.CharField(help_text=_("操作人"), max_length=USER_NAME_MAX_LENGTH, required=True)


class GetTaskNodeDetailSerializer(serializers.Serializer):
    loop = serializers.IntegerField(help_text=_("循环次数"), required=False)
    component_code = serializers.CharField(help_text=_("组件code"), max_length=128, required=False)
