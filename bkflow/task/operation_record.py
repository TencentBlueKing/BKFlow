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
import abc
import logging

from bkflow.contrib.operation_record.interface import OperationRecorderInterface
from bkflow.exceptions import ValidationError
from bkflow.task.models import TaskOperationRecord
from bkflow.task.operations import TaskOperation
from bkflow.task.views import TaskInstanceViewSet

logger = logging.getLogger("root")


class TaskCommonOperationRecorder(OperationRecorderInterface):
    def __init__(self, operate_type: str, operate_source: str, *args, **kwargs):
        self.operate_type = operate_type
        self.operate_source = operate_source

    def record(self, *args, **kwargs):
        try:
            data = self.get_data(*args, **kwargs)
        except Exception as e:
            logger.exception(f"record operate failed, error:{e}")
        else:
            TaskOperationRecord.objects.create(**data)

    @abc.abstractmethod
    def get_data(self, *args, **kwargs):
        pass


class TaskOperationRecorder(TaskCommonOperationRecorder):
    def get_data(self, *args, **kwargs):
        if isinstance(args[0], TaskOperation):
            # 通过装饰器从TaskOperation中的操作函数中获取数据
            task_operation = args[0]
            operator = kwargs.get("operator")
            return {
                "operate_type": self.operate_type,
                "operate_source": self.operate_source,
                "instance_id": task_operation.task_instance.id,
                "operator": operator,
            }
        elif isinstance(args[0], TaskInstanceViewSet):
            # 通过装饰器从TaskInstanceViewSet中的操作函数中获取数据
            request, response = args[1], kwargs["func_result"]
            instance_id = response.data.get("id", -1)
            operator = response.data.get("creator", "")
            return {
                "operate_type": self.operate_type,
                "operate_source": self.operate_source,
                "instance_id": instance_id,
                "operator": operator or request.user.username,
            }
        else:
            raise ValidationError(f"can not get data from this type of decorated function: {args}, {kwargs}")


class TaskNodeOperationRecorder(TaskCommonOperationRecorder):
    def get_data(self, *args, **kwargs):
        """通过装饰器从TaskNodeOperation中的操作函数中获取数据"""
        task_node_operation = args[0]
        operator = kwargs.get("operator")
        return {
            "operate_type": self.operate_type,
            "operate_source": self.operate_source,
            "instance_id": task_node_operation.task_instance.id,
            "operator": operator,
            "node_id": task_node_operation.node_id,
        }
