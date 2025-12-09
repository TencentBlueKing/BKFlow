"""
Simplified tests for bkflow/space/views.py focusing on coverage
"""
from unittest import mock

import pytest

from bkflow.space.models import Credential, CredentialType, Space
from bkflow.space.views import (
    CredentialConfigAdminViewSet,
    SpaceConfigAdminViewSet,
    SpaceConfigViewSet,
    SpaceFilterSet,
    SpaceInternalViewSet,
)


@pytest.mark.django_db
class TestSpaceFilterSet:
    def test_filter_by_id_or_name_with_digit(self):
        """Test filter_by_id_or_name with digit value"""
        space1 = Space.objects.create(id=100, name="Test Space", app_code="app1")
        Space.objects.create(id=200, name="Another", app_code="app2")

        queryset = Space.objects.all()
        result = SpaceFilterSet.filter_by_id_or_name(queryset, "id_or_name", "100")
        assert space1 in result

    def test_filter_by_id_or_name_with_text(self):
        """Test filter_by_id_or_name with text value"""
        space1 = Space.objects.create(name="Test Space", app_code="app1")
        space2 = Space.objects.create(name="Another", app_code="app2")

        queryset = Space.objects.all()
        result = SpaceFilterSet.filter_by_id_or_name(queryset, "id_or_name", "Test")
        assert space1 in result
        assert space2 not in result

    def test_filter_by_id_or_name_empty(self):
        """Test filter_by_id_or_name with empty value"""
        Space.objects.create(name="Test1", app_code="app1")
        Space.objects.create(name="Test2", app_code="app2")

        queryset = Space.objects.all()
        result = SpaceFilterSet.filter_by_id_or_name(queryset, "id_or_name", "")
        assert result.count() == 2


@pytest.mark.django_db
class TestSpaceInternalViewSet:
    def test_get_credential_config_string(self):
        """Test get_credential_config with string config"""
        space = Space.objects.create(name="Test", app_code="test")
        Credential.objects.create(
            space_id=space.id, name="test_cred", type=CredentialType.BK_APP.value, content={"key": "value"}
        )

        viewset = SpaceInternalViewSet()
        result = viewset.get_credential_config("test_cred", space.id, "default")

        assert result == {"key": "value"}

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

    def test_get_credential_config_not_found(self):
        """Test get_credential_config when credential doesn't exist"""
        space = Space.objects.create(name="Test", app_code="test")

        viewset = SpaceInternalViewSet()
        result = viewset.get_credential_config("nonexistent", space.id, "default")

        assert result == {}


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
class TestCredentialConfigAdminViewSet:
    def test_get_object(self):
        """Test get_object method"""
        space = Space.objects.create(name="Test", app_code="test")
        credential = Credential.objects.create(
            space_id=space.id, name="test_cred", type=CredentialType.BK_APP.value, content={"key": "value"}
        )

        viewset = CredentialConfigAdminViewSet()
        viewset.kwargs = {"pk": credential.id}
        viewset.queryset = Credential.objects.all()

        # Mock request
        mock_request = mock.Mock()
        mock_request.query_params = {"space_id": space.id}
        viewset.request = mock_request

        obj = viewset.get_object()
        assert obj.id == credential.id

    def test_get_queryset(self):
        """Test get_queryset filters by space_id"""
        space1 = Space.objects.create(name="Test1", app_code="test1")
        space2 = Space.objects.create(name="Test2", app_code="test2")

        cred1 = Credential.objects.create(
            space_id=space1.id, name="cred1", type=CredentialType.BK_APP.value, content={}
        )
        cred2 = Credential.objects.create(
            space_id=space2.id, name="cred2", type=CredentialType.BK_APP.value, content={}
        )

        viewset = CredentialConfigAdminViewSet()
        mock_request = mock.Mock()
        mock_request.query_params = {"space_id": space1.id}
        viewset.request = mock_request

        queryset = viewset.get_queryset()
        assert cred1 in queryset
        assert cred2 not in queryset


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
