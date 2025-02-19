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
import copy
from typing import Optional, Union

import jmespath
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from pipeline.component_framework.component import Component
from pipeline.core.flow.io import IntItemSchema, ObjectItemSchema
from pydantic import BaseModel, ValidationError

from bkflow.contrib.api.collections.interface import InterfaceModuleClient
from bkflow.pipeline_plugins.components.collections.base import (
    BKFlowBaseService,
    StepIntervalGenerator,
)
from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
from bkflow.pipeline_plugins.utils import convert_dict_value
from bkflow.utils.api_client import HttpRequestResult
from bkflow.utils.handlers import handle_plain_log


class StatusTag(BaseModel):
    key: str
    value: Union[str, int]
    msg_key: Optional[str] = None
    data_key: Optional[str] = None


class PollingConfig(BaseModel):
    url: str
    task_tag_key: str
    success_tag: StatusTag
    fail_tag: StatusTag
    running_tag: StatusTag


class CallbackConfig(BaseModel):
    success_tag: StatusTag
    fail_tag: StatusTag


class UniformAPIService(BKFlowBaseService):
    __need_schedule__ = True
    interval = StepIntervalGenerator(init_interval=0)

    def inputs_format(self):
        return []

    def outputs_format(self):
        return [
            self.OutputItem(
                name=_("响应内容"),
                key="data",
                type="object",
                schema=ObjectItemSchema(description=_("HTTP 请求响应内容，内部结构不固定"), property_schemas={}),
            ),
            self.OutputItem(
                name=_("状态码"),
                key="status_code",
                type="int",
                schema=IntItemSchema(description=_("HTTP 请求响应状态码")),
            ),
        ]

    def plugin_execute(self, data, parent_data):
        # callback 的情况需要在 execute 中进行调用
        callback = data.get_one_of_inputs("uniform_api_plugin_callback", None)
        if callback:
            return self._dispatch_schedule_trigger(data, parent_data)
        return True

    def plugin_schedule(self, data, parent_data, callback_data=None):
        need_polling = data.get_one_of_outputs("need_polling", False)
        need_callback = data.get_one_of_outputs("need_callback", False)
        action = "trigger"
        if need_polling:
            action = "polling"
        if need_callback:
            action = "callback"
        dispatched_func = getattr(self, f"_dispatch_schedule_{action}")
        return dispatched_func(data, parent_data, callback_data)

    def _load_parent_data(self, parent_data):
        operator = parent_data.get_one_of_inputs("operator")
        space_id = parent_data.get_one_of_inputs("task_space_id")
        extra_data = {
            "caller": operator,
            "scope_type": parent_data.get_one_of_inputs("task_scope_type"),
            "scope_value": parent_data.get_one_of_inputs("task_scope_value"),
            "task_id": parent_data.get_one_of_inputs("task_id"),
            "task_name": parent_data.get_one_of_inputs("task_name"),
            "space_id": space_id,
            "node_id": self.id,
        }
        return operator, space_id, extra_data

    def _dispatch_schedule_trigger(self, data, parent_data, callback_data=None):
        operator, space_id, extra_data = self._load_parent_data(parent_data)
        api_data = copy.deepcopy(data.inputs)
        api_data.update({"bkflow_extra_info": extra_data})
        url = api_data.pop("uniform_api_plugin_url")
        polling = api_data.pop("uniform_api_plugin_polling", None)
        callback = api_data.pop("uniform_api_plugin_callback", None)
        method = api_data.pop("uniform_api_plugin_method")
        timeout = api_data.pop("uniform_api_plugin_timeout", settings.BKAPP_API_PLUGIN_REQUEST_TIMEOUT)
        resp_data_path: str = api_data.pop("response_data_path", None)

        # 获取空间相关配置信息
        interface_client = InterfaceModuleClient()
        space_infos_result = interface_client.get_space_infos(
            {"space_id": space_id, "config_names": "uniform_api,credential"}
        )
        if not space_infos_result["result"]:
            message = handle_plain_log(
                "[uniform_api error] get apigw credential failed: {}".format(space_infos_result["message"])
            )
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        space_configs = space_infos_result.get("data", {}).get("configs", {})

        # 开启的enable_api_parameter_conversion配置只对POST参数生效
        if (
            space_configs.get("uniform_api", {}).get("enable_api_parameter_conversion", False)
            and method.upper() == "POST"
        ):
            # 启动参数转换
            api_data = convert_dict_value(api_data)

        credential_data = space_configs.get("credential")
        if credential_data:
            app_code, app_secret = credential_data["bk_app_code"], credential_data["bk_app_secret"]
        else:
            app_code, app_secret = settings.APP_CODE, settings.SECRET_KEY

        client = UniformAPIClient()
        headers = client.gen_default_apigw_header(app_code=app_code, app_secret=app_secret, username=operator)
        try:
            self.logger.info(handle_plain_log(f"[uniform_api] request url: {url}, method: {method}, data: {api_data}"))
            request_result: HttpRequestResult = client.request(
                url=url, method=method, data=api_data, headers=headers, timeout=timeout
            )
        except Exception as e:
            message = handle_plain_log("[uniform_api error] url request failed: {}".format(e))
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        data.outputs.status_code = request_result.resp.status_code
        if not request_result.json_resp:
            message = handle_plain_log(
                "[uniform_api error] get json response data failed: {}".format(request_result.message)
            )
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        if request_result.result is False:
            message = handle_plain_log(
                "[uniform_api error] response result is False: {}".format(request_result.message)
            )
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        self.logger.info(handle_plain_log(f"[uniform_api] response: {request_result.json_resp}"))
        resp_data = request_result.json_resp
        if resp_data_path:
            try:
                resp_data = request_result.extract_json_resp_with_jmespath(resp_data_path)
                if resp_data is None:
                    raise ValidationError(
                        f"no data matched with resp_data_path: {resp_data_path}, response: {request_result.json_resp}"
                    )
            except Exception as e:
                message = handle_plain_log(f"[uniform_api error] extract response result error: {e}")
                self.logger.error(message)
                data.outputs.ex_data = message
                return False

        if callback:
            self.interval = None
            data.set_outputs("need_callback", True)
            return True

        if polling:
            # 10s interval for polling
            self.interval.init_interval = 10
            data.outputs.trigger_data = resp_data
            data.set_outputs("need_polling", True)
            return True

        data.outputs.data = resp_data
        self.finish_schedule()
        return True

    def _dispatch_schedule_polling(self, data, parent_data, callback_data=None):
        if self.interval.reach_limit():
            data.set_outputs(
                "ex_data",
                message="[uniform_api polling] reach max count of schedule, "
                "please ensure the task can be finished in one day",
            )
            return False

        operator, space_id, extra_data = self._load_parent_data(parent_data)

        polling = data.get_one_of_inputs("uniform_api_plugin_polling")
        try:
            polling_config: PollingConfig = PollingConfig(**polling)
        except ValidationError as e:
            message = handle_plain_log("polling config is invalid: {}".format(str(e)))
            self.logger.exception(message)
            data.outputs.ex_data = message
            return False

        # 获取空间相关配置信息
        interface_client = InterfaceModuleClient()
        space_infos_result = interface_client.get_space_infos({"space_id": space_id, "config_names": "credential"})
        if not space_infos_result["result"]:
            message = handle_plain_log(
                "[uniform_api error] get apigw credential failed: {}".format(space_infos_result["message"])
            )
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        space_configs = space_infos_result.get("data", {}).get("configs", {})
        credential_data = space_configs.get("credential")
        if credential_data:
            app_code, app_secret = credential_data["bk_app_code"], credential_data["bk_app_secret"]
        else:
            app_code, app_secret = settings.APP_CODE, settings.SECRET_KEY

        client = UniformAPIClient()
        headers = client.gen_default_apigw_header(app_code=app_code, app_secret=app_secret, username=operator)
        trigger_data = data.get_one_of_outputs("trigger_data", {})
        task_tag_value = jmespath.search(polling_config.task_tag_key, trigger_data)
        if task_tag_value is None:
            message = handle_plain_log(
                f"[uniform_api polling] can not matched task_tag_key {polling_config.task_tag_key} "
                f"in output data {trigger_data}"
            )
            self.logger.error(message)
            data.outputs.ex_data = message
            return False
        api_data = {"task_tag": task_tag_value, **extra_data}
        self.logger.info(
            handle_plain_log(f"[uniform_api polling] request url: {polling_config.url}, method: get, data: {api_data}")
        )
        try:
            request_result: HttpRequestResult = client.request(
                url=polling_config.url,
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
        if not request_result.json_resp:
            message = handle_plain_log(
                "[uniform_api polling error] get json response data failed: {}".format(request_result.message)
            )
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        if request_result.result is False:
            message = handle_plain_log(
                "[uniform_api polling error] response result is False: {}".format(request_result.message)
            )
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        self.logger.info(handle_plain_log(f"[uniform_api polling] response: {request_result.json_resp}"))

        # 按照优先级进行判断：成功 > 失败 > 执行中
        status_data = request_result.json_resp
        if jmespath.search(polling_config.success_tag.key, status_data) == polling_config.success_tag.value:
            self.logger.info("[uniform_api polling] get success status")
            if polling_config.success_tag.data_key:
                data.outputs.data = jmespath.search(polling_config.success_tag.data_key, status_data)
            self.finish_schedule()
            return True

        if jmespath.search(polling_config.fail_tag.key, status_data) == polling_config.fail_tag.value:
            default_msg = f"[uniform_api polling] get fail status: {status_data}"
            self.logger.info(default_msg)
            data.outputs.ex_data = (
                jmespath.search(polling_config.fail_tag.msg_key, status_data)
                if polling_config.fail_tag.msg_key
                else default_msg
            )
            return False

        if jmespath.search(polling_config.running_tag.key, status_data) == polling_config.running_tag.value:
            self.logger.info(f"[uniform_api polling] get running status: {status_data}")
            return True

        message = f"[uniform_api polling] get status fail: {status_data}"
        self.logger.error(message)
        data.outputs.ex_data = message
        return False

    def _dispatch_schedule_callback(self, data, parent_data, callback_data=None):
        self.logger.info(f"[uniform_api callback] callback_data: {callback_data}")
        callback = data.get_one_of_inputs("uniform_api_plugin_callback")
        try:
            callback_config: CallbackConfig = CallbackConfig(**callback)
        except ValidationError as e:
            message = handle_plain_log("callback config is invalid: {}".format(str(e)))
            self.logger.exception(message)
            data.outputs.ex_data = message
            return False

        if jmespath.search(callback_config.success_tag.key, callback_data) == callback_config.success_tag.value:
            self.logger.info("[uniform_api callback] get success status")
            if callback_config.success_tag.data_key:
                data.outputs.data = jmespath.search(callback_config.success_tag.data_key, callback_data)
            self.finish_schedule()
            return True

        if jmespath.search(callback_config.fail_tag.key, callback_data) == callback_config.fail_tag.value:
            default_msg = f"[uniform_api callback] get fail status: {callback_data}"
            self.logger.info(default_msg)
            data.outputs.ex_data = (
                jmespath.search(callback_config.fail_tag.msg_key, callback_data)
                if callback_config.fail_tag.msg_key
                else default_msg
            )
            return False

        message = f"[uniform_api callback] get status fail: {callback_data}"
        self.logger.error(message)
        data.outputs.ex_data = message
        return False


class UniformAPIComponent(Component):
    name = _("统一API调用")
    code = "uniform_api"
    bound_service = UniformAPIService
    desc = _("用于调用符合接口协议的统一API")
    version = "v2.0.0"
