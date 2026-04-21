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
import copy

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from pipeline.component_framework.component import Component

from bkflow.contrib.api.collections.interface import InterfaceModuleClient
from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
from bkflow.pipeline_plugins.utils import convert_dict_value
from bkflow.plugin.models import OpenPluginCatalogIndex, OpenPluginRunCallbackRef
from bkflow.plugin.services.open_plugin_callback import (
    build_open_plugin_callback_url,
    build_open_plugin_client_request_id,
    callback_token_digest,
    issue_open_plugin_callback_token,
)
from bkflow.space.configs import UniformAPIConfigHandler
from bkflow.utils.handlers import handle_plain_log

from .v3_0_0 import UniformAPIService as V3UniformAPIService


def build_open_plugin_execute_payload(
    source_key,
    plugin_id,
    plugin_version,
    inputs,
    client_request_id,
    callback_url,
    callback_token,
    project_id=None,
):
    payload = {
        "source_key": source_key,
        "plugin_id": plugin_id,
        "plugin_version": plugin_version,
        "client_request_id": client_request_id,
        "callback_url": callback_url,
        "callback_token": callback_token,
        "inputs": inputs,
    }
    if project_id:
        payload["project_id"] = project_id
    return payload


def build_open_plugin_cancel_url(trigger_url, open_plugin_run_id):
    return "{}/{}/cancel".format(trigger_url.rstrip("/"), open_plugin_run_id)


class UniformAPIService(V3UniformAPIService):
    OPEN_PLUGIN_WAITING_CALLBACK = "WAITING_CALLBACK"
    OPEN_PLUGIN_RUNNING_STATES = {"CREATED", "RUNNING"}
    OPEN_PLUGIN_SUCCESS_STATES = {"SUCCEEDED"}
    OPEN_PLUGIN_FAILED_STATES = {"FAILED", "CANCELLED"}

    @staticmethod
    def _is_open_plugin_request(data):
        return bool(data.get_one_of_inputs("uniform_api_plugin_id"))

    @staticmethod
    def _resolve_open_plugin_source_key(space_id, plugin_id, explicit_source_key=""):
        if explicit_source_key:
            return explicit_source_key
        catalog = (
            OpenPluginCatalogIndex.objects.filter(space_id=space_id, plugin_id=plugin_id)
            .order_by("-update_time", "-id")
            .first()
        )
        return getattr(catalog, "source_key", "")

    @staticmethod
    def _upsert_open_plugin_callback_ref(
        task_id,
        node_id,
        node_version,
        client_request_id,
        open_plugin_run_id,
        callback_token,
        callback_expire_at,
        plugin_source,
        source_key,
        plugin_id,
        plugin_version,
        cancel_url,
        credential_key="",
    ):
        defaults = {
            "task_id": task_id,
            "node_id": node_id,
            "node_version": node_version,
            "callback_token_digest": callback_token_digest(callback_token),
            "callback_expire_at": callback_expire_at,
            "plugin_source": plugin_source,
            "source_key": source_key,
            "plugin_id": plugin_id,
            "plugin_version": plugin_version,
            "cancel_url": cancel_url,
            "credential_key": credential_key or "",
        }
        OpenPluginRunCallbackRef.objects.update_or_create(
            client_request_id=client_request_id,
            defaults={**defaults, "open_plugin_run_id": open_plugin_run_id},
        )

    def _dispatch_schedule_trigger(self, data, parent_data, callback_data=None):
        if not self._is_open_plugin_request(data):
            return super()._dispatch_schedule_trigger(data, parent_data, callback_data)

        operator, space_id, extra_data = self._load_parent_data(parent_data)
        api_data = copy.deepcopy(data.inputs)
        url = api_data.pop("uniform_api_plugin_url")
        polling = api_data.pop("uniform_api_plugin_polling", None)
        callback = api_data.pop("uniform_api_plugin_callback", None)
        method = api_data.pop("uniform_api_plugin_method")
        credential_key = api_data.pop("uniform_api_plugin_credential_key", None)
        plugin_id = api_data.pop("uniform_api_plugin_id")
        plugin_version = api_data.pop("uniform_api_plugin_version")
        explicit_source_key = api_data.pop("uniform_api_plugin_source_key", "")

        interface_client = InterfaceModuleClient()
        scope_type = parent_data.get_one_of_inputs("task_scope_type")
        scope_id = parent_data.get_one_of_inputs("task_scope_value")
        space_infos_params = {
            "space_id": space_id,
            "config_names": "uniform_api,credential,api_gateway_credential_name",
        }
        if scope_type and scope_id:
            space_infos_params["scope"] = f"{scope_type}_{scope_id}"
        space_infos_result = interface_client.get_space_infos(space_infos_params)
        if not space_infos_result["result"]:
            message = handle_plain_log(
                "[uniform_api error] get apigw credential failed: {}".format(space_infos_result["message"])
            )
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        space_configs = space_infos_result.get("data", {}).get("configs", {})
        uniform_api_config = space_configs.get("uniform_api", {})
        validated_config = UniformAPIConfigHandler(uniform_api_config).handle()

        if validated_config.exclude_none_fields:
            keys_to_remove = [key for key, value in api_data.items() if value == ""]
            for key in keys_to_remove:
                api_data.pop(key)
        if validated_config.enable_api_parameter_conversion:
            api_data = convert_dict_value(api_data)

        app_code, app_secret = self._get_credential(scope_type, scope_id, parent_data, space_configs, credential_key)
        if not app_code or not app_secret:
            message = "不存在调用凭证"
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        client = UniformAPIClient()
        headers = client.gen_default_apigw_header(app_code=app_code, app_secret=app_secret, username=operator)
        api_config = self._get_api_config_by_url(validated_config, url)
        if api_config and getattr(api_config, "headers", None):
            headers.update(self._render_headers(api_config.headers, operator, parent_data))

        source_key = self._resolve_open_plugin_source_key(space_id=space_id, plugin_id=plugin_id, explicit_source_key=explicit_source_key)
        if not source_key:
            message = f"[uniform_api error] can not resolve source_key for open plugin {plugin_id}"
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        retry_no = data.get_one_of_outputs("open_plugin_retry_no", 0) + 1
        data.set_outputs("open_plugin_retry_no", retry_no)
        client_request_id = build_open_plugin_client_request_id(
            task_id=parent_data.get_one_of_inputs("task_id"), node_id=self.id, retry_no=retry_no
        )
        callback_url = build_open_plugin_callback_url(space_id=space_id, task_id=parent_data.get_one_of_inputs("task_id"), node_id=self.id)
        callback_token, expire_at = issue_open_plugin_callback_token(
            task_id=parent_data.get_one_of_inputs("task_id"),
            node_id=self.id,
            client_request_id=client_request_id,
            node_version=getattr(self, "version", ""),
        )
        execute_payload = build_open_plugin_execute_payload(
            source_key=source_key,
            plugin_id=plugin_id,
            plugin_version=plugin_version,
            inputs=api_data,
            client_request_id=client_request_id,
            callback_url=callback_url,
            callback_token=callback_token,
        )

        try:
            request_result = client.request(
                url=url,
                method=method,
                data=execute_payload,
                headers=headers,
                timeout=settings.BKAPP_API_PLUGIN_REQUEST_TIMEOUT,
            )
        except Exception as e:
            message = handle_plain_log("[uniform_api error] url request failed: {}".format(e))
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        data.outputs.status_code = request_result.resp.status_code
        is_success, _ = self._check_response_success(request_result, validated_config.enable_standard_response)
        if not is_success:
            return self._handle_error_response(data, request_result, "[uniform_api error]")
        if not request_result.json_resp:
            message = "[uniform_api error] open plugin execute requires JSON response"
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        resp_data = request_result.json_resp.get("data", {})
        open_plugin_run_id = resp_data.get("open_plugin_run_id")
        if not open_plugin_run_id:
            message = "[uniform_api error] open plugin response missing open_plugin_run_id"
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        self._upsert_open_plugin_callback_ref(
            task_id=parent_data.get_one_of_inputs("task_id"),
            node_id=self.id,
            node_version=getattr(self, "version", ""),
            client_request_id=client_request_id,
            open_plugin_run_id=open_plugin_run_id,
            callback_token=callback_token,
            callback_expire_at=expire_at,
            plugin_source="open_plugin",
            source_key=source_key,
            plugin_id=plugin_id,
            plugin_version=plugin_version,
            cancel_url=build_open_plugin_cancel_url(url, open_plugin_run_id),
            credential_key=credential_key or "",
        )
        data.outputs.trigger_data = {"open_plugin_run_id": open_plugin_run_id}

        run_status = resp_data.get("status")
        if callback and run_status == self.OPEN_PLUGIN_WAITING_CALLBACK:
            self.interval = None
            data.set_outputs("need_callback", True)
            data.set_outputs("need_polling", False)
            return True
        if polling:
            self.interval.init_interval = 10
            data.set_outputs("need_polling", True)
            return True

        data.outputs.data = resp_data
        self.finish_schedule()
        return True

    def _dispatch_schedule_polling(self, data, parent_data, callback_data=None):
        if not self._is_open_plugin_request(data):
            return super()._dispatch_schedule_polling(data, parent_data, callback_data)

        if self.interval.reach_limit():
            message = (
                "[uniform_api polling] reach max count of schedule, "
                "please ensure the task can be finished in one day"
            )
            data.set_outputs("ex_data", message)
            return False

        operator, space_id, extra_data = self._load_parent_data(parent_data)
        polling = data.get_one_of_inputs("uniform_api_plugin_polling")

        interface_client = InterfaceModuleClient()
        scope_type = parent_data.get_one_of_inputs("task_scope_type")
        scope_id = parent_data.get_one_of_inputs("task_scope_value")
        space_infos_params = {
            "space_id": space_id,
            "config_names": "uniform_api,credential,api_gateway_credential_name",
        }
        if scope_type and scope_id:
            space_infos_params["scope"] = f"{scope_type}_{scope_id}"
        space_infos_result = interface_client.get_space_infos(space_infos_params)
        if not space_infos_result["result"]:
            message = handle_plain_log(
                "[uniform_api error] get apigw credential failed: {}".format(space_infos_result["message"])
            )
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        space_configs = space_infos_result.get("data", {}).get("configs", {})
        uniform_api_config = space_configs.get("uniform_api", {})
        validated_config = UniformAPIConfigHandler(uniform_api_config).handle()
        credential_key = data.get_one_of_inputs("uniform_api_plugin_credential_key", None)
        app_code, app_secret = self._get_credential(scope_type, scope_id, parent_data, space_configs, credential_key)
        if not app_code or not app_secret:
            message = "不存在调用凭证"
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        client = UniformAPIClient()
        headers = client.gen_default_apigw_header(app_code=app_code, app_secret=app_secret, username=operator)
        polling_url = polling.get("url")
        api_config = self._get_api_config_by_url(validated_config, polling_url)
        if api_config and getattr(api_config, "headers", None):
            headers.update(self._render_headers(api_config.headers, operator, parent_data))

        trigger_data = data.get_one_of_outputs("trigger_data", {})
        open_plugin_run_id = trigger_data.get("open_plugin_run_id")
        if not open_plugin_run_id:
            message = "[uniform_api polling] can not matched open_plugin_run_id in trigger data"
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        api_data = {"task_tag": open_plugin_run_id, **extra_data}
        try:
            request_result = client.request(
                url=polling_url,
                method="get",
                data=api_data,
                headers=headers,
                timeout=settings.BKAPP_API_PLUGIN_REQUEST_TIMEOUT,
            )
        except Exception as e:
            message = handle_plain_log("[uniform_api polling error] url request failed: {}".format(e))
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        data.outputs.status_code = request_result.resp.status_code
        is_success, _ = self._check_response_success(request_result, validated_config.enable_standard_response)
        if not is_success:
            return self._handle_error_response(data, request_result, "[uniform_api polling error]")
        if not request_result.json_resp:
            message = "[uniform_api polling error] open plugin polling requires JSON response"
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        status_data = request_result.json_resp.get("data", {})
        run_status = status_data.get("status")
        if run_status == self.OPEN_PLUGIN_WAITING_CALLBACK:
            self.interval = None
            data.set_outputs("need_polling", False)
            data.set_outputs("need_callback", True)
            return True
        if run_status in self.OPEN_PLUGIN_SUCCESS_STATES:
            data.outputs.data = status_data.get("outputs", {})
            self.finish_schedule()
            return True
        if run_status in self.OPEN_PLUGIN_FAILED_STATES:
            data.outputs.ex_data = status_data.get("error_message") or f"[uniform_api polling] get fail status: {status_data}"
            return False
        if run_status in self.OPEN_PLUGIN_RUNNING_STATES:
            return True

        message = f"[uniform_api polling] get status fail: {status_data}"
        self.logger.error(message)
        data.outputs.ex_data = message
        return False


class UniformAPIComponent(Component):
    name = _("统一API调用")
    code = "uniform_api"
    bound_service = UniformAPIService
    desc = _("用于调用符合接口协议的统一API")
    version = "v4.0.0"
