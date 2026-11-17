from unittest import mock

from bkflow.utils.apigw import check_url_from_apigw


class TestApigwUtils:
    @mock.patch("bkflow.utils.apigw.settings")
    def test_check_url_from_apigw(self, mock_settings):
        """Test URL checking from APIGW"""
        # Skip check enabled
        mock_settings.SKIP_APIGW_CHECK = True
        assert check_url_from_apigw("http://example.com") is True

        # URL is None
        mock_settings.SKIP_APIGW_CHECK = False
        assert check_url_from_apigw(None) is False

        # No pattern configured
        mock_settings.BK_APIGW_NETLOC_PATTERN = None
        assert check_url_from_apigw("http://example.com") is False

        # Pattern match
        mock_settings.BK_APIGW_NETLOC_PATTERN = r".*\.apigw\.example\.com$"
        assert check_url_from_apigw("http://api.apigw.example.com/path") is True
        assert check_url_from_apigw("http://other.example.com") is False

        # Exact match pattern
        mock_settings.BK_APIGW_NETLOC_PATTERN = r"^apigw\.example\.com$"
        assert check_url_from_apigw("http://apigw.example.com/path") is True
        assert check_url_from_apigw("http://sub.apigw.example.com") is False

        # 默认部署模式必须完整匹配，不能被后缀域名或 userinfo 绕过
        mock_settings.BK_APIGW_NETLOC_PATTERN = r"^bkapi\.example\.com$"
        assert check_url_from_apigw("https://bkapi.example.com/path") is True
        assert check_url_from_apigw("https://bkapi.example.com.attacker.net/path") is False
        assert check_url_from_apigw("https://bkapi.example.com@attacker.net/path") is False
