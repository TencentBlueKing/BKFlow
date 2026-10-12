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
from bkflow.harness.services.capability_ref import (
    CapabilityReferenceError,
    validate_capability_identity,
)

CATALOG_PAGE_SIZE = 200


class CatalogPaginationError(ValueError):
    """The ACL-preserving catalog cannot be replayed as one consistent snapshot."""


def list_authorized_plugins(plugin_schema_service, plugin_source=None, refresh=False, strict=False):
    """Return every plugin from the already permission-filtered schema service."""
    expected_total = None
    offset = 0
    catalog = []
    seen_identities = set()

    while True:
        kwargs = {"limit": CATALOG_PAGE_SIZE, "offset": offset, "plugin_source": plugin_source}
        if strict:
            kwargs["strict"] = True
        if refresh:
            kwargs["refresh"] = True
        page, total_count = plugin_schema_service.list_plugins(**kwargs)
        if (
            not isinstance(page, list)
            or isinstance(total_count, bool)
            or not isinstance(total_count, int)
            or total_count < 0
        ):
            raise CatalogPaginationError("invalid authorized catalog total_count")
        if expected_total is None:
            expected_total = total_count
        elif total_count != expected_total:
            raise CatalogPaginationError("inconsistent authorized catalog total_count")
        if expected_total == 0:
            if page:
                raise CatalogPaginationError("inconsistent authorized catalog page")
            return catalog
        if not page:
            raise CatalogPaginationError("non-progressing authorized catalog page")
        if len(page) > CATALOG_PAGE_SIZE or len(catalog) + len(page) > expected_total:
            raise CatalogPaginationError("inconsistent authorized catalog page")
        for plugin in page:
            if not isinstance(plugin, dict):
                raise CatalogPaginationError("invalid authorized catalog item")
            try:
                identity = validate_capability_identity(
                    plugin.get("plugin_type"), plugin.get("source_key"), plugin.get("code")
                )
            except (CapabilityReferenceError, TypeError, UnicodeError) as error:
                raise CatalogPaginationError("invalid authorized catalog identity") from error
            if identity in seen_identities:
                raise CatalogPaginationError("duplicated authorized catalog identity")
            seen_identities.add(identity)

        catalog.extend(page)
        next_offset = offset + len(page)
        if next_offset <= offset:
            raise CatalogPaginationError("non-progressing authorized catalog offset")
        offset = next_offset
        if len(catalog) == expected_total:
            return catalog
