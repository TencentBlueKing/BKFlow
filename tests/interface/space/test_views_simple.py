"""
Simplified tests for bkflow/space/views.py focusing on coverage
"""
import pytest

from bkflow.space.models import Credential, CredentialType, Space
from bkflow.space.views import (
    SpaceConfigAdminViewSet,
    SpaceConfigViewSet,
    SpaceInternalViewSet,
)


@pytest.mark.django_db
class TestSpaceInternalViewSet:
    def test_get_credential_config_dict_with_scope(self):
        """Test get_credential_config with dict config and specific scope"""
        space = Space.objects.create(name="Test", app_code="test")
        Credential.objects.create(
            space_id=space.id, name="test_cred", type=CredentialType.BK_APP.value, content={"key": "value"}
        )

        viewset = SpaceInternalViewSet()
        config = {"scope1": "test_cred", "default": "default_cred"}
        result = viewset.get_credential_config(config, space.id, "scope1")

        assert result == {"key": "value"}

    def test_get_credential_config_dict_fallback_to_default(self):
        """Test get_credential_config falls back to default when scope not found"""
        space = Space.objects.create(name="Test", app_code="test")
        Credential.objects.create(
            space_id=space.id, name="default_cred", type=CredentialType.BK_APP.value, content={"default": "value"}
        )

        viewset = SpaceInternalViewSet()
        config = {"default": "default_cred"}
        result = viewset.get_credential_config(config, space.id, "nonexistent_scope")

        assert result == {"default": "value"}


@pytest.mark.django_db
class TestSpaceConfigAdminViewSet:
    def test_process_config_with_default_value(self):
        """Test process_config with default_value"""
        viewset = SpaceConfigAdminViewSet()
        config_dict = {"name": "test", "default_value": "value"}
        result = viewset.process_config(config_dict)
        assert result["default_value"] == "value"

    def test_process_config_without_default_value(self):
        """Test process_config without default_value"""
        viewset = SpaceConfigAdminViewSet()
        config_dict = {"name": "test"}
        result = viewset.process_config(config_dict)
        assert result["default_value"] is None


@pytest.mark.django_db
class TestSpaceConfigViewSet:
    def test_process_config_with_default_value(self):
        """Test process_config with default_value"""
        viewset = SpaceConfigViewSet()
        config_dict = {"name": "test", "default_value": "value"}
        result = viewset.process_config(config_dict)
        assert result["default_value"] == "value"

    def test_process_config_without_default_value(self):
        """Test process_config without default_value"""
        viewset = SpaceConfigViewSet()
        config_dict = {"name": "test"}
        result = viewset.process_config(config_dict)
        assert result["default_value"] is None
