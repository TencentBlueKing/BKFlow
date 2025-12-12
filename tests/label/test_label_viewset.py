import pytest
from blueapps.account.models import User
from rest_framework import status
from rest_framework.test import APIRequestFactory

from bkflow.label.models import Label
from bkflow.label.views import LabelViewSet
from .test_label import make_label
# Enable database access for all tests in this module
pytestmark = pytest.mark.django_db


class TestLabelViewSet:
    """Tests for LabelViewSet API behavior."""

    def setup_method(self):
        """Prepare APIRequestFactory and an admin user for each test."""
        self.factory = APIRequestFactory()
        # Admin user to pass AdminPermission and provide username for CustomViewSetMixin
        self.admin_user, created = User.objects.get_or_create(
            username="label_admin",
            defaults={
                "is_superuser": True,
                "is_staff": True,
            },
        )

        self.list_view = LabelViewSet.as_view({"get": "list"})
        self.create_view = LabelViewSet.as_view({"post": "create"})
        self.destroy_view = LabelViewSet.as_view({"delete": "destroy"})

    def test_list_returns_root_labels_with_has_children_flag(self):
        """list should return only root labels when parent_id is not provided."""
        root = make_label("root", space_id=1)
        child = make_label("child", space_id=1, parent_id=root.id)
        other_space_root = make_label("other_space_root", space_id=2)

        url = "/api/label/"
        request = self.factory.get(
            url,
            {"space_id": 1, "label_scope": "task", "limit": -1},
        )
        request.user = self.admin_user

        response = self.list_view(request)
        assert response.status_code == status.HTTP_200_OK

        # SimpleGenericViewSet wraps DRF response data into {"result": True, "data": ..., "code": "0", "message": ""}
        data = response.data["data"]
        results = data["results"]
        returned_ids = {item["id"] for item in results}

        # Only root labels in space 1 should be returned
        assert root.id in returned_ids
        assert other_space_root.id not in returned_ids
        assert child.id not in returned_ids

        # All returned labels should be roots; root with children should have has_children=True
        for item in results:
            label_obj = Label.objects.get(id=item["id"])
            assert label_obj.parent_id is None
            if item["id"] == root.id:
                assert item["has_children"] is True

    def test_create_nested_name_creates_parent_and_child(self):
        """create should support 'parent/child' name format and auto-create parent label."""
        url = "/api/label/"
        payload = {
            "name": "ParentLabel/ChildLabel",
            "space_id": 1,
            "color": "#123456",
            "label_scope": ["task"],
        }
        request = self.factory.post(url, payload, format="json")
        request.user = self.admin_user

        response = self.create_view(request)
        assert response.status_code == status.HTTP_201_CREATED

        # SimpleGenericViewSet wraps data under "data"
        resp_data = response.data["data"]
        assert resp_data["name"] == "ChildLabel"

        # Parent should be auto-created as a root label
        parent = Label.objects.get(name="ParentLabel", parent_id__isnull=True)
        child = Label.objects.get(id=resp_data["id"])

        assert child.parent_id == parent.id
        assert child.full_path == "ParentLabel/ChildLabel"

    def test_destroy_root_label_cascades_children(self):
        """destroy should delete root label and all of its direct children."""
        root = make_label("root_to_delete", space_id=1)
        child1 = make_label("child1", space_id=1, parent_id=root.id)
        child2 = make_label("child2", space_id=1, parent_id=root.id)

        url = f"/api/label/{root.id}/"
        request = self.factory.delete(url)
        request.user = self.admin_user

        response = self.destroy_view(request, pk=root.id)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        assert not Label.objects.filter(id=root.id).exists()
        assert not Label.objects.filter(id__in=[child1.id, child2.id]).exists()
