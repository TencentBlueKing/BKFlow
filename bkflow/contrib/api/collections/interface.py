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
import random
import time

from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from bkflow.contrib.api.client import BaseComponentClient
from bkflow.utils.trace import get_current_trace_context

logger = logging.getLogger("component")


class InterfaceModuleClient(BaseComponentClient):
    SNAPSHOT_MAX_ATTEMPTS = 3
    SNAPSHOT_RETRY_BUDGET = 30.0
    SNAPSHOT_CONNECT_TIMEOUT = 3.0
    SNAPSHOT_READ_TIMEOUT = 10.0

    def __init__(self):
        super().__init__()

    def _pre_process_headers(self, headers):
        if not headers:
            headers = {
                "Content-Type": "application/json",
                settings.APP_INTERNAL_TOKEN_HEADER_KEY: settings.INTERFACE_APP_INTERNAL_TOKEN,
            }
        else:
            headers[settings.APP_INTERNAL_TOKEN_HEADER_KEY] = settings.INTERFACE_APP_INTERNAL_TOKEN

        return headers

    def _get_interface_url(self, api_name):
        return "{}/{}".format(settings.INTERFACE_APP_URL, api_name)

    def get_decision_table(self, decision_table_id, data):
        return self._request(
            method="get", url=self._get_interface_url(f"api/decision_table/internal/{decision_table_id}/"), data=data
        )

    def get_space_infos(self, data):
        return self._request(
            method="get", url=self._get_interface_url("api/space/internal/get_space_infos/"), data=data
        )

    def broadcast_task_events(self, data):
        return self._request(
            method="post", url=self._get_interface_url("api/space/internal/broadcast_task_events/"), data=data
        )

    def get_template_data(self, template_id, data):
        return self._request(
            method="get",
            url=self._get_interface_url(f"api/template/internal/{template_id}/get_template_data/"),
            data=data,
        )

    def get_variable(self, space_id):
        return self._request(
            method="get",
            url=self._get_interface_url("api/variable/internal/get_variable/"),
            data={"space_id": space_id},
        )

    def validate_open_plugins_for_start(self, data):
        return self._request(
            method="post",
            url=self._get_interface_url("api/plugin/internal/validate_open_plugins_for_start/"),
            data=data,
        )

    def build_open_plugin_snapshots(self, data):
        return self._request(
            method="post",
            url=self._get_interface_url("api/plugin/internal/build_open_plugin_snapshots/"),
            data=data,
        )

    def prepare_task_extra_info(self, data):
        """只重试无任务写入的快照准备请求，业务校验失败立即返回。"""
        deadline = time.monotonic() + self.SNAPSHOT_RETRY_BUDGET
        trace_id = (get_current_trace_context() or {}).get("trace_id")
        result = {"retryable": True}
        for attempt in range(self.SNAPSHOT_MAX_ATTEMPTS):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            connect_timeout = min(self.SNAPSHOT_CONNECT_TIMEOUT, remaining / 2)
            result = self._request(
                method="post",
                url=self._get_interface_url("api/template/internal/prepare_task_extra_info/"),
                data=data,
                timeout=(connect_timeout, min(self.SNAPSHOT_READ_TIMEOUT, remaining - connect_timeout)),
            )
            if result.get("result"):
                if isinstance(result.get("data"), dict) and isinstance(result["data"].get("extra_info"), dict):
                    return result
                result = {"error_type": "invalid_response", "retryable": False}
            elif not result.get("error_type"):
                return result

            logger.warning(
                "Snapshot preparation request failed: attempt=%s, error_type=%s, status_code=%s, trace_id=%s",
                attempt + 1,
                result.get("error_type"),
                result.get("status_code"),
                trace_id,
            )
            if not result.get("retryable") or attempt + 1 == self.SNAPSHOT_MAX_ATTEMPTS:
                break
            delay = 2**attempt + random.uniform(0, 0.5)
            if time.monotonic() + delay >= deadline:
                break
            time.sleep(delay)

        retryable = result.get("retryable", False)
        message = _("子任务准备服务暂时不可用，请稍后重试") if retryable else _("子任务准备服务请求失败，请联系管理员处理")
        if trace_id:
            message = _("%(message)s（Trace ID: %(trace_id)s）") % {"message": message, "trace_id": trace_id}
        return {
            "result": False,
            "message": message,
            "code": "SNAPSHOT_PREPARE_UNAVAILABLE" if retryable else "SNAPSHOT_PREPARE_REQUEST_FAILED",
            "retryable": retryable,
            "trace_id": trace_id,
        }
