"""Test handler utils"""
from unittest import mock

from bkflow.utils.handlers import (
    CREDENTIAL_MASK,
    handle_api_error,
    handle_plain_log,
    mask_credential_values,
    mask_credentials_in_string,
    mask_sensitive_data_for_display,
)


class TestHandlerUtils:
    """Test handler utility functions"""

    @mock.patch("bkflow.utils.handlers.settings")
    def test_handlers(self, mock_settings):
        """Test handler utilities"""
        # Handle API error
        mock_settings.LOG_SHIELDING_KEYWORDS = []
        message = handle_api_error(
            "test_system", "test_api", {"param": "value"}, {"message": "API failed", "request_id": "req123"}
        )
        assert "test_system" in message
        assert "req123" in message

        message = handle_api_error("system", "api", {}, {"message": "API failed"})
        assert "system" in message

        # Handle plain log
        mock_settings.LOG_SHIELDING_KEYWORDS = ["password", "secret"]
        result = handle_plain_log("User password is 12345 and secret is abc")
        assert "password" not in result
        assert "******" in result

        assert handle_plain_log(None) is None

        mock_settings.LOG_SHIELDING_KEYWORDS = []
        assert handle_plain_log("Normal log message") == "Normal log message"


class TestCredentialMasking:
    """Test credential masking functions"""

    def test_mask_credential_values_with_dict(self):
        """Test masking credentials in a dictionary"""
        data = {
            "credentials": {
                "my_cred": {
                    "bk_app_code": "app123",
                    "bk_app_secret": "secret123",
                    "token": "token123",
                }
            },
            "other_field": "value",
        }

        result = mask_credential_values(data)

        # Original data should not be modified
        assert data["credentials"]["my_cred"]["bk_app_secret"] == "secret123"

        # Result should have masked sensitive fields
        assert result["credentials"]["my_cred"]["bk_app_code"] == "app123"  # Not sensitive
        assert result["credentials"]["my_cred"]["bk_app_secret"] == CREDENTIAL_MASK
        assert result["credentials"]["my_cred"]["token"] == CREDENTIAL_MASK
        assert result["other_field"] == "value"

    def test_mask_credential_values_with_nested_dict(self):
        """Test masking credentials in a nested dictionary"""
        data = {
            "outer": {
                "credentials": {
                    "nested_cred": {
                        "password": "pass123",
                        "api_key": "key123",
                    }
                }
            }
        }

        result = mask_credential_values(data)

        assert result["outer"]["credentials"]["nested_cred"]["password"] == CREDENTIAL_MASK
        assert result["outer"]["credentials"]["nested_cred"]["api_key"] == CREDENTIAL_MASK

    def test_mask_credential_values_with_list(self):
        """Test masking credentials in a list of dictionaries"""
        data = [
            {"credentials": {"cred1": {"secret": "secret1"}}},
            {"credentials": {"cred2": {"secret": "secret2"}}},
        ]

        result = mask_credential_values(data)

        assert result[0]["credentials"]["cred1"]["secret"] == CREDENTIAL_MASK
        assert result[1]["credentials"]["cred2"]["secret"] == CREDENTIAL_MASK

    def test_mask_credential_values_in_place(self):
        """Test in-place modification of data"""
        data = {"credentials": {"my_cred": {"bk_app_secret": "secret123"}}}

        result = mask_credential_values(data, in_place=True)

        # Both should point to the same modified data
        assert result is data
        assert data["credentials"]["my_cred"]["bk_app_secret"] == CREDENTIAL_MASK

    def test_mask_credential_values_with_string_credential(self):
        """Test masking when credential value is a string"""
        data = {"credentials": {"simple_token": "raw_token_value"}}

        result = mask_credential_values(data)

        assert result["credentials"]["simple_token"] == CREDENTIAL_MASK

    def test_mask_credential_values_unknown_sensitive_fields(self):
        """Test that credentials with unknown field names are fully masked"""
        # 当凭证字典中没有已知的敏感字段时，整个字典应该被脱敏为 "{***}"
        data = {
            "credentials": {
                "custom_cred": {
                    "custom_key": "custom_secret_value",
                    "another_field": "another_value",
                }
            }
        }

        result = mask_credential_values(data)

        # 整个字典应该被替换为 "{***}"
        assert result["credentials"]["custom_cred"] == "{***}"

    def test_mask_credential_values_mixed_known_and_unknown(self):
        """Test mixed case: one credential has known fields, another doesn't"""
        data = {
            "credentials": {
                "known_cred": {
                    "bk_app_code": "app123",
                    "bk_app_secret": "secret123",
                },
                "unknown_cred": {
                    "my_custom_secret": "custom_value",
                },
            }
        }

        result = mask_credential_values(data)

        # known_cred: 只有敏感字段被脱敏
        assert result["credentials"]["known_cred"]["bk_app_code"] == "app123"
        assert result["credentials"]["known_cred"]["bk_app_secret"] == CREDENTIAL_MASK
        # unknown_cred: 整个字典被脱敏
        assert result["credentials"]["unknown_cred"] == "{***}"

    def test_mask_credential_values_with_none(self):
        """Test that None input returns None"""
        assert mask_credential_values(None) is None

    def test_mask_credential_values_no_credentials(self):
        """Test that data without credentials is unchanged"""
        data = {"name": "test", "value": 123}

        result = mask_credential_values(data)

        assert result == data
        assert result is not data  # Should be a copy

    def test_mask_credentials_in_string_json_format(self):
        """Test masking in JSON-like string"""
        text = '{"bk_app_secret": "mysecret", "bk_app_code": "mycode"}'

        result = mask_credentials_in_string(text)

        assert "mysecret" not in result
        assert CREDENTIAL_MASK in result
        assert "mycode" in result  # Non-sensitive field should remain

    def test_mask_credentials_in_string_python_format(self):
        """Test masking in Python dict string format"""
        text = "{'token': 'mytoken', 'name': 'test'}"

        result = mask_credentials_in_string(text)

        assert "mytoken" not in result
        assert CREDENTIAL_MASK in result
        assert "test" in result

    def test_mask_credentials_in_string_multiple_fields(self):
        """Test masking multiple sensitive fields"""
        text = '{"password": "pass123", "api_key": "key456", "username": "user1"}'

        result = mask_credentials_in_string(text)

        assert "pass123" not in result
        assert "key456" not in result
        assert "user1" in result  # username is not sensitive

    def test_mask_sensitive_data_for_display(self):
        """Test the main display masking function"""
        data = {"credentials": {"test": {"bk_app_secret": "secret", "other": "value"}}}

        result = mask_sensitive_data_for_display(data)

        assert result["credentials"]["test"]["bk_app_secret"] == CREDENTIAL_MASK
        assert result["credentials"]["test"]["other"] == "value"

    @mock.patch("bkflow.utils.handlers.settings")
    def test_handle_plain_log_with_credentials(self, mock_settings):
        """Test handle_plain_log masks credentials in strings"""
        mock_settings.LOG_SHIELDING_KEYWORDS = []

        log = '{"bk_app_secret": "secretvalue"}'
        result = handle_plain_log(log)

        assert "secretvalue" not in result
        assert CREDENTIAL_MASK in result

    def test_mask_credential_values_with_object(self):
        """Test masking credentials in an object (like TaskContext)"""

        # 模拟 TaskContext 对象
        class MockTaskContext:
            def __init__(self):
                self.task_id = 123
                self.operator = "admin"
                self.credentials = {
                    "my_cred": {
                        "bk_app_code": "app123",
                        "bk_app_secret": "secret123",
                    }
                }

        obj = MockTaskContext()
        result = mask_credential_values(obj)

        # credentials 中的敏感字段应该被脱敏
        assert result.credentials["my_cred"]["bk_app_code"] == "app123"
        assert result.credentials["my_cred"]["bk_app_secret"] == CREDENTIAL_MASK
        # 其他属性应该保持不变
        assert result.task_id == 123
        assert result.operator == "admin"

    def test_mask_credential_values_dict_with_object_value(self):
        """Test masking credentials when dict contains object values"""

        class MockContext:
            def __init__(self):
                self.credentials = {"cred": {"token": "secret_token"}}

        data = {"${_system}": MockContext(), "other_key": "value"}

        result = mask_credential_values(data)

        # 对象中的 credentials 应该被脱敏
        assert result["${_system}"].credentials["cred"]["token"] == CREDENTIAL_MASK
        assert result["other_key"] == "value"

    def test_mask_credential_values_object_with_unknown_fields(self):
        """Test that object credentials with unknown fields are fully masked"""

        class MockContext:
            def __init__(self):
                self.credentials = {"custom_cred": {"custom_field": "custom_value"}}

        obj = MockContext()
        result = mask_credential_values(obj)

        # 没有已知敏感字段时，整个凭证字典应该被脱敏
        assert result.credentials["custom_cred"] == "{***}"
