"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from bkflow.exceptions import ValidationError
from bkflow.harness.contracts import HarnessContextError, TrustedHarnessContext
from bkflow.harness.safety import normalize_correlation_id
from bkflow.space.configs import HarnessDeploymentConfig
from bkflow.space.models import Space, SpaceConfig


def route_space_id(space_id):
    """Normalize the permission-checked route space identifier without reading request input."""
    try:
        normalized_space_id = int(space_id)
    except (TypeError, ValueError):
        raise HarnessContextError("HARNESS_ROUTE_SPACE_INVALID")
    if normalized_space_id <= 0:
        raise HarnessContextError("HARNESS_ROUTE_SPACE_INVALID")
    return normalized_space_id


def get_route_space_id(view):
    """Read a Harness route's space identifier from the resolved view kwargs only."""
    return route_space_id(getattr(view, "kwargs", {}).get("space_id"))


def resolve_space(space_id, space=None):
    """Resolve the route space and reject a conflicting pre-resolved instance."""
    normalized_space_id = route_space_id(space_id)
    if space is not None:
        if space.id != normalized_space_id:
            raise HarnessContextError("HARNESS_ROUTE_SPACE_INVALID")
        return space
    try:
        return Space.objects.get(id=normalized_space_id, is_deleted=False)
    except Space.DoesNotExist:
        raise HarnessContextError("HARNESS_SPACE_UNAVAILABLE")


def authenticated_app_code(request):
    """Return only a gateway-injected application code."""
    app = getattr(request, "app", None)
    app_code = getattr(app, "bk_app_code", None)
    if getattr(app, "verified", None) is not True or not isinstance(app_code, str) or not app_code:
        raise HarnessContextError("HARNESS_APP_UNAUTHENTICATED")
    return app_code


def authenticated_actor(request):
    """Return only a gateway-authenticated user name."""
    user = getattr(request, "user", None)
    actor = getattr(user, "username", None)
    if not getattr(user, "is_authenticated", False) or not isinstance(actor, str) or not actor:
        raise HarnessContextError("HARNESS_USER_UNAUTHENTICATED")
    return actor


def deployment_binding(space_id):
    """Load and revalidate the non-public binding, including missing default values."""
    binding = SpaceConfig.get_config(space_id, HarnessDeploymentConfig.name)
    try:
        HarnessDeploymentConfig.validate(binding)
    except ValidationError:
        raise HarnessContextError("HARNESS_DEPLOYMENT_INVALID")
    return binding


def correlation_id(request):
    """Use gateway tracing when available and generate an opaque fallback otherwise."""
    candidate = getattr(request, "trace_id", None) or request.META.get("HTTP_X_REQUEST_ID")
    return normalize_correlation_id(candidate)


def build_trusted_harness_context(request, space_id=None, space=None):
    """Construct immutable Harness authority without inspecting request body or query values."""
    if space_id is None:
        space_id = getattr(getattr(request, "harness_space", None), "id", None)
    resolved_space = resolve_space(space_id=space_id, space=space)
    platform_app = authenticated_app_code(request)
    if resolved_space.app_code != platform_app:
        raise HarnessContextError("HARNESS_APP_SPACE_FORBIDDEN")
    binding = deployment_binding(resolved_space.id)
    return TrustedHarnessContext(
        platform_key=binding["platform_key"],
        platform_app=platform_app,
        actor=authenticated_actor(request),
        space_id=resolved_space.id,
        scope_type=binding["scope_type"],
        scope_value=binding["scope_value"],
        target_environment=binding["target_environment"],
        policy_version=binding["risk_policy_version"],
        mcp_contract_version=binding["mcp_contract_version"],
        correlation_id=correlation_id(request),
    )
