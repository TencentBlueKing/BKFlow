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
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import return_json_response
from bkflow.utils import err_code
from bkflow.variable_manager.models import VariableManager


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@return_json_response
def delete_variable(request, space_id, variable_id):
    try:
        try:
            variable = VariableManager.objects.get(id=variable_id, space_id=space_id)
        except VariableManager.DoesNotExist:
            return {"result": False, "code": err_code.VALIDATION_ERROR.code, "message": "变量不存在"}

        variable.delete()
        return {"result": True, "code": err_code.SUCCESS.code, "message": "变量删除成功"}

    except Exception as e:
        return {"result": False, "code": err_code.ERROR.code, "message": f"删除变量失败: {str(e)}"}
