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
from bkflow.plugin.services.open_plugin_detect import (
    OPEN_PLUGIN_WRAPPER_VERSION,
    REFERENCE_SNAPSHOT_KEY,
    extract_data_value,
    has_open_plugin_nodes,
    is_open_plugin_component,
    needs_start_validation,
)
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService


class OpenPluginSnapshotService:
    REFERENCE_SNAPSHOT_KEY = REFERENCE_SNAPSHOT_KEY
    SCHEMA_SNAPSHOT_KEY = "plugin_schema_snapshot"
    SCHEMA_PROTOCOL_VERSION = "open_plugin_snapshot.v1"
    OPEN_PLUGIN_WRAPPER_VERSION = OPEN_PLUGIN_WRAPPER_VERSION

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
    def has_open_plugin_nodes(cls, pipeline_tree):
        """仅根据 pipeline 结构判断是否包含开放插件节点，不访问 Interface 目录库。"""
        return has_open_plugin_nodes(pipeline_tree)

    @classmethod
    def needs_start_validation(cls, extra_info=None, pipeline_tree=None):
        """启动时是否需要做开放插件可用性预检。"""
        return needs_start_validation(extra_info=extra_info, pipeline_tree=pipeline_tree)

    @classmethod
    def validate_for_start(cls, space_id, snapshot=None, extra_info=None, pipeline_tree=None):
        """启动预检：优先使用已有快照，否则回退到扫描 pipeline_tree。"""
        refs = snapshot if snapshot is not None else cls.get_reference_snapshot(extra_info)
        if refs:
            cls.validate_reference_snapshot(space_id, refs)
            return
        if pipeline_tree:
            cls.validate_pipeline_tree(space_id, pipeline_tree)

    @classmethod
    def validate_reference_snapshot(cls, space_id, snapshot):
        """按任务 extra_info 中的开放插件快照做可用性校验。"""
        for ref in snapshot or []:
            plugin_id = ref.get("plugin_id")
            plugin_version = ref.get("plugin_version")
            catalog = cls._get_catalog_entry(space_id=space_id, plugin_id=plugin_id, source_key=ref.get("source_key"))
            enabled = False
            if catalog is not None:
                enabled = SpaceOpenPluginAvailability.objects.filter(
                    space_id=space_id,
                    source_key=catalog.source_key,
                    plugin_id=catalog.plugin_id,
                    enabled=True,
                ).exists()
            cls._validate_resolved_reference(
                plugin_id=plugin_id,
                plugin_version=plugin_version,
                catalog=catalog,
                enabled=enabled,
            )

    @classmethod
    def validate_pipeline_tree(cls, space_id, pipeline_tree):
        for ref in cls.collect_plugin_references(
            space_id=space_id, pipeline_tree=pipeline_tree, include_unmatched=True
        ):
            cls._validate_resolved_reference(
                plugin_id=ref["plugin_id"],
                plugin_version=ref["plugin_version"],
                catalog=ref["catalog"],
                enabled=ref["enabled"],
            )

    @staticmethod
    def _validate_resolved_reference(plugin_id, plugin_version, catalog, enabled):
        if catalog is None:
            raise serializers.ValidationError("开放插件 [{}] 不存在或已下线".format(plugin_id))
        if catalog.status != OpenPluginCatalogIndex.Status.AVAILABLE:
            raise serializers.ValidationError("开放插件 [{}] 当前不可用".format(plugin_id))
        if not plugin_version:
            raise serializers.ValidationError("开放插件 [{}] 未指定精确版本".format(plugin_id))
        if not catalog.is_plugin_version_available(plugin_version):
            raise serializers.ValidationError("开放插件 [{}] 版本 [{}] 当前不可用".format(plugin_id, plugin_version or ""))
        if not enabled:
            raise serializers.ValidationError("开放插件 [{}] 在当前空间未开放".format(plugin_id))

    @classmethod
    def build_reference_snapshot(cls, space_id, pipeline_tree):
        references = []
        for ref in cls.collect_plugin_references(
            space_id=space_id, pipeline_tree=pipeline_tree, include_unmatched=False
        ):
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
        for ref in cls.collect_plugin_references(
            space_id=space_id, pipeline_tree=pipeline_tree, include_unmatched=False
        ):
            schema = service.get_plugin_schema(
                code=ref["plugin_id"],
                version=ref["plugin_version"],
                plugin_type="uniform_api",
                source_key=ref.get("source_key") or None,
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
    def prepare_task_extra_info(
        cls,
        space_id,
        pipeline_tree,
        extra_info=None,
        username=None,
        scope_type=None,
        scope_id=None,
    ):
        """校验开放插件引用并为新任务生成不可变快照。"""
        cls.validate_pipeline_tree(space_id=space_id, pipeline_tree=pipeline_tree)
        reference_snapshot = cls.build_reference_snapshot(space_id=space_id, pipeline_tree=pipeline_tree)
        schema_snapshot = cls.build_schema_snapshot(
            space_id=space_id,
            pipeline_tree=pipeline_tree,
            username=username,
            scope_type=scope_type,
            scope_id=scope_id,
        )
        return cls.merge_snapshots(
            extra_info=extra_info,
            reference_snapshot=reference_snapshot,
            schema_snapshot=schema_snapshot,
        )

    @classmethod
    def merge_snapshots(cls, extra_info, reference_snapshot, schema_snapshot=None):
        merged = dict(extra_info or {})
        if reference_snapshot:
            merged[cls.REFERENCE_SNAPSHOT_KEY] = reference_snapshot
        else:
            merged.pop(cls.REFERENCE_SNAPSHOT_KEY, None)
            merged.pop(cls.SCHEMA_SNAPSHOT_KEY, None)
        if schema_snapshot:
            merged[cls.SCHEMA_SNAPSHOT_KEY] = schema_snapshot
        return merged

    @classmethod
    def backfill_extra_info(
        cls, space_id, pipeline_tree, extra_info=None, username=None, scope_type=None, scope_id=None
    ):
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
            reference_wrapper_map = cls._fill_reference_wrapper_versions(
                space_id=space_id, reference_snapshot=reference_snapshot
            )
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
            if not cls._is_open_plugin_component(component):
                continue

            data = component.get("data", {})
            api_meta = component.get("api_meta", {})
            plugin_id = cls._extract_data_value(data, "uniform_api_plugin_id") or api_meta.get("id")
            plugin_version = (
                cls._extract_data_value(data, "uniform_api_plugin_version") or api_meta.get("plugin_version") or ""
            )
            source_key = cls._extract_data_value(data, "uniform_api_plugin_source_key") or api_meta.get("source_key")
            wrapper_version = component.get("version", "")

            if not plugin_id:
                continue

            catalog = cls._get_catalog_entry(space_id=space_id, plugin_id=plugin_id, source_key=source_key)

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

    @classmethod
    def _is_open_plugin_component(cls, component):
        """判断 uniform_api 节点是否使用开放插件 v4 协议。"""
        return is_open_plugin_component(component)

    @staticmethod
    def _extract_data_value(data, key):
        return extract_data_value(data, key)

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
