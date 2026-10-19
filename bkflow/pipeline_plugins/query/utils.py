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
import logging
from functools import wraps

from rest_framework.response import Response

logger = logging.getLogger("root")


class QueryResponseError(Exception):
    """可由 query_response_handler 稳定序列化的业务错误。"""

    def __init__(self, message, error_code):
        super().__init__(message)
        self.error_code = error_code


def query_response_handler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            data = func(*args, **kwargs)
        except QueryResponseError as e:
            logger.exception(f"call query function {func.__name__} error: {e}")
            data = {
                "result": False,
                "message": str(e),
                "data": None,
                "error_code": e.error_code,
            }
            return Response(data)
        except Exception as e:
            logger.exception(f"call query function {func.__name__} error: {e}")
            return Response({"result": False, "message": str(e), "data": None})

        return Response({"result": True, "message": "", "data": data})

    return wrapper
