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
import json
import logging

from apigw_manager.apigw.decorators import apigw_require
from apigw_manager.apigw.utils import get_configuration
from apigw_manager.core.permission import Manager as PermissionManager
from blueapps.account.decorators import login_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.apigw import ApigwPermissionGrantSerializer
from bkflow.utils import err_code

logger = logging.getLogger("root")


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
def grant_apigw_permissions_to_app(request):
    """限制接口：用于平台级应用给其他应用进行授权"""
    data = json.loads(request.body)

    ser = ApigwPermissionGrantSerializer(data=data)
    ser.is_valid(raise_exception=True)

    configuration = get_configuration()
    manager = PermissionManager(configuration)
    for app_code in ser.validated_data["apps"]:
        params = {
            "target_app_code": app_code,
            "grant_dimension": "resource",
            "resource_names": ser.validated_data["permissions"],
        }
        manager.grant_permission(**params)
        logger.info(
            f"Granted API gateway {manager.config.api_name} for app code {app_code} "
            f"with resources {ser.validated_data['permissions']}"
        )

    return {"result": True, "data": "permission granted", "message": "", "code": err_code.SUCCESS.code}
