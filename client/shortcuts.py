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

from django.conf import settings

from .client import RequestAPIClient
from .config import APP_CODE, SECRET_KEY
from .exceptions import APIException

logger = logging.getLogger(__name__)

__all__ = [
    "get_client_by_request",
    "get_client_by_user",
]


HEADER_BK_AUTHORIZATION = "X-Bkapi-Authorization"
DEFAULT_STAGE = settings.BK_APIGW_STAGE_NAME


def get_client_by_request(request, stage=DEFAULT_STAGE, common_args=None, headers=None):
    """
    根据当前请求返回一个client
    :param request: 一个django request实例
    :param stage: 请求环境，默认为prod
    :param common_args: 公共请求参数
    :param headers: 头部信息
    :returns: 一个初始化好的APIClint对象
    """
    headers = headers or {}

    is_authenticated = request.user.is_authenticated
    if callable(is_authenticated):
        is_authenticated = is_authenticated()
    if is_authenticated:
        try:
            from bkoauth import get_access_token

            access_token = get_access_token(request)
            headers.update(
                {
                    HEADER_BK_AUTHORIZATION: json.dumps({"access_token": access_token.access_token}),
                }
            )
        except Exception:
            pass
    else:
        raise APIException("用户未通过验证")

    return RequestAPIClient(
        app_code=APP_CODE, app_secret=SECRET_KEY, headers=headers, common_args=common_args, stage=stage
    )


def get_client_by_user(user, stage=DEFAULT_STAGE, common_args=None, headers=None):
    """
    根据user实例返回一个client
    :param user: 用户
    :param stage: 请求环境，默认为prod
    :param common_args: 公共请求参数
    :param common_args: 公共请求参数
    :param headers: 头部信息
    :returns: 一个初始化好的APIClint对象
    """
    headers = headers or {}
    common_args = common_args or {}
    if hasattr(user, "username"):
        user = user.username
    try:
        from bkoauth import get_access_token_by_user

        access_token = get_access_token_by_user(user)
        headers.update(
            {
                HEADER_BK_AUTHORIZATION: json.dumps({"access_token": access_token.access_token}),
            }
        )
    except Exception as e:
        logger.warn("get_access_token_by_user error %s, using header authorization", str(e))
        headers.update(
            {
                HEADER_BK_AUTHORIZATION: json.dumps(
                    {"bk_username": user, "bk_app_code": APP_CODE, "bk_app_secret": SECRET_KEY}
                )
            }
        )

    return RequestAPIClient(
        app_code=APP_CODE, app_secret=SECRET_KEY, headers=headers, common_args=common_args, stage=stage
    )
