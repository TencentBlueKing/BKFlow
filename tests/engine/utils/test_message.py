"""Test message utils"""
from unittest import mock

from bkflow.utils.message import send_message


class TestMessageUtils:
    """Test message sending utilities"""

    @mock.patch("bkflow.utils.message.handle_api_error")
    @mock.patch("bkflow.utils.message.get_client_by_user")
    def test_send_message(self, mock_get_client, mock_handle_error):
        """Test message sending"""
        # Success
        mock_client = mock.Mock()
        mock_client.cmsi.send_msg.return_value = {"result": True}
        mock_get_client.return_value = mock_client
        has_error, error_msg = send_message(
            executor="admin", notify_types=["weixin"], receivers="user1", title="Test", content="Test message"
        )
        assert has_error is False
        mock_client.cmsi.send_msg.assert_called_once()

        # Voice message
        mock_client.cmsi.send_voice_msg.return_value = {"result": True}
        has_error, error_msg = send_message(
            executor="admin", notify_types=["voice"], receivers="user1", title="Alert", content="Important message"
        )
        assert has_error is False

        # Mail formatting
        send_message(executor="admin", notify_types=["mail"], receivers="user1", title="Test", content="Test content")
        call_args = mock_client.cmsi.send_msg.call_args[0][0]
        assert "<pre>" in call_args["content"]

        # Failure
        mock_client.cmsi.send_msg.return_value = {"result": False, "message": "API Error"}
        mock_handle_error.return_value = "Error message"
        has_error, error_msg = send_message(
            executor="admin", notify_types=["weixin"], receivers="user1", title="Test", content="Test message"
        )
        assert has_error is True

        # Multiple types
        mock_client.cmsi.send_msg.return_value = {"result": True}
        mock_client.cmsi.send_msg.reset_mock()  # Reset call count before testing multiple types
        send_message(
            executor="admin",
            notify_types=["weixin", "mail", "sms"],
            receivers="user1",
            title="Test",
            content="Test message",
        )
        assert mock_client.cmsi.send_msg.call_count == 3

        # Mixed success/failure
        mock_client.cmsi.send_msg.side_effect = [{"result": True}, {"result": False, "message": "Failed"}]
        mock_handle_error.return_value = "Error"
        has_error, error_msg = send_message(
            executor="admin", notify_types=["weixin", "mail"], receivers="user1", title="Test", content="Test message"
        )
        assert has_error is True

        # Voice failure
        mock_client.cmsi.send_voice_msg.return_value = {"result": False}
        mock_handle_error.return_value = "Voice error"
        has_error, error_msg = send_message(
            executor="admin", notify_types=["voice"], receivers="user1", title="Test", content="Test"
        )
        assert has_error is True
