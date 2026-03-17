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
from django.utils.translation import ugettext_lazy as _

from bkflow.space.credential.scope_validator import validate_credential_scope
from bkflow.space.exceptions import CredentialNotFoundError
from bkflow.space.models import Credential


def resolve_credentials(credentials_dict, space_id, scope_type=None, scope_value=None):
    """
    解析凭证字典，将凭证引用转换为实际的凭证值

    :param credentials_dict: 凭证字典，格式为 {"${token1}": {"value": "credential_id_or_direct_value", ...}}
    :param space_id: 空间ID
    :param scope_type: 模板的作用域类型（可选）
    :param scope_value: 模板的作用域值（可选）

    :return: 解析后的凭证字典，保留原有结构但填充实际值

    :raises CredentialNotFoundError: 当引用的凭证不存在时
    :raises CredentialScopeValidationError: 当凭证不能在指定作用域使用时
    """
    if not credentials_dict:
        return {}

    resolved_credentials = {}

    for key, cred_info in credentials_dict.items():
        # 创建凭证信息的副本
        resolved_info = dict(cred_info)

        # 获取凭证值
        value = cred_info.get("value", "")

        # 如果value是数字，尝试作为credential_id解析
        if isinstance(value, (int, str)) and str(value).isdigit():
            credential_id = int(value)
            try:
                credential = Credential.objects.get(id=credential_id, space_id=space_id, is_deleted=False)

                # 验证凭证作用域
                validate_credential_scope(credential, scope_type, scope_value)

                # 获取凭证的实际值
                resolved_info["value"] = credential.value
                resolved_info["credential_id"] = credential_id
                resolved_info["credential_name"] = credential.name
                resolved_info["credential_type"] = credential.type

            except Credential.DoesNotExist:
                raise CredentialNotFoundError(
                    _("凭证不存在: space_id={space_id}, credential_id={credential_id}").format(
                        space_id=space_id, credential_id=credential_id
                    )
                )
        else:
            # 如果不是数字，直接使用提供的值
            resolved_info["value"] = value

        resolved_credentials[key] = resolved_info

    return resolved_credentials
