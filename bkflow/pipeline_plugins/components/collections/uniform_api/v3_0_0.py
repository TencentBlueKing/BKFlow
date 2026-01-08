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
from typing import Optional, Tuple, Union

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
from bkflow.pipeline_plugins.components.collections.uniform_api.credential_handlers import (
    ApiGatewayCredentialNameUserProvidedHandler,
    CredentialKeySpaceConfigHandler,
    CredentialKeyUserProvidedHandler,
    DefaultCredentialHandler,
    SpaceCredentialHandler,
)
from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
from bkflow.pipeline_plugins.utils import convert_dict_value
from bkflow.space.configs import UniformAPIConfigHandler
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

    def _render_headers(self, headers_config: dict, operator: str, parent_data) -> dict:
        """渲染headers配置中的变量

        支持的变量格式：
        - ${_system.operator}: 操作人
        - ${_system.task_id}: 任务ID
        - ${_system.task_name}: 任务名称
        - ${_system.space_id}: 空间ID
        - ${_system.scope_type}: 作用域类型
        - ${_system.scope_value}: 作用域值

        :param headers_config: headers配置字典
        :param operator: 操作人
        :param parent_data: 父数据
        :return: 渲染后的headers字典
        """
        if not headers_config:
            return {}

        # 构建变量映射表
        variable_map = {
            "${_system.operator}": operator,
            "${_system.task_id}": str(parent_data.get_one_of_inputs("task_id", "")),
            "${_system.task_name}": parent_data.get_one_of_inputs("task_name", ""),
            "${_system.space_id}": str(parent_data.get_one_of_inputs("task_space_id", "")),
            "${_system.scope_type}": parent_data.get_one_of_inputs("task_scope_type", ""),
            "${_system.scope_value}": parent_data.get_one_of_inputs("task_scope_value", ""),
        }

        rendered_headers = {}
        for key, value in headers_config.items():
            if isinstance(value, str):
                # 替换所有支持的变量
                rendered_value = value
                for var_name, var_value in variable_map.items():
                    if var_name in rendered_value:
                        rendered_value = rendered_value.replace(var_name, var_value)
                rendered_headers[key] = rendered_value
            else:
                rendered_headers[key] = value

        return rendered_headers

    def _get_api_config_by_url(self, validated_config, url: str) -> Optional[dict]:
        """根据URL匹配对应的API配置

        :param validated_config: 验证后的配置对象
        :param url: API请求URL
        :return: 匹配的API配置，如果没有匹配则返回None
        """
        if not hasattr(validated_config, "api") or not validated_config.api:
            return None

        # 尝试通过URL匹配meta_apis来确定使用的API key
        # 提取URL的域名部分进行匹配
        try:
            from urllib.parse import urlparse

            url_domain = urlparse(url).netloc
        except Exception:
            url_domain = ""

        for __, api_model in validated_config.api.items():
            if hasattr(api_model, "meta_apis") and api_model.meta_apis:
                try:
                    meta_domain = urlparse(api_model.meta_apis).netloc
                    # 如果URL的域名与meta_apis的域名相同，则认为匹配
                    if url_domain and meta_domain and url_domain == meta_domain:
                        return api_model
                except Exception:
                    # 如果解析失败，使用简单的包含匹配
                    if api_model.meta_apis in url:
                        return api_model

        # 如果只有一个API配置，直接返回
        if len(validated_config.api) == 1:
            return list(validated_config.api.values())[0]

        # 如果无法匹配，返回第一个（默认行为）
        if validated_config.api:
            return list(validated_config.api.values())[0]

        return None

    def _get_credential(
        self,
        scope_type: Optional[str],
        scope_id: Optional[str],
        parent_data,
        space_configs: dict,
        credential_key: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """获取凭证信息，优先使用用户传入的凭证，否则使用空间配置或默认凭证

        :param scope_type: 范围类型
        :param scope_id: 范围ID
        :param parent_data: 父任务数据
        :param space_configs: 空间配置字典（从space_infos_result中获取）
        :param credential_key: 凭证key
        :return: (app_code, app_secret) 元组，如果获取失败返回 (None, None)
        """
        # 按优先级顺序定义凭证处理器
        handlers = [
            CredentialKeyUserProvidedHandler(self.logger, scope_type, scope_id, parent_data, space_configs),
            CredentialKeySpaceConfigHandler(self.logger, scope_type, scope_id, parent_data, space_configs),
            ApiGatewayCredentialNameUserProvidedHandler(self.logger, scope_type, scope_id, parent_data, space_configs),
            SpaceCredentialHandler(self.logger, scope_type, scope_id, parent_data, space_configs),
            DefaultCredentialHandler(self.logger, scope_type, scope_id, parent_data, space_configs),
        ]

        # 按优先级顺序尝试各个处理器
        for handler in handlers:
            try:
                if handler.can_handle(credential_key):
                    app_code, app_secret = handler.get_credential(credential_key)
                    if app_code and app_secret:
                        return app_code, app_secret
            except Exception as e:
                self.logger.warning(f"[uniform_api] Handler {handler.get_name()} failed: {e}")
                continue

        # 如果 credential_key 存在但所有处理器都失败，记录警告
        if credential_key:
            # 创建一个临时处理器来获取 api_gateway_credential_name（用于日志）
            temp_handler = CredentialKeyUserProvidedHandler(
                self.logger, scope_type, scope_id, parent_data, space_configs
            )
            api_gateway_credential_name = temp_handler._get_api_gateway_credential_name()
            self.logger.warning(
                f"[uniform_api] credential_key {credential_key} not found in credentials and "
                f"does not match api_gateway_credential_name {api_gateway_credential_name}"
            )

        return None, None

    def _extract_error_message(self, request_result: HttpRequestResult) -> str:
        """提取错误信息，优先从JSON响应的message字段获取"""
        if request_result.json_resp and isinstance(request_result.json_resp, dict):
            return request_result.json_resp.get("message") or request_result.message
        return request_result.message or f"HTTP status code: {request_result.resp.status_code}"

    def _handle_error_response(
        self, data, request_result: HttpRequestResult, error_prefix: str = "[uniform_api error]"
    ) -> bool:
        """处理错误响应，设置错误信息并返回False"""
        error_message = self._extract_error_message(request_result)
        message = handle_plain_log(
            "{} HTTP status code: {}, message: {}".format(error_prefix, request_result.resp.status_code, error_message)
        )
        self.logger.error(message)
        data.outputs.ex_data = message
        return False

    def _check_response_success(
        self, request_result: HttpRequestResult, enable_standard_response: bool
    ) -> Tuple[bool, Optional[str]]:
        """
        检查响应是否成功
        返回: (is_success, error_reason)
        """
        if enable_standard_response:
            # 标准响应模式：使用HTTP状态码判断
            if 200 <= request_result.resp.status_code < 300:
                return True, None
            else:
                return False, f"HTTP status code indicates failure: {request_result.resp.status_code}"
        else:
            # 非标准模式：检查JSON响应和result字段
            if not request_result.json_resp:
                return False, "get json response data failed"
            if request_result.result is False:
                return False, "response result is False"
            return True, None

    def _extract_response_data(
        self, request_result: HttpRequestResult, enable_standard_response: bool, log_prefix: str = "[uniform_api]"
    ) -> Tuple[Union[dict, list, str], bool]:
        """
        提取响应数据
        返回: (response_data, is_json)
        """
        if enable_standard_response:
            # 标准响应模式：优先使用JSON，否则使用原始body
            if request_result.json_resp is not None:
                self.logger.info(handle_plain_log(f"{log_prefix} response: {request_result.json_resp}"))
                return request_result.json_resp, True
            else:
                # 如果响应不是JSON格式，将body的原始数据作为字符串返回
                raw_body = request_result.resp.text if request_result.resp else ""
                self.logger.warning(
                    handle_plain_log(
                        "{} warning: response is not valid JSON, using raw body as string: {}".format(
                            log_prefix, raw_body[:200] if len(raw_body) > 200 else raw_body
                        )
                    )
                )
                return raw_body, False
        else:
            # 非标准模式：必须使用JSON响应
            self.logger.info(handle_plain_log(f"{log_prefix} response: {request_result.json_resp}"))
            return request_result.json_resp, True

    def _dispatch_schedule_trigger(self, data, parent_data, callback_data=None):
        operator, space_id, extra_data = self._load_parent_data(parent_data)
        api_data = copy.deepcopy(data.inputs)
        api_data.update({"bkflow_extra_info": extra_data})
        url = api_data.pop("uniform_api_plugin_url")
        polling = api_data.pop("uniform_api_plugin_polling", None)
        callback = api_data.pop("uniform_api_plugin_callback", None)
        method = api_data.pop("uniform_api_plugin_method")
        credential_key = api_data.pop("uniform_api_plugin_credential_key", None)
        resp_data_path: str = api_data.pop("response_data_path", None)
        # 获取空间相关配置信息
        interface_client = InterfaceModuleClient()
        scope_type, scope_id = parent_data.get_one_of_inputs("task_scope_type"), parent_data.get_one_of_inputs(
            "task_scope_value"
        )
        space_infos_params = {
            "space_id": space_id,
            "config_names": "uniform_api,credential,api_gateway_credential_name",
        }
        if scope_type and scope_id:
            space_infos_params["scope"] = f"{scope_type}_{scope_id}"
        self.logger.info(f"get_space_info params: {space_infos_params}")
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
            # 过滤字符串为空的基础类型
            keys_to_remove = [key for key, value in api_data.items() if value == ""]
            self.logger.info(f"none fields keys to remove: {keys_to_remove}")
            for key in keys_to_remove:
                api_data.pop(key)
            self.logger.info(f"plugin_data after poping: {api_data}")

        # 开启的enable_api_parameter_conversion配置只对POST参数生效
        if validated_config.enable_api_parameter_conversion:
            # 启动参数转换
            api_data = convert_dict_value(api_data)

        # 获取凭证信息
        app_code, app_secret = self._get_credential(scope_type, scope_id, parent_data, space_configs, credential_key)
        if not app_code or not app_secret:
            message = "不存在调用凭证"
            self.logger.error(message)
            data.outputs.ex_data = message
            return False
        client = UniformAPIClient()
        headers = client.gen_default_apigw_header(app_code=app_code, app_secret=app_secret, username=operator)

        # 获取并合并配置的headers
        api_config = self._get_api_config_by_url(validated_config, url)
        if api_config and hasattr(api_config, "headers") and api_config.headers:
            rendered_headers = self._render_headers(api_config.headers, operator, parent_data)
            # 合并headers，配置的headers优先级更高
            headers.update(rendered_headers)
            self.logger.info(handle_plain_log(f"[uniform_api] merged custom headers: {rendered_headers}"))
        else:
            self.logger.info(handle_plain_log(f"[uniform_api] no headers config found for url: {url}"))

        try:
            self.logger.info(handle_plain_log(f"[uniform_api] request url: {url}, method: {method}, data: {api_data}"))
            request_result: HttpRequestResult = client.request(
                url=url,
                method=method,
                data=api_data,
                headers=headers,
                timeout=settings.BKAPP_API_PLUGIN_REQUEST_TIMEOUT,
            )
        except Exception as e:
            message = handle_plain_log("[uniform_api error] url request failed: {}".format(e))
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        data.outputs.status_code = request_result.resp.status_code

        # 检查响应是否成功
        enable_standard_response = validated_config.enable_standard_response
        is_success, error_reason = self._check_response_success(request_result, enable_standard_response)

        if not is_success:
            # 处理错误响应
            return self._handle_error_response(data, request_result, "[uniform_api error]")

        # 提取响应数据
        resp_data, is_json = self._extract_response_data(request_result, enable_standard_response)

        # 如果后续需要使用JSON数据（resp_data_path、polling、callback），需要确保有JSON响应
        if resp_data_path or polling or callback:
            if not is_json:
                message = handle_plain_log(
                    "[uniform_api error] JSON response is required for resp_data_path/polling/callback, "
                    "but response is not valid JSON: {}".format(request_result.message)
                )
                self.logger.error(message)
                data.outputs.ex_data = message
                return False
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
        scope_type, scope_id = parent_data.get_one_of_inputs("task_scope_type"), parent_data.get_one_of_inputs(
            "task_scope_value"
        )
        space_infos_params = {
            "space_id": space_id,
            "config_names": "uniform_api,credential,api_gateway_credential_name",
        }
        if scope_type and scope_id:
            space_infos_params["scope"] = f"{scope_type}_{scope_id}"
        self.logger.info(f"get_space_info params: {space_infos_params}")
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

        # 获取凭证信息
        credential_key = data.get_one_of_inputs("uniform_api_plugin_credential_key", None)
        app_code, app_secret = self._get_credential(scope_type, scope_id, parent_data, space_configs, credential_key)
        if not app_code or not app_secret:
            message = "不存在调用凭证"
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        client = UniformAPIClient()
        headers = client.gen_default_apigw_header(app_code=app_code, app_secret=app_secret, username=operator)

        # 获取并合并配置的headers
        api_config = self._get_api_config_by_url(validated_config, polling_config.url)
        if api_config and hasattr(api_config, "headers") and api_config.headers:
            rendered_headers = self._render_headers(api_config.headers, operator, parent_data)
            # 合并headers，配置的headers优先级更高
            headers.update(rendered_headers)
            self.logger.info(handle_plain_log(f"[uniform_api polling] merged custom headers: {rendered_headers}"))

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

        # 轮询模式需要JSON响应来进行状态判断
        if not request_result.json_resp:
            message = handle_plain_log(
                "[uniform_api polling error] get json response data failed: {}".format(request_result.message)
            )
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        # 检查响应是否成功
        enable_standard_response = validated_config.enable_standard_response
        is_success, error_reason = self._check_response_success(request_result, enable_standard_response)

        if not is_success:
            # 处理错误响应
            return self._handle_error_response(data, request_result, "[uniform_api polling error]")

        # 记录响应日志
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
    version = "v3.0.0"
