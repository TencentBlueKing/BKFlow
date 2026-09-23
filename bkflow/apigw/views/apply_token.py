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
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from pytimeparse import parse

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.exceptions import CreateTokenException
from bkflow.apigw.serializers.token import (
    ApiGwTokenSerializer,
    CompositeTokenSerializer,
    TokenResourceValidator,
)
from bkflow.permission.grants import Grant
from bkflow.permission.services import issue_token
from bkflow.space.configs import TokenAutoRenewalConfig, TokenExpirationConfig
from bkflow.space.models import SpaceConfig
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

    legacy_keys = {"resource_type", "resource_id", "permission_type"}
    is_composite_request = isinstance(data, dict) and not (legacy_keys & data.keys()) and "grants" in data
    if is_composite_request:
        if not settings.TOKEN_COMPOSITE_ENABLED:
            raise CreateTokenException(_("组合 Token 申请功能未启用"))
        ser = CompositeTokenSerializer(data=data, context={"space_id": space_id})
    else:
        ser = ApiGwTokenSerializer(data=data)
    ser.is_valid(raise_exception=True)

    # 获取空间下的过期时间配置
    expiration = SpaceConfig.get_config(space_id, config_name=TokenExpirationConfig.name)

    if not request.user.username:
        raise CreateTokenException(_("用户名不能为空"))

    try:
        expiration_seconds = parse(expiration)
        if expiration_seconds is None:
            raise ValueError("Invalid token expiration")
    except Exception:
        raise CreateTokenException()

    if is_composite_request:
        grants = ser.validated_data["grants"]
    else:
        TokenResourceValidator(space_id, ser.data["resource_type"], ser.data["resource_id"]).validate()
        grants = [Grant(**ser.validated_data)]

    token = issue_token(
        space_id,
        request.user.username,
        grants,
        expiration_seconds,
        SpaceConfig.get_config(space_id, TokenAutoRenewalConfig.name) == "true",
    )
    if is_composite_request:
        response_data = {
            "space_id": int(token.space_id),
            "user": token.user,
            "token": token.token,
            "expired_time": token.expired_time,
            "grants": [grant.as_dict() for grant in token.get_grants()],
        }
    else:
        response_data = token.to_json()
    return {"result": True, "data": response_data, "code": err_code.SUCCESS.code}
