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
import datetime
import json
import logging

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from pytimeparse import parse

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.exceptions import CreateTokenException
from bkflow.apigw.serializers.token import ApiGwTokenSerializer, TokenResourceValidator
from bkflow.permission.models import Token
from bkflow.space.configs import TokenExpirationConfig
from bkflow.space.models import SpaceConfig
from bkflow.utils import err_code

logger = logging.getLogger("root")


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

    # 获取空间下的过期时间配置
    expiration = SpaceConfig.get_config(space_id, config_name=TokenExpirationConfig.name)

    if not request.user.username:
        raise CreateTokenException(_("用户名不能为空"))

    try:
        # 计算过期时间
        expire_time = timezone.now() + datetime.timedelta(seconds=parse(expiration))
    except Exception:
        raise CreateTokenException()

    TokenResourceValidator(space_id, ser.data["resource_type"], ser.data["resource_id"]).validate()

    # 检查该token是否存在，考虑可能有多个token的情况
    tokens = Token.objects.filter(
        **ser.data, expired_time__gte=timezone.now(), user=request.user.username, space_id=space_id
    ).order_by(
        "-expired_time"
    )  # 按过期时间降序排列，选择最晚过期的token

    if tokens.exists():
        token = tokens.first()
    else:
        logger.error("[apigw>apply_token], the token is not exists, now while create a new token。")
        token = Token.objects.create(
            **ser.data,
            expired_time=expire_time,
            token=Token.generate_token(),
            user=request.user.username,
            space_id=space_id
        )

    return {"result": True, "data": token.to_json(), "code": err_code.SUCCESS.code}
