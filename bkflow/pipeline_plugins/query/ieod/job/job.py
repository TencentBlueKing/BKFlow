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
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view

from bkflow.constants import JobBizScopeType
from bkflow.pipeline_plugins.query.utils import query_response_handler
from bkflow.utils.requests import batch_request
from client.shortcuts import get_client_by_request

from .utils import job_get_scripts_data


@swagger_auto_schema(methods=["GET"])
@api_view(["GET"])
@query_response_handler
def get_business(request):
    """
    根据请求拉取对应业务
    """
    client = get_client_by_request(request, stage=settings.BK_CMDB_APIGW_STAGE)
    result = client.bkcmdb.search_business(
        {
            "condition": {"bk_data_status": {"$in": ["enable", "disabled", None]}},
        }
    )

    if result["result"]:
        data = result["data"]["info"]
        result = [{"text": item["bk_biz_name"], "value": item["bk_biz_id"]} for item in data]

    return result


@swagger_auto_schema(methods=["GET"])
@api_view(["GET"])
@query_response_handler
def job_get_public_script_name_list(request):
    """
    根据请求拉取Job平台公共脚本
    """
    script_list = job_get_scripts_data(request)
    script_names = []
    for script in script_list:
        if script.get("online_script_version_id"):
            script_names.append({"text": script["name"], "value": script["name"]})
    return script_names


@swagger_auto_schema(methods=["GET"])
@api_view(["GET"])
@query_response_handler
def job_get_script_name_list(request, biz_cc_id):
    """
    根据请求拉取Job平台对应业务脚本
    """
    script_list = job_get_scripts_data(request, biz_cc_id)
    script_names = []
    for script in script_list:
        if script.get("online_script_version_id"):
            script_names.append({"text": script["name"], "value": script["name"]})
    return script_names


@swagger_auto_schema(methods=["GET"])
@api_view(["GET"])
@query_response_handler
def get_job_account_list(request, biz_cc_id):
    """
    根据请求拉取Job平台对应业务下执行账号
    """
    bk_scope_type = request.GET.get("bk_scope_type", JobBizScopeType.BIZ.value)
    job_kwargs = {"bk_scope_id": biz_cc_id, "bk_scope_type": bk_scope_type, "category": 1}
    client = get_client_by_request(request, stage=settings.BK_JOB_APIGW_STAGE)
    account_list = batch_request(
        client.jobv3.get_account_list,
        job_kwargs,
        get_data=lambda x: x["data"]["data"],
        get_count=lambda x: x["data"]["total"],
        limit=500,
        page_param={"cur_page_param": "start", "page_size_param": "length"},
        is_page_merge=True,
        check_iam_auth_fail=True,
    )

    if not account_list:
        return []

    data = [{"text": account["alias"], "value": account["alias"]} for account in account_list]
    return data
