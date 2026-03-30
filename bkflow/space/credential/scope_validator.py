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

from bkflow.space.exceptions import CredentialScopeValidationError
from bkflow.space.models import CredentialScope, CredentialScopeLevel


def validate_credential_scope(credential, template_scope_type, template_scope_value):
    """
    验证凭证是否可以在指定的模板作用域中使用

    :param credential: Credential 模型实例
    :param template_scope_type: 模板的作用域类型
    :param template_scope_value: 模板的作用域值
    :return: 验证通过返回 True
    :raises CredentialScopeValidationError: 当凭证不能在指定作用域中使用时
    """
    if not credential.can_use_in_scope(template_scope_type, template_scope_value):
        raise CredentialScopeValidationError(
            _("凭证 {name}(ID:{id}) 不能在作用域 {scope_type}:{scope_value} 中使用").format(
                name=credential.name,
                id=credential.id,
                scope_type=template_scope_type or "None",
                scope_value=template_scope_value or "None",
            )
        )
    return True


def filter_credentials_by_scope(credentials_queryset, scope_type, scope_value):
    """
    根据作用域过滤凭证列表，返回可以在指定作用域中使用的凭证

    :param credentials_queryset: Credential 查询集
    :param scope_type: 作用域类型
    :param scope_value: 作用域值
    :return: 过滤后的凭证查询集
    """
    # 获取所有凭证ID
    all_credential_ids = list(credentials_queryset.values_list("id", flat=True))

    # 如果模板没有作用域（scope_type 和 scope_value 都为 None）
    if not scope_type and not scope_value:
        # 只返回 scope_level == ALL 的凭证（空间内开放）
        return credentials_queryset.filter(id__in=all_credential_ids, scope_level=CredentialScopeLevel.ALL.value)

    # 模板有作用域时，需要过滤：
    # 1. scope_level == ALL 的凭证（空间内开放，可以在任何地方使用）
    # 2. scope_level == PART 且作用域匹配的凭证

    # 获取 scope_level == ALL 的凭证ID
    all_level_credential_ids = set(
        credentials_queryset.filter(id__in=all_credential_ids, scope_level=CredentialScopeLevel.ALL.value).values_list(
            "id", flat=True
        )
    )

    # 获取 scope_level == PART 的凭证ID
    part_level_credential_ids = set(
        credentials_queryset.filter(id__in=all_credential_ids, scope_level=CredentialScopeLevel.PART.value).values_list(
            "id", flat=True
        )
    )

    # 查找 scope_level == PART 且作用域匹配的凭证ID
    matching_credential_ids = set(
        CredentialScope.objects.filter(
            credential_id__in=part_level_credential_ids, scope_type=scope_type, scope_value=scope_value
        ).values_list("credential_id", flat=True)
    )

    # 返回：scope_level == ALL 的凭证 + scope_level == PART 且作用域匹配的凭证
    available_credential_ids = all_level_credential_ids | matching_credential_ids

    return credentials_queryset.filter(id__in=available_credential_ids)
