from unittest import mock

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

        # Failure status without JSON
        mock_resp.json.side_effect = Exception("Not JSON")
        mock_resp.content = b"Raw Error"
        result = http.get("http://example.com", {})
        assert result["result"] is False
        assert "Raw Error" in result["message"]

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
