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
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from pipeline.component_framework.component import Component
from pipeline.core.flow.io import IntItemSchema, ObjectItemSchema

from bkflow.contrib.api.collections.interface import InterfaceModuleClient
from bkflow.pipeline_plugins.components.collections.base import BKFlowBaseService
from bkflow.pipeline_plugins.query.uniform_api.utils import UniformAPIClient
from bkflow.pipeline_plugins.utils import convert_dict_value
from bkflow.utils.api_client import HttpRequestResult
from bkflow.utils.handlers import handle_plain_log

__group_name__ = _("蓝鲸服务(BK)")


class UniformAPIService(BKFlowBaseService):
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

    @staticmethod
    def _parse_api_config(api_config):
        url, method, params = api_config.get("url"), api_config.get("method"), api_config.get("params")
        data = {param["key"]: param["value"] for param in params}
        return url, method, data

    def plugin_execute(self, data, parent_data):
        api_config = data.inputs.get("api_config")
        if not api_config:
            message = "api_config can not be empty"
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        timeout = api_config.get("timeout", 30)
        url, method, api_data = self._parse_api_config(api_config)
        operator = parent_data.get_one_of_inputs("operator")
        space_id = parent_data.get_one_of_inputs("task_space_id")
        extra_data = {
            "caller": operator,
            "scope_type": parent_data.get_one_of_inputs("task_scope_type"),
            "scope_value": parent_data.get_one_of_inputs("task_scope_value"),
            "task_id": parent_data.get_one_of_inputs("task_id"),
            "task_name": parent_data.get_one_of_inputs("task_name"),
            "space_id": space_id,
        }

        api_data.update({"bkflow_extra_info": extra_data})

        # 获取apigw的凭证
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

        if space_configs.get("uniform_api", {}).get("enable_api_parameter_conversion", False):
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

        data.outputs.data = request_result.json_resp
        return True


class UniformAPIComponent(Component):
    name = _("统一API调用")
    code = "uniform_api"
    bound_service = UniformAPIService
    desc = _("用于调用符合接口协议的统一API")
    version = "v1.0.0"
