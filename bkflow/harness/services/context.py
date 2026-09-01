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
import uuid
from typing import Any, Optional, Tuple

from django.utils.translation import ugettext_lazy as _

from bkflow.exceptions import ValidationError
from bkflow.harness.contracts import TrustedHarnessContext
from bkflow.harness.exceptions import HarnessAuthorizationError
from bkflow.space.configs import (
    HarnessDeploymentConfig,
    HarnessEnabledConfig,
    SuperusersConfig,
)
from bkflow.space.models import Space, SpaceConfig


def _request_app_code(request: Any) -> Optional[str]:
    app = getattr(request, "app", None)
    return getattr(app, "bk_app_code", None) if app is not None else None


def _request_username(request: Any) -> Optional[str]:
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return getattr(user, "username", None) or None


def authorize_harness_request(request: Any, space_id: int) -> Tuple[Space, dict]:
    """
    以 AND 语义校验 Harness 调用方。

    :raises HarnessAuthorizationError: 任一谓词失败
    """
    app_code = _request_app_code(request)
    if not app_code:
        raise HarnessAuthorizationError("HARNESS_APP_UNAUTHENTICATED", _("缺少已认证应用"))

    username = _request_username(request)
    if not username:
        raise HarnessAuthorizationError("HARNESS_USER_UNAUTHENTICATED", _("缺少已认证用户"))

    space = Space.objects.filter(id=space_id, is_deleted=False).first()
    if space is None or space.app_code != app_code:
        raise HarnessAuthorizationError("HARNESS_APP_FORBIDDEN", _("当前应用无权操作此空间"))

    superusers = SpaceConfig.get_config(space.id, SuperusersConfig.name) or []
    if username not in superusers:
        raise HarnessAuthorizationError("HARNESS_USER_FORBIDDEN", _("当前用户无权操作此空间"))

    if SpaceConfig.get_config(space.id, HarnessEnabledConfig.name) != "true":
        raise HarnessAuthorizationError("HARNESS_DISABLED", _("空间未启用 AI 流程生成 Harness"))

    deployment = SpaceConfig.get_config(space.id, HarnessDeploymentConfig.name) or {}
    try:
        HarnessDeploymentConfig.validate(deployment)
    except ValidationError:
        raise HarnessAuthorizationError("HARNESS_DEPLOYMENT_INVALID", _("Harness 部署绑定无效"))
    return space, deployment


def derive_trusted_context(request: Any, space_id: int) -> TrustedHarnessContext:
    """从已鉴权请求推导可信上下文，忽略 body 中的身份字段。"""
    space, deployment = authorize_harness_request(request, space_id)
    correlation_id = getattr(request, "trace_id", None) or uuid.uuid4().hex
    return TrustedHarnessContext(
        platform_key=deployment["platform_key"],
        platform_app=_request_app_code(request),
        actor=_request_username(request),
        space_id=space.id,
        scope_type=deployment.get("scope_type"),
        scope_value=deployment.get("scope_value"),
        target_environment=deployment["target_environment"],
        policy_version=deployment["risk_policy_version"],
        mcp_contract_version=deployment["mcp_contract_version"],
        correlation_id=str(correlation_id),
    )
