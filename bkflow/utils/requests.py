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

from django.utils.translation import ugettext_lazy as _
from iam.contrib.http import HTTP_AUTH_FORBIDDEN_CODE
from iam.exceptions import RawAuthFailedException

from bkflow.exceptions import APIRequestError
from bkflow.utils.handlers import handle_api_error

from .thread import ThreadPool

logger = logging.getLogger("root")
logger_celery = logging.getLogger("celery")


def check_and_raise_raw_auth_fail_exception(result: dict, message=None):
    if result.get("code", 0) == HTTP_AUTH_FORBIDDEN_CODE:
        logger.warning(message or result.get("message", "[check_and_raise_raw_auth_fail_exception]"))
        raise RawAuthFailedException(permissions=result.get("permission", {}))


def local_wrapper(target_func, request_params, node_id=None, node_info=None):
    from bamboo_engine import local as bamboo_local
    from pipeline.engine.core import context as pipeline_context

    if node_info:
        bamboo_local.set_node_info(node_info)

    if node_id:
        pipeline_context.set_node_id(node_id)

    return target_func(**request_params)


def batch_request(
    func,
    params,
    get_data=lambda x: x["data"]["info"],
    get_count=lambda x: x["data"]["count"],
    limit=500,
    page_param=None,
    is_page_merge=False,
    check_iam_auth_fail=False,
):
    """
    并发请求接口
    :param page_param: 分页参数，默认使用start/limit分页，例如：{"cur_page_param":"start", "page_size_param":"limit"}
    :param is_page_merge: 分页参数是否合并到请求体，默认False，例如：
        is_page_merge=True, {"x": "y", "cur_page_param":"start", "page_size_param":"limit"};
        is_page_merge=False, {"x": "y", page: {"cur_page_param":"start", "page_size_param":"limit"}}
    :param func: 请求方法
    :param params: 请求参数
    :param get_data: 获取数据函数
    :param get_count: 获取总数函数
    :param limit: 一次请求数量
    :param check_iam_auth_fail: 是否检查iam授权失败
    :return: 请求结果
    """
    # 兼容其他分页参数类型
    if page_param:
        try:
            cur_page_param = page_param["cur_page_param"]
            page_size_param = page_param["page_size_param"]
        except Exception as e:
            message = _(f"批量请求接口分页参数错误: {e} | batch_request")
            logger.error(message)
            raise APIRequestError(message)
    else:
        cur_page_param = "start"
        page_size_param = "limit"

    # 请求第一次获取总数
    if is_page_merge:
        result = func(**{cur_page_param: 0, page_size_param: 1}, **params)
    else:
        result = func(page={cur_page_param: 0, page_size_param: 1}, **params)

    if not result["result"]:
        message = handle_api_error("[batch_request]", func.path, params, result)
        logger.error(message)
        if check_iam_auth_fail:
            check_and_raise_raw_auth_fail_exception(result, message)
        raise APIRequestError(message)

    count = get_count(result)
    data = []
    start = 0

    # 根据请求总数并发请求
    pool = ThreadPool()
    params_and_future_list = []
    from bamboo_engine import local as bamboo_local
    from pipeline.engine.core import context as pipeline_context

    node_info = bamboo_local.get_node_info()
    node_id = pipeline_context.get_node_id()
    while start < count:
        if is_page_merge:
            request_params = {page_size_param: limit, cur_page_param: start}
        else:
            request_params = {"page": {page_size_param: limit, cur_page_param: start}}
        request_params.update(params)
        kwds = {"target_func": func, "node_id": node_id, "node_info": node_info, "request_params": request_params}
        params_and_future_list.append(
            {"params": request_params, "future": pool.apply_async(func=local_wrapper, kwds=kwds)}
        )

        start += limit

    pool.close()
    pool.join()

    # 取值
    for params_and_future in params_and_future_list:
        result = params_and_future["future"].get()

        if not result:
            message = handle_api_error("[batch_request]", func.path, params_and_future["params"], result)
            logger.error(message)
            if check_iam_auth_fail:
                check_and_raise_raw_auth_fail_exception(result, message)
            raise APIRequestError(message)

        try:
            data.extend(get_data(result))
        except Exception as e:
            message = handle_api_error("[batch_request get_data]", func.path, params_and_future["params"], result)
            logger.exception(f"{e}: {message}")
            raise APIRequestError(message)

    return data
