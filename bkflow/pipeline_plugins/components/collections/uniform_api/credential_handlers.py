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
from typing import Optional, Tuple

from django.conf import settings


class UniformAPICredentialHandler:
    """凭证处理器基类"""

    def __init__(self, logger, scope_type: Optional[str], scope_id: Optional[str], parent_data, space_configs: dict):
        self.logger = logger
        self.scope_type = scope_type
        self.scope_id = scope_id
        self.parent_data = parent_data
        self.space_configs = space_configs

    def can_handle(self, credential_key: Optional[str] = None) -> bool:
        """判断是否能处理当前情况"""
        raise NotImplementedError

    def get_credential(self, credential_key: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """获取凭证，返回 (app_code, app_secret)"""
        raise NotImplementedError

    def get_name(self) -> str:
        """返回处理器名称，用于日志"""
        return self.__class__.__name__

    def _get_api_gateway_credential_name(self) -> Optional[str]:
        """从空间配置中获取 api_gateway_credential_name"""
        api_gateway_credential_name_config = self.space_configs.get("api_gateway_credential_name")
        if not api_gateway_credential_name_config:
            return None

        if isinstance(api_gateway_credential_name_config, str):
            return api_gateway_credential_name_config
        elif isinstance(api_gateway_credential_name_config, dict):
            scope = f"{self.scope_type}_{self.scope_id}" if self.scope_type and self.scope_id else None
            if scope and scope in api_gateway_credential_name_config:
                return api_gateway_credential_name_config[scope]
            elif "default" in api_gateway_credential_name_config:
                return api_gateway_credential_name_config["default"]
        return None


class CredentialKeyUserProvidedHandler(UniformAPICredentialHandler):
    """从用户传入的 credentials 中获取 credential_key 对应的凭证"""

    def can_handle(self, credential_key: Optional[str] = None) -> bool:
        if not credential_key:
            return False
        credentials = self.parent_data.inputs.get("credentials", {})
        return credential_key in credentials

    def get_credential(self, credential_key: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        credentials = self.parent_data.inputs.get("credentials", {})
        credential_dict = credentials[credential_key]
        if isinstance(credential_dict, dict):
            app_code = credential_dict.get("bk_app_code")
            app_secret = credential_dict.get("bk_app_secret")
            self.logger.info(f"[uniform_api] using user-provided credential from credential_key: {credential_key}")
            return app_code, app_secret
        else:
            self.logger.warning(f"[uniform_api] Credential {credential_key} from credentials is not a valid dict")
            return None, None


class CredentialKeySpaceConfigHandler(UniformAPICredentialHandler):
    """当 credential_key 匹配空间配置的 api_gateway_credential_name 时，使用空间配置的凭证"""

    def can_handle(self, credential_key: Optional[str] = None) -> bool:
        if not credential_key:
            return False
        api_gateway_credential_name = self._get_api_gateway_credential_name()
        return credential_key == api_gateway_credential_name

    def get_credential(self, credential_key: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        credential_data = self.space_configs.get("credential")
        if credential_data:
            app_code = credential_data["bk_app_code"]
            app_secret = credential_data["bk_app_secret"]
            self.logger.info(
                f"[uniform_api] using space credential config for credential_key"
                f": {credential_key}, app_code: {app_code}"
            )
            return app_code, app_secret
        return None, None


class ApiGatewayCredentialNameUserProvidedHandler(UniformAPICredentialHandler):
    """当没有 credential_key 时，从用户传入的 credentials 中获取 api_gateway_credential_name 对应的凭证"""

    def can_handle(self, credential_key: Optional[str] = None) -> bool:
        if credential_key:
            return False
        api_gateway_credential_name = self._get_api_gateway_credential_name()
        if not api_gateway_credential_name:
            return False
        credentials = self.parent_data.inputs.get("credentials", {})
        return api_gateway_credential_name in credentials

    def get_credential(self, credential_key: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        api_gateway_credential_name = self._get_api_gateway_credential_name()
        credentials = self.parent_data.inputs.get("credentials", {})
        credential_dict = credentials[api_gateway_credential_name]
        if isinstance(credential_dict, dict):
            app_code = credential_dict.get("bk_app_code")
            app_secret = credential_dict.get("bk_app_secret")
            self.logger.info(f"[uniform_api] using user-provided credential: {api_gateway_credential_name}")
            return app_code, app_secret
        else:
            self.logger.warning(f"[uniform_api] Credential {api_gateway_credential_name} is not a valid dict")
            return None, None


class SpaceCredentialHandler(UniformAPICredentialHandler):
    """从空间配置的 credential 中获取凭证"""

    def can_handle(self, credential_key: Optional[str] = None) -> bool:
        credential_data = self.space_configs.get("credential")
        return credential_data is not None

    def get_credential(self, credential_key: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        credential_data = self.space_configs.get("credential")
        app_code = credential_data["bk_app_code"]
        app_secret = credential_data["bk_app_secret"]
        self.logger.info(f"[uniform_api] using credential config app_code: {app_code}")
        return app_code, app_secret


class DefaultCredentialHandler(UniformAPICredentialHandler):
    """使用默认凭证（settings）"""

    def can_handle(self, credential_key: Optional[str] = None) -> bool:
        return settings.USE_BKFLOW_CREDENTIAL

    def get_credential(self, credential_key: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        self.logger.info("using bkflow credential")
        return settings.APP_CODE, settings.SECRET_KEY
