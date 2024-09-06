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
import keyword

from django.conf import settings
from pipeline.variable_framework.models import VariableModel
from rest_framework.decorators import action
from rest_framework.response import Response

from bkflow.constants import formatted_key_pattern
from bkflow.exceptions import ValidationError
from bkflow.template.context import get_constant_values
from bkflow.template.serializers.variable import VariableSerializer
from bkflow.utils.context import TaskContext
from bkflow.utils.views import ReadOnlyViewSet


class VariableViewSet(ReadOnlyViewSet):
    serializer_class = VariableSerializer
    queryset = VariableModel.objects.filter(status=True)
    lookup_field = "code"

    @action(methods=["GET"], detail=False)
    def check_variable_key(self, request, *args, **kwargs):
        """
        检验变量key值是否合法

        param: key: 变量key, string, query, required

        return: 根据result字段判断是否合法
        {
            "result": "是否合法(boolean)",
            "data": "占位字段(None)",
            "message": "错误时提示(string)"
        }
        """
        variable_key = request.GET.get("key")
        # 处理格式为${xxx}的情况
        if formatted_key_pattern.match(variable_key):
            variable_key = variable_key[2:-1]
        if not variable_key or keyword.iskeyword(variable_key) or variable_key in settings.VARIABLE_KEY_BLACKLIST:
            raise ValidationError("{} is not allow to be the key of variable".format(variable_key))

        return Response()

    @action(methods=["POST"], detail=False)
    def get_constant_preview_result(self, request, *args, **kwargs):
        constants = request.data.get("constants", {})
        extra_data = request.data.get("extra_data", {})
        preview_results = get_constant_values(constants, extra_data)
        return Response(preview_results)

    @action(methods=["GET"], detail=False)
    def system_variable(self, request, *args, **kwargs):
        return Response(TaskContext.flat_details())
