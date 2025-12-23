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
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.credential import UpdateCredentialSerializer
from bkflow.exceptions import ValidationError
from bkflow.space.models import Credential, CredentialScope


@login_exempt
@csrf_exempt
@require_http_methods(["PUT", "PATCH"])
@apigw_require
@check_jwt_and_space
@return_json_response
def update_credential(request, space_id, credential_id):
    """
    更新凭证

    :param request: HTTP 请求对象
    :param space_id: 空间ID
    :param credential_id: 凭证ID
    :return: 更新后的凭证信息
    """
    data = json.loads(request.body)
    ser = UpdateCredentialSerializer(data=data)
    ser.is_valid(raise_exception=True)

    try:
        credential = Credential.objects.get(id=credential_id, space_id=space_id, is_deleted=False)
    except Credential.DoesNotExist:
        raise ValidationError(_("凭证不存在: space_id={}, credential_id={}").format(space_id, credential_id))

    with transaction.atomic():
        # 更新凭证基本信息
        credential_data = dict(ser.validated_data)
        scopes_data = credential_data.pop("scopes", None)

        for attr, value in credential_data.items():
            if attr == "content":
                # 使用update_credential方法来更新content，会做验证
                credential.update_credential(value)
            else:
                setattr(credential, attr, value)

        credential.updated_by = request.user.username
        credential.save()

        # 更新凭证作用域
        if scopes_data is not None:
            # 删除旧的作用域
            CredentialScope.objects.filter(credential_id=credential.id).delete()
            # 创建新的作用域
            if scopes_data:
                scope_objects = [
                    CredentialScope(
                        credential_id=credential.id,
                        scope_type=scope.get("scope_type"),
                        scope_value=scope.get("scope_value"),
                    )
                    for scope in scopes_data
                ]
                CredentialScope.objects.bulk_create(scope_objects)

    return credential.display_json()
