"""Contracts for reusable a2flow template domain writes."""

from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ValidationError

from bkflow.template.services.a2flow_template import (
    create_template_draft_from_pipeline_tree,
    create_template_from_a2flow,
    update_template_draft_from_a2flow,
)


def test_draft_update_rejects_template_outside_trusted_space_before_conversion():
    """A managed draft cannot be switched to another space by a caller supplied template id."""
    template = type("Template", (), {"space_id": 2, "bk_app_code": "trusted"})()

    with pytest.raises(ValidationError, match="ownership"):
        update_template_draft_from_a2flow(
            template=template,
            username="operator",
            a2flow={},
            expected_space_id=1,
            expected_bind_app_code="trusted",
        )


@patch("bkflow.template.services.a2flow_template.Template.objects.create")
@patch("bkflow.template.services.a2flow_template.TemplateSnapshot.create_draft_snapshot")
@patch("bkflow.template.services.a2flow_template.SpaceConfig.get_config", return_value="true")
@patch("bkflow.template.services.a2flow_template._pipeline_tree", return_value={"id": "pipeline"})
@pytest.mark.django_db
def test_create_template_keeps_auto_release_false_as_a_draft(
    mock_tree, mock_versioning, mock_snapshot, mock_template_create
):
    """A Harness caller can use the shared service without creating a released snapshot."""
    snapshot = MagicMock(id=12)
    template = MagicMock(id=34)
    mock_snapshot.return_value = snapshot
    mock_template_create.return_value = template

    result = create_template_from_a2flow(
        space_id=1,
        username="operator",
        a2flow={"name": "draft", "desc": "server owned", "nodes": []},
        scope_type="project",
        scope_value="1",
        bind_app_code="trusted-app",
        auto_release=False,
    )

    assert result is template
    mock_snapshot.assert_called_once_with({"id": "pipeline"}, "operator")
    mock_template_create.assert_called_once_with(
        name="draft",
        desc="server owned",
        space_id=1,
        scope_type="project",
        scope_value="1",
        bk_app_code="trusted-app",
        creator="operator",
        updated_by="operator",
        snapshot_id=12,
    )


@pytest.mark.django_db
@patch("bkflow.template.services.a2flow_template.Template.objects.create")
@patch("bkflow.template.services.a2flow_template.TemplateSnapshot.create_draft_snapshot")
@pytest.mark.parametrize("versioning", ["true", "false"])
def test_harness_pipeline_tree_write_is_always_a_draft(mock_snapshot, mock_template_create, versioning):
    """Harness materialization never turns a checked tree into a released snapshot."""
    snapshot = MagicMock(id=12)
    template = MagicMock(id=34)
    mock_snapshot.return_value = snapshot
    mock_template_create.return_value = template

    result = create_template_draft_from_pipeline_tree(
        pipeline_tree={"id": "governed"},
        name="draft",
        desc="",
        space_id=1,
        username="operator",
        scope_type="project",
        scope_value="1",
        bind_app_code="trusted-app",
    )

    assert result is template
    mock_snapshot.assert_called_once_with({"id": "governed"}, "operator")
