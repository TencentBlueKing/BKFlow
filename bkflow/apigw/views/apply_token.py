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
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.exceptions import CreateTokenException
from bkflow.apigw.serializers.token import ApiGwTokenSerializer
from bkflow.permission.services.token_issuer import (
    TokenIssueContext,
    TokenResource,
    issue_resource_token,
)
from bkflow.utils import err_code


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
def apply_token(request, space_id):
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

    ser = ApiGwTokenSerializer(data=data)
    ser.is_valid(raise_exception=True)

    if not request.user.username:
        raise CreateTokenException(_("用户名不能为空"))

    try:
        issued = issue_resource_token(
            TokenIssueContext(
                platform_app=request.app.bk_app_code,
                actor=request.user.username,
                space_id=int(space_id),
            ),
            TokenResource(
                resource_type=ser.validated_data["resource_type"],
                resource_id=ser.validated_data["resource_id"],
            ),
            ser.validated_data["permission_type"],
        )
    except ValidationError:
        raise CreateTokenException()

    # This legacy API intentionally preserves its plaintext response contract.
    # Harness callers use TokenBroker and never receive this projection.
    return {
        "result": True,
        "data": {
            "space_id": int(issued.space_id),
            "user": issued.actor,
            "resource_type": issued.resource_type,
            "resource_id": issued.resource_id,
            "token": issued.secret,
            "expired_time": issued.expires_at,
        },
        "code": err_code.SUCCESS.code,
    }
