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
from copy import deepcopy

from rest_framework import serializers

from bkflow.plugin.models import OpenPluginCatalogIndex, SpaceOpenPluginAvailability
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService


class OpenPluginSnapshotService:
    REFERENCE_SNAPSHOT_KEY = "plugin_reference_snapshot"
    SCHEMA_SNAPSHOT_KEY = "plugin_schema_snapshot"
    SCHEMA_PROTOCOL_VERSION = "open_plugin_snapshot.v1"

    @classmethod
    def get_reference_snapshot(cls, extra_info):
        return deepcopy((extra_info or {}).get(cls.REFERENCE_SNAPSHOT_KEY) or [])

    @classmethod
    def get_schema_snapshot(cls, extra_info):
        return deepcopy((extra_info or {}).get(cls.SCHEMA_SNAPSHOT_KEY) or {})

    @classmethod
    def get_snapshot_node_statuses(cls, space_id, extra_info):
        statuses = {}
        for ref in cls.get_reference_snapshot(extra_info):
            catalog = cls._get_catalog_entry(
                space_id=space_id,
                plugin_id=ref.get("plugin_id"),
                source_key=ref.get("source_key"),
            )
            if catalog is None or catalog.status != OpenPluginCatalogIndex.Status.AVAILABLE:
                statuses[ref["node_id"]] = OpenPluginCatalogIndex.Status.UNAVAILABLE
                continue

            is_enabled = SpaceOpenPluginAvailability.objects.filter(
                space_id=space_id,
                source_key=catalog.source_key,
                plugin_id=catalog.plugin_id,
                enabled=True,
            ).exists()
            statuses[ref["node_id"]] = (
                OpenPluginCatalogIndex.Status.AVAILABLE if is_enabled else OpenPluginCatalogIndex.Status.UNAVAILABLE
            )
        return statuses

    @classmethod
    def validate_pipeline_tree(cls, space_id, pipeline_tree):
        for ref in cls.collect_plugin_references(space_id=space_id, pipeline_tree=pipeline_tree, include_unmatched=True):
            if ref["catalog"] is None:
                raise serializers.ValidationError("开放插件 [{}] 不存在或已下线".format(ref["plugin_id"]))
            if ref["catalog"].status != OpenPluginCatalogIndex.Status.AVAILABLE:
                raise serializers.ValidationError("开放插件 [{}] 当前不可用".format(ref["plugin_id"]))
            if not ref["enabled"]:
                raise serializers.ValidationError("开放插件 [{}] 在当前空间未开放".format(ref["plugin_id"]))

    @classmethod
    def build_reference_snapshot(cls, space_id, pipeline_tree):
        references = []
        for ref in cls.collect_plugin_references(space_id=space_id, pipeline_tree=pipeline_tree, include_unmatched=False):
            catalog = ref["catalog"]
            references.append(
                {
                    "node_id": ref["node_id"],
                    "plugin_id": ref["plugin_id"],
                    "plugin_code": catalog.plugin_code,
                    "plugin_name": catalog.plugin_name,
                    "plugin_source": catalog.plugin_source,
                    "source_key": catalog.source_key,
                    "plugin_version": ref["plugin_version"],
                    "wrapper_version": catalog.wrapper_version or ref["wrapper_version"],
                }
            )
        return references

    @classmethod
    def build_schema_snapshot(cls, space_id, pipeline_tree, username=None, scope_type=None, scope_id=None):
        service = PluginSchemaService(space_id=space_id, username=username, scope_type=scope_type, scope_id=scope_id)
        snapshots = {}
        for ref in cls.collect_plugin_references(space_id=space_id, pipeline_tree=pipeline_tree, include_unmatched=False):
            schema = service.get_plugin_schema(
                code=ref["plugin_id"],
                version=ref["plugin_version"],
                plugin_type="uniform_api",
            )
            snapshots[ref["node_id"]] = {
                "schema_protocol_version": cls.SCHEMA_PROTOCOL_VERSION,
                "plugin_id": ref["plugin_id"],
                "plugin_code": schema.get("plugin_code", ""),
                "plugin_source": schema.get("plugin_source", ""),
                "plugin_version": schema.get("version", ref["plugin_version"]),
                "wrapper_version": schema.get("wrapper_version", ref["wrapper_version"]),
                "inputs": schema.get("inputs", []),
                "outputs": schema.get("outputs", []),
                "description": schema.get("description", ""),
            }
        return snapshots

    @classmethod
    def merge_snapshots(cls, extra_info, reference_snapshot, schema_snapshot=None):
        merged = dict(extra_info or {})
        if reference_snapshot:
            merged[cls.REFERENCE_SNAPSHOT_KEY] = reference_snapshot
        if schema_snapshot:
            merged[cls.SCHEMA_SNAPSHOT_KEY] = schema_snapshot
        return merged

    @classmethod
    def backfill_extra_info(cls, space_id, pipeline_tree, extra_info=None, username=None, scope_type=None, scope_id=None):
        merged = dict(extra_info or {})
        changed = False

        reference_snapshot = cls.get_reference_snapshot(merged)
        if not reference_snapshot:
            reference_snapshot = cls.build_reference_snapshot(space_id=space_id, pipeline_tree=pipeline_tree)
            if reference_snapshot:
                merged[cls.REFERENCE_SNAPSHOT_KEY] = reference_snapshot
                changed = True

        schema_snapshot = cls.get_schema_snapshot(merged)
        if reference_snapshot and not schema_snapshot:
            schema_snapshot = cls.build_schema_snapshot(
                space_id=space_id,
                pipeline_tree=pipeline_tree,
                username=username,
                scope_type=scope_type,
                scope_id=scope_id,
            )
            if schema_snapshot:
                merged[cls.SCHEMA_SNAPSHOT_KEY] = schema_snapshot
                changed = True

        reference_snapshot = cls.get_reference_snapshot(merged)
        schema_snapshot = cls.get_schema_snapshot(merged)

        if reference_snapshot:
            reference_wrapper_map = cls._fill_reference_wrapper_versions(space_id=space_id, reference_snapshot=reference_snapshot)
            if reference_wrapper_map["changed"]:
                merged[cls.REFERENCE_SNAPSHOT_KEY] = reference_snapshot
                changed = True
            if schema_snapshot:
                if cls._fill_schema_wrapper_versions(
                    space_id=space_id,
                    reference_snapshot=reference_snapshot,
                    schema_snapshot=schema_snapshot,
                ):
                    merged[cls.SCHEMA_SNAPSHOT_KEY] = schema_snapshot
                    changed = True

        return merged, changed

    @classmethod
    def collect_plugin_references(cls, space_id, pipeline_tree, include_unmatched=False):
        activities = (pipeline_tree or {}).get("activities", {})
        references = []
        for node_id, node in activities.items():
            if node.get("type") != "ServiceActivity":
                continue
            component = node.get("component", {})
            if component.get("code") != "uniform_api":
                continue

            data = component.get("data", {})
            api_meta = component.get("api_meta", {})
            plugin_id = cls._extract_data_value(data, "uniform_api_plugin_id") or api_meta.get("id")
            plugin_version = (
                cls._extract_data_value(data, "uniform_api_plugin_version")
                or api_meta.get("plugin_version")
                or ""
            )
            source_key = api_meta.get("source_key")
            wrapper_version = component.get("version", "")

            if not plugin_id:
                continue

            catalog = cls._get_catalog_entry(space_id=space_id, plugin_id=plugin_id, source_key=source_key)
            is_explicit_open_plugin = bool(source_key or cls._extract_data_value(data, "uniform_api_plugin_id"))
            if catalog is None and not is_explicit_open_plugin:
                continue

            if catalog and not plugin_version:
                plugin_version = catalog.latest_version or catalog.default_version or ""

            enabled = False
            if catalog is not None:
                enabled = SpaceOpenPluginAvailability.objects.filter(
                    space_id=space_id,
                    source_key=catalog.source_key,
                    plugin_id=catalog.plugin_id,
                    enabled=True,
                ).exists()

            references.append(
                {
                    "node_id": node_id,
                    "plugin_id": plugin_id,
                    "plugin_version": plugin_version,
                    "source_key": source_key or (catalog.source_key if catalog else ""),
                    "wrapper_version": wrapper_version,
                    "catalog": catalog,
                    "enabled": enabled,
                }
            )

        if include_unmatched:
            return references
        return [ref for ref in references if ref["catalog"] is not None]

    @staticmethod
    def _extract_data_value(data, key):
        value = data.get(key)
        if isinstance(value, dict):
            return value.get("value")
        return value

    @staticmethod
    def _get_catalog_entry(space_id, plugin_id, source_key=None):
        query = OpenPluginCatalogIndex.objects.filter(space_id=space_id, plugin_id=plugin_id)
        if source_key:
            query = query.filter(source_key=source_key)
        return query.order_by("-update_time", "-id").first()

    @classmethod
    def _fill_reference_wrapper_versions(cls, space_id, reference_snapshot):
        changed = False
        wrapper_version_map = {}
        for ref in reference_snapshot:
            wrapper_version = ref.get("wrapper_version") or cls._resolve_wrapper_version(
                space_id=space_id,
                plugin_id=ref.get("plugin_id"),
                source_key=ref.get("source_key"),
            )
            if wrapper_version and not ref.get("wrapper_version"):
                ref["wrapper_version"] = wrapper_version
                changed = True
            wrapper_version_map[ref["node_id"]] = wrapper_version
        return {"changed": changed, "wrapper_version_map": wrapper_version_map}

    @classmethod
    def _fill_schema_wrapper_versions(cls, space_id, reference_snapshot, schema_snapshot):
        changed = False
        reference_wrapper_map = {
            ref["node_id"]: ref.get("wrapper_version")
            or cls._resolve_wrapper_version(
                space_id=space_id,
                plugin_id=ref.get("plugin_id"),
                source_key=ref.get("source_key"),
            )
            for ref in reference_snapshot
        }
        for node_id, schema in schema_snapshot.items():
            if not schema.get("schema_protocol_version"):
                schema["schema_protocol_version"] = cls.SCHEMA_PROTOCOL_VERSION
                changed = True
            wrapper_version = schema.get("wrapper_version") or reference_wrapper_map.get(node_id)
            if wrapper_version and not schema.get("wrapper_version"):
                schema["wrapper_version"] = wrapper_version
                changed = True
        return changed

    @classmethod
    def _resolve_wrapper_version(cls, space_id, plugin_id, source_key=None):
        catalog = cls._get_catalog_entry(space_id=space_id, plugin_id=plugin_id, source_key=source_key)
        if catalog is None:
            return ""
        return catalog.wrapper_version or ""
