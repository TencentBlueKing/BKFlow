from unittest.mock import call, patch

import pytest
from blueapps.core.celery.celery import app
from django.conf import settings

from bkflow.plugin.services.open_plugin_grant import OpenPluginGrantService


@pytest.mark.django_db
def test_dispatch_catalog_sync_only_for_configured_granted_sources():
    """测试周期调度只投递已配置且已准入的来源"""
    OpenPluginGrantService.grant(space_id=1, source_key="sops", operator="admin")
    OpenPluginGrantService.grant(space_id=2, source_key="unused", operator="admin")

    from bkflow.plugin.tasks import dispatch_open_plugin_catalog_sync

    with patch(
        "bkflow.plugin.tasks.OpenPluginCatalogService.iter_configured_sources",
        return_value=[(1, "sops"), (1, "ungranted"), (3, "sops")],
    ), patch("bkflow.plugin.tasks.sync_open_plugin_catalog_source.delay") as mock_delay:
        queued = dispatch_open_plugin_catalog_sync()

    assert queued == 1
    assert mock_delay.call_args_list == [call(space_id=1, source_key="sops")]


def test_sync_catalog_source_runs_one_source_without_retry():
    """测试每个来源由独立子任务同步且不自动重试"""
    from bkflow.plugin.tasks import sync_open_plugin_catalog_source

    with patch("bkflow.plugin.tasks.OpenPluginCatalogService.sync_space_plugins") as mock_sync:
        sync_open_plugin_catalog_source(space_id=1, source_key="sops")

    mock_sync.assert_called_once_with(space_id=1, source_key="sops")
    assert sync_open_plugin_catalog_source.max_retries == 0


def test_sync_catalog_source_has_rate_and_time_limits():
    """测试来源子任务具备限速和超时保护"""
    from bkflow.plugin.tasks import sync_open_plugin_catalog_source

    assert sync_open_plugin_catalog_source.rate_limit == "10/m"
    assert sync_open_plugin_catalog_source.soft_time_limit == settings.OPEN_PLUGIN_CATALOG_SYNC_REQUEST_TIMEOUT + 60
    assert sync_open_plugin_catalog_source.time_limit == settings.OPEN_PLUGIN_CATALOG_SYNC_REQUEST_TIMEOUT + 90


def test_open_plugin_catalog_sync_is_registered_in_beat_schedule():
    """测试 interface Beat 默认注册开放插件目录同步任务"""
    schedule = app.conf.beat_schedule["dispatch_open_plugin_catalog_sync"]

    assert schedule["task"] == "bkflow.plugin.tasks.dispatch_open_plugin_catalog_sync"
