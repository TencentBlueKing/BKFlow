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

from bkflow.contrib.api.client import BaseComponentClient


class InterfaceModuleClient(BaseComponentClient):
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

    def get_apigw_credential(self, data):
        return self._request(
            method="get", url=self._get_interface_url("api/space/credential/get_api_gateway_credential/"), data=data
        )

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

    def get_subproc_data(self, template_id, data):
        return self._request(
            method="get",
            url=self._get_interface_url(f"api/template/internal/{template_id}/get_subproc_data/"),
            data=data,
        )
