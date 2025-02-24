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
from django.conf import settings

from bkflow.constants import JobBizScopeType
from bkflow.utils.requests import batch_request
from client.shortcuts import get_client_by_request


def _job_get_scripts_data(request, biz_cc_id=None):
    client = get_client_by_request(request, stage=settings.BK_APIGW_STAGE_NAME)
    source_type = request.GET.get("type")
    script_type = request.GET.get("script_type")

    if biz_cc_id is None or source_type == "public":
        kwargs = {"script_language": script_type or 0}
        func = client.jobv3.get_public_script_list
    else:
        kwargs = {
            "bk_scope_type": JobBizScopeType.BIZ.value,
            "bk_scope_id": str(biz_cc_id),
            "bk_biz_id": biz_cc_id,
            "script_language": script_type or 0,
        }
        func = client.jobv3.get_script_list

    script_list = batch_request(
        func=func,
        params=kwargs,
        get_data=lambda x: x["data"]["data"],
        get_count=lambda x: x["data"]["total"],
        page_param={"cur_page_param": "start", "page_size_param": "length"},
        is_page_merge=True,
        check_iam_auth_fail=True,
    )

    return script_list
