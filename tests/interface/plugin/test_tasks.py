from unittest.mock import call, patch

from blueapps.core.celery.celery import app
from django.conf import settings


def test_dispatch_catalog_sync_covers_every_configured_source():
    """测试周期调度为每个已配置来源去重投递一次"""
    from bkflow.plugin.tasks import dispatch_open_plugin_catalog_sync

    with patch(
        "bkflow.plugin.tasks.OpenPluginCatalogService.iter_configured_sources",
        return_value=[(1, "sops"), (1, "sops"), (1, "other"), (3, "sops")],
    ), patch("bkflow.plugin.tasks.sync_open_plugin_catalog_source.delay") as mock_delay:
        queued = dispatch_open_plugin_catalog_sync()

    assert queued == 3
    assert mock_delay.call_args_list == [
        call(space_id=1, source_key="other"),
        call(space_id=1, source_key="sops"),
        call(space_id=3, source_key="sops"),
    ]


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
