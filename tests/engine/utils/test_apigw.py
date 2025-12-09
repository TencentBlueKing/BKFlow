from unittest import mock

from bkflow.utils.apigw import check_url_from_apigw


class TestApigwUtils:
    @mock.patch("bkflow.utils.apigw.settings")
    def test_skip_check_enabled(self, mock_settings):
        """Test when SKIP_APIGW_CHECK is True"""
        mock_settings.SKIP_APIGW_CHECK = True
        assert check_url_from_apigw("http://example.com") is True
        assert check_url_from_apigw("http://any-url.com") is True

    @mock.patch("bkflow.utils.apigw.settings")
    def test_url_is_none(self, mock_settings):
        """Test when url is None"""
        mock_settings.SKIP_APIGW_CHECK = False
        assert check_url_from_apigw(None) is False

    @mock.patch("bkflow.utils.apigw.settings")
    def test_no_pattern_configured(self, mock_settings):
        """Test when BK_APIGW_NETLOC_PATTERN is None"""
        mock_settings.SKIP_APIGW_CHECK = False
        mock_settings.BK_APIGW_NETLOC_PATTERN = None
        assert check_url_from_apigw("http://example.com") is False

    @mock.patch("bkflow.utils.apigw.settings")
    def test_pattern_match(self, mock_settings):
        """Test when URL matches the pattern"""
        mock_settings.SKIP_APIGW_CHECK = False
        mock_settings.BK_APIGW_NETLOC_PATTERN = r".*\.apigw\.example\.com$"

        assert check_url_from_apigw("http://api.apigw.example.com/path") is True
        assert check_url_from_apigw("https://service.apigw.example.com") is True

    @mock.patch("bkflow.utils.apigw.settings")
    def test_pattern_no_match(self, mock_settings):
        """Test when URL does not match the pattern"""
        mock_settings.SKIP_APIGW_CHECK = False
        mock_settings.BK_APIGW_NETLOC_PATTERN = r".*\.apigw\.example\.com$"

        assert check_url_from_apigw("http://other.example.com") is False
        assert check_url_from_apigw("http://example.com") is False

    @mock.patch("bkflow.utils.apigw.settings")
    def test_exact_match_pattern(self, mock_settings):
        """Test with exact match pattern"""
        mock_settings.SKIP_APIGW_CHECK = False
        mock_settings.BK_APIGW_NETLOC_PATTERN = r"^apigw\.example\.com$"

        assert check_url_from_apigw("http://apigw.example.com/path") is True
        assert check_url_from_apigw("http://sub.apigw.example.com") is False
