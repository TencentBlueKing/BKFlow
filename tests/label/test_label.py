import pytest
from django.core.exceptions import ValidationError

from bkflow.label.models import Label, TemplateLabelRelation, TaskLabelRelation

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

        with pytest.raises(ValidationError) as exc:
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

        with pytest.raises(ValidationError) as exc:
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

        with pytest.raises(ValidationError) as exc:
            parent.save()

        msg = str(exc.value)
        assert "禁止循环引用" in msg

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
            TemplateLabelRelation.objects.filter(template_id=template_id).values_list(
                "label_id", flat=True
            )
        )
        assert current_ids == {l1.id, l2.id}

        # update set: {l2, l3} -> l1 removed, l3 added
        TemplateLabelRelation.objects.set_labels(template_id, [l2.id, l3.id])
        current_ids = set(
            TemplateLabelRelation.objects.filter(template_id=template_id).values_list(
                "label_id", flat=True
            )
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

        result = TemplateLabelRelation.objects.fetch_objects_labels(
            [t1, t2], label_fields=("name", "color")
        )

        assert set(result.keys()) == {t1, t2}
        ids_t1 = {label["id"] for label in result[t1]}
        ids_t2 = {label["id"] for label in result[t2]}
        assert ids_t1 == {l1.id, l2.id}
        assert ids_t2 == {l2.id, l3.id}

        # each label dict should contain requested fields and full_path
        for labels in result.values():
            for item in labels:
                assert set(item.keys()) >= {"id", "name", "color", "full_path"}


class TestTaskLabelRelationManager:
    """
    Tests for BaseLabelRelationManager via TaskLabelRelation.
    """

    def test_manager_uses_task_id(self):
        """
        set_labels should use 'task_id' as fk_field for TaskLabelRelation.
        """
        label = make_label("task_label")
        task_id = 200

        TaskLabelRelation.objects.set_labels(task_id, [label.id])

        relations = TaskLabelRelation.objects.filter(task_id=task_id)
        assert relations.count() == 1
        assert relations.first().label_id == label.id
