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
import functools
import logging

from . import env
from .conf import PLUGIN_CLIENT_LOGGER
from .utils import handle_plain_message

logger = logging.getLogger(PLUGIN_CLIENT_LOGGER)


def data_parser(func):
    """用于解析插件服务应用标准格式接口返回数据"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            message = f"plugin client request {func.__name__} error: {e}, with params: {args} and kwargs: {kwargs}."
            return False, {"message": message}
        if not result.get("result"):
            logger.error(f"{func.__name__} request error: {result.get('message')}")
            data = {"message": result.get("message")}
            if "trace_id" in result:
                data["trace_id"] = result["trace_id"]
            return False, data
        else:
            data = result.get("data")
            if "trace_id" in result and isinstance(data, dict):
                data["trace_id"] = result["trace_id"]
            return True, data

    return wrapper


def json_response_decoder(func):
    """用于处理json格式接口返回"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            response = func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"{func.__name__} request error: {e}")
            return {"result": False, "message": str(e), "data": None}
        if response.status_code != 200:
            inject_authorization = kwargs.get("inject_authorization") or {}
            for auth_item in inject_authorization:
                inject_authorization[auth_item] = "******"

            message = handle_plain_message(
                f"{func.__name__} gets error status code [{response.status_code}], "
                f"request with params: {args} and kwargs: {kwargs}. "
            )
            logger.error(message + f"response content: {response.content}")
            return {"result": False, "data": None, "message": message}
        return response.json()

    return wrapper


def check_use_plugin_service(func):
    """检查是否启用插件服务"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not env.USE_PLUGIN_SERVICE == "1":
            return {"result": False, "message": "插件服务未启用，请联系管理员进行配置", "data": None}
        return func(*args, **kwargs)

    return wrapper
