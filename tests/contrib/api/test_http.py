from unittest import mock

import requests

from bkflow.contrib.api import http


class TestHttpApi:
    def test_gen_header(self):
        headers = http._gen_header()
        assert headers == {"Content-Type": "application/json"}

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.get")
    def test_get_success(self, mock_get, mock_curlify):
        mock_resp = mock.Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"result": True, "message": "success", "request_id": "123"}
        mock_resp.status_code = 200
        mock_resp.request = mock.Mock()  # Mock request to avoid curlify issues if not mocked properly
        mock_resp.request.method = "GET"
        mock_get.return_value = mock_resp

        url = "http://example.com"
        data = {"key": "value"}
        result = http.get(url, data)

        assert result == {"result": True, "message": "success", "request_id": "123"}
        mock_get.assert_called_with(
            url=url, headers=http._gen_header(), params=data, verify=False, cert=None, timeout=None, cookies=None
        )

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.post")
    def test_post_success(self, mock_post, mock_curlify):
        mock_resp = mock.Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"result": True, "message": "success", "request_id": "123"}
        mock_resp.request = mock.Mock()
        mock_resp.request.method = "POST"
        mock_post.return_value = mock_resp

        url = "http://example.com"
        data = {"key": "value"}
        result = http.post(url, data)

        assert result == {"result": True, "message": "success", "request_id": "123"}
        mock_post.assert_called_with(
            url=url, headers=http._gen_header(), json=data, verify=False, cert=None, timeout=None, cookies=None
        )

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.put")
    def test_put_success(self, mock_put, mock_curlify):
        mock_resp = mock.Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"result": True, "message": "success", "request_id": "123"}
        mock_resp.request = mock.Mock()
        mock_resp.request.method = "PUT"
        mock_put.return_value = mock_resp

        url = "http://example.com"
        data = {"key": "value"}
        result = http.put(url, data)

        assert result == {"result": True, "message": "success", "request_id": "123"}
        mock_put.assert_called_with(
            url=url, headers=http._gen_header(), json=data, verify=False, cert=None, timeout=None, cookies=None
        )

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.delete")
    def test_delete_success(self, mock_delete, mock_curlify):
        mock_resp = mock.Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"result": True, "message": "success", "request_id": "123"}
        mock_resp.request = mock.Mock()
        mock_resp.request.method = "DELETE"
        mock_delete.return_value = mock_resp

        url = "http://example.com"
        data = {"key": "value"}
        result = http.delete(url, data)

        assert result == {"result": True, "message": "success", "request_id": "123"}
        mock_delete.assert_called_with(
            url=url, headers=http._gen_header(), json=data, verify=False, cert=None, timeout=None, cookies=None
        )

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.head")
    def test_head_success(self, mock_head, mock_curlify):
        mock_resp = mock.Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"result": True, "message": "success", "request_id": "123"}
        mock_resp.request = mock.Mock()
        mock_resp.request.method = "HEAD"
        mock_head.return_value = mock_resp

        url = "http://example.com"
        headers = http._gen_header()

        # _http_request directly for HEAD as there is no wrapper
        result = http._http_request(method="HEAD", url=url, headers=headers)

        assert result == {"result": True, "message": "success", "request_id": "123"}
        mock_head.assert_called_with(url=url, headers=headers, verify=False, cert=None, timeout=None, cookies=None)

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.get")
    def test_request_exception(self, mock_get, mock_curlify):
        mock_get.side_effect = Exception("Network Error")

        result = http.get("http://example.com", {})
        assert result["result"] is False
        assert "Request API error, exception: Network Error" in result["message"]

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.get")
    def test_request_failure_status(self, mock_get, mock_curlify):
        mock_resp = mock.Mock()
        mock_resp.ok = False
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Internal Server Error"}
        mock_resp.request = mock.Mock()
        mock_resp.request.method = "GET"
        mock_get.return_value = mock_resp

        result = http.get("http://example.com", {})
        assert result["result"] is False
        assert "Request API error, status_code: 500" in result["message"]

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.get")
    def test_request_failure_status_no_json(self, mock_get, mock_curlify):
        mock_resp = mock.Mock()
        mock_resp.ok = False
        mock_resp.status_code = 500
        mock_resp.json.side_effect = Exception("Not JSON")
        mock_resp.content = b"Raw Error"
        mock_resp.request = mock.Mock()
        mock_resp.request.method = "GET"
        mock_get.return_value = mock_resp

        result = http.get("http://example.com", {})
        assert result["result"] is False
        assert "Raw Error" in result["message"]

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.get")
    def test_request_invalid_json_response(self, mock_get, mock_curlify):
        mock_resp = mock.Mock()
        mock_resp.ok = True
        mock_resp.json.side_effect = Exception("Invalid JSON")
        mock_resp.content = b"Invalid JSON Content" * 20
        mock_resp.request = mock.Mock()
        mock_resp.request.method = "GET"
        mock_get.return_value = mock_resp

        result = http.get("http://example.com", {})
        assert result["result"] is False
        assert "API return is not a valid json" in result["message"]

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.get")
    def test_request_api_return_false(self, mock_get, mock_curlify):
        mock_resp = mock.Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"result": False, "message": "API Error", "request_id": "123"}
        mock_resp.request = mock.Mock()
        mock_resp.request.method = "GET"
        mock_get.return_value = mock_resp

        result = http.get("http://example.com", {})
        assert result["result"] is False
        assert result["message"] == "API Error"

    @mock.patch("bkflow.contrib.api.http.curlify")
    def test_unsupported_method(self, mock_curlify):
        result = http._http_request("PATCH", "http://example.com")
        assert result["result"] is False
        assert "Unsupported http method PATCH" in result["message"]

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.get")
    def test_get_with_custom_headers(self, mock_get, mock_curlify):
        """Test GET request with custom headers"""
        mock_resp = mock.Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"result": True, "data": "test"}
        mock_resp.request = mock.Mock()
        mock_get.return_value = mock_resp

        custom_headers = {"Authorization": "Bearer token123"}
        result = http.get("http://example.com", {}, headers=custom_headers)

        assert result["result"] is True
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["headers"] == custom_headers

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.post")
    def test_post_with_timeout_and_cert(self, mock_post, mock_curlify):
        """Test POST request with timeout and cert"""
        mock_resp = mock.Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"result": True}
        mock_resp.request = mock.Mock()
        mock_post.return_value = mock_resp

        result = http.post(
            "http://example.com", {"data": "test"}, timeout=30, cert=("/path/to/cert", "/path/to/key"), verify=True
        )

        assert result["result"] is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["timeout"] == 30
        assert call_kwargs["cert"] == ("/path/to/cert", "/path/to/key")
        assert call_kwargs["verify"] is True

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.put")
    def test_put_with_cookies(self, mock_put, mock_curlify):
        """Test PUT request with cookies"""
        mock_resp = mock.Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"result": True}
        mock_resp.request = mock.Mock()
        mock_put.return_value = mock_resp

        cookies = {"session_id": "abc123"}
        result = http.put("http://example.com", {"key": "value"}, cookies=cookies)

        assert result["result"] is True
        mock_put.assert_called_once()
        call_kwargs = mock_put.call_args[1]
        assert call_kwargs["cookies"] == cookies

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.delete")
    def test_delete_with_all_params(self, mock_delete, mock_curlify):
        """Test DELETE request with all optional parameters"""
        mock_resp = mock.Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"result": True}
        mock_resp.request = mock.Mock()
        mock_delete.return_value = mock_resp

        custom_headers = {"X-Custom": "value"}
        cookies = {"token": "xyz"}
        cert = ("/cert/path", "/key/path")

        result = http.delete(
            "http://example.com",
            {"id": 123},
            headers=custom_headers,
            verify=True,
            cert=cert,
            timeout=60,
            cookies=cookies,
        )

        assert result["result"] is True
        mock_delete.assert_called_once()

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.get")
    def test_request_with_no_request_object(self, mock_get, mock_curlify):
        """Test request when response.request is None (finally block path)"""
        mock_resp = mock.Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"result": True}
        mock_resp.request = None  # Simulate None request
        mock_get.return_value = mock_resp

        result = http.get("http://example.com", {"key": "value"})

        assert result["result"] is True
        # Verify that finally block creates a request object
        assert mock_resp.request is not None

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.get")
    def test_request_success_with_debug_log(self, mock_get, mock_curlify):
        """Test successful request that triggers debug logging"""
        mock_resp = mock.Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "result": True,
            "message": "Success",
            "request_id": "req-123",
            "data": "test_data",
        }
        mock_resp.text = '{"result": true}'
        mock_resp.request = mock.Mock()
        mock_get.return_value = mock_resp

        result = http.get("http://example.com", {"param": "value"})

        assert result["result"] is True
        assert result["request_id"] == "req-123"

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.get")
    def test_request_api_error_with_log(self, mock_get, mock_curlify):
        """Test API returns result=False which triggers error logging"""
        mock_resp = mock.Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"result": False, "message": "Business logic error", "request_id": "req-456"}
        mock_resp.text = '{"result": false}'
        mock_resp.request = mock.Mock()
        mock_get.return_value = mock_resp

        result = http.get("http://example.com", {"key": "value"})

        assert result["result"] is False
        assert result["message"] == "Business logic error"

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.post")
    def test_request_exception_with_logging(self, mock_post, mock_curlify):
        """Test exception handling with different exception types"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        result = http.post("http://example.com", {"data": "test"})

        assert result["result"] is False
        assert "Connection refused" in result["message"]

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.get")
    def test_request_timeout_exception(self, mock_get, mock_curlify):
        """Test timeout exception"""
        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")

        result = http.get("http://example.com", {})

        assert result["result"] is False
        assert "timeout" in result["message"].lower()
