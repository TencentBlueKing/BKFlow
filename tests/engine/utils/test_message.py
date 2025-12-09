"""Test message utils"""
from unittest import mock

from bkflow.utils.message import send_message


class TestMessageUtils:
    """Test message sending utilities"""

    @mock.patch("bkflow.utils.message.get_client_by_user")
    def test_send_message_success(self, mock_get_client):
        """Test successful message sending"""
        mock_client = mock.Mock()
        mock_client.cmsi.send_msg.return_value = {"result": True}
        mock_get_client.return_value = mock_client

        has_error, error_msg = send_message(
            executor="admin", notify_types=["weixin"], receivers="user1", title="Test", content="Test message"
        )

        assert has_error is False
        assert error_msg == ""
        mock_client.cmsi.send_msg.assert_called_once()

    @mock.patch("bkflow.utils.message.get_client_by_user")
    def test_send_voice_message(self, mock_get_client):
        """Test sending voice message"""
        mock_client = mock.Mock()
        mock_client.cmsi.send_voice_msg.return_value = {"result": True}
        mock_get_client.return_value = mock_client

        has_error, error_msg = send_message(
            executor="admin", notify_types=["voice"], receivers="user1", title="Alert", content="Important message"
        )

        assert has_error is False
        mock_client.cmsi.send_voice_msg.assert_called_once()

    @mock.patch("bkflow.utils.message.get_client_by_user")
    def test_send_mail_with_formatting(self, mock_get_client):
        """Test sending email with HTML formatting"""
        mock_client = mock.Mock()
        mock_client.cmsi.send_msg.return_value = {"result": True}
        mock_get_client.return_value = mock_client

        send_message(executor="admin", notify_types=["mail"], receivers="user1", title="Test", content="Test content")

        call_args = mock_client.cmsi.send_msg.call_args[0][0]
        assert "<pre>" in call_args["content"]
        assert "</pre>" in call_args["content"]

    @mock.patch("bkflow.utils.message.handle_api_error")
    @mock.patch("bkflow.utils.message.get_client_by_user")
    def test_send_message_failure(self, mock_get_client, mock_handle_error):
        """Test message sending failure"""
        mock_client = mock.Mock()
        mock_client.cmsi.send_msg.return_value = {"result": False, "message": "API Error"}
        mock_get_client.return_value = mock_client
        mock_handle_error.return_value = "Error message"

        has_error, error_msg = send_message(
            executor="admin", notify_types=["weixin"], receivers="user1", title="Test", content="Test message"
        )

        assert has_error is True
        assert "Error message" in error_msg

    @mock.patch("bkflow.utils.message.handle_api_error")
    @mock.patch("bkflow.utils.message.get_client_by_user")
    def test_send_multiple_types(self, mock_get_client, mock_handle_error):
        """Test sending multiple notification types"""
        mock_client = mock.Mock()
        mock_client.cmsi.send_msg.return_value = {"result": True}
        mock_get_client.return_value = mock_client

        send_message(
            executor="admin",
            notify_types=["weixin", "mail", "sms"],
            receivers="user1",
            title="Test",
            content="Test message",
        )

        assert mock_client.cmsi.send_msg.call_count == 3

    @mock.patch("bkflow.utils.message.handle_api_error")
    @mock.patch("bkflow.utils.message.get_client_by_user")
    def test_send_mixed_success_failure(self, mock_get_client, mock_handle_error):
        """Test mixed success and failure for multiple types"""
        mock_client = mock.Mock()
        # First succeeds, second fails
        mock_client.cmsi.send_msg.side_effect = [{"result": True}, {"result": False, "message": "Failed"}]
        mock_get_client.return_value = mock_client
        mock_handle_error.return_value = "Error"

        has_error, error_msg = send_message(
            executor="admin", notify_types=["weixin", "mail"], receivers="user1", title="Test", content="Test message"
        )

        assert has_error is True
        assert "Error" in error_msg

    @mock.patch("bkflow.utils.message.handle_api_error")
    @mock.patch("bkflow.utils.message.get_client_by_user")
    def test_send_voice_failure(self, mock_get_client, mock_handle_error):
        """Test voice message sending failure"""
        mock_client = mock.Mock()
        mock_client.cmsi.send_voice_msg.return_value = {"result": False}
        mock_get_client.return_value = mock_client
        mock_handle_error.return_value = "Voice error"

        has_error, error_msg = send_message(
            executor="admin", notify_types=["voice"], receivers="user1", title="Test", content="Test"
        )

        assert has_error is True
        mock_handle_error.assert_called_with("cmsi", "cmsi.send_voice_msg", mock.ANY, mock.ANY)
