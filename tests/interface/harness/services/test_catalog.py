"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import pytest

from bkflow.harness.services.catalog import (
    CatalogPaginationError,
    list_authorized_plugins,
)


class PagedRegistry:
    """Model the ACL-filtered plugin registry without changing its pagination behavior."""

    def __init__(self, plugins, total_counts=None):
        self.plugins = plugins
        self.total_counts = total_counts or []
        self.calls = []

    def list_plugins(self, limit=100, offset=0, plugin_source=None):
        self.calls.append((limit, offset, plugin_source))
        filtered = [item for item in self.plugins if not plugin_source or item.get("plugin_source") == plugin_source]
        total = self.total_counts.pop(0) if self.total_counts else len(filtered)
        return filtered[offset : offset + limit], total


@pytest.mark.parametrize("plugin_type", ("component", "remote_plugin", "uniform_api"))
@pytest.mark.parametrize("target_index", (100, 200))
def test_list_authorized_plugins_reads_beyond_default_and_max_page_boundaries(plugin_type, target_index):
    """Stopping at either 100 or 200 would hide an otherwise authorized source-family capability."""
    plugins = [
        {
            "plugin_type": plugin_type,
            "source_key": "source-a" if plugin_type == "uniform_api" else None,
            "code": "cap-{}".format(index),
        }
        for index in range(201)
    ]
    registry = PagedRegistry(plugins)

    catalog = list_authorized_plugins(registry)

    assert catalog[target_index]["code"] == "cap-{}".format(target_index)
    assert len(catalog) == 201
    assert registry.calls == [(200, 0, None), (200, 200, None)]


def test_list_authorized_plugins_rejects_inconsistent_total_count():
    """Accepting a moving total could resolve against a partial or stale ACL snapshot."""
    registry = PagedRegistry(
        [{"plugin_type": "component", "source_key": None, "code": "cap-{}".format(index)} for index in range(201)],
        total_counts=[201, 202],
    )

    with pytest.raises(CatalogPaginationError, match="inconsistent"):
        list_authorized_plugins(registry)


def test_list_authorized_plugins_rejects_empty_page_before_advertised_total():
    """Treating a non-progressing page as complete would turn an ACL failure into a truncated catalog."""
    registry = PagedRegistry([], total_counts=[1])

    with pytest.raises(CatalogPaginationError, match="non-progress"):
        list_authorized_plugins(registry)


def test_list_authorized_plugins_rejects_repeated_identity_across_pages():
    """Accepting a duplicate page identity would make exact authorization depend on a broken snapshot."""
    repeated = {"plugin_type": "component", "source_key": None, "code": "same"}
    registry = PagedRegistry([repeated] * 201)

    with pytest.raises(CatalogPaginationError, match="duplicated"):
        list_authorized_plugins(registry)


@pytest.mark.parametrize("page,total", (([], True), ([], -1), ([{}], 0), ("not-a-list", 1)))
def test_list_authorized_plugins_rejects_malformed_page_contract(page, total):
    """Completing before validating a provider page would accept malformed ACL snapshots."""
    registry = PagedRegistry([])
    registry.list_plugins = lambda **kwargs: (page, total)

    with pytest.raises(CatalogPaginationError):
        list_authorized_plugins(registry)


@pytest.mark.parametrize(
    "plugin",
    (
        {},
        {"plugin_type": "component", "source_key": None, "code": None},
        {"plugin_type": "component", "source_key": None, "code": []},
        {"plugin_type": "unknown", "source_key": None, "code": "cap"},
    ),
)
def test_list_authorized_plugins_rejects_malformed_source_identity(plugin):
    """Malformed provider identities must fail closed with the catalog error contract."""
    registry = PagedRegistry([plugin])

    with pytest.raises(CatalogPaginationError, match="identity"):
        list_authorized_plugins(registry)
