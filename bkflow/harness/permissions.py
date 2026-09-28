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
from dataclasses import dataclass

from django.conf import settings
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from bkflow.harness.contracts import HarnessContextError, TrustedHarnessContext
from bkflow.harness.services.context import (
    authenticated_actor,
    authenticated_app_code,
    get_route_space_id,
    resolve_space,
)
from bkflow.space.configs import HarnessEnabledConfig, SuperusersConfig
from bkflow.space.models import SpaceConfig
from bkflow.utils.tenant import get_apigw_request_tenant_id, get_request_tenant_id


@dataclass(frozen=True)
class HarnessAuthorizationFailure:
    """A stable, non-secret reason suitable for a Harness transport adapter."""

    code: str
    message: str = "Harness access denied."


class HarnessPermission(permissions.BasePermission):
    """Require all gateway, space, user, and feature predicates in one permission class."""

    message = "Harness access denied."

    @staticmethod
    def _deny(request, code):
        request.harness_authorization_error = HarnessAuthorizationFailure(code=code)
        return False

    def has_permission(self, request, view):
        """Authorize a route only after every trusted predicate has passed."""
        try:
            platform_app = authenticated_app_code(request)
        except HarnessContextError as error:
            return self._deny(request, error.code)
        try:
            actor = authenticated_actor(request)
        except HarnessContextError as error:
            return self._deny(request, error.code)
        try:
            space = resolve_space(get_route_space_id(view))
        except HarnessContextError:
            return self._deny(request, "HARNESS_APP_SPACE_FORBIDDEN")
        if space.app_code != platform_app:
            return self._deny(request, "HARNESS_APP_SPACE_FORBIDDEN")
        if settings.ENABLE_MULTI_TENANT_MODE:
            try:
                if get_apigw_request_tenant_id(request) != space.tenant_id:
                    return self._deny(request, "HARNESS_APP_SPACE_FORBIDDEN")
                if get_request_tenant_id(request) != space.tenant_id:
                    return self._deny(request, "HARNESS_USER_SPACE_FORBIDDEN")
            except PermissionDenied:
                return self._deny(request, "HARNESS_APP_SPACE_FORBIDDEN")
        superusers = SpaceConfig.get_config(space.id, SuperusersConfig.name)
        if settings.BLOCK_ADMIN_PERMISSION or actor not in superusers:
            return self._deny(request, "HARNESS_USER_SPACE_FORBIDDEN")
        if SpaceConfig.get_config(space.id, HarnessEnabledConfig.name) != "true":
            return self._deny(request, "HARNESS_DISABLED")
        try:
            request.harness_space = space
            request.harness_context = TrustedHarnessContext.from_request(request, space_id=space.id, space=space)
        except HarnessContextError as error:
            return self._deny(request, error.code)
        return True

    def has_object_permission(self, request, view, obj):
        """Keep object-level checks fail-closed when a view invokes them."""
        return self.has_permission(request, view)
