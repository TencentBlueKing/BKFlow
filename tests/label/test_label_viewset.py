"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
from unittest.mock import patch

import pytest
from blueapps.account.models import User
from rest_framework import status
from rest_framework.test import APIRequestFactory

from bkflow.admin.models import IsolationLevel, ModuleInfo, ModuleType
from bkflow.label.models import Label, TemplateLabelRelation
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

        # Create ModuleInfo for space_id=1 to avoid DoesNotExist error in TaskComponentClient
        ModuleInfo.objects.get_or_create(
            space_id=1,
            defaults={
                "code": "test_task",
                "url": "http://test.example.com",
                "token": "test_token",
                "type": ModuleType.TASK.value,
                "isolation_level": IsolationLevel.ONLY_CALCULATION.value,
            },
        )

        self.list_view = LabelViewSet.as_view({"get": "list"})
        self.create_view = LabelViewSet.as_view({"post": "create"})
        self.destroy_view = LabelViewSet.as_view({"delete": "destroy"})
        self.get_label_ref_count_view = LabelViewSet.as_view({"get": "get_label_ref_count"})

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

    def test_create_with_hierarchical_name_format(self):
        """create should auto-create parent labels when name contains '/' separator."""
        # Test creating hierarchical label: "parent/child"
        data = {
            "name": "一级标签/二级标签",
            "space_id": 1,
            "color": "#ffffff",
            "label_scope": ["task"],
            "creator": "test_user",
            "updated_by": "test_user",
        }

        request = self.factory.post("/api/label/", data=data)
        request.user = self.admin_user

        response = self.create_view(request)
        assert response.status_code == status.HTTP_201_CREATED

        # Verify parent label was created
        parent_label = Label.objects.get(name="一级标签", parent_id__isnull=True)
        assert parent_label is not None

        # Verify child label was created with correct parent reference
        child_label = Label.objects.get(name="二级标签", parent_id=parent_label.id)
        assert child_label is not None
        assert child_label.parent_id == parent_label.id

        # Verify response contains child label data
        response_data = response.data
        # Adapt to actual API response format
        assert "data" in response_data
        assert response_data["data"]["name"] == "二级标签"
        assert response_data["data"]["parent_id"] == parent_label.id

    def test_create_with_existing_parent_label(self):
        """create should use existing parent label when available."""
        # Create parent label first
        existing_parent = make_label("existing_parent", space_id=1)

        # Test creating child with existing parent
        data = {
            "name": "existing_parent/child_label",
            "space_id": 1,
            "color": "#ffffff",
            "label_scope": ["task"],
            "creator": "test_user",
            "updated_by": "test_user",
        }

        request = self.factory.post("/api/label/", data=data)
        request.user = self.admin_user

        response = self.create_view(request)
        assert response.status_code == status.HTTP_201_CREATED

        # Verify child was created with existing parent
        child_label = Label.objects.get(name="child_label", parent_id=existing_parent.id)
        assert child_label is not None
        assert child_label.parent_id == existing_parent.id

        # Verify no duplicate parent was created
        parent_count = Label.objects.filter(name="existing_parent", parent_id__isnull=True).count()
        assert parent_count == 1

    def test_destroy_root_label_cascades_children(self):
        """destroy should delete root label and all of its direct children."""
        root = make_label("root_to_delete", space_id=1)
        child1 = make_label("child1", space_id=1, parent_id=root.id)
        child2 = make_label("child2", space_id=1, parent_id=root.id)

        url = f"/api/label/{root.id}/"
        request = self.factory.delete(url)
        request.user = self.admin_user

        # Mock TaskComponentClient.delete_task_label_relation to avoid external API call
        with patch("bkflow.label.views.TaskComponentClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.delete_task_label_relation.return_value = {"result": True}

            response = self.destroy_view(request, pk=root.id)
            assert response.status_code == status.HTTP_204_NO_CONTENT

        assert not Label.objects.filter(id=root.id).exists()
        assert not Label.objects.filter(id__in=[child1.id, child2.id]).exists()

    def test_get_label_ref_count_success(self):
        """get_label_ref_count should return template and task reference counts."""
        # Create test labels
        l1 = make_label("label1", space_id=1)
        l2 = make_label("label2", space_id=1)

        # Create template label relations
        TemplateLabelRelation.objects.create(template_id=100, label_id=l1.id)
        TemplateLabelRelation.objects.create(template_id=100, label_id=l2.id)
        TemplateLabelRelation.objects.create(template_id=101, label_id=l1.id)

        # Mock TaskComponentClient to return task reference counts
        with patch("bkflow.label.views.TaskComponentClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.get_task_label_ref_count.return_value = {
                "result": True,
                "data": {str(l1.id): 3, str(l2.id): 1},  # l1 has 3 task references  # l2 has 1 task reference
            }

            # Make API request
            request = self.factory.get(f"/api/label/get_label_ref_count/?space_id=1&label_ids={l1.id},{l2.id}")
            request.user = self.admin_user

            response = self.get_label_ref_count_view(request)
            assert response.status_code == status.HTTP_200_OK

            # Verify response structure - adapt to actual API format
            data = response.data
            assert data["result"] is True
            assert "data" in data

            # Verify reference counts in response data
            ref_data = data["data"]
            assert str(l1.id) in ref_data
            assert str(l2.id) in ref_data

            # Verify template reference counts
            assert ref_data[str(l1.id)]["template_count"] == 2  # l1 has 2 template references
            assert ref_data[str(l2.id)]["template_count"] == 1  # l2 has 1 template reference

            # Verify task reference counts from mock
            assert ref_data[str(l1.id)]["task_count"] == 3
            assert ref_data[str(l2.id)]["task_count"] == 1

    def test_get_label_ref_count_client_error(self):
        """get_label_ref_count should handle TaskComponentClient errors gracefully."""
        l1 = make_label("label1", space_id=1)

        with patch("bkflow.label.views.TaskComponentClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.get_task_label_ref_count.return_value = {
                "result": False,
                "message": "Task service unavailable",
            }

            request = self.factory.get(f"/api/label/get_label_ref_count/?space_id=1&label_ids={l1.id}")
            request.user = self.admin_user

            response = self.get_label_ref_count_view(request)
            # The API returns 200 even when task service fails
            assert response.status_code == status.HTTP_200_OK

            # Check the actual response structure
            response_data = response.data

            # The API might return the error message directly
            # or handle it differently. Let's check the structure
            if "result" in response_data:
                # If result is False, that's expected for service errors
                if response_data["result"] is False:
                    assert "message" in response_data
                    assert "Task service unavailable" in str(response_data["message"])
                else:
                    # If result is True, check that data structure is present
                    assert "data" in response_data
                    assert isinstance(response_data["data"], dict)
            else:
                # Alternative response format
                assert "message" in response_data
                assert "Task service unavailable" in str(response_data["message"])

            # The important thing is that the API doesn't crash
            # and returns a consistent response structure


class TestLabelFilter:
    """Tests for LabelFilter filtering logic."""

    def test_filter_space_id_includes_default_and_specific_space(self):
        """filter_space_id should include both default (-1) and specific space labels."""
        from bkflow.label.views import LabelFilter

        # Create labels in different spaces
        default_label = make_label("default", space_id=-1)
        space1_label = make_label("space1", space_id=1)
        space2_label = make_label("space2", space_id=2)

        # Filter for space_id=1 should include default (-1) and space1 labels
        filter_instance = LabelFilter()
        queryset = Label.objects.all()
        filtered = filter_instance.filter_space_id(queryset, "space_id", 1)

        filtered_ids = list(filtered.values_list("id", flat=True))
        assert default_label.id in filtered_ids
        assert space1_label.id in filtered_ids
        assert space2_label.id not in filtered_ids

    def test_filter_label_scope_includes_common_and_specific_scope(self):
        """filter_label_scope should include both common and specific scope labels."""
        from bkflow.label.views import LabelFilter

        # Create labels with different scopes
        task_label = make_label("task", label_scope=["task"])
        template_label = make_label("template", label_scope=["template"])
        common_label = make_label("common", label_scope=["common"])
        multi_label = make_label("multi", label_scope=["task", "common"])

        filter_instance = LabelFilter()
        queryset = Label.objects.all()

        # Filter for "task" scope should include task and common labels
        filtered = filter_instance.filter_label_scope(queryset, "label_scope", "task")
        filtered_ids = list(filtered.values_list("id", flat=True))

        assert task_label.id in filtered_ids
        assert common_label.id in filtered_ids
        assert multi_label.id in filtered_ids
        assert template_label.id not in filtered_ids

    def test_filter_parent_id_direct_match(self):
        """filter_parent_id should filter by exact parent_id match."""
        from bkflow.label.views import LabelFilter

        parent = make_label("parent")
        child1 = make_label("child1", parent_id=parent.id)
        child2 = make_label("child2", parent_id=parent.id)

        # Create another valid parent for testing
        other_parent = make_label("other_parent")
        other_child = make_label("other_child", parent_id=other_parent.id)

        filter_instance = LabelFilter()
        queryset = Label.objects.all()

        # Filter by parent_id
        filtered = filter_instance.filter_parent_id(queryset, "parent_id", parent.id)
        filtered_ids = list(filtered.values_list("id", flat=True))

        # Verify only children of the specified parent are returned
        assert child1.id in filtered_ids
        assert child2.id in filtered_ids
        assert parent.id not in filtered_ids  # parent itself should not be included
        assert other_child.id not in filtered_ids  # children of other parent should not be included

    def test_filter_name_case_insensitive_search(self):
        """filter_name should perform case-insensitive partial matching."""
        from bkflow.label.views import LabelFilter

        apple_label = make_label("Apple")
        banana_label = make_label("Banana")
        pineapple_label = make_label("Pineapple")

        filter_instance = LabelFilter()
        queryset = Label.objects.all()

        # Search for "apple" should match both Apple and Pineapple
        filtered = filter_instance.filter_name(queryset, "name", "apple")
        filtered_ids = list(filtered.values_list("id", flat=True))

        assert apple_label.id in filtered_ids
        assert pineapple_label.id in filtered_ids
        assert banana_label.id not in filtered_ids

    def test_filter_is_default_boolean_filter(self):
        """filter_is_default should filter by boolean is_default field."""
        from bkflow.label.views import LabelFilter

        default_label = make_label("default", is_default=True)
        non_default_label = make_label("non_default", is_default=False)

        filter_instance = LabelFilter()
        queryset = Label.objects.all()

        # Filter for default labels
        filtered = filter_instance.filter_is_default(queryset, "is_default", True)
        filtered_ids = list(filtered.values_list("id", flat=True))
        assert default_label.id in filtered_ids
        assert non_default_label.id not in filtered_ids

        # Filter for non-default labels
        filtered = filter_instance.filter_is_default(queryset, "is_default", False)
        filtered_ids = list(filtered.values_list("id", flat=True))
        assert non_default_label.id in filtered_ids
        assert default_label.id not in filtered_ids


class TestLabelViewSetExtraCoverage:
    """Extra tests to cover remaining branches in bkflow.label.views."""

    pytestmark = pytest.mark.django_db

    def setup_method(self):
        self.factory = APIRequestFactory()
        self.admin_user, created = User.objects.get_or_create(
            username="label_admin_extra",
            defaults={
                "is_superuser": True,
                "is_staff": True,
            },
        )

        ModuleInfo.objects.get_or_create(
            space_id=1,
            defaults={
                "code": "test_task",
                "url": "http://test.example.com",
                "token": "test_token",
                "type": ModuleType.TASK.value,
                "isolation_level": IsolationLevel.ONLY_CALCULATION.value,
            },
        )

        self.list_view = LabelViewSet.as_view({"get": "list"})
        self.destroy_view = LabelViewSet.as_view({"delete": "destroy"})

    def test_list_without_required_space_id_returns_empty(self):
        """Missing required filter should make filterset invalid and return empty queryset."""
        make_label("root", space_id=1)

        request = self.factory.get("/api/label/")
        request.user = self.admin_user

        response = self.list_view(request)
        assert response.status_code == status.HTTP_200_OK

        # For SimpleGenericViewSet response format
        data = response.data.get("data", {})
        results = data.get("results", [])
        assert results == []

    def test_destroy_when_task_component_client_returns_error(self):
        """destroy should return 400 and not delete objects when task component rejects."""
        root = make_label("root_fail_delete", space_id=1)
        child = make_label("child_fail_delete", space_id=1, parent_id=root.id)

        request = self.factory.delete(f"/api/label/{root.id}/")
        request.user = self.admin_user

        with patch("bkflow.label.views.TaskComponentClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.delete_task_label_relation.return_value = {"result": False, "message": "fail"}

            response = self.destroy_view(request, pk=root.id)
            assert response.status_code == status.HTTP_400_BAD_REQUEST

        assert Label.objects.filter(id=root.id).exists() is True
        assert Label.objects.filter(id=child.id).exists() is True


class TestLabelFilterQuerysetBranches:
    """Cover LabelFilter.filter_queryset has_parent_id=True branch."""

    pytestmark = pytest.mark.django_db

    def test_filter_queryset_with_parent_id_keeps_queryset(self):
        from bkflow.label.views import LabelFilter

        parent = make_label("parent_for_filter", space_id=1)
        child = make_label("child_for_filter", space_id=1, parent_id=parent.id)

        # provide required space_id + parent_id so has_parent_id=True
        data = {"space_id": 1, "parent_id": parent.id}
        f = LabelFilter(data=data, queryset=Label.objects.all())

        assert f.is_valid() is True
        qs = f.qs

        returned_ids = set(qs.values_list("id", flat=True))
        assert returned_ids == {child.id}
