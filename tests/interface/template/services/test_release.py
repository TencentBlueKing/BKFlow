"""Atomic template-release domain service contracts."""

import pytest
from django.db import connection

from bkflow.constants import TemplateOperationSource, TemplateOperationType
from bkflow.exceptions import ValidationError
from bkflow.space.configs import FlowVersioning, SpaceConfigValueType
from bkflow.space.models import Space, SpaceConfig
from bkflow.template.models import Template, TemplateOperationRecord, TemplateSnapshot


@pytest.fixture
def release_template_case(db):
    """Build one versioned template whose exact snapshot is still a draft."""
    space = Space.objects.create(name="release-service", app_code="trusted-app", platform_url="")
    SpaceConfig.objects.create(
        space_id=space.id,
        name=FlowVersioning.name,
        value_type=SpaceConfigValueType.TEXT.value,
        text_value="true",
    )
    draft = TemplateSnapshot.objects.create(
        template_id=None,
        draft=True,
        data={"id": "pipeline-v1", "activities": {}, "gateways": {}, "flows": {}, "constants": {}, "outputs": []},
        md5sum="a" * 32,
        creator="dannydeng",
        operator="dannydeng",
    )
    template = Template.objects.create(
        name="release service",
        space_id=space.id,
        snapshot_id=draft.id,
        creator="dannydeng",
        updated_by="dannydeng",
    )
    draft.template_id = template.id
    draft.save(update_fields=["template_id"])
    return template, draft


@pytest.mark.django_db(transaction=True)
def test_release_locks_and_atomically_publishes_exact_draft_with_operation_and_post_commit_webhook(
    release_template_case,
    mocker,
):
    """A release commits the exact draft, template pointer and audit before dispatching its webhook."""
    from bkflow.template.services.release import TemplateReleaseService

    template, draft = release_template_case
    transaction_states = []
    signal = mocker.patch("bkflow.template.services.release.event_broadcast_signal.send")
    signal.side_effect = lambda **kwargs: transaction_states.append(connection.in_atomic_block)

    snapshot = TemplateReleaseService.release(
        template,
        {"version": "1.0.0", "desc": "first release", "force": False},
        operator="dannydeng",
        source=TemplateOperationSource.app.name,
        emit_webhook=True,
        expected_draft_snapshot_id=draft.id,
    )

    template.refresh_from_db()
    snapshot.refresh_from_db()
    assert snapshot.id == draft.id
    assert snapshot.draft is False
    assert snapshot.version == "1.0.0"
    assert template.snapshot_id == draft.id
    assert (
        TemplateOperationRecord.objects.filter(
            instance_id=template.id,
            operate_type=TemplateOperationType.release.name,
            operate_source=TemplateOperationSource.app.name,
            operator="dannydeng",
            extra_info={"version": "1.0.0"},
        ).count()
        == 1
    )
    assert signal.call_count == 1
    assert transaction_states == [False]


@pytest.mark.django_db(transaction=True)
def test_release_rolls_back_snapshot_when_operation_record_fails(release_template_case, mocker):
    """The published snapshot cannot commit without its release operation record."""
    from bkflow.template.services.release import TemplateReleaseService

    template, draft = release_template_case
    mocker.patch("bkflow.template.services.release.TemplateOperationRecord.objects.create", side_effect=RuntimeError())

    with pytest.raises(RuntimeError):
        TemplateReleaseService.release(
            template,
            {"version": "1.0.0", "force": False},
            operator="dannydeng",
            source=TemplateOperationSource.api.name,
            emit_webhook=False,
            expected_draft_snapshot_id=draft.id,
        )

    draft.refresh_from_db()
    template.refresh_from_db()
    assert draft.draft is True
    assert draft.version is None
    assert template.snapshot_id == draft.id


@pytest.mark.django_db(transaction=True)
def test_release_rechecks_versioning_collision_and_exact_draft_under_lock(release_template_case):
    """Disabled versioning, a duplicate version or a replaced draft all fail before publication."""
    from bkflow.template.services.release import TemplateReleaseService

    template, draft = release_template_case
    TemplateSnapshot.objects.create(
        template_id=template.id,
        draft=False,
        version="1.0.0",
        data={"id": "old"},
        md5sum="b" * 32,
    )
    with pytest.raises(ValidationError):
        TemplateReleaseService.release(
            template,
            {"version": "1.0.0", "force": False},
            operator="dannydeng",
            source=TemplateOperationSource.api.name,
            emit_webhook=False,
            expected_draft_snapshot_id=draft.id,
        )

    SpaceConfig.objects.filter(space_id=template.space_id, name=FlowVersioning.name).update(text_value="false")
    with pytest.raises(ValidationError):
        TemplateReleaseService.release(
            template,
            {"version": "1.0.1", "force": False},
            operator="dannydeng",
            source=TemplateOperationSource.api.name,
            emit_webhook=False,
            expected_draft_snapshot_id=draft.id + 1,
        )
    draft.refresh_from_db()
    assert draft.draft is True


@pytest.mark.django_db(transaction=True)
def test_post_commit_webhook_failure_does_not_turn_committed_release_into_failure(release_template_case, mocker):
    """A broker failure after commit is logged while the committed release remains successful."""
    from bkflow.template.services.release import TemplateReleaseService

    template, draft = release_template_case
    mocker.patch(
        "bkflow.template.services.release.event_broadcast_signal.send",
        side_effect=RuntimeError("webhook broker unavailable"),
    )

    snapshot = TemplateReleaseService.release(
        template,
        {"version": "1.0.0", "force": False},
        operator="dannydeng",
        source=TemplateOperationSource.app.name,
        emit_webhook=True,
        expected_draft_snapshot_id=draft.id,
    )

    snapshot.refresh_from_db()
    assert snapshot.draft is False
    assert snapshot.version == "1.0.0"


@pytest.mark.django_db(transaction=True)
def test_update_draft_locks_template_before_the_draft_snapshot(release_template_case, mocker):
    """Every draft mutation enters through the global Template-to-Snapshot lock order."""
    template, draft = release_template_case
    acquired = []
    template_lock = Template.objects.select_for_update
    snapshot_lock = TemplateSnapshot.objects.select_for_update
    mocker.patch.object(
        Template.objects,
        "select_for_update",
        side_effect=lambda: acquired.append("template") or template_lock(),
    )
    mocker.patch.object(
        TemplateSnapshot.objects,
        "select_for_update",
        side_effect=lambda: acquired.append("snapshot") or snapshot_lock(),
    )

    updated = template.update_draft_snapshot(
        {"id": "pipeline-v2", "activities": {}, "gateways": {}, "flows": {}, "constants": {}, "outputs": []},
        "dannydeng",
    )

    assert updated.id == draft.id
    assert acquired[:2] == ["template", "snapshot"]


@pytest.mark.django_db(transaction=True)
def test_update_draft_rejects_multiple_drafts_without_mutating_either(release_template_case):
    """Ambiguous draft state fails closed instead of selecting an arbitrary row."""
    template, first = release_template_case
    second = TemplateSnapshot.objects.create(
        template_id=template.id,
        draft=True,
        data={"id": "pipeline-other"},
        md5sum="b" * 32,
        creator="dannydeng",
        operator="dannydeng",
    )

    with pytest.raises(ValidationError):
        template.update_draft_snapshot({"id": "pipeline-v2"}, "dannydeng")

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.data["id"] == "pipeline-v1"
    assert second.data["id"] == "pipeline-other"
