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

from django.urls import include, re_path
from rest_framework.routers import DefaultRouter

from bkflow.plugin_catalog.views.catalog import PluginCatalogAdminViewSet
from bkflow.plugin_catalog.views.directory import DirectoryManageViewSet
from bkflow.plugin_catalog.views.node import PluginNodeViewSet
from bkflow.plugin_catalog.views.picker import PluginPickerViewSet
from bkflow.plugin_catalog.views.strategy import StrategyViewSet

router = DefaultRouter()
router.register(r"directories", DirectoryManageViewSet, basename="plugin_catalog_directory")
router.register(r"strategy", StrategyViewSet, basename="plugin_catalog_strategy")

# 插件列表的 `plugins/` 系列接口不走 router 自动注册：需要 `POST plugins/<id>/` 这种
# 无子路径的 detail 写接口（router 默认只给 detail 路由 PUT/PATCH/DELETE），改为手工
# 按 method 精确映射 action，参考 bkflow/urls.py 里 engine_admin 的同类写法。
_entry_views = PluginCatalogAdminViewSet.as_view
_PLUGIN_CATALOG_ENTRY_BASENAME = "plugin_catalog_entry"

plugin_entry_urlpatterns = [
    # --- 列表 / summary / 推荐（无子路径冲突，顺序不敏感，仍按从具体到概括排列） ---
    re_path(
        r"^plugins/summary/$",
        _entry_views({"get": "summary"}, basename=_PLUGIN_CATALOG_ENTRY_BASENAME),
        name="plugin_catalog_entry-summary",
    ),
    re_path(
        r"^plugins/recommend/$",
        _entry_views({"get": "recommend_list"}, basename=_PLUGIN_CATALOG_ENTRY_BASENAME),
        name="plugin_catalog_entry-recommend-list",
    ),
    re_path(
        r"^plugins/batch_category/$",
        _entry_views({"post": "batch_category"}, basename=_PLUGIN_CATALOG_ENTRY_BASENAME),
        name="plugin_catalog_entry-batch-category",
    ),
    re_path(
        r"^plugins/batch_status/$",
        _entry_views({"post": "batch_status"}, basename=_PLUGIN_CATALOG_ENTRY_BASENAME),
        name="plugin_catalog_entry-batch-status",
    ),
    re_path(
        r"^plugins/batch_clean/$",
        _entry_views({"delete": "batch_clean"}, basename=_PLUGIN_CATALOG_ENTRY_BASENAME),
        name="plugin_catalog_entry-batch-clean",
    ),
    re_path(
        r"^plugins/picker/$",
        PluginPickerViewSet.as_view({"get": "list"}, basename="plugin_catalog_picker"),
        name="plugin_catalog_picker-list",
    ),
    # --- 12 节点配置（已停用提示）/ 13 节点配置（版本切换）---
    re_path(
        r"^plugins/statuses/$",
        PluginNodeViewSet.as_view({"post": "statuses"}, basename="plugin_catalog_node"),
        name="plugin_catalog_node-statuses",
    ),
    re_path(
        r"^plugins/versions/$",
        PluginNodeViewSet.as_view({"get": "versions"}, basename="plugin_catalog_node"),
        name="plugin_catalog_node-versions",
    ),
    re_path(
        r"^plugins/version_diff/$",
        PluginNodeViewSet.as_view({"post": "version_diff"}, basename="plugin_catalog_node"),
        name="plugin_catalog_node-version-diff",
    ),
    re_path(
        r"^plugins/$",
        _entry_views({"get": "list"}, basename=_PLUGIN_CATALOG_ENTRY_BASENAME),
        name="plugin_catalog_entry-list",
    ),
    # --- detail：先匹配带子路径的，再匹配裸 `plugins/<id>/` ---
    re_path(
        r"^plugins/(?P<pk>\d+)/status/suggest_directory/$",
        _entry_views({"get": "suggest_directory"}, basename=_PLUGIN_CATALOG_ENTRY_BASENAME),
        name="plugin_catalog_entry-suggest-directory",
    ),
    re_path(
        r"^plugins/(?P<pk>\d+)/detail/$",
        _entry_views({"get": "plugin_detail"}, basename=_PLUGIN_CATALOG_ENTRY_BASENAME),
        name="plugin_catalog_entry-detail",
    ),
    re_path(
        r"^plugins/(?P<pk>\d+)/references/$",
        _entry_views({"get": "references"}, basename=_PLUGIN_CATALOG_ENTRY_BASENAME),
        name="plugin_catalog_entry-references",
    ),
    re_path(
        r"^plugins/(?P<pk>\d+)/status/$",
        _entry_views({"post": "status"}, basename=_PLUGIN_CATALOG_ENTRY_BASENAME),
        name="plugin_catalog_entry-status",
    ),
    re_path(
        r"^plugins/(?P<pk>\d+)/disable_config/$",
        _entry_views({"post": "disable_config"}, basename=_PLUGIN_CATALOG_ENTRY_BASENAME),
        name="plugin_catalog_entry-disable-config",
    ),
    re_path(
        r"^plugins/(?P<pk>\d+)/recommend/$",
        _entry_views({"delete": "recommend_cancel"}, basename=_PLUGIN_CATALOG_ENTRY_BASENAME),
        name="plugin_catalog_entry-recommend-cancel",
    ),
    re_path(
        r"^plugins/(?P<pk>\d+)/$",
        _entry_views({"post": "update_entry"}, basename=_PLUGIN_CATALOG_ENTRY_BASENAME),
        name="plugin_catalog_entry-update",
    ),
]

urlpatterns = [
    re_path(r"^", include(router.urls)),
    *plugin_entry_urlpatterns,
]
