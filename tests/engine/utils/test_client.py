"""Test API client"""
from unittest import mock

from bkflow.contrib.api.client import BaseComponentClient, BKComponentClient


class TestBKComponentClient:
    """Test BKComponentClient"""

    def test_client_initialization(self):
        """Test client initialization"""
        client = BKComponentClient(username="admin", language="zh-cn")
        assert client.username == "admin"
        assert client.language == "zh-cn"
        assert client.use_test_env is False

    @mock.patch("bkflow.contrib.api.client.translation.get_language")
    def test_client_default_language(self, mock_get_lang):
        """Test client with default language"""
        mock_get_lang.return_value = "en"
        client = BKComponentClient(username="admin")
        assert client.language == "en"

    @mock.patch("bkflow.contrib.api.client.settings")
    def test_client_default_app_credentials(self, mock_settings):
        """Test client with default app credentials"""
        mock_settings.APP_CODE = "test_app"
        mock_settings.SECRET_KEY = "test_secret"

        client = BKComponentClient(username="admin")
        assert client.app_code == "test_app"
        assert client.app_secret == "test_secret"

    def test_client_custom_credentials(self):
        """Test client with custom credentials"""
        client = BKComponentClient(username="admin", app_code="custom_app", app_secret="custom_secret")
        assert client.app_code == "custom_app"
        assert client.app_secret == "custom_secret"

    def test_pre_process_headers_default(self):
        """Test preprocessing headers with None"""
        client = BKComponentClient(username="admin", language="zh-cn")
        headers = client._pre_process_headers(None)

        assert headers["Content-Type"] == "application/json"
        assert headers["blueking-language"] == "zh-cn"

    def test_pre_process_headers_existing(self):
        """Test preprocessing existing headers"""
        client = BKComponentClient(username="admin", language="en")
        headers = {"Authorization": "Bearer token"}
        result = client._pre_process_headers(headers)

        assert result["Authorization"] == "Bearer token"
        assert result["blueking-language"] == "en"

    def test_pre_process_headers_test_env(self):
        """Test headers with test environment flag"""
        client = BKComponentClient(username="admin", use_test_env=True)
        headers = client._pre_process_headers(None)

        assert headers["x-use-test-env"] == "1"

    @mock.patch("bkflow.contrib.api.client.settings")
    def test_pre_process_data(self, mock_settings):
        """Test preprocessing request data"""
        mock_settings.APP_CODE = "app"
        mock_settings.SECRET_KEY = "secret"

        client = BKComponentClient(username="admin")
        data = {"key": "value"}
        client._pre_process_data(data)

        assert data["bk_username"] == "admin"
        assert data["bk_app_code"] == "app"
        assert data["bk_app_secret"] == "secret"

    @mock.patch("bkflow.contrib.api.client.http.post")
    @mock.patch("bkflow.contrib.api.client.settings")
    def test_request_post(self, mock_settings, mock_http_post):
        """Test making POST request"""
        mock_settings.APP_CODE = "app"
        mock_settings.SECRET_KEY = "secret"
        mock_http_post.return_value = {"result": True}

        client = BKComponentClient(username="admin")
        data = {"param": "value"}
        result = client._request("POST", "http://api.example.com", data)

        assert result["result"] is True
        mock_http_post.assert_called_once()
        call_kwargs = mock_http_post.call_args[1]
        assert call_kwargs["data"]["bk_username"] == "admin"

    @mock.patch("bkflow.contrib.api.client.http.get")
    def test_request_get(self, mock_http_get):
        """Test making GET request"""
        mock_http_get.return_value = {"result": True}

        client = BKComponentClient(username="admin")
        result = client._request("GET", "http://api.example.com", {})

        assert result["result"] is True
        mock_http_get.assert_called_once()


class TestBaseComponentClient:
    """Test BaseComponentClient"""

    def test_base_client_initialization(self):
        """Test base client initialization"""
        client = BaseComponentClient(username="admin")
        assert client.username == "admin"

    def test_base_client_default_username(self):
        """Test base client with default username"""
        client = BaseComponentClient()
        assert client.username == ""

    def test_base_pre_process_headers_none(self):
        """Test base client header preprocessing with None"""
        client = BaseComponentClient()
        headers = client._pre_process_headers(None)

        assert headers["Content-Type"] == "application/json"

    def test_base_pre_process_headers_existing(self):
        """Test base client with existing headers"""
        client = BaseComponentClient()
        headers = {"Custom": "Header"}
        result = client._pre_process_headers(headers)

        assert result["Custom"] == "Header"

    @mock.patch("bkflow.contrib.api.client.http.post")
    def test_base_request(self, mock_http_post):
        """Test base client request"""
        mock_http_post.return_value = {"result": True}

        client = BaseComponentClient(username="test")
        result = client._request("POST", "http://api.com", {"data": "test"})

        assert result["result"] is True
        mock_http_post.assert_called_once()
