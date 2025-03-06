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

from .. import config
from ..base import RequestAPI


class CollectionsJOBV3(object):
    def __init__(self, client):

        self.client = client
        self.host = config.HOST.format(api_name="jobv3-cloud")

        self.fast_execute_script = RequestAPI(
            client=self.client,
            method="POST",
            host=self.host,
            path="/{stage}/api/{bk_apigw_ver}/system/fast_execute_script/",
            description="快速执行脚本",
        )

        self.get_public_script_list = RequestAPI(
            client=self.client,
            method="GET",
            host=self.host,
            path="/{stage}/api/{bk_apigw_ver}/system/get_public_script_list/",
            description="查询公共脚本列表",
        )

        self.get_script_list = RequestAPI(
            client=self.client,
            method="GET",
            host=self.host,
            path="/{stage}/api/{bk_apigw_ver}/system/get_script_list/",
            description="查询业务脚本列表",
        )

        self.get_account_list = RequestAPI(
            client=self.client,
            method="GET",
            host=self.host,
            path="/{stage}/api/{bk_apigw_ver}/system/get_account_list/",
            description="查询业务下用户有权限的执行账号列表",
        )

        self.get_job_instance_ip_log = RequestAPI(
            client=self.client,
            method="GET",
            host=self.host,
            path="/{stage}/api/{bk_apigw_ver}/system/get_job_instance_ip_log/",
            description="根据ip查询作业执行日志",
        )

        self.get_job_instance_status = RequestAPI(
            client=self.client,
            method="GET",
            host=self.host,
            path="/{stage}/api/{bk_apigw_ver}/system/get_job_instance_status/",
            description="查询作业实例状态",
        )

        self.get_job_instance_global_var_value = RequestAPI(
            client=self.client,
            method="GET",
            host=self.host,
            path="/{stage}/api/{bk_apigw_ver}/system/get_job_instance_global_var_value/",
            description="查询作业实例全局变量值",
        )
