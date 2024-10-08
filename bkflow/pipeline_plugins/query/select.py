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

from django.http import JsonResponse

logger = logging.getLogger("root")


def variable_select_source_data_proxy(request):
    """
    @summary: 获取下拉框源数据的通用接口，暂时关闭该接口
    @param request:
    @return:
    """
    return JsonResponse([{"text": "text1", "value": "value1"}])

    # url = request.GET.get("url")
    # try:
    #     response = requests.get(url=url, verify=False, timeout=10)
    # except Exception as e:
    #     logger.exception("variable select get data from url[url={url}] raise error: {error}".format(url=url, error=e))
    #     text = _("请求数据异常: {error}").format(error=e)
    #     data = [{"text": text, "value": ""}]
    #     return JsonResponse(data, safe=False)
    #
    # try:
    #     data = response.json()
    # except Exception:
    #     try:
    #         content = response.content.decode(response.encoding)
    #         logger.exception(
    #             "variable select get data from url[url={url}] is not a valid JSON: {data}".format(
    #                 url=url, data=content[:500]
    #             )
    #         )
    #     except Exception:
    #         logger.exception("variable select get data from url[url={url}] data is not a valid JSON".format(url=url))
    #     text = _("返回数据格式错误，不是合法 JSON 格式")
    #     data = [{"text": text, "value": ""}]
    #     return JsonResponse(data, safe=False)
    #
    # # 支持开发者对远程数据源数据配置处理函数，进行再处理
    # post_process_function = getattr(settings, "REMOTE_SOURCE_DATA_TRANSFORM_FUNCTION", None)
    # if post_process_function and callable(post_process_function):
    #     try:
    #         data = post_process_function(data)
    #     except Exception as e:
    #         logger.exception(
    #             "variable select transforming data from remote resource url[url={url}] "
    #             "raise error: {error}".format(url=url, error=e)
    #         )
    #         text = _("远程数据源数据转换失败: {error}").format(error=e)
    #         data = [{"text": text, "value": ""}]
    # return JsonResponse(data, safe=False)
