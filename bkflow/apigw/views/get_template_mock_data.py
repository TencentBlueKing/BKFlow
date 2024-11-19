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
from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.template.models import TemplateMockData
from bkflow.template.serializers.template import TemplateMockDataSerializer
from bkflow.utils import err_code


@login_exempt
@csrf_exempt
@require_GET
@apigw_require
@check_jwt_and_space
@return_json_response
def get_template_mock_data(request, space_id, template_id):
    mock_data_qs = TemplateMockData.objects.filter(space_id=space_id, template_id=template_id)
    if "node_id" in request.GET:
        mock_data_qs = mock_data_qs.filter(node_id=request.GET.get("node_id"))
    response_ser = TemplateMockDataSerializer(mock_data_qs, many=True)
    response = {
        "result": True,
        "data": response_ser.data,
        "code": err_code.SUCCESS.code,
        "message": "",
    }
    return response
