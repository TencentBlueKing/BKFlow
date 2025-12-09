"""Test validate utils"""
from unittest import mock

from bkflow.utils.validate import DomainValidator, get_top_level_domain


class TestValidateUtils:
    """Test domain validation utilities"""

    def test_get_top_level_domain(self):
        """Test extracting top level domain"""
        assert get_top_level_domain("http://example.com") == "example.com"
        assert get_top_level_domain("https://sub.example.com") == "example.com"
        assert get_top_level_domain("http://test.example.co.uk") == "example.co.uk"

    @mock.patch("bkflow.utils.validate.settings")
    def test_validate_domain_check_disabled(self, mock_settings):
        """Test validation when check is disabled"""
        mock_settings.ENABLE_HTTP_PLUGIN_DOMAINS_CHECK = False
        is_valid, err = DomainValidator.validate("http://any-domain.com")
        assert is_valid is True
        assert err == []

    @mock.patch("bkflow.utils.validate.settings")
    def test_validate_default_allowed_domain(self, mock_settings):
        """Test validation with default BK_URL domain"""
        mock_settings.ENABLE_HTTP_PLUGIN_DOMAINS_CHECK = True
        mock_settings.ALLOWED_HTTP_PLUGIN_DOMAINS = None
        mock_settings.BK_URL = "http://bk.example.com"

        is_valid, err = DomainValidator.validate("http://api.bk.example.com")
        assert is_valid is True

    @mock.patch("bkflow.utils.validate.settings")
    def test_validate_custom_allowed_domains(self, mock_settings):
        """Test validation with custom allowed domains"""
        mock_settings.ENABLE_HTTP_PLUGIN_DOMAINS_CHECK = True
        mock_settings.ALLOWED_HTTP_PLUGIN_DOMAINS = "example.com,test.com"

        is_valid, err = DomainValidator.validate("http://sub.example.com")
        assert is_valid is True

        is_valid, err = DomainValidator.validate("http://other.com")
        assert is_valid is False
        assert "example.com" in err

    @mock.patch("bkflow.utils.validate.settings")
    def test_validate_domain_not_allowed(self, mock_settings):
        """Test validation with disallowed domain"""
        mock_settings.ENABLE_HTTP_PLUGIN_DOMAINS_CHECK = True
        mock_settings.ALLOWED_HTTP_PLUGIN_DOMAINS = "allowed.com"

        is_valid, err = DomainValidator.validate("http://forbidden.com")
        assert is_valid is False
        assert err == ["allowed.com"]
