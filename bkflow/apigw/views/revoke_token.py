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
from blueapps.account.decorators import login_exempt
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.token import ApiGwTokenRevokeSerializer
from bkflow.permission.models import Token
from bkflow.utils import err_code

logger = logging.getLogger("root")


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
def revoke_token(request, space_id):
    """
    data : {
        "space_id": 1,
        "user": "xxx",
        "resource_type": "TEMPLATE",
        "resource_id": 1,
        "permission_type": "VIEW"
    }
    """
    data = json.loads(request.body)

    ser = ApiGwTokenRevokeSerializer(data=data)
    ser.is_valid(raise_exception=True)

    filter_kwargs = ser.validated_data

    now_time = timezone.now()
    revoke_num = Token.objects.filter(space_id=space_id).filter(**filter_kwargs).update(expired_time=now_time)

    logger.info(f"[revoke tokens] params: {filter_kwargs}, expired_time: {now_time}, revoke numbers: {revoke_num}")

    return {"result": True, "data": f"{revoke_num} tokens revoke success", "message": "", "code": err_code.SUCCESS.code}
