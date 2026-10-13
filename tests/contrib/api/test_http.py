from unittest import mock

import pytest

from bkflow.contrib.api import http


class TestSanitizeSensitiveData:
    """测试敏感数据脱敏函数"""

    def test_sanitize_none(self):
        """测试 None 输入"""
        assert http._sanitize_sensitive_data(None) is None

    def test_sanitize_simple_dict(self):
        """测试简单字典，包含敏感字段"""
        data = {
            "username": "admin",
            "password": "secret123",
            "credentials": {"key": "value"},
            "api_key": "abc123",
            "normal_field": "normal_value",
        }
        result = http._sanitize_sensitive_data(data)
        assert result["username"] == "admin"
        assert result["password"] == "***REDACTED***"
        assert result["credentials"] == "***REDACTED***"
        assert result["api_key"] == "***REDACTED***"
        assert result["normal_field"] == "normal_value"

    def test_sanitize_nested_dict(self):
        """测试嵌套字典"""
        data = {
            "user": {
                "name": "admin",
                "secret_token": "token123",
            },
            "config": {
                "url": "http://example.com",
                "accesskey": "key123",
            },
        }
        result = http._sanitize_sensitive_data(data)
        assert result["user"]["name"] == "admin"
        assert result["user"]["secret_token"] == "***REDACTED***"
        assert result["config"]["url"] == "http://example.com"
        assert result["config"]["accesskey"] == "***REDACTED***"

    def test_sanitize_list(self):
        """测试列表中的敏感数据"""
        data = [
            {"name": "item1", "password": "pass1"},
            {"name": "item2", "token": "token2"},
        ]
        result = http._sanitize_sensitive_data(data)
        assert result[0]["name"] == "item1"
        assert result[0]["password"] == "***REDACTED***"
        assert result[1]["name"] == "item2"
        assert result[1]["token"] == "***REDACTED***"

    def test_sanitize_max_depth_exceeded(self):
        """测试超过最大递归深度"""
        data = {"level1": {"level2": {"level3": "value"}}}
        result = http._sanitize_sensitive_data(data, max_depth=1)
        assert result["level1"] == "***MAX_DEPTH_EXCEEDED***"

    def test_sanitize_primitive_types(self):
        """测试基本类型直接返回"""
        assert http._sanitize_sensitive_data("string") == "string"
        assert http._sanitize_sensitive_data(123) == 123
        assert http._sanitize_sensitive_data(True) is True

    def test_sanitize_case_insensitive(self):
        """测试大小写不敏感"""
        data = {
            "PASSWORD": "secret",
            "Api_Key": "key",
            "CREDENTIAL_info": "cred",
        }
        result = http._sanitize_sensitive_data(data)
        assert result["PASSWORD"] == "***REDACTED***"
        assert result["Api_Key"] == "***REDACTED***"
        assert result["CREDENTIAL_info"] == "***REDACTED***"


class TestHttpApi:
    def test_gen_header(self):
        headers = http._gen_header()
        assert headers == {"Content-Type": "application/json"}

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.get")
    @mock.patch("bkflow.contrib.api.http.requests.post")
    @mock.patch("bkflow.contrib.api.http.requests.put")
    @mock.patch("bkflow.contrib.api.http.requests.delete")
    def test_http_methods_success(self, mock_delete, mock_put, mock_post, mock_get, mock_curlify):
        """Test GET, POST, PUT, DELETE success cases"""
        mock_resp = mock.Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"result": True, "message": "success", "request_id": "123"}
        mock_resp.status_code = 200
        mock_resp.request = mock.Mock()
        mock_resp.request.method = "GET"
        mock_get.return_value = mock_resp
        mock_post.return_value = mock_resp
        mock_put.return_value = mock_resp
        mock_delete.return_value = mock_resp

        url = "http://example.com"
        data = {"key": "value"}

        # GET
        result = http.get(url, data)
        assert result == {"result": True, "message": "success", "request_id": "123"}

        # POST
        mock_resp.request.method = "POST"
        result = http.post(url, data)
        assert result == {"result": True, "message": "success", "request_id": "123"}

        # PUT
        mock_resp.request.method = "PUT"
        result = http.put(url, data)
        assert result == {"result": True, "message": "success", "request_id": "123"}

        # DELETE
        mock_resp.request.method = "DELETE"
        result = http.delete(url, data)
        assert result == {"result": True, "message": "success", "request_id": "123"}

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
    def test_request_error_cases(self, mock_get, mock_curlify):
        """Test various error cases"""
        # Exception
        mock_get.side_effect = Exception("Network Error")
        result = http.get("http://example.com", {})
        assert result["result"] is False
        assert "Network Error" in result["message"]
        assert "http_status" not in result

        # Failure status with JSON
        mock_resp = mock.Mock()
        mock_resp.ok = False
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Internal Server Error"}
        mock_resp.request = mock.Mock()
        mock_resp.request.method = "GET"
        mock_get.return_value = mock_resp
        mock_get.side_effect = None
        result = http.get("http://example.com", {})
        assert result["result"] is False
        assert "status_code: 500" in result["message"]
        assert result["http_status"] == 500

        # Failure status without JSON
        mock_resp.json.side_effect = Exception("Not JSON")
        mock_resp.content = b"Raw Error"
        result = http.get("http://example.com", {})
        assert result["result"] is False
        assert result["http_status"] == 500
        assert "Raw Error" not in result["message"]

        # Invalid JSON response
        mock_resp.ok = True
        mock_resp.json.side_effect = Exception("Invalid JSON")
        mock_resp.content = b"Invalid JSON Content" * 20
        result = http.get("http://example.com", {})
        assert result["result"] is False
        assert "not a valid json" in result["message"]

        # API returns result=False
        mock_resp.json.return_value = {"result": False, "message": "API Error", "request_id": "123"}
        mock_resp.json.side_effect = None
        result = http.get("http://example.com", {})
        assert result["result"] is False
        assert result["message"] == "API Error"

    @mock.patch("bkflow.contrib.api.http.curlify")
    def test_unsupported_method(self, mock_curlify):
        result = http._http_request("PATCH", "http://example.com")
        assert result["result"] is False
        assert "Unsupported http method PATCH" in result["message"]
        assert "http_status" not in result

    @mock.patch("bkflow.contrib.api.http.requests.get")
    def test_non_2xx_returns_safe_structured_integer_http_status(self, mock_get, caplog):
        """Expose transport status without returning or logging the response body."""
        response_secret = "HTTP_404_RESPONSE_BODY_SENTINEL"
        response = mock.Mock()
        response.ok = False
        response.status_code = 404
        response.json.return_value = {"detail": response_secret}
        response.content = response_secret.encode()
        mock_get.return_value = response
        caplog.set_level("DEBUG", logger="component")

        result = http.get(
            "http://example.com/tasks/404",
            {},
            headers={"aUtHoRiZaTiOn": "HTTP_404_AUTHORIZATION_SENTINEL"},
        )

        assert result == {
            "result": False,
            "message": "Request API error, status_code: 404",
            "http_status": 404,
            "error_type": "http",
            "status_code": 404,
            "retryable": False,
        }
        assert response_secret not in repr(result)
        assert response_secret not in caplog.text

    @pytest.mark.parametrize("response_result", [True, False])
    @mock.patch("bkflow.contrib.api.http.requests.post")
    def test_sensitive_request_redacts_curl_and_success_or_api_error_response_logs(
        self, mock_post, response_result, caplog
    ):
        request_secret = "CUSTOM_AUTH_REQUEST_SENTINEL"
        response_secret = "CUSTOM_AUTH_RESPONSE_SENTINEL"
        message_secret = "CUSTOM_AUTH_MESSAGE_SENTINEL"
        response = mock.Mock()
        response.ok = True
        response.status_code = 200
        response.request = mock.Mock()
        response.json.return_value = {
            "result": response_result,
            "message": message_secret,
            "request_id": "request-1",
            "credentials": {"auth": response_secret},
        }
        response.text = response_secret
        mock_post.return_value = response
        caplog.set_level("DEBUG", logger="component")

        result = http.post(
            "http://example.com/tasks",
            {"name": "safe", "credentials": {"auth": request_secret}},
        )

        assert result["result"] is response_result
        assert request_secret not in caplog.text
        assert response_secret not in caplog.text
        assert message_secret not in caplog.text
        assert "***REDACTED***" in caplog.text

    @mock.patch("bkflow.contrib.api.http.requests.post")
    def test_sensitive_request_redacts_http_error_response_log(self, mock_post, caplog):
        request_secret = "CUSTOM_AUTH_HTTP_ERROR_REQUEST_SENTINEL"
        response_secret = "CUSTOM_AUTH_HTTP_ERROR_RESPONSE_SENTINEL"
        response = mock.Mock()
        response.ok = False
        response.status_code = 500
        response.request = mock.Mock()
        response.json.return_value = {"error": response_secret}
        response.content = response_secret.encode()
        mock_post.return_value = response
        caplog.set_level("DEBUG", logger="component")

        result = http.post(
            "http://example.com/tasks",
            {"credentials": {"auth": request_secret}},
        )

        assert result["result"] is False
        assert result["http_status"] == 500
        assert response_secret not in result["message"]
        assert request_secret not in caplog.text
        assert response_secret not in caplog.text
        assert "***REDACTED***" in caplog.text

    @mock.patch("bkflow.contrib.api.http.requests.post")
    def test_sensitive_request_redacts_exception_log_without_changing_return_contract(self, mock_post, caplog):
        request_secret = "CUSTOM_AUTH_EXCEPTION_REQUEST_SENTINEL"
        exception_secret = "CUSTOM_AUTH_EXCEPTION_RESPONSE_SENTINEL"
        mock_post.side_effect = RuntimeError(exception_secret)
        caplog.set_level("DEBUG", logger="component")

        result = http.post(
            "http://example.com/tasks",
            {"credentials": {"auth": request_secret}},
        )

        assert result == {
            "result": False,
            "message": "Request API error, exception: {}".format(exception_secret),
            "error_type": "request",
            "retryable": False,
        }
        assert request_secret not in caplog.text
        assert exception_secret not in caplog.text
        assert "***REDACTED***" in caplog.text

    @mock.patch("bkflow.contrib.api.http.requests.post")
    def test_cookie_container_is_removed_from_sanitized_curl(self, mock_post, caplog):
        cookie_secret = "CUSTOM_COOKIE_SESSION_SENTINEL"
        response = mock.Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {"result": True, "message": "done", "request_id": "request-2"}
        response.text = "safe"
        mock_post.return_value = response
        caplog.set_level("DEBUG", logger="component")

        result = http.post(
            "http://example.com/tasks",
            {"name": "safe"},
            cookies={"session": cookie_secret},
        )

        assert result["result"] is True
        assert cookie_secret not in caplog.text
        assert "***REDACTED***" in caplog.text

    @pytest.mark.parametrize("header_name", ["cOoKiE", "sEt-CoOkIe"])
    @mock.patch("bkflow.contrib.api.http.requests.post")
    def test_cookie_headers_are_removed_from_sanitized_curl(self, mock_post, header_name, caplog):
        header_secret = "CUSTOM_COOKIE_HEADER_SENTINEL"
        response_secret = "CUSTOM_COOKIE_HEADER_RESPONSE_SENTINEL"
        response = mock.Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {
            "result": True,
            "message": response_secret,
            "request_id": "request-3",
        }
        response.text = response_secret
        mock_post.return_value = response
        caplog.set_level("DEBUG", logger="component")

        result = http.post(
            "http://example.com/tasks",
            {"name": "safe"},
            headers={"Content-Type": "application/json", header_name: header_secret},
        )

        assert result["result"] is True
        assert header_secret not in caplog.text
        assert response_secret not in caplog.text
        assert header_name.lower() not in caplog.text.lower()
        assert "***REDACTED***" in caplog.text

    @mock.patch("bkflow.contrib.api.http.requests.post")
    def test_authorization_header_is_redacted_only_in_diagnostic_curl(self, mock_post, caplog):
        authorization_secret = "CUSTOM_AUTHORIZATION_HEADER_SENTINEL"
        headers = {
            "Content-Type": "application/json",
            "aUtHoRiZaTiOn": authorization_secret,
        }
        response = mock.Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {"result": True, "message": "safe", "request_id": "request-4"}
        response.text = "safe"
        mock_post.return_value = response
        caplog.set_level("DEBUG", logger="component")

        result = http.post("http://example.com/tasks", {"name": "safe"}, headers=headers)

        assert result["result"] is True
        assert authorization_secret not in caplog.text
        assert "***REDACTED***" in caplog.text
        assert mock_post.call_args.kwargs["headers"] == headers

    @mock.patch("bkflow.contrib.api.http.curlify")
    @mock.patch("bkflow.contrib.api.http.requests.get")
    @mock.patch("bkflow.contrib.api.http.requests.post")
    @mock.patch("bkflow.contrib.api.http.requests.put")
    @mock.patch("bkflow.contrib.api.http.requests.delete")
    def test_request_with_optional_params(self, mock_delete, mock_put, mock_post, mock_get, mock_curlify):
        """Test requests with optional parameters"""
        mock_resp = mock.Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"result": True}
        mock_resp.request = mock.Mock()
        mock_get.return_value = mock_resp
        mock_post.return_value = mock_resp
        mock_put.return_value = mock_resp
        mock_delete.return_value = mock_resp

        # GET with custom headers
        custom_headers = {"Authorization": "Bearer token123"}
        result = http.get("http://example.com", {}, headers=custom_headers)
        assert result["result"] is True
        assert mock_get.call_args[1]["headers"] == custom_headers

        # POST with timeout and cert
        result = http.post(
            "http://example.com", {"data": "test"}, timeout=30, cert=("/path/to/cert", "/path/to/key"), verify=True
        )
        assert result["result"] is True
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["timeout"] == 30
        assert call_kwargs["cert"] == ("/path/to/cert", "/path/to/key")
        assert call_kwargs["verify"] is True

        # PUT with cookies
        cookies = {"session_id": "abc123"}
        result = http.put("http://example.com", {"key": "value"}, cookies=cookies)
        assert result["result"] is True
        assert mock_put.call_args[1]["cookies"] == cookies

        # DELETE with all params
        result = http.delete(
            "http://example.com",
            {"id": 123},
            headers={"X-Custom": "value"},
            verify=True,
            cert=("/cert/path", "/key/path"),
            timeout=60,
            cookies={"token": "xyz"},
        )
        assert result["result"] is True
