from django.contrib import admin

from bkflow.plugin.models import OpenPluginCatalogIndex, SpaceOpenPluginAvailability


def test_open_plugin_catalog_index_is_registered():
    """目录索引需要在 admin 可见，用于确认同步是否落库。"""
    model_admin = admin.site._registry[OpenPluginCatalogIndex]

    assert "status" in model_admin.list_display
    assert "plugin_id" in model_admin.search_fields


def test_space_open_plugin_availability_is_editable_in_admin():
    """开放插件的空间开关是 V4 唯一闸门，admin 必须能直接改。"""
    model_admin = admin.site._registry[SpaceOpenPluginAvailability]

    assert "enabled" in model_admin.list_editable
    assert "enabled" in model_admin.list_display
