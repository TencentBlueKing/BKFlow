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
from django.db import IntegrityError

from bkflow.space.models import Credential, CredentialScope, CredentialType, Space


@pytest.mark.django_db
class TestCredentialModel:
    """测试凭证模型"""

    @pytest.fixture
    def test_space(self):
        """创建测试空间"""
        space = Space.objects.create(name="test_space", app_code="test_app", creator="test_user")
        yield space
        space.hard_delete()

    @pytest.fixture
    def test_credential(self, test_space):
        """创建测试凭证"""
        credential = Credential.create_credential(
            space_id=test_space.id,
            name="test_credential",
            type=CredentialType.BK_APP.value,
            content={"bk_app_code": "app", "bk_app_secret": "secret"},
            creator="test_user",
            desc="Test credential",
        )
        yield credential
        credential.hard_delete()

    def test_create_credential(self, test_space):
        """测试创建凭证"""
        credential = Credential.create_credential(
            space_id=test_space.id,
            name="new_credential",
            type=CredentialType.BK_ACCESS_TOKEN.value,
            content={"access_token": "token123"},
            creator="test_user",
        )

        assert credential.id is not None
        assert credential.space_id == test_space.id
        assert credential.name == "new_credential"
        assert credential.type == CredentialType.BK_ACCESS_TOKEN.value
        assert credential.creator == "test_user"

        # 清理
        credential.hard_delete()

    def test_create_duplicate_credential_name(self, test_space, test_credential):
        """测试创建重复名称的凭证"""
        from django.db import transaction

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Credential.create_credential(
                    space_id=test_space.id,
                    name="test_credential",  # 与 fixture 中的名称重复
                    type=CredentialType.BK_APP.value,
                    content={"bk_app_code": "app2", "bk_app_secret": "secret2"},
                    creator="test_user",
                )

    def test_update_credential(self, test_credential):
        """测试更新凭证内容"""
        new_content = {"bk_app_code": "new_app", "bk_app_secret": "new_secret"}
        test_credential.update_credential(new_content)

        # 重新从数据库读取
        credential = Credential.objects.get(id=test_credential.id)
        assert credential.content == new_content

    def test_credential_value_property(self, test_credential):
        """测试凭证 value 属性"""
        value = test_credential.value
        assert isinstance(value, dict)
        assert "bk_app_code" in value
        assert "bk_app_secret" in value

    def test_credential_display_json(self, test_credential):
        """测试凭证 display_json 方法"""
        display = test_credential.display_json()
        assert display["id"] == test_credential.id
        assert display["space_id"] == test_credential.space_id
        assert display["type"] == test_credential.type
        assert "content" in display
        # bk_app_secret 应该被脱敏
        assert display["content"]["bk_app_secret"] == "*********"

    def test_soft_delete(self, test_credential):
        """测试软删除"""
        credential_id = test_credential.id
        test_credential.delete()

        # 验证软删除
        assert test_credential.is_deleted is True

        # 验证在查询中被过滤
        with pytest.raises(Credential.DoesNotExist):
            Credential.objects.get(id=credential_id, is_deleted=False)

        # 但仍然存在于数据库
        credential = Credential.objects.get(id=credential_id)
        assert credential.is_deleted is True

    def test_hard_delete(self, test_space):
        """测试硬删除"""
        credential = Credential.create_credential(
            space_id=test_space.id,
            name="to_be_deleted",
            type=CredentialType.CUSTOM.value,
            content={"key": "value"},
            creator="test_user",
        )
        credential_id = credential.id

        credential.hard_delete()

        # 验证已从数据库删除
        with pytest.raises(Credential.DoesNotExist):
            Credential.objects.get(id=credential_id)


@pytest.mark.django_db
class TestCredentialScope:
    """测试凭证作用域"""

    @pytest.fixture
    def test_space(self):
        """创建测试空间"""
        space = Space.objects.create(name="test_space", app_code="test_app", creator="test_user")
        yield space
        space.hard_delete()

    @pytest.fixture
    def test_credential(self, test_space):
        """创建测试凭证"""
        credential = Credential.create_credential(
            space_id=test_space.id,
            name="scoped_credential",
            type=CredentialType.BK_APP.value,
            content={"bk_app_code": "app", "bk_app_secret": "secret"},
            creator="test_user",
        )
        yield credential
        credential.hard_delete()

    def test_create_credential_scope(self, test_credential):
        """测试创建凭证作用域"""
        scope = CredentialScope.objects.create(
            credential_id=test_credential.id, scope_type="project", scope_value="project_1"
        )

        assert scope.id is not None
        assert scope.credential_id == test_credential.id
        assert scope.scope_type == "project"
        assert scope.scope_value == "project_1"

        # 清理
        scope.delete()

    def test_get_scopes(self, test_credential):
        """测试获取凭证的作用域列表"""
        # 创建多个作用域
        CredentialScope.objects.create(credential_id=test_credential.id, scope_type="project", scope_value="project_1")
        CredentialScope.objects.create(credential_id=test_credential.id, scope_type="project", scope_value="project_2")

        scopes = test_credential.get_scopes()
        assert scopes.count() == 2

        # 清理
        scopes.delete()

    def test_has_scope(self, test_credential):
        """测试检查凭证是否设置了作用域"""
        # 初始状态：没有作用域
        assert test_credential.has_scope() is False

        # 添加作用域
        CredentialScope.objects.create(credential_id=test_credential.id, scope_type="project", scope_value="project_1")

        # 现在应该有作用域
        assert test_credential.has_scope() is True

        # 清理
        test_credential.get_scopes().delete()

    def test_can_use_in_scope_without_scope(self, test_credential):
        """测试没有作用域限制的凭证不能被使用"""
        # 凭证没有设置作用域，不允许被使用
        assert test_credential.can_use_in_scope("project", "project_1") is False
        assert test_credential.can_use_in_scope(None, None) is False

    def test_can_use_in_scope_with_matching_scope(self, test_credential):
        """测试匹配作用域的凭证可以使用"""
        # 添加作用域
        CredentialScope.objects.create(credential_id=test_credential.id, scope_type="project", scope_value="project_1")

        # 匹配的作用域应该可以使用
        assert test_credential.can_use_in_scope("project", "project_1") is True

        # 不匹配的作用域不能使用
        assert test_credential.can_use_in_scope("project", "project_2") is False
        assert test_credential.can_use_in_scope("template", "template_1") is False

        # 清理
        test_credential.get_scopes().delete()

    def test_can_use_in_scope_with_template_no_scope(self, test_credential):
        """测试模板没有作用域时，有作用域的凭证也可以使用"""
        # 添加作用域
        CredentialScope.objects.create(credential_id=test_credential.id, scope_type="project", scope_value="project_1")

        # 模板没有作用域（都为 None），有作用域的凭证也可以使用
        assert test_credential.can_use_in_scope(None, None) is True

        # 清理
        test_credential.get_scopes().delete()

    def test_multiple_scopes(self, test_credential):
        """测试多个作用域"""
        # 添加多个作用域
        CredentialScope.objects.create(credential_id=test_credential.id, scope_type="project", scope_value="project_1")
        CredentialScope.objects.create(credential_id=test_credential.id, scope_type="project", scope_value="project_2")

        # 两个作用域都应该可以使用
        assert test_credential.can_use_in_scope("project", "project_1") is True
        assert test_credential.can_use_in_scope("project", "project_2") is True

        # 其他作用域不能使用
        assert test_credential.can_use_in_scope("project", "project_3") is False

        # 清理
        test_credential.get_scopes().delete()
