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

from bkflow.contrib.operation_record.interface import OperationRecorderInterface
from bkflow.exceptions import ValidationError
from bkflow.template.models import TemplateOperationRecord
from bkflow.template.views.template import TemplateViewSet

logger = logging.getLogger("root")


class TemplateOperationRecorder(OperationRecorderInterface):
    def __init__(self, operate_type: str, operate_source: str, extra_info: dict = None, *args, **kwargs):
        self.operate_type = operate_type
        self.operate_source = operate_source
        self.tag = extra_info.get("tag") if extra_info else None

    def record(self, *args, **kwargs):
        try:
            if isinstance(args[0], TemplateViewSet):
                # 修饰的是ViewSet的方法
                request, pk = args[1], kwargs.get("pk")
                data = self.get_data_from_request(request, pk)
            elif self.tag == "apigw":
                # 修饰的是apigw的方法
                request, func_result = args[0], kwargs["func_result"]
                data = self.get_data_from_apigw(request, func_result)
            else:
                raise ValidationError(f"can not get data from this type of decorated function: {args}, {kwargs}")
        except Exception as e:
            logger.exception(f"record operate failed, error:{e}")
        else:
            TemplateOperationRecord.objects.create(**data)

    def get_data_from_request(self, request, pk):
        return {
            "operate_type": self.operate_type,
            "operate_source": self.operate_source,
            "instance_id": pk,
            "operator": request.user.username,
        }

    def get_data_from_apigw(self, request, func_result):
        return {
            "operate_type": self.operate_type,
            "operate_source": self.operate_source,
            "instance_id": func_result["data"]["id"] if func_result["result"] else -1,
            "operator": request.user.username,
        }
