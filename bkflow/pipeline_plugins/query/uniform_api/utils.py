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
from functools import wraps

from django.conf import settings

from bkflow.exceptions import APIRequestError, ValidationError
from bkflow.utils.api_client import (
    ApigwClientMixin,
    HttpRequestMixin,
    HttpRequestResult,
)

logger = logging.getLogger("root")


def check_resource_token(func: callable) -> callable:
    """检查资源 token.

    :param func: 被装饰的函数
    :return: 装饰后的函数
    """

    @wraps(func)
    def wrapper(request, *args, **kwargs):
        from bkflow.permission.models import Token
        from bkflow.space.configs import SuperusersConfig
        from bkflow.space.models import SpaceConfig

        space_id = kwargs.get("space_id")
        space_superusers = SpaceConfig.get_config(space_id, SuperusersConfig.name)
        is_space_superuser = request.user.username in space_superusers

        if request.user.is_superuser or is_space_superuser:
            return func(request, *args, **kwargs)
        # 获取并解析 token 适用于通过 token 操作模版的情况(非系统 or 空间管理员)
        if not request.token:
            raise ValidationError("不存在访问 token")

        token = Token.objects.get_resource_tokens(request.token, request.query_params)
        if not token.exists():
            if settings.ENABLE_DEBUG_LOG:
                logger.error(f"token 不存在或有误: {request.token}")
            raise ValidationError("token 不存在或有误")
        return func(request, *args, **kwargs)

    return wrapper


class UniformAPIClient(ApigwClientMixin, HttpRequestMixin):

    SUPPORT_METHODS = {"GET", "POST"}
    TIMEOUT = 30

    UNIFORM_API_CATEGORY_LIST_RESPONSE_DATA_SCHEMA = {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["id", "name"],
        },
    }

    UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA = {
        "type": "object",
        "required": ["total", "apis"],
        "properties": {
            "total": {"type": "integer"},
            "apis": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "meta_url", "name"],
                    "properties": {
                        "id": {"type": "string"},
                        "meta_url": {"type": "string"},
                        "name": {"type": "string"},
                    },
                },
            },
        },
    }

    UNIFORM_API_META_RESPONSE_DATA_SCHEMA = {
        "type": "object",
        "required": ["id", "name", "url", "methods", "inputs"],
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "desc": {"type": "string"},
            "url": {"type": "string"},
            "methods": {
                "type": "array",
                "items": {"type": "string", "enum": ["GET", "POST"]},
                "minItems": 1,
            },
            "inputs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "key"],
                    "properties": {
                        "name": {"type": "string"},
                        "key": {"type": "string"},
                        "required": {"type": "boolean"},
                        "type": {"type": "string"},
                        "desc": {"type": "string"},
                        "options": {"type": "array"},
                        "form_type": {"type": "string"},
                    },
                },
            },
        },
    }

    def __init__(self, from_apigw_check=True, *args, **kwargs):
        self.from_apigw_check = from_apigw_check
        super().__init__(*args, **kwargs)

    def request(self, url: str, method: str, data=None, headers=None, *args, **kwargs) -> HttpRequestResult:
        """
        请求统一API，可能抛出APIRequestError
        """
        method = method.upper()
        if method not in self.SUPPORT_METHODS:
            raise APIRequestError(f"method not supported: {method}，supported methods: {self.SUPPORT_METHODS}")

        if self.from_apigw_check and self.check_url_from_apigw(url) is False:
            raise APIRequestError(f"check url from apigw fail: {url}")

        if headers is None:
            headers = self.gen_default_apigw_header(
                app_code=settings.BK_APP_CODE, app_secret=settings.BK_APP_SECRET, username=kwargs.get("username")
            )

        timeout = kwargs.pop("timeout", self.TIMEOUT)
        return self.http_request(
            url=url,
            method=method,
            data=data,
            headers=headers,
            timeout=timeout,
            *args,
            **kwargs,
        )
