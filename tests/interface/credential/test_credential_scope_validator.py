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

from bkflow.space.credential.scope_validator import (
    filter_credentials_by_scope,
    validate_credential_scope,
)
from bkflow.space.exceptions import CredentialScopeValidationError
from bkflow.space.models import (
    Credential,
    CredentialScope,
    CredentialScopeLevel,
    CredentialType,
    Space,
)


@pytest.mark.django_db
class TestValidateCredentialScope:
    """测试凭证作用域验证"""

    @pytest.fixture
    def test_space(self):
        """创建测试空间"""
        space = Space.objects.create(name="test_space", app_code="test_app", creator="test_user")
        yield space
        space.hard_delete()

    @pytest.fixture
    def credential_with_scope(self, test_space):
        """创建有作用域限制的凭证"""
        credential = Credential.create_credential(
            space_id=test_space.id,
            name="scoped_credential",
            type=CredentialType.BK_APP.value,
            content={"bk_app_code": "app", "bk_app_secret": "secret"},
            creator="test_user",
            scope_level=CredentialScopeLevel.PART.value,
        )
        CredentialScope.objects.create(credential_id=credential.id, scope_type="project", scope_value="project_1")
        yield credential
        credential.hard_delete()

    @pytest.fixture
    def credential_without_scope(self, test_space):
        """创建没有作用域限制的凭证（scope_level == ALL）"""
        credential = Credential.create_credential(
            space_id=test_space.id,
            name="no_scope_credential",
            type=CredentialType.BASIC_AUTH.value,
            content={"username": "admin", "password": "secret"},
            creator="test_user",
            scope_level=CredentialScopeLevel.ALL.value,
        )
        yield credential
        credential.hard_delete()

    def test_validate_credential_with_matching_scope(self, credential_with_scope):
        """测试验证匹配作用域的凭证"""
        # 应该通过验证
        result = validate_credential_scope(credential_with_scope, "project", "project_1")
        assert result is True

    def test_validate_credential_with_non_matching_scope(self, credential_with_scope):
        """测试验证不匹配作用域的凭证"""
        # 应该抛出异常
        with pytest.raises(CredentialScopeValidationError) as exc_info:
            validate_credential_scope(credential_with_scope, "project", "project_2")
        assert "不能在作用域" in str(exc_info.value)

    def test_validate_credential_without_scope_fails(self, credential_without_scope):
        """测试验证 scope_level == ALL 的凭证（应该可以使用）"""
        # scope_level == ALL 的凭证可以在任何地方使用
        result = validate_credential_scope(credential_without_scope, "project", "project_1")
        assert result is True

    def test_validate_credential_with_scope_on_template_without_scope(self, credential_with_scope):
        """测试在没有作用域的模板中使用 scope_level == PART 的凭证（应该失败）"""
        # 模板没有作用域，scope_level == PART 的凭证不能使用
        with pytest.raises(CredentialScopeValidationError):
            validate_credential_scope(credential_with_scope, None, None)


@pytest.mark.django_db
class TestFilterCredentialsByScope:
    """测试根据作用域过滤凭证"""

    @pytest.fixture
    def test_space(self):
        """创建测试空间"""
        space = Space.objects.create(name="test_space", app_code="test_app", creator="test_user")
        yield space
        space.hard_delete()

    @pytest.fixture
    def setup_credentials(self, test_space):
        """创建测试凭证"""
        # 1. scope_level == ALL 的凭证（空间内开放，可以在任何地方使用）
        cred1 = Credential.create_credential(
            space_id=test_space.id,
            name="no_scope",
            type=CredentialType.BK_APP.value,
            content={"bk_app_code": "app1", "bk_app_secret": "secret1"},
            creator="test_user",
            scope_level=CredentialScopeLevel.ALL.value,
        )

        # 2. scope_level == PART 且有匹配作用域的凭证
        cred2 = Credential.create_credential(
            space_id=test_space.id,
            name="matching_scope",
            type=CredentialType.BK_APP.value,
            content={"bk_app_code": "app2", "bk_app_secret": "secret2"},
            creator="test_user",
            scope_level=CredentialScopeLevel.PART.value,
        )
        CredentialScope.objects.create(credential_id=cred2.id, scope_type="project", scope_value="project_1")

        # 3. scope_level == PART 且有不匹配作用域的凭证
        cred3 = Credential.create_credential(
            space_id=test_space.id,
            name="non_matching_scope",
            type=CredentialType.BK_APP.value,
            content={"bk_app_code": "app3", "bk_app_secret": "secret3"},
            creator="test_user",
            scope_level=CredentialScopeLevel.PART.value,
        )
        CredentialScope.objects.create(credential_id=cred3.id, scope_type="project", scope_value="project_2")

        yield {"no_scope": cred1, "matching": cred2, "non_matching": cred3}

        # 清理
        cred1.hard_delete()
        cred2.hard_delete()
        cred3.hard_delete()

    def test_filter_with_no_template_scope(self, test_space, setup_credentials):
        """测试模板没有作用域时的过滤"""
        queryset = Credential.objects.filter(space_id=test_space.id, is_deleted=False)

        # 模板没有作用域，只应该返回 scope_level == ALL 的凭证
        filtered = filter_credentials_by_scope(queryset, None, None)
        assert filtered.count() == 1
        assert filtered.first().name == "no_scope"

    def test_filter_with_matching_scope(self, test_space, setup_credentials):
        """测试匹配作用域的过滤"""
        queryset = Credential.objects.filter(space_id=test_space.id, is_deleted=False)

        # 应该返回：scope_level == ALL 的凭证 + scope_level == PART 且作用域匹配的凭证
        filtered = filter_credentials_by_scope(queryset, "project", "project_1")

        # 应该只有 2 个凭证：no_scope (ALL) 和 matching_scope (PART 且匹配)
        assert filtered.count() == 2
        names = [c.name for c in filtered]
        assert "no_scope" in names
        assert "matching_scope" in names
        assert "non_matching_scope" not in names

    def test_filter_with_non_existing_scope(self, test_space, setup_credentials):
        """测试不存在的作用域过滤"""
        queryset = Credential.objects.filter(space_id=test_space.id, is_deleted=False)

        # 只应该返回 scope_level == ALL 的凭证（空间内开放，可以在任何地方使用）
        filtered = filter_credentials_by_scope(queryset, "project", "project_999")

        assert filtered.count() == 1
        assert filtered.first().name == "no_scope"

    def test_filter_empty_queryset(self, test_space):
        """测试空查询集的过滤"""
        queryset = Credential.objects.filter(space_id=99999)  # 不存在的 space_id

        filtered = filter_credentials_by_scope(queryset, "project", "project_1")
        assert filtered.count() == 0
