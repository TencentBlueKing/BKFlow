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

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.conf import settings
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import return_json_response
from bkflow.apigw.serializers.space import CreateSpaceSerializer
from bkflow.apigw.utils import get_space_config_presentation
from bkflow.space.models import Space, SpaceConfig, SpaceCreateType
from bkflow.utils import err_code


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@return_json_response
def create_space(request):
    """
    request.data :  {
        "space_name": "默认空间",
        "platform_url": "http:/xxx.com",
        "app_code": "xxx"
    }
    """
    data = json.loads(request.body)
    if hasattr(request, "app") and request.app.bk_app_code not in settings.APP_WHITE_LIST:
        data["app_code"] = request.app.bk_app_code

    ser = CreateSpaceSerializer(data=data)

    ser.is_valid(raise_exception=True)

    config = ser.validated_data.pop("config", None)

    with transaction.atomic():
        username = request.user.username
        space = Space.objects.create(
            **ser.validated_data, create_type=SpaceCreateType.API.value, creator=username, updated_by=username
        )
        default_config = {"superusers": [request.user.username], "flow_versioning": "true"}
        if config:
            default_config.update(config)
        SpaceConfig.objects.batch_update(space_id=space.id, configs=default_config)

    space_config_presentation = get_space_config_presentation(space.id)
    resp = {"space": space.to_json(), "config": space_config_presentation}
    return {"result": True, "data": resp, "code": err_code.SUCCESS.code}
