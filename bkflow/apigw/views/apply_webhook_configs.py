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

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from webhook.api import apply_scope_subscriptions, apply_scope_webhooks
from webhook.contrib.drf.serializers import WebhookConfigsWithEventsSerializer

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.constants import WebhookScopeType
from bkflow.utils import err_code

logger = logging.getLogger("root")


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
def apply_webhook_configs(request, space_id):
    """
    全量应用webhook配置，会覆盖原有配置
    data : {
        "webhooks": [
            "code": "webhook1",
            "name": "webhook1",
            "endpoint": "https://xxx",
            "token": "xxx",
            "events": ["*"],
        ]
    }
    """
    data = json.loads(request.body)

    ser = WebhookConfigsWithEventsSerializer(data=data)
    ser.is_valid(raise_exception=True)

    webhook_configs = ser.validated_data["webhooks"]
    subscription_configs = {webhook_config["code"]: webhook_config["events"] for webhook_config in webhook_configs}

    if len(subscription_configs) != len(webhook_configs):
        return {"result": False, "message": "webhook code can not repeat", "data": {}, "code": err_code.ERROR.code}

    try:
        scope_type, scope_code = WebhookScopeType.SPACE.value, str(space_id)
        with transaction.atomic():
            apply_scope_webhooks(scope_type=scope_type, scope_code=scope_code, webhooks=webhook_configs)
            apply_scope_subscriptions(
                scope_type=scope_type, scope_code=scope_code, subscription_configs=subscription_configs
            )
    except Exception as e:
        logger.exception("apply_webhook_configs error")
        return {"result": False, "message": f"fail: {e}", "data": {}, "code": err_code.ERROR.code}

    return {"result": True, "message": "success", "data": {}, "code": err_code.SUCCESS.code}
