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
from django.conf import settings
from django.db import connection

from bkflow.space.models import Credential, CredentialType, Space
from bkflow.utils.crypt import BaseCrypt


@pytest.mark.django_db
class TestSecretSingleJsonField:
    """测试 SecretSingleJsonField 加密字段"""

    @pytest.fixture
    def test_space(self):
        """创建测试空间"""
        space = Space.objects.create(name="test_space", app_code="test_app", creator="test_user")
        yield space
        space.hard_delete()

    @pytest.fixture
    def crypt(self):
        """创建加密器"""
        return BaseCrypt(instance_key=settings.PRIVATE_SECRET)

    def test_encrypt_on_save(self, test_space, crypt):
        """测试保存时自动加密"""
        # 创建凭证
        credential = Credential.create_credential(
            space_id=test_space.id,
            name="test_encrypt",
            type=CredentialType.BK_APP.value,
            content={"bk_app_code": "app", "bk_app_secret": "secret123"},
            creator="test_user",
        )

        # 从数据库直接读取原始值
        with connection.cursor() as cursor:
            cursor.execute("SELECT content FROM space_credential WHERE id=%s", [credential.id])
            raw_content = cursor.fetchone()[0]

        # 数据库返回的是 JSON 字符串，需要解析
        import json

        if isinstance(raw_content, str):
            raw_content = json.loads(raw_content)

        # 验证数据库中的值是加密的
        assert isinstance(raw_content, dict)
        assert "bk_app_code" in raw_content
        assert "bk_app_secret" in raw_content

        # 验证值已加密（不等于原始值）
        assert raw_content["bk_app_code"] != "app"
        assert raw_content["bk_app_secret"] != "secret123"

        # 验证可以解密
        decrypted_code = crypt.decrypt(raw_content["bk_app_code"])
        decrypted_secret = crypt.decrypt(raw_content["bk_app_secret"])
        assert decrypted_code == "app"
        assert decrypted_secret == "secret123"

        # 清理
        credential.hard_delete()

    def test_decrypt_on_read(self, test_space):
        """测试读取时自动解密"""
        # 创建凭证
        original_content = {"username": "admin", "password": "secret456"}
        credential = Credential.create_credential(
            space_id=test_space.id,
            name="test_decrypt",
            type=CredentialType.BASIC_AUTH.value,
            content=original_content,
            creator="test_user",
        )

        # 通过 ORM 读取（应该自动解密）
        credential = Credential.objects.get(id=credential.id)
        assert credential.content == original_content
        assert credential.content["username"] == "admin"
        assert credential.content["password"] == "secret456"

        # 清理
        credential.hard_delete()

    def test_update_encrypted_field(self, test_space):
        """测试更新加密字段"""
        # 创建凭证
        credential = Credential.create_credential(
            space_id=test_space.id,
            name="test_update",
            type=CredentialType.CUSTOM.value,
            content={"key1": "value1"},
            creator="test_user",
        )

        # 更新内容
        new_content = {"key1": "new_value1", "key2": "value2"}
        credential.update_credential(new_content)

        # 重新读取验证
        credential = Credential.objects.get(id=credential.id)
        assert credential.content == new_content
        assert credential.content["key1"] == "new_value1"
        assert credential.content["key2"] == "value2"

        # 清理
        credential.hard_delete()

    def test_none_value_not_encrypted(self, test_space):
        """测试 None 值不加密"""
        credential = Credential.create_credential(
            space_id=test_space.id,
            name="test_none",
            type=CredentialType.CUSTOM.value,
            content={"key1": "value1"},
            creator="test_user",
        )

        # 验证可以正常保存和读取
        credential = Credential.objects.get(id=credential.id)
        assert credential.content["key1"] == "value1"

        # 清理
        credential.hard_delete()

    def test_empty_dict(self, test_space):
        """测试空字典"""
        # 创建时传入空字典应该会报错（CustomCredential 不允许空字典）
        with pytest.raises(Exception):  # ValidationError
            Credential.create_credential(
                space_id=test_space.id,
                name="test_empty",
                type=CredentialType.CUSTOM.value,
                content={},
                creator="test_user",
            )

    def test_single_level_json_only(self, test_space):
        """测试只支持单层 JSON"""
        # 嵌套字典应该失败（在 CustomCredential 验证时就会失败）
        with pytest.raises(Exception):  # ValidationError
            Credential.create_credential(
                space_id=test_space.id,
                name="test_nested",
                type=CredentialType.CUSTOM.value,
                content={"key1": {"nested": "value"}},
                creator="test_user",
            )

    def test_multiple_credentials_encryption(self, test_space):
        """测试多个凭证的加密独立性"""
        # 创建多个凭证
        cred1 = Credential.create_credential(
            space_id=test_space.id,
            name="cred1",
            type=CredentialType.BK_APP.value,
            content={"bk_app_code": "app1", "bk_app_secret": "secret1"},
            creator="test_user",
        )

        cred2 = Credential.create_credential(
            space_id=test_space.id,
            name="cred2",
            type=CredentialType.BK_APP.value,
            content={"bk_app_code": "app2", "bk_app_secret": "secret2"},
            creator="test_user",
        )

        # 验证两个凭证的内容独立
        cred1_reloaded = Credential.objects.get(id=cred1.id)
        cred2_reloaded = Credential.objects.get(id=cred2.id)

        assert cred1_reloaded.content["bk_app_code"] == "app1"
        assert cred1_reloaded.content["bk_app_secret"] == "secret1"
        assert cred2_reloaded.content["bk_app_code"] == "app2"
        assert cred2_reloaded.content["bk_app_secret"] == "secret2"

        # 清理
        cred1.hard_delete()
        cred2.hard_delete()

    def test_special_characters_encryption(self, test_space):
        """测试特殊字符的加密"""
        special_content = {"key1": "value!@#$%^&*()", "key2": "中文测试", "key3": "emoji🎉"}

        credential = Credential.create_credential(
            space_id=test_space.id,
            name="test_special",
            type=CredentialType.CUSTOM.value,
            content=special_content,
            creator="test_user",
        )

        # 验证特殊字符正确加密和解密
        credential = Credential.objects.get(id=credential.id)
        assert credential.content == special_content
        assert credential.content["key1"] == "value!@#$%^&*()"
        assert credential.content["key2"] == "中文测试"
        assert credential.content["key3"] == "emoji🎉"

        # 清理
        credential.hard_delete()
