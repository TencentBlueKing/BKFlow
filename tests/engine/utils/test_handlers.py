"""Test handler utils"""
from unittest import mock

from bkflow.utils.handlers import handle_api_error, handle_plain_log


class TestHandlerUtils:
    """Test handler utility functions"""

    @mock.patch("bkflow.utils.handlers.settings")
    def test_handle_api_error_with_request_id(self, mock_settings):
        """Test handling API error with request_id"""
        mock_settings.LOG_SHIELDING_KEYWORDS = []
        result = {"message": "API failed", "request_id": "req123"}

        message = handle_api_error("test_system", "test_api", {"param": "value"}, result)

        assert "test_system" in message
        assert "test_api" in message
        assert "req123" in message
        assert "API failed" in message

    @mock.patch("bkflow.utils.handlers.settings")
    def test_handle_api_error_without_request_id(self, mock_settings):
        """Test handling API error without request_id"""
        mock_settings.LOG_SHIELDING_KEYWORDS = []
        result = {"message": "API failed"}

        message = handle_api_error("system", "api", {}, result)

        assert "system" in message
        assert "api" in message
        assert "API failed" in message

    @mock.patch("bkflow.utils.handlers.settings")
    def test_handle_plain_log_with_keywords(self, mock_settings):
        """Test shielding sensitive keywords in logs"""
        mock_settings.LOG_SHIELDING_KEYWORDS = ["password", "secret"]

        log = "User password is 12345 and secret is abc"
        result = handle_plain_log(log)

        assert "password" not in result
        assert "secret" not in result
        assert "******" in result

    @mock.patch("bkflow.utils.handlers.settings")
    def test_handle_plain_log_empty(self, mock_settings):
        """Test handling empty log"""
        mock_settings.LOG_SHIELDING_KEYWORDS = ["test"]
        result = handle_plain_log(None)
        assert result is None

    @mock.patch("bkflow.utils.handlers.settings")
    def test_handle_plain_log_no_keywords(self, mock_settings):
        """Test log without sensitive keywords"""
        mock_settings.LOG_SHIELDING_KEYWORDS = []
        log = "Normal log message"
        result = handle_plain_log(log)
        assert result == log
