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

from bkflow.space.credential.resolver import resolve_credentials
from bkflow.space.exceptions import (
    CredentialNotFoundError,
    CredentialScopeValidationError,
)
from bkflow.space.models import (
    Credential,
    CredentialScope,
    CredentialScopeLevel,
    CredentialType,
    Space,
)


@pytest.mark.django_db
class TestResolveCredentials:
    """测试凭证解析器"""

    @pytest.fixture
    def test_space(self):
        """创建测试空间"""
        space = Space.objects.create(name="test_space", app_code="test_app", creator="test_user")
        yield space
        space.hard_delete()

    @pytest.fixture
    def test_credential(self, test_space):
        """创建测试凭证（有作用域）"""
        credential = Credential.create_credential(
            space_id=test_space.id,
            name="test_credential",
            type=CredentialType.BK_APP.value,
            content={"bk_app_code": "app", "bk_app_secret": "secret"},
            creator="test_user",
            scope_level=CredentialScopeLevel.PART.value,
        )
        # 添加默认作用域
        CredentialScope.objects.create(credential_id=credential.id, scope_type="test", scope_value="test_1")
        yield credential
        credential.hard_delete()

    @pytest.fixture
    def scoped_credential(self, test_space):
        """创建有作用域的凭证"""
        credential = Credential.create_credential(
            space_id=test_space.id,
            name="scoped_credential",
            type=CredentialType.BASIC_AUTH.value,
            content={"username": "admin", "password": "secret"},
            creator="test_user",
            scope_level=CredentialScopeLevel.PART.value,
        )
        CredentialScope.objects.create(credential_id=credential.id, scope_type="project", scope_value="project_1")
        yield credential
        credential.hard_delete()

    def test_resolve_empty_credentials(self, test_space):
        """测试解析空凭证字典"""
        result = resolve_credentials({}, test_space.id, None, None)
        assert result == {}

    def test_resolve_none_credentials(self, test_space):
        """测试解析 None"""
        result = resolve_credentials(None, test_space.id, None, None)
        assert result == {}

    def test_resolve_credential_by_id(self, test_space, test_credential):
        """测试通过 ID 解析凭证"""
        credentials_dict = {
            "${token1}": {
                "desc": "测试凭证",
                "index": 1,
                "key": "${token1}",
                "name": "凭证1",
                "show_type": "show",
                "value": str(test_credential.id),
                "version": "legacy",
            }
        }

        result = resolve_credentials(credentials_dict, test_space.id, "test", "test_1")  # 匹配fixture中的作用域

        assert "${token1}" in result
        assert result["${token1}"]["credential_id"] == test_credential.id
        assert result["${token1}"]["credential_name"] == "test_credential"
        assert result["${token1}"]["credential_type"] == CredentialType.BK_APP.value
        # value 应该是解密后的实际内容
        assert isinstance(result["${token1}"]["value"], dict)

    def test_resolve_credential_by_int_id(self, test_space, test_credential):
        """测试通过整数 ID 解析凭证"""
        credentials_dict = {"${token1}": {"value": test_credential.id, "name": "凭证1"}}  # 整数类型

        result = resolve_credentials(credentials_dict, test_space.id, "test", "test_1")  # 匹配fixture中的作用域

        assert "${token1}" in result
        assert result["${token1}"]["credential_id"] == test_credential.id

    def test_resolve_non_existent_credential(self, test_space):
        """测试解析不存在的凭证"""
        credentials_dict = {"${token1}": {"value": "99999", "name": "不存在的凭证"}}  # 不存在的 ID

        with pytest.raises(CredentialNotFoundError) as exc_info:
            resolve_credentials(credentials_dict, test_space.id, None, None)
        assert "不存在" in str(exc_info.value)

    def test_resolve_credential_with_scope_validation_pass(self, test_space, scoped_credential):
        """测试解析凭证时作用域验证通过"""
        credentials_dict = {"${token1}": {"value": str(scoped_credential.id), "name": "作用域凭证"}}

        # 匹配的作用域应该通过
        result = resolve_credentials(credentials_dict, test_space.id, "project", "project_1")

        assert "${token1}" in result
        assert result["${token1}"]["credential_id"] == scoped_credential.id

    def test_resolve_credential_with_scope_validation_fail(self, test_space, scoped_credential):
        """测试解析凭证时作用域验证失败"""
        credentials_dict = {"${token1}": {"value": str(scoped_credential.id), "name": "作用域凭证"}}

        # 不匹配的作用域应该失败
        with pytest.raises(CredentialScopeValidationError):
            resolve_credentials(credentials_dict, test_space.id, "project", "project_2")  # 不匹配

    def test_resolve_direct_value(self, test_space):
        """测试解析直接提供的值（非 ID）"""
        credentials_dict = {"${token1}": {"value": "direct_token_value", "name": "直接值"}}  # 不是数字，直接使用

        result = resolve_credentials(credentials_dict, test_space.id, None, None)

        assert "${token1}" in result
        assert result["${token1}"]["value"] == "direct_token_value"
        assert "credential_id" not in result["${token1}"]

    def test_resolve_multiple_credentials(self, test_space, test_credential, scoped_credential):
        """测试解析多个凭证"""
        # 添加匹配的作用域到 scoped_credential
        CredentialScope.objects.create(credential_id=scoped_credential.id, scope_type="test", scope_value="test_1")

        credentials_dict = {
            "${token1}": {"value": str(test_credential.id), "name": "凭证1"},
            "${token2}": {"value": str(scoped_credential.id), "name": "凭证2"},
            "${token3}": {"value": "direct_value", "name": "直接值"},
        }

        result = resolve_credentials(credentials_dict, test_space.id, "test", "test_1")  # 匹配作用域

        assert len(result) == 3
        assert "${token1}" in result
        assert "${token2}" in result
        assert "${token3}" in result
        assert result["${token1}"]["credential_id"] == test_credential.id
        assert result["${token2}"]["credential_id"] == scoped_credential.id
        assert result["${token3}"]["value"] == "direct_value"

    def test_resolve_credential_with_empty_value(self, test_space):
        """测试解析空值的凭证"""
        credentials_dict = {"${token1}": {"value": "", "name": "空值凭证"}}  # 空值

        result = resolve_credentials(credentials_dict, test_space.id, None, None)

        # 空值应该被跳过或保持原样
        assert "${token1}" in result
        assert result["${token1}"]["value"] == ""
