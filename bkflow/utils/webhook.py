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

from django.conf import settings
from django.db import transaction
from webhook.api import apply_scope_subscriptions, apply_scope_webhooks
from webhook.contrib.drf.serializers import WebhookSerializer
from webhook.models import Event, History
from webhook.models import Scope as ScopeModel
from webhook.models import Subscription
from webhook.models import Webhook as WebhookModel
from webhook.utils import process_sensitive_info

from bkflow.constants import WebhookEventType, WebhookScopeType
from bkflow.utils.dates import format_datetime
from bkflow.utils.local import thread_local

logger = logging.getLogger("root")


def get_webhook_configs(scope_code):
    """
    get webhook retry policy of scope
    """
    try:
        webhook = WebhookModel.objects.filter(scope_type=WebhookScopeType.TEMPLATE.value, scope_code=scope_code).first()
        if not webhook:
            return {}
        result = {
            "method": webhook.method,
            "endpoint": webhook.endpoint,
            "extra_info": process_sensitive_info(webhook.extra_info, is_decrypt=True),
        }
    except Exception as e:
        logger.exception(f"get_scope_webhooks error: {e}")
        return {}

    return result


def get_webhook_delivery_history_by_delivery_id(delivery_id):
    """
    根据 delivery_id 查询 webhook 投递历史。
    delivery_id 对应业务中的 task_id，用于关联任务与其 webhook 回调记录。
    """
    histories = History.objects.filter(delivery_id=delivery_id)
    result = []

    event_name_mapping = thread_local.get("event_name_mapping")
    if not event_name_mapping:
        events = Event.objects.values_list("code", "name")
        event_name_mapping = {code: name for code, name in events}
        thread_local.set("event_name_mapping", event_name_mapping)
    for history in histories:
        response = history.extra_info.get("response", {})
        result.append(
            {
                "created_at": format_datetime(history.created_at),
                "event_code": history.event_code,
                "event_code_name": event_name_mapping.get(history.event_code, history.event_code),
                "is_success": history.success,
                "status_code": history.status_code,
                "response": response.get("message", None) if isinstance(response, dict) else None,
            }
        )

    return result


def clear_scope_webhooks(scope_code: list):
    try:
        with transaction.atomic():
            WebhookModel.objects.filter(scope_type=WebhookScopeType.TEMPLATE.value, scope_code__in=scope_code).delete()
            ScopeModel.objects.filter(type=WebhookScopeType.TEMPLATE.value, code__in=scope_code).delete()
            Subscription.objects.filter(scope_type=WebhookScopeType.TEMPLATE.value, scope_code__in=scope_code).delete()
    except Exception as e:
        logger.exception(f"clear_webhooks error: {e}")
        return {"result": False, "message": f"Failed to clear webhooks: {e}", "data": {}, "code": "500"}

    return {"result": True, "message": "success", "data": {}, "code": "0"}


def apply_webhook_configs(webhook_configs, scope_code):
    webhook_code = f"template_{scope_code}_webhook"
    webhook_name = f"template_{scope_code}_webhook"
    # 避免修改调用方传入的原始数据
    webhook_configs = {**webhook_configs, "code": webhook_code, "name": webhook_name}
    serializer = WebhookSerializer(data=webhook_configs)
    serializer.is_valid(raise_exception=True)
    extra_info = webhook_configs.get("extra_info", {})
    extra_info_mappings = {
        "retry_times": {"name": "重试次数", "max_value": settings.MAX_WEBHOOK_RETRY_TIMES, "unit": "次"},
        "interval": {"name": "重试间隔", "max_value": settings.MAX_WEBHOOK_RETRY_INTERVAL, "unit": "秒"},
        "timeout": {"name": "请求超时", "max_value": settings.MAX_WEBHOOK_TIMEOUT, "unit": "秒"},
    }
    for field, rule in extra_info_mappings.items():
        raw_value = extra_info.get(field)
        max_val = rule["max_value"]
        if raw_value and raw_value > max_val:
            return {
                "result": False,
                "message": f"HTTP回调配置{rule['name']}不能超过 {max_val} {rule['unit']}",
                "data": {},
                "code": "500",
            }

    scope_type = WebhookScopeType.TEMPLATE.value
    subscription_configs = {webhook_code: [WebhookEventType.TASK_FAILED.value, WebhookEventType.TASK_FINISHED.value]}
    try:
        apply_scope_webhooks(scope_type=scope_type, scope_code=scope_code, webhooks=[webhook_configs])
        apply_scope_subscriptions(
            scope_type=scope_type, scope_code=scope_code, subscription_configs=subscription_configs
        )
    except Exception as e:
        logger.exception(f"apply_webhook_configs error: {e}")
        return {"result": False, "message": f"Failed to apply webhook configs: {e}", "data": {}, "code": "500"}

    return {"result": True, "message": "success", "data": {}, "code": "0"}
