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

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.utils import get_space_config_presentation
from bkflow.utils import err_code


@login_exempt
@csrf_exempt
@require_GET
@apigw_require
@check_jwt_and_space
@return_json_response
def get_space_configs(request, space_id):
    # 获取到所有的配置
    space_config_presentation = get_space_config_presentation(space_id)
    return {"result": True, "data": space_config_presentation, "code": err_code.SUCCESS.code}
