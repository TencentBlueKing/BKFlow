"""Test validate utils"""
from unittest import mock

from bkflow.utils.validate import DomainValidator, get_top_level_domain


class TestValidateUtils:
    """Test domain validation utilities"""

    def test_domain_validation(self):
        """Test domain validation"""
        # Get top level domain
        assert get_top_level_domain("http://example.com") == "example.com"
        assert get_top_level_domain("https://sub.example.com") == "example.com"

        # Check disabled
        with mock.patch("bkflow.utils.validate.settings") as mock_settings:
            mock_settings.ENABLE_HTTP_PLUGIN_DOMAINS_CHECK = False
            is_valid, err = DomainValidator.validate("http://any-domain.com")
            assert is_valid is True

        # Default allowed domain
        with mock.patch("bkflow.utils.validate.settings") as mock_settings:
            mock_settings.ENABLE_HTTP_PLUGIN_DOMAINS_CHECK = True
            mock_settings.ALLOWED_HTTP_PLUGIN_DOMAINS = None
            mock_settings.BK_URL = "http://bk.example.com"
            is_valid, err = DomainValidator.validate("http://api.bk.example.com")
            assert is_valid is True

        # Custom allowed domains
        with mock.patch("bkflow.utils.validate.settings") as mock_settings:
            mock_settings.ENABLE_HTTP_PLUGIN_DOMAINS_CHECK = True
            mock_settings.ALLOWED_HTTP_PLUGIN_DOMAINS = "example.com,test.com"
            assert DomainValidator.validate("http://sub.example.com")[0] is True
            is_valid, err = DomainValidator.validate("http://other.com")
            assert is_valid is False
            assert "example.com" in err

        # Not allowed
        with mock.patch("bkflow.utils.validate.settings") as mock_settings:
            mock_settings.ENABLE_HTTP_PLUGIN_DOMAINS_CHECK = True
            mock_settings.ALLOWED_HTTP_PLUGIN_DOMAINS = "allowed.com"
            is_valid, err = DomainValidator.validate("http://forbidden.com")
            assert is_valid is False
