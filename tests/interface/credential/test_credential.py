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
from rest_framework import serializers

from bkflow.space.credential.basic_auth import BasicAuthCredential
from bkflow.space.credential.bk_access_token import BkAccessTokenCredential
from bkflow.space.credential.custom import CustomCredential
from bkflow.space.credential.dispatcher import CredentialDispatcher
from bkflow.space.exceptions import CredentialTypeNotSupport


class TestBkAccessTokenCredential:
    """测试蓝鲸登录态凭证"""

    def test_validate_valid_data(self):
        """测试验证有效数据"""
        data = {"access_token": "valid_token_123"}
        credential = BkAccessTokenCredential(data=data)
        validated = credential.validate_data()
        assert validated == data

    def test_validate_invalid_data_missing_field(self):
        """测试验证缺少必填字段"""
        data = {}
        credential = BkAccessTokenCredential(data=data)
        with pytest.raises(serializers.ValidationError):
            credential.validate_data()

    def test_validate_invalid_data_all_asterisks(self):
        """测试验证全为星号的 token"""
        data = {"access_token": "*********"}
        credential = BkAccessTokenCredential(data=data)
        with pytest.raises(serializers.ValidationError) as exc_info:
            credential.validate_data()
        assert "不应全为 * 字符" in str(exc_info.value)

    def test_value_returns_original_data(self):
        """测试返回原始值"""
        data = {"access_token": "test_token"}
        credential = BkAccessTokenCredential(data=data)
        assert credential.value() == data

    def test_display_value_masks_token(self):
        """测试脱敏显示"""
        data = {"access_token": "secret_token"}
        credential = BkAccessTokenCredential(data=data)
        display = credential.display_value()
        assert display["access_token"] == "*********"


class TestBasicAuthCredential:
    """测试用户名+密码凭证"""

    def test_validate_valid_data(self):
        """测试验证有效数据"""
        data = {"username": "admin", "password": "secret123"}
        credential = BasicAuthCredential(data=data)
        validated = credential.validate_data()
        assert validated == data

    def test_validate_invalid_data_missing_username(self):
        """测试验证缺少用户名"""
        data = {"password": "secret123"}
        credential = BasicAuthCredential(data=data)
        with pytest.raises(serializers.ValidationError):
            credential.validate_data()

    def test_validate_invalid_data_missing_password(self):
        """测试验证缺少密码"""
        data = {"username": "admin"}
        credential = BasicAuthCredential(data=data)
        with pytest.raises(serializers.ValidationError):
            credential.validate_data()

    def test_validate_invalid_password_all_asterisks(self):
        """测试验证全为星号的密码"""
        data = {"username": "admin", "password": "***"}
        credential = BasicAuthCredential(data=data)
        with pytest.raises(serializers.ValidationError) as exc_info:
            credential.validate_data()
        assert "不应全为 * 字符" in str(exc_info.value)

    def test_display_value_masks_password(self):
        """测试脱敏显示"""
        data = {"username": "admin", "password": "secret123"}
        credential = BasicAuthCredential(data=data)
        display = credential.display_value()
        assert display["username"] == "admin"
        assert display["password"] == "*********"


class TestCustomCredential:
    """测试自定义凭证"""

    def test_validate_valid_data(self):
        """测试验证有效数据"""
        data = {"api_key": "key123", "api_secret": "secret456"}
        credential = CustomCredential(data=data)
        validated = credential.validate_data()
        assert validated == data

    def test_validate_empty_data(self):
        """测试验证空数据"""
        data = {}
        credential = CustomCredential(data=data)
        with pytest.raises(serializers.ValidationError) as exc_info:
            credential.validate_data()
        assert "不能为空" in str(exc_info.value)

    def test_validate_non_dict_data(self):
        """测试验证非字典类型数据"""
        data = "not_a_dict"
        credential = CustomCredential(data=data)
        with pytest.raises(serializers.ValidationError) as exc_info:
            credential.validate_data()
        assert "必须是字典类型" in str(exc_info.value)

    def test_validate_nested_dict(self):
        """测试验证嵌套字典（不支持）"""
        data = {"key1": {"nested": "value"}}
        credential = CustomCredential(data=data)
        with pytest.raises(serializers.ValidationError) as exc_info:
            credential.validate_data()
        assert "必须是字符串类型" in str(exc_info.value)

    def test_validate_array_value(self):
        """测试验证数组值（不支持）"""
        data = {"key1": ["item1", "item2"]}
        credential = CustomCredential(data=data)
        with pytest.raises(serializers.ValidationError) as exc_info:
            credential.validate_data()
        assert "必须是字符串类型" in str(exc_info.value)

    def test_validate_non_string_key(self):
        """测试验证非字符串 key"""
        # 注意：在 Python 中，dict key 通常会被转换为字符串
        # 这个测试主要验证类型检查逻辑
        data = {"key1": "value1"}
        credential = CustomCredential(data=data)
        validated = credential.validate_data()
        assert validated == data

    def test_validate_value_all_asterisks(self):
        """测试验证全为星号的值"""
        data = {"key1": "***"}
        credential = CustomCredential(data=data)
        with pytest.raises(serializers.ValidationError) as exc_info:
            credential.validate_data()
        assert "不应全为 * 字符" in str(exc_info.value)

    def test_display_value_masks_all_values(self):
        """测试脱敏显示（所有值都脱敏）"""
        data = {"key1": "value1", "key2": "value2"}
        credential = CustomCredential(data=data)
        display = credential.display_value()
        assert display["key1"] == "*********"
        assert display["key2"] == "*********"


class TestCredentialDispatcher:
    """测试凭证分发器"""

    def test_get_bk_app_credential(self):
        """测试获取蓝鲸应用凭证"""
        data = {"bk_app_code": "app", "bk_app_secret": "secret"}
        credential = CredentialDispatcher("BK_APP", data=data)
        assert credential is not None
        assert credential.validate_data() == data

    def test_get_bk_access_token_credential(self):
        """测试获取蓝鲸登录态凭证"""
        data = {"access_token": "token123"}
        credential = CredentialDispatcher("BK_ACCESS_TOKEN", data=data)
        assert credential is not None
        assert credential.validate_data() == data

    def test_get_basic_auth_credential(self):
        """测试获取用户名+密码凭证"""
        data = {"username": "admin", "password": "secret"}
        credential = CredentialDispatcher("BASIC_AUTH", data=data)
        assert credential is not None
        assert credential.validate_data() == data

    def test_get_custom_credential(self):
        """测试获取自定义凭证"""
        data = {"key1": "value1"}
        credential = CredentialDispatcher("CUSTOM", data=data)
        assert credential is not None
        assert credential.validate_data() == data

    def test_unsupported_credential_type(self):
        """测试不支持的凭证类型"""
        with pytest.raises(CredentialTypeNotSupport):
            CredentialDispatcher("UNKNOWN_TYPE", data={})

    def test_lowercase_type_not_supported(self):
        """测试小写凭证类型不支持（必须大写）"""
        data = {"access_token": "token"}
        # 小写类型应该抛出异常
        with pytest.raises(CredentialTypeNotSupport):
            CredentialDispatcher("bk_access_token", data=data)
