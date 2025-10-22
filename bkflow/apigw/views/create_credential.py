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
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.credential import CreateCredentialSerializer
from bkflow.space.models import Credential, CredentialScope


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
def create_credential(request, space_id):
    """
    创建凭证

    :param request: HTTP 请求对象
    :param space_id: 空间ID
    :return: 创建的凭证信息
    """
    data = json.loads(request.body)
    ser = CreateCredentialSerializer(data=data)
    ser.is_valid(raise_exception=True)

    # 提取作用域数据
    credential_data = dict(ser.validated_data)
    scopes = credential_data.pop("scopes", [])

    # 创建凭证和作用域
    with transaction.atomic():
        # 序列化器已经检查过是否存在了
        credential = Credential.create_credential(**credential_data, space_id=space_id, creator=request.user.username)

        # 创建凭证作用域
        if scopes:
            scope_objects = [
                CredentialScope(
                    credential_id=credential.id,
                    scope_type=scope.get("scope_type"),
                    scope_value=scope.get("scope_value"),
                )
                for scope in scopes
            ]
            CredentialScope.objects.bulk_create(scope_objects)

    return credential.display_json()
