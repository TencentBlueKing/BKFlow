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
import json
import logging

from bkflow.conf import settings

get_client_by_user = settings.ESB_GET_CLIENT_BY_USER

logger = logging.getLogger("root")


def send_message(executor: str, notify_type: list, receivers: str, title: str, content: str):
    client = get_client_by_user(executor)
    kwargs = {
        "receiver__username": receivers,
        "title": title,
        "content": content,
    }
    for msg_type in notify_type:
        kwargs.update({"msg_type": msg_type})
        send_result = client.cmsi.send_msg(kwargs)
        if not send_result["result"]:
            logger.error(
                "send message failed, kwargs={}, result={}".format(json.dumps(kwargs), json.dumps(send_result))
            )
    return True
