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

import logging

import pytz
from django.conf import settings
from django.core.cache import cache

from bkflow.utils.platform import use_apigw
from packages.bkapi.bk_login.shortcuts import get_client_by_request

logger = logging.getLogger("root")
NOT_FOUND = object()


def _valid_timezone(value):
    """忽略非法用户偏好，避免中间件因无效时区而中断请求。"""
    if not isinstance(value, str) or not value:
        return None
    try:
        pytz.timezone(value)
    except pytz.exceptions.UnknownTimeZoneError:
        return None
    return value


def get_user_timezone(request, use_cache=True):
    """单/多租户统一解析显式时区、用户偏好和登录平台设置。"""
    cookies = getattr(request, "COOKIES", {})
    for value in (
        request.headers.get(settings.APP_INTERNAL_TIME_ZONE_HEADER_KEY),
        request.headers.get("blueking-timezone"),
        cookies.get("blueking_timezone"),
        getattr(request, "session", {}).get("blueking_timezone"),
    ):
        time_zone = _valid_timezone(value)
        if time_zone:
            return time_zone
    tenant_id = getattr(request.user, "tenant_id", "") if settings.ENABLE_MULTI_TENANT_MODE else "default"
    if not use_apigw() or not tenant_id:
        return settings.TIME_ZONE
    user_time_zone_cache_key = f"tenant:{tenant_id}:user:{request.user.username}:time_zone"
    if use_cache:
        time_zone_cache = cache.get(user_time_zone_cache_key, default=NOT_FOUND)
        if time_zone_cache is not NOT_FOUND and _valid_timezone(time_zone_cache):
            # use cache
            return time_zone_cache

    time_zone = None
    # get time_zone of user
    try:
        client = get_client_by_request(request)
        user_info = client.api.get_bk_token_userinfo(
            {"bk_token": cookies.get("bk_token")}, headers={"X-Bk-Tenant-Id": tenant_id}
        )

        time_zone = _valid_timezone((user_info.get("data") or {}).get("time_zone"))
    except Exception as e:
        logger.error("get time_zone error: {}".format(e))

    if time_zone:
        cache.set(user_time_zone_cache_key, time_zone, 15 * 60)
    return time_zone or settings.TIME_ZONE
