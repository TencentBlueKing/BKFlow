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

import json

import requests
from django.conf import settings


def build_user_api_url(api_name, endpoint: str) -> str:
    """构建用户管理API的完整URL"""
    base_url = f"{settings.BK_API_URL_TMPL.format(api_name=api_name).rstrip('/')}/{settings.BK_APIGW_STAGE_NAME}"
    return f"{base_url}/{endpoint}"


def fetch_tenant_list():
    """
    获取租户列表
    """

    headers = {
        "x-bkapi-authorization": json.dumps({"bk_app_code": settings.APP_CODE, "bk_app_secret": settings.SECRET_KEY}),
        "x-bk-tenant-id": "system",
    }
    url = build_user_api_url("bk-user", "api/v3/open/tenants/")
    response = requests.get(url, headers=headers)
    return response.json()
