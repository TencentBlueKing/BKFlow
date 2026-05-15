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
from bkflow.utils.handlers import handle_api_error
from bkflow.utils.message_cmsi import send_cmsi_message
from packages.bkapi.bk_cmsi.shortcuts import get_client_by_username

logger = logging.getLogger("root")


def send_message(executor: str, notify_types: list, receivers: str, title: str, content: str, tenant_id: str):
    client = get_client_by_username(executor, stage=settings.BK_APIGW_STAGE_NAME)

    has_error = False
    error_message = ""

    logger.info(
        f"taskflow send message, receivers={receivers},title={title} content={content}, "
        f"tenant_id={tenant_id}, notify_types={notify_types}"
    )
    for msg_type in notify_types:
        kwargs = {}
        operation_name = ""
        try:
            operation_name, kwargs, result = send_cmsi_message(
                client=client,
                tenant_id=tenant_id,
                msg_type=msg_type,
                receivers=receivers,
                title=title,
                content=content,
            )
        except Exception as e:
            err_msg = "taskflow send message failed, msg_type={}, operation={}, kwargs={}, error={}".format(
                msg_type, operation_name, json.dumps(kwargs), str(e)
            )
            logger.exception(err_msg)
            has_error = True
            error_message = "{};{}".format(err_msg, error_message) if error_message else err_msg
            continue

        if not result:
            api_error_msg = handle_api_error(
                "cmsi",
                "cmsi.send_voice_msg" if msg_type == "voice" else "cmsi.send_msg",
                kwargs,
                result,
            )
            logger.error(
                "send message failed, msg_type={}, kwargs={}, result={}".format(
                    msg_type, json.dumps(kwargs), json.dumps(result)
                )
            )
            has_error = True
            error_message = "{};{}".format(api_error_msg, error_message) if error_message else api_error_msg

    return has_error, error_message
