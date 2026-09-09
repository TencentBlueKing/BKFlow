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

import pytest

from bkflow.apigw.serializers.token import (
    ApiGwTokenRevokeSerializer,
    ApiGwTokenSerializer,
)
from bkflow.permission import models as permission_models


@pytest.mark.parametrize("value", ["VIEW", "EDIT", "OPERATE", "MOCK"])
@pytest.mark.parametrize("serializer_class", [ApiGwTokenSerializer, ApiGwTokenRevokeSerializer])
def test_token_permissions_keep_existing_api_values(value, serializer_class):
    """枚举拆分后，签发与撤销仍接受原有四个操作字符串。"""
    permission = permission_models.TokenPermissionType(value)
    serializer = serializer_class(
        data={"resource_type": "TEMPLATE", "resource_id": "100", "permission_type": permission.value}
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["permission_type"] == value


@pytest.mark.parametrize("value", ["FLOW_VIEW", "FLOW_EDIT", "FLOW_MOCK"])
@pytest.mark.parametrize("serializer_class", [ApiGwTokenSerializer, ApiGwTokenRevokeSerializer])
def test_task_auth_codes_cannot_be_used_as_token_permissions(value, serializer_class):
    """展示标记可被识别，但不能转换为 Token 操作或用于签发、撤销过滤。"""
    auth_code = permission_models.TaskAuthCode(value)

    with pytest.raises(ValueError):
        permission_models.TokenPermissionType(auth_code.value)

    serializer = serializer_class(
        data={"resource_type": "TEMPLATE", "resource_id": "100", "permission_type": auth_code.value}
    )

    assert not serializer.is_valid()
    assert serializer.errors["permission_type"][0].code == "invalid_choice"
