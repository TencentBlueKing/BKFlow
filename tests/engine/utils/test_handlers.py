"""Test handler utils"""
from unittest import mock

from bkflow.utils.handlers import handle_api_error, handle_plain_log


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
