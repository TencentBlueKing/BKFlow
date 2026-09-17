"""真实旧表升级演练，确认加租户列不改变旧插件及授权。"""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings

from bkflow.bk_plugin.models import BKPlugin, BKPluginAuthorization
from bkflow.bk_plugin.serializer import BKPluginSerializer
from tests.interface.bk_plugin.test_tenant_catalog import remote


def migrate_to(target):
    executor = MigrationExecutor(connection)
    executor.migrate([target])
    return executor.loader.project_state([target]).apps


@pytest.mark.django_db(transaction=True)
def test_existing_catalog_survives_migration_and_single_mode():
    """旧记录完整保留，单租户直接可用；多租户重同步后才确定归属。"""
    latest = ("bk_plugin", "0002_bkplugin_tenant_id")
    try:
        apps = migrate_to(("bk_plugin", "0001_initial"))
        old = apps.get_model("bk_plugin", "BKPlugin").objects.create(
            code="old-plugin", name="旧插件", tag=1, managers=["admin"], extra_info={"old": True}
        )
        apps.get_model("bk_plugin", "BKPluginAuthorization").objects.create(code=old.pk, status=1)
        migrate_to(latest)
        plugin = BKPlugin.objects.get(code=old.pk)
        assert plugin.name == "旧插件" and plugin.tenant_id == ""
        assert plugin.managers == ["admin"] and plugin.extra_info == {"old": True}
        assert BKPluginAuthorization.objects.get(code=old.pk).status == 1
        with override_settings(ENABLE_MULTI_TENANT_MODE=False):
            assert BKPlugin.objects.for_space(None).filter(code=old.pk).exists()
            assert "tenant_id" not in BKPluginSerializer(plugin).data
        with override_settings(ENABLE_MULTI_TENANT_MODE=True):
            BKPlugin.objects.sync_bk_plugins({old.pk: remote(old.pk)}, tenant_id="a")
        plugin.refresh_from_db()
        assert plugin.tenant_id == "a"
        assert BKPluginAuthorization.objects.get(code=old.pk).status == 1
    finally:
        migrate_to(latest)
