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
import json

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import return_json_response
from bkflow.utils import err_code
from bkflow.variable_manager.models import VariableManager
from bkflow.variable_manager.serializers import VariableManagerSerializer


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@return_json_response
def get_variable_list(request, space_id):
    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            return {"result": False, "code": err_code.VALIDATION_ERROR.code, "message": f"JSON格式错误: {str(e)}"}

        query_params = {"space_id": space_id, "is_deleted": False}

        # 支持按变量名过滤
        if "name" in data and data["name"]:
            query_params["name__icontains"] = data["name"]

        # 支持按变量类型过滤
        if "type" in data and data["type"]:
            query_params["type"] = data["type"]

        # 支持按变量键过滤
        if "key" in data and data["key"]:
            query_params["key__icontains"] = data["key"]

        variables = VariableManager.objects.filter(**query_params)
        serializer = VariableManagerSerializer(variables, many=True, context={"request": request})

        return {"result": True, "code": err_code.SUCCESS.code, "data": serializer.data}
    except Exception as e:
        return {"result": False, "code": err_code.ERROR.code, "message": f"获取变量列表失败: {str(e)}"}
