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
import datetime
from unittest import mock

import pytest
from django.conf import settings

from bkflow.utils.webhook import (
    apply_webhook_configs,
    clear_scope_webhooks,
    get_webhook_configs,
    get_webhook_delivery_history_by_delivery_id,
)


class TestGetWebhookConfigs:
    """测试 get_webhook_configs"""

    def test_get_webhook_configs_success(self, mocker):
        """测试正常获取 webhook 配置"""
        mock_webhook = mock.MagicMock()
        mock_webhook.method = "POST"
        mock_webhook.endpoint = "http://example.com/webhook"
        mock_webhook.extra_info = {"token": "secret"}

        mocker.patch("bkflow.utils.webhook.WebhookModel.objects.filter").return_value.first.return_value = mock_webhook

        mocker.patch("bkflow.utils.webhook.process_sensitive_info", return_value={"token": "decrypted"})

        result = get_webhook_configs("scope_123")

        assert result["method"] == "POST"
        assert result["endpoint"] == "http://example.com/webhook"
        assert result["extra_info"] == {"token": "decrypted"}

    def test_get_webhook_configs_not_found(self, mocker):
        """测试 webhook 不存在时返回空字典"""
        mocker.patch("bkflow.utils.webhook.WebhookModel.objects.filter").return_value.first.return_value = None

        result = get_webhook_configs("scope_123")
        assert result == {}

    def test_get_webhook_configs_exception(self, mocker):
        """测试查询异常时返回空字典"""
        mocker.patch(
            "bkflow.utils.webhook.WebhookModel.objects.filter",
            side_effect=Exception("DB error"),
        )

        result = get_webhook_configs("scope_123")
        assert result == {}


class TestGetWebhookDeliveryHistory:
    """测试 get_webhook_delivery_history_by_delivery_id"""

    def test_get_history_with_dict_response(self, mocker):
        """测试正常获取历史记录，response 为字典"""
        mock_history = mock.MagicMock()
        mock_history.created_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
        mock_history.event_code = "task_finished"
        mock_history.success = True
        mock_history.status_code = 200
        mock_history.extra_info = {"response": {"message": "ok"}}

        mock_events = [("task_finished", "任务完成")]

        mocker.patch("bkflow.utils.webhook.thread_local.get", return_value=None)
        mocker.patch("bkflow.utils.webhook.thread_local.set")
        mocker.patch(
            "bkflow.utils.webhook.Event.objects.values_list",
            return_value=mock_events,
        )
        mocker.patch(
            "bkflow.utils.webhook.History.objects.filter",
            return_value=[mock_history],
        )

        result = get_webhook_delivery_history_by_delivery_id("delivery_123")

        assert len(result) == 1
        assert result[0]["event_code"] == "task_finished"
        assert result[0]["event_code_name"] == "任务完成"
        assert result[0]["is_success"] is True
        assert result[0]["status_code"] == 200
        assert result[0]["response"] == "ok"

    def test_get_history_with_non_dict_response(self, mocker):
        """测试 response 不是字典的情况"""
        mock_history = mock.MagicMock()
        mock_history.created_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
        mock_history.event_code = "task_failed"
        mock_history.success = False
        mock_history.status_code = 500
        mock_history.extra_info = {"response": "raw string"}

        event_mapping = {"task_failed": "任务失败"}
        mocker.patch("bkflow.utils.webhook.thread_local.get", return_value=event_mapping)
        mocker.patch(
            "bkflow.utils.webhook.History.objects.filter",
            return_value=[mock_history],
        )

        result = get_webhook_delivery_history_by_delivery_id("delivery_456")

        assert len(result) == 1
        assert result[0]["event_code_name"] == "任务失败"
        assert result[0]["is_success"] is False
        assert result[0]["response"] is None

    def test_get_history_empty(self, mocker):
        """测试没有历史记录时返回空列表"""
        mocker.patch("bkflow.utils.webhook.thread_local.get", return_value=None)
        mocker.patch("bkflow.utils.webhook.thread_local.set")
        mocker.patch(
            "bkflow.utils.webhook.Event.objects.values_list",
            return_value=[],
        )
        mocker.patch(
            "bkflow.utils.webhook.History.objects.filter",
            return_value=[],
        )

        result = get_webhook_delivery_history_by_delivery_id("delivery_789")
        assert result == []

    def test_get_history_with_fallback_event_name(self, mocker):
        """测试事件名称映射不存在时使用 event_code 作为回退"""
        mock_history = mock.MagicMock()
        mock_history.created_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
        mock_history.event_code = "unknown_event"
        mock_history.success = True
        mock_history.status_code = 200
        mock_history.extra_info = {"response": {}}

        event_mapping = {"other_event": "其他事件"}
        mocker.patch("bkflow.utils.webhook.thread_local.get", return_value=event_mapping)
        mocker.patch(
            "bkflow.utils.webhook.History.objects.filter",
            return_value=[mock_history],
        )

        result = get_webhook_delivery_history_by_delivery_id("delivery_999")

        assert result[0]["event_code_name"] == "unknown_event"


class TestClearScopeWebhooks:
    """测试 clear_scope_webhooks"""

    def test_clear_success(self, mocker):
        """测试成功清除 webhook 配置"""
        mock_delete = mocker.patch("bkflow.utils.webhook.WebhookModel.objects.filter").return_value.delete
        mocker.patch("bkflow.utils.webhook.ScopeModel.objects.filter").return_value.delete
        mocker.patch("bkflow.utils.webhook.Subscription.objects.filter").return_value.delete

        result = clear_scope_webhooks(["scope_1", "scope_2"])

        assert result["result"] is True
        assert result["code"] == "0"
        mock_delete.assert_called_once()

    def test_clear_exception(self, mocker):
        """测试清除时发生异常"""
        mocker.patch(
            "bkflow.utils.webhook.WebhookModel.objects.filter",
            side_effect=Exception("DB error"),
        )

        result = clear_scope_webhooks(["scope_1"])

        assert result["result"] is False
        assert result["code"] == "500"
        assert "DB error" in result["message"]


class TestApplyWebhookConfigs:
    """测试 apply_webhook_configs"""

    @pytest.fixture(autouse=True)
    def setup_settings(self):
        """设置 webhook 相关配置上限"""
        settings.MAX_WEBHOOK_RETRY_TIMES = 5
        settings.MAX_WEBHOOK_RETRY_INTERVAL = 60
        settings.MAX_WEBHOOK_TIMEOUT = 30

    def test_apply_success(self, mocker):
        """测试正常应用 webhook 配置"""
        mocker.patch("bkflow.utils.webhook.WebhookSerializer")
        mock_serializer = mocker.patch("bkflow.utils.webhook.WebhookSerializer")
        mock_serializer.return_value.is_valid.return_value = True

        mocker.patch("bkflow.utils.webhook.apply_scope_webhooks")
        mocker.patch("bkflow.utils.webhook.apply_scope_subscriptions")

        webhook_configs = {
            "method": "POST",
            "endpoint": "http://example.com",
            "extra_info": {
                "retry_times": 3,
                "interval": 10,
                "timeout": 5,
            },
        }

        result = apply_webhook_configs(webhook_configs, "scope_123")

        assert result["result"] is True
        assert result["code"] == "0"

    def test_apply_invalid_serializer(self, mocker):
        """测试序列化器校验失败"""
        mock_serializer = mocker.patch("bkflow.utils.webhook.WebhookSerializer")
        mock_serializer.return_value.is_valid.return_value = False
        mock_serializer.return_value.errors = {"endpoint": ["This field is required."]}

        webhook_configs = {"method": "POST"}
        result = apply_webhook_configs(webhook_configs, "scope_123")

        assert result["result"] is False
        assert "endpoint" in result["message"]

    def test_apply_retry_times_exceeds_limit(self, mocker):
        """测试重试次数超过限制"""
        mock_serializer = mocker.patch("bkflow.utils.webhook.WebhookSerializer")
        mock_serializer.return_value.is_valid.return_value = True

        webhook_configs = {
            "method": "POST",
            "endpoint": "http://example.com",
            "extra_info": {"retry_times": 10},
        }
        result = apply_webhook_configs(webhook_configs, "scope_123")

        assert result["result"] is False
        assert "重试次数" in result["message"]
        assert "5" in result["message"]

    def test_apply_interval_exceeds_limit(self, mocker):
        """测试重试间隔超过限制"""
        mock_serializer = mocker.patch("bkflow.utils.webhook.WebhookSerializer")
        mock_serializer.return_value.is_valid.return_value = True

        webhook_configs = {
            "method": "POST",
            "endpoint": "http://example.com",
            "extra_info": {"interval": 100},
        }
        result = apply_webhook_configs(webhook_configs, "scope_123")

        assert result["result"] is False
        assert "重试间隔" in result["message"]
        assert "60" in result["message"]

    def test_apply_timeout_exceeds_limit(self, mocker):
        """测试超时时间超过限制"""
        mock_serializer = mocker.patch("bkflow.utils.webhook.WebhookSerializer")
        mock_serializer.return_value.is_valid.return_value = True

        webhook_configs = {
            "method": "POST",
            "endpoint": "http://example.com",
            "extra_info": {"timeout": 60},
        }
        result = apply_webhook_configs(webhook_configs, "scope_123")

        assert result["result"] is False
        assert "请求超时" in result["message"]
        assert "30" in result["message"]

    def test_apply_api_exception(self, mocker):
        """测试调用底层 API 时发生异常"""
        mock_serializer = mocker.patch("bkflow.utils.webhook.WebhookSerializer")
        mock_serializer.return_value.is_valid.return_value = True

        mocker.patch(
            "bkflow.utils.webhook.apply_scope_webhooks",
            side_effect=Exception("API error"),
        )

        webhook_configs = {
            "method": "POST",
            "endpoint": "http://example.com",
            "extra_info": {},
        }
        result = apply_webhook_configs(webhook_configs, "scope_123")

        assert result["result"] is False
        assert result["code"] == "500"
        assert "API error" in result["message"]

    def test_apply_does_not_modify_original_config(self, mocker):
        """测试不会修改传入的原始配置"""
        mock_serializer = mocker.patch("bkflow.utils.webhook.WebhookSerializer")
        mock_serializer.return_value.is_valid.return_value = True
        mocker.patch("bkflow.utils.webhook.apply_scope_webhooks")
        mocker.patch("bkflow.utils.webhook.apply_scope_subscriptions")

        original_config = {"method": "POST", "endpoint": "http://example.com"}
        original_copy = original_config.copy()

        apply_webhook_configs(original_config, "scope_123")

        # 确认原始配置未被修改
        assert original_config == original_copy
