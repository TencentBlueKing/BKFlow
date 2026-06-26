import io

import pytest
from django.core.management import call_command

from bkflow.plugin.models import OpenPluginSpaceGrant
from bkflow.plugin.services.open_plugin_grant import OpenPluginGrantService


@pytest.mark.django_db
class TestOpenPluginGrantService:
    def test_space_source_is_not_granted_by_default(self):
        assert OpenPluginGrantService.is_granted(space_id=1, source_key="sops") is False
        assert OpenPluginGrantService.granted_source_keys(space_id=1) == []

    def test_grant_source_for_space_is_idempotent(self):
        grant = OpenPluginGrantService.grant(space_id=1, source_key="sops", operator="admin")
        grant_again = OpenPluginGrantService.grant(space_id=1, source_key="sops", operator="operator")

        assert grant.id == grant_again.id
        assert OpenPluginGrantService.is_granted(space_id=1, source_key="sops") is True
        assert OpenPluginGrantService.granted_source_keys(space_id=1) == ["sops"]

        grant.refresh_from_db()
        assert grant.enabled is True
        assert grant.operator == "operator"

    def test_revoke_source_for_space_keeps_record_disabled(self):
        OpenPluginGrantService.grant(space_id=1, source_key="sops", operator="admin")

        grant = OpenPluginGrantService.revoke(space_id=1, source_key="sops", operator="operator")

        assert OpenPluginGrantService.is_granted(space_id=1, source_key="sops") is False
        assert OpenPluginGrantService.granted_source_keys(space_id=1) == []
        assert grant.enabled is False
        assert grant.operator == "operator"

    def test_granted_source_keys_only_returns_enabled_sources_for_space(self):
        OpenPluginGrantService.grant(space_id=1, source_key="sops", operator="admin")
        OpenPluginGrantService.grant(space_id=1, source_key="bk_monitor", operator="admin")
        OpenPluginGrantService.grant(space_id=2, source_key="other_space", operator="admin")
        OpenPluginGrantService.revoke(space_id=1, source_key="bk_monitor", operator="admin")

        assert OpenPluginGrantService.granted_source_keys(space_id=1) == ["sops"]


@pytest.mark.django_db
def test_grant_open_plugin_source_command_can_grant_and_revoke():
    grant_stdout = io.StringIO()
    call_command(
        "grant_open_plugin_source",
        "--space-id",
        "1",
        "--space-id",
        "2",
        "--source-key",
        "sops",
        "--operator",
        "admin",
        stdout=grant_stdout,
    )

    assert OpenPluginSpaceGrant.objects.filter(space_id=1, source_key="sops", enabled=True).exists()
    assert OpenPluginSpaceGrant.objects.filter(space_id=2, source_key="sops", enabled=True).exists()
    assert "granted=2" in grant_stdout.getvalue()

    revoke_stdout = io.StringIO()
    call_command(
        "grant_open_plugin_source",
        "--space-id",
        "1",
        "--source-key",
        "sops",
        "--operator",
        "admin",
        "--revoke",
        stdout=revoke_stdout,
    )

    assert OpenPluginGrantService.is_granted(space_id=1, source_key="sops") is False
    assert OpenPluginGrantService.is_granted(space_id=2, source_key="sops") is True
    assert "revoked=1" in revoke_stdout.getvalue()
