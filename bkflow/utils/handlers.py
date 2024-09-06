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

import ujson as json
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

logger = logging.getLogger("root")


def handle_api_error(system, api_name, params, result):
    request_id = result.get("request_id", "")

    message = _("调用{system}接口{api_name}返回失败, params={params}, error={error}").format(
        system=system, api_name=api_name, params=json.dumps(params), error=result.get("message", "")
    )
    if request_id:
        message = "{}, request_id={}".format(message, request_id)

    logger.error(message)

    handle_plain_log(message)
    return message


def handle_plain_log(plain_log):
    if plain_log:
        for key_word in settings.LOG_SHIELDING_KEYWORDS:
            plain_log = plain_log.replace(key_word, "******")
    return plain_log
