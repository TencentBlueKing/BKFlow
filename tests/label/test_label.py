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
import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from bkflow.label.models import Label, TemplateLabelRelation

# Enable database access for all tests in this module
pytestmark = pytest.mark.django_db


def make_label(
    name,
    space_id=1,
    parent_id=None,
    label_scope=None,
    creator="tester",
    updated_by="tester",
    color="#ffffff",
    is_default=False,
):
    """
    Helper factory for creating Label instances with sensible defaults.
    """
    if label_scope is None:
        label_scope = ["task"]
    return Label.objects.create(
        name=name,
        space_id=space_id,
        parent_id=parent_id,
        label_scope=label_scope,
        creator=creator,
        updated_by=updated_by,
        color=color,
        is_default=is_default,
    )


class TestLabelManager:
    """
    Tests for custom methods defined in LabelManager.
    """

    def test_check_label_ids_true_and_false(self):
        """
        check_label_ids should return True only when all ids exist.
        """
        l1 = make_label("label1")
        l2 = make_label("label2")

        assert Label.objects.check_label_ids([l1.id, l2.id]) is True
        # add a non-existing id
        assert Label.objects.check_label_ids([l1.id, l2.id, 999999]) is False

    def test_get_root_labels_filters_by_space_and_scope(self):
        """
        get_root_labels should respect space_id and optional label_scope.
        """
        # space 1 roots
        root_task = make_label("root_task", space_id=1, label_scope=["task"])
        root_template = make_label("root_template", space_id=1, label_scope=["template"])
        # different space root
        root_other_space = make_label("root_other_space", space_id=2, label_scope=["task"])
        # child in space 1
        child = make_label("child", space_id=1, parent_id=root_task.id, label_scope=["task"])

        roots_task = Label.objects.get_root_labels(space_id=1, label_scope="task")
        roots_all_space1 = Label.objects.get_root_labels(space_id=1)

        # only the task root should appear when label_scope="task"
        assert list(roots_task.values_list("id", flat=True)) == [root_task.id]

        # all roots in space 1 (both task and template), children must not appear
        assert set(roots_all_space1.values_list("id", flat=True)) == {
            root_task.id,
            root_template.id,
        }
        assert child.id not in roots_all_space1.values_list("id", flat=True)
        assert root_other_space.id not in roots_all_space1.values_list("id", flat=True)

    def test_get_sub_labels_recursive_and_non_recursive(self):
        """
        get_sub_labels should support both direct and recursive queries.
        """
        root = make_label("root")
        child1 = make_label("child1", parent_id=root.id)
        child2 = make_label("child2", parent_id=root.id)
        grandchild = make_label("grandchild", parent_id=child1.id)

        # non-recursive: only direct children
        direct_children = Label.objects.get_sub_labels(root.id, recursive=False)
        names = list(direct_children.values_list("name", flat=True))
        assert names == ["child1", "child2"]

        # recursive: all descendants as list
        all_descendants = Label.objects.get_sub_labels(root.id, recursive=True)
        ids = {label.id for label in all_descendants}
        assert ids == {child1.id, child2.id, grandchild.id}
        assert isinstance(all_descendants, list)

    def test_get_parent_label_and_is_root(self):
        """
        get_parent_label should return parent for children and None for roots.
        is_root should be True only for roots.
        """
        root = make_label("root")
        child = make_label("child", parent_id=root.id)

        assert Label.objects.get_parent_label(child.id) == root
        assert Label.objects.get_parent_label(root.id) is None
        assert Label.objects.get_parent_label(999999) is None

        assert root.is_root() is True
        assert child.is_root() is False

    def test_get_labels_map_returns_full_info(self):
        """
        get_labels_map should return label info including full_path.
        """
        root = make_label("root")
        child = make_label("child", parent_id=root.id, color="#123456")

        labels_map = Label.objects.get_labels_map([child.id])

        assert set(labels_map.keys()) == {child.id}
        info = labels_map[child.id]
        assert info["id"] == child.id
        assert info["name"] == "child"
        assert info["color"] == "#123456"
        assert info["full_path"] == child.full_path
        # full_path should include both root and child names
        assert info["full_path"].split("/") == ["root", "child"]


class TestLabelModel:
    """
    Tests for Label model instance methods and validation logic.
    """

    def test_full_path_builds_hierarchy(self):
        """
        full_path should join names from root to current label with "/".
        """
        root = make_label("root")
        child = make_label("child", parent_id=root.id)
        grandchild = make_label("grandchild", parent_id=child.id)

        assert root.full_path == "root"
        assert child.full_path == "root/child"
        assert grandchild.full_path == "root/child/grandchild"

    def test_str_contains_parent_name_or_default(self):
        """__str__ should include parent name when available, otherwise use default text."""
        root = make_label("root_for_str")
        child = make_label("child_for_str", parent_id=root.id)

        assert "root_for_str" in str(child)
        assert "child_for_str" in str(child)
        assert "父标签：无" in str(root)

    def test_label_clean_validates_parent_space(self):
        """
        save should fail when child's space_id does not match parent space_id.
        """
        parent = make_label("parent", space_id=1)
        # do not save child yet; we expect validation error on save()
        child = Label(
            name="child_wrong_space",
            space_id=2,  # different space from parent
            parent_id=parent.id,
            label_scope=["task"],
            creator="tester",
            updated_by="tester",
        )

        with pytest.raises(DjangoValidationError) as exc:
            child.save()

        msg = str(exc.value)
        assert "子标签的空间ID必须与父标签一致" in msg

    def test_label_clean_raises_for_missing_parent(self):
        """
        save should fail when parent_id points to a non-existing label.
        """
        child = Label(
            name="child_missing_parent",
            space_id=1,
            parent_id=999999,  # non-existent
            label_scope=["task"],
            creator="tester",
            updated_by="tester",
        )

        with pytest.raises(DjangoValidationError) as exc:
            child.save()

        msg = str(exc.value)
        assert "父标签不存在" in msg

    def test_label_clean_prevents_cycle_reference(self):
        """
        save should prevent cycles like A -> B -> A.
        """
        parent = make_label("parent")
        child = make_label("child", parent_id=parent.id)

        # introduce a cycle: parent -> child, child -> parent already exists
        parent.parent_id = child.id

        with pytest.raises(DjangoValidationError) as exc:
            parent.save()

        msg = str(exc.value)
        assert "禁止循环引用" in msg

    def test_label_clean_breaks_when_ancestor_missing(self):
        """Cycle check should break gracefully when an ancestor record is missing."""
        parent = make_label("parent_inconsistent")
        # Create an inconsistent chain: parent.parent_id points to a missing label.
        # Use queryset.update to bypass model clean/save.
        Label.objects.filter(id=parent.id).update(parent_id=999999)

        child = Label(
            name="child_ok",
            space_id=parent.space_id,
            parent_id=parent.id,
            label_scope=["task"],
            creator="tester",
            updated_by="tester",
        )
        # Should not raise, even though parent's parent is missing.
        child.save()

    def test_get_all_children_delegates_to_manager(self):
        """
        get_all_children should delegate to LabelManager.get_sub_labels.
        """
        root = make_label("root")
        child1 = make_label("child1", parent_id=root.id)
        child2 = make_label("child2", parent_id=root.id)
        grandchild = make_label("grandchild", parent_id=child1.id)

        # non-recursive: only direct children
        direct_children = root.get_all_children(recursive=False)
        assert set(direct_children.values_list("id", flat=True)) == {
            child1.id,
            child2.id,
        }

        # recursive: all descendants as list
        all_descendants = root.get_all_children(recursive=True)
        ids = {label.id for label in all_descendants}
        assert ids == {child1.id, child2.id, grandchild.id}

    def test_get_label_ids_by_names(self):
        """get_label_ids_by_names should return label IDs matching given names."""
        l1 = make_label("apple")
        l2 = make_label("banana")

        # Test exact name matching
        ids = Label.get_label_ids_by_names("apple")
        assert ids == [l1.id]

        # Test multiple names separated by commas
        ids = Label.get_label_ids_by_names("apple,banana")
        assert set(ids) == {l1.id, l2.id}

        # Test multiple names separated by spaces
        ids = Label.get_label_ids_by_names("apple banana")
        assert set(ids) == {l1.id, l2.id}

        # Test case insensitive matching
        ids = Label.get_label_ids_by_names("APPLE")
        assert ids == [l1.id]

        # Test partial matching
        ids = Label.get_label_ids_by_names("app")
        assert ids == [l1.id]

        # Test no matches
        ids = Label.get_label_ids_by_names("grape")
        assert ids == []

        # Test empty input
        ids = Label.get_label_ids_by_names("")
        assert ids == []

        # Test with extra whitespace
        ids = Label.get_label_ids_by_names("  apple  ,  banana  ")
        assert set(ids) == {l1.id, l2.id}


class TestTemplateLabelRelationManager:
    """
    Tests for BaseLabelRelationManager via TemplateLabelRelation.
    """

    def test_set_and_fetch_labels(self):
        """
        set_labels and fetch_labels should correctly manage template-label relations.
        """
        l1 = make_label("label1")
        l2 = make_label("label2")
        l3 = make_label("label3")

        template_id = 100

        # initial set: {l1, l2}
        TemplateLabelRelation.objects.set_labels(template_id, [l1.id, l2.id])
        current_ids = set(
            TemplateLabelRelation.objects.filter(template_id=template_id).values_list("label_id", flat=True)
        )
        assert current_ids == {l1.id, l2.id}

        # update set: {l2, l3} -> l1 removed, l3 added
        TemplateLabelRelation.objects.set_labels(template_id, [l2.id, l3.id])
        current_ids = set(
            TemplateLabelRelation.objects.filter(template_id=template_id).values_list("label_id", flat=True)
        )
        assert current_ids == {l2.id, l3.id}

        # fetch_labels should return label descriptions with full_path
        labels = TemplateLabelRelation.objects.fetch_labels(template_id)
        returned_ids = {item["id"] for item in labels}
        assert returned_ids == {l2.id, l3.id}
        for item in labels:
            assert "name" in item
            assert "color" in item
            assert "full_path" in item

    def test_fetch_objects_labels(self):
        """
        fetch_objects_labels should return a mapping {obj_id: [label_info, ...]}.
        """
        l1 = make_label("label1")
        l2 = make_label("label2")
        l3 = make_label("label3")

        t1 = 101
        t2 = 102

        TemplateLabelRelation.objects.set_labels(t1, [l1.id, l2.id])
        TemplateLabelRelation.objects.set_labels(t2, [l2.id, l3.id])

        result = TemplateLabelRelation.objects.fetch_objects_labels([t1, t2], label_fields=("name", "color"))

        assert set(result.keys()) == {t1, t2}
        ids_t1 = {label["id"] for label in result[t1]}
        ids_t2 = {label["id"] for label in result[t2]}
        assert ids_t1 == {l1.id, l2.id}
        assert ids_t2 == {l2.id, l3.id}

        # each label dict should contain requested fields and full_path
        for labels in result.values():
            for item in labels:
                assert set(item.keys()) >= {"id", "name", "color", "full_path"}

    def test_fetch_objects_labels_returns_empty_when_no_relations(self):
        """fetch_objects_labels should return {} when the provided objects have no relations."""
        assert TemplateLabelRelation.objects.fetch_objects_labels([999999], label_fields=("name", "color")) == {}


class TestLabelSerializer:
    """Tests for LabelSerializer validation logic."""

    def test_validate_color_valid_and_invalid_formats(self):
        """validate_color should accept valid hex colors and reject invalid ones."""
        from rest_framework.test import APIRequestFactory

        from bkflow.label.serializers import LabelSerializer

        factory = APIRequestFactory()
        request = factory.post("/api/label/", data={"space_id": 1})

        # Test individual validation method
        serializer = LabelSerializer(context={"request": request})

        # Valid hex colors should pass
        assert serializer.validate_color("#ffffff") == "#ffffff"
        assert serializer.validate_color("#000000") == "#000000"
        assert serializer.validate_color("#FF00FF") == "#FF00FF"

        # Invalid hex colors should raise ValidationError - this is CORRECT behavior
        with pytest.raises(DRFValidationError) as exc:
            serializer.validate_color("ffffff")  # missing #
        assert "颜色格式错误" == str(exc.value.detail[0])

        with pytest.raises(DRFValidationError) as exc:
            serializer.validate_color("#fff")  # wrong length
        assert "颜色格式错误" == str(exc.value.detail[0])

        with pytest.raises(DRFValidationError) as exc:
            serializer.validate_color("#gggggg")  # invalid characters
        assert "颜色格式错误" == str(exc.value.detail[0])

        with pytest.raises(DRFValidationError) as exc:
            serializer.validate_color("#12345")  # wrong length
        assert "颜色格式错误" == str(exc.value.detail[0])

    def test_validate_name_duplicate_check(self):
        """validate_name should prevent duplicate names within same space and parent."""
        from rest_framework.test import APIRequestFactory

        from bkflow.label.serializers import LabelSerializer

        # Create initial label
        existing_label = make_label("existing_label", space_id=1, color="#ffffff", label_scope=["task"])

        factory = APIRequestFactory()

        # Test duplicate detection on create
        request = factory.post("/api/label/", data={"space_id": 1})

        # Provide all required fields
        serializer = LabelSerializer(
            data={"space_id": 1, "name": "existing_label", "color": "#ffffff", "label_scope": ["task"]},
            context={"request": request},
        )

        # Should raise validation error for duplicate name - this is CORRECT behavior
        with pytest.raises(DRFValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "该空间下已存在名称为「existing_label」的标签" == exc.value.detail["name"][0]

        # Test duplicate detection on update (should exclude self)
        request = factory.put(f"/api/label/{existing_label.id}/", data={"space_id": 1})
        serializer = LabelSerializer(
            instance=existing_label,
            data={"space_id": 1, "name": "existing_label", "color": "#ffffff", "label_scope": ["task"]},
            context={"request": request},
        )
        # Should not raise for same name when updating self
        assert serializer.is_valid() is True

        # Should raise for duplicate with different label
        existing_label2 = make_label("existing_label2", space_id=1, color="#ffffff", label_scope=["task"])
        request = factory.put(f"/api/label/{existing_label2.id}/", data={"space_id": 1})
        serializer = LabelSerializer(
            instance=existing_label2,
            data={"space_id": 1, "name": "existing_label", "color": "#ffffff", "label_scope": ["task"]},
            context={"request": request},
        )
        with pytest.raises(DRFValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        error_message = str(exc.value)
        assert "该空间下已存在名称为「existing_label」的标签" in error_message

    def test_validate_label_scope_parent_validation(self):
        """validate_label_scope should enforce parent-child scope consistency."""
        from rest_framework.test import APIRequestFactory

        from bkflow.label.serializers import LabelSerializer

        # Create parent with specific scope
        parent = make_label("parent", label_scope=["task", "template"], color="#ffffff", space_id=1)

        factory = APIRequestFactory()

        # Valid child scope (subset of parent)
        request = factory.post("/api/label/", data={"parent_id": parent.id})

        # Valid: child scope is subset of parent scope
        serializer = LabelSerializer(
            data={"parent_id": parent.id, "name": "child", "color": "#ffffff", "label_scope": ["task"], "space_id": 1},
            context={"request": request},
        )

        # The validation should pass for valid subset
        assert serializer.is_valid() is True

        # Invalid: child scope not subset of parent scope
        serializer = LabelSerializer(
            data={
                "parent_id": parent.id,
                "name": "child",
                "color": "#ffffff",
                "label_scope": ["common"],
                "space_id": 1,
            },
            context={"request": request},
        )

        # Should raise ValidationError for invalid scope - this is CORRECT behavior
        with pytest.raises(DRFValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "子标签的范围必须是父标签的子集" == exc.value.detail["label_scope"][0]

        # Invalid: parent doesn't exist
        request = factory.post("/api/label/", data={"parent_id": 999999})
        serializer = LabelSerializer(
            data={"parent_id": 999999, "name": "child", "color": "#ffffff", "label_scope": ["task"], "space_id": 1},
            context={"request": request},
        )

        with pytest.raises(DRFValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "父标签不存在" in str(exc.value)

    def test_validate_name_empty_and_whitespace(self):
        """validate_name should reject empty and whitespace-only names."""
        from rest_framework.test import APIRequestFactory

        from bkflow.label.serializers import LabelSerializer

        factory = APIRequestFactory()
        request = factory.post("/api/label/", data={"space_id": 1})

        # Test with empty name
        serializer = LabelSerializer(
            data={"space_id": 1, "name": "", "color": "#ffffff", "label_scope": ["task"]}, context={"request": request}
        )

        # Should raise validation error for empty name - this is CORRECT behavior
        with pytest.raises(DRFValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "该字段不能为空。" == exc.value.detail["name"][0]

        # Test with whitespace-only name
        serializer = LabelSerializer(
            data={"space_id": 1, "name": "   ", "color": "#ffffff", "label_scope": ["task"]},
            context={"request": request},
        )

        with pytest.raises(DRFValidationError) as exc:
            serializer.is_valid(raise_exception=True)

        # Valid name with surrounding whitespace should be trimmed
        serializer = LabelSerializer(
            data={"space_id": 1, "name": "  valid_name  ", "color": "#ffffff", "label_scope": ["task"]},
            context={"request": request},
        )

        assert serializer.is_valid() is True
        assert serializer.validated_data["name"] == "valid_name"

    def test_validate_name_custom_error_when_blank_after_strip(self):
        """Direct validate_name should raise the custom error when value becomes blank after strip."""
        from bkflow.label.serializers import LabelSerializer

        serializer = LabelSerializer()
        with pytest.raises(DRFValidationError) as exc:
            serializer.validate_name("   ")
        assert "标签名称不能为空" == str(exc.value.detail[0])


class TestLabelPermission:
    """Tests for bkflow.label.permissions.LabelPermission."""

    def test_get_resource_type(self):
        from bkflow.label.permissions import LabelPermission

        assert LabelPermission().get_resource_type() == "LABEL"

    def test_has_object_permission_edit_actions_use_edit_permission_only(self, monkeypatch):
        """When action is in EDIT_ABOVE_ACTIONS, only edit permission matters."""
        from types import SimpleNamespace

        from bkflow.label.permissions import LabelPermission

        perm = LabelPermission()

        monkeypatch.setattr(perm, "has_edit_permission", lambda *args, **kwargs: True)
        monkeypatch.setattr(perm, "has_view_permission", lambda *args, **kwargs: False)

        request = SimpleNamespace(user=SimpleNamespace(username="tester"), token="t")
        view = SimpleNamespace(action="create", EDIT_ABOVE_ACTIONS=["create", "update", "partial_update", "destroy"])
        obj = SimpleNamespace(space_id=1, id=123)

        assert perm.has_object_permission(request, view, obj) is True

        monkeypatch.setattr(perm, "has_edit_permission", lambda *args, **kwargs: False)
        assert perm.has_object_permission(request, view, obj) is False

    def test_has_object_permission_view_actions_allow_view_or_edit(self, monkeypatch):
        """When action is not edit-type, view permission OR edit permission passes."""
        from types import SimpleNamespace

        from bkflow.label.permissions import LabelPermission

        perm = LabelPermission()
        request = SimpleNamespace(user=SimpleNamespace(username="tester"), token="t")
        view = SimpleNamespace(action="list", EDIT_ABOVE_ACTIONS=["create", "update", "partial_update", "destroy"])
        obj = SimpleNamespace(space_id=1, id=123)

        # view=True, edit=False -> True
        monkeypatch.setattr(perm, "has_edit_permission", lambda *args, **kwargs: False)
        monkeypatch.setattr(perm, "has_view_permission", lambda *args, **kwargs: True)
        assert perm.has_object_permission(request, view, obj) is True

        # view=False, edit=True -> True
        monkeypatch.setattr(perm, "has_edit_permission", lambda *args, **kwargs: True)
        monkeypatch.setattr(perm, "has_view_permission", lambda *args, **kwargs: False)
        assert perm.has_object_permission(request, view, obj) is True

        # view=False, edit=False -> False
        monkeypatch.setattr(perm, "has_edit_permission", lambda *args, **kwargs: False)
        monkeypatch.setattr(perm, "has_view_permission", lambda *args, **kwargs: False)
        assert perm.has_object_permission(request, view, obj) is False


class TestLabelAdminHelpers:
    """Cover admin helper methods in bkflow.label.admin."""

    def test_label_admin_parent_label(self):
        from django.contrib import admin

        from bkflow.label.admin import LabelAdmin
        from bkflow.label.models import Label

        root = make_label("root_admin")
        child = make_label("child_admin", parent_id=root.id)

        admin_obj = LabelAdmin(Label, admin.site)

        assert admin_obj.parent_label(root) == "-"
        assert admin_obj.parent_label(child) == "root_admin"

    def test_template_label_relation_admin_label_name(self):
        from django.contrib import admin

        from bkflow.label.admin import TemplateLabelRelationAdmin
        from bkflow.label.models import TemplateLabelRelation

        label = make_label("label_for_relation")
        rel_ok = TemplateLabelRelation.objects.create(template_id=1, label_id=label.id)
        rel_missing = TemplateLabelRelation.objects.create(template_id=1, label_id=999999999)

        admin_obj = TemplateLabelRelationAdmin(TemplateLabelRelation, admin.site)

        assert admin_obj.label_name(rel_ok) == "label_for_relation"
        assert admin_obj.label_name(rel_missing) == "-"


class TestLabelRefSerializer:
    def test_validate_label_ids_accepts_list_and_sorts_dedup(self):
        from bkflow.label.serializers import LabelRefSerializer

        ser = LabelRefSerializer()
        assert ser.validate_label_ids([3, "2", 2]) == "2,3"

    def test_validate_label_ids_rejects_invalid_list_item(self):
        from rest_framework.exceptions import ValidationError

        from bkflow.label.serializers import LabelRefSerializer

        ser = LabelRefSerializer()
        with pytest.raises(ValidationError):
            ser.validate_label_ids(["x"])

    def test_validate_label_ids_rejects_empty_and_bad_format(self):
        from rest_framework.exceptions import ValidationError

        from bkflow.label.serializers import LabelRefSerializer

        ser = LabelRefSerializer()

        # empty
        with pytest.raises(ValidationError):
            ser.validate_label_ids("")

        # leading/trailing commas / illegal chars
        for v in [",1,2", "1,2,", "1,a"]:
            with pytest.raises(ValidationError):
                ser.validate_label_ids(v)
