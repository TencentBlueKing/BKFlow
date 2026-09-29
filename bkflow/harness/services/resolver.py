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

from dataclasses import dataclass
from typing import Any, Dict, Optional

from bkflow.harness.services.canonical import schema_hash
from bkflow.harness.services.capability_ref import (
    UNVERSIONED,
    CapabilityReferenceError,
    decode_capability_ref,
)
from bkflow.harness.services.catalog import list_authorized_plugins
from bkflow.harness.services.plugin_schema import generator_schema as _schema_payload
from bkflow.harness.services.projection import (
    ALLOWED_LIFECYCLES,
    load_manifest,
    reconcile_manifest_overrides,
    validate_manifest,
)
from bkflow.plugin.services.plugin_schema_service import (
    PluginSchemaAccessDenied,
    PluginSchemaInfrastructureError,
    PluginSchemaNotFound,
    PluginSchemaVersionUnavailable,
)


class CapabilityResolutionError(ValueError):
    """Fail-closed error for a capability that cannot be resolved in the trusted catalog."""

    code = "CAPABILITY_NOT_FOUND"

    def __init__(self, code=None):
        if code:
            self.code = code
        super().__init__(self.code)


class SchemaDriftError(CapabilityResolutionError):
    """Signal that the selected version or parameter schema is no longer current."""

    code = "SCHEMA_DRIFT"
    next_action = "search_workflow_capabilities"


class ProviderInfrastructureError(CapabilityResolutionError):
    """A registry/provider dependency failed without proving Schema drift."""

    code = "RETRYABLE_INFRA"


@dataclass(frozen=True)
class ResolvedCapability:
    """An exact, currently authorized capability fact; it has no execution behavior."""

    capability_ref: str
    plugin_type: str
    code: str
    source_key: Optional[str]
    resolved_version: str
    schema_hash: str
    schema: Dict[str, Any]
    risk_level: str
    conversion_metadata: Optional[Dict[str, Any]] = None
    conversion_fingerprint: Optional[str] = None


def _conversion_metadata(plugin_schema, reference, resolved_version):
    """Validate conversion facts derived from the exact trusted provider record."""
    metadata = plugin_schema.get("conversion_metadata")
    if reference.plugin_type == "component" and metadata is None:
        metadata = {"kind": "component", "wrapper_code": reference.code, "wrapper_version": resolved_version}
    elif reference.plugin_type == "remote_plugin" and metadata is None:
        metadata = {
            "kind": "remote_plugin",
            "wrapper_code": "remote_plugin",
            "wrapper_version": "1.0.0",
            "remote_plugin_version": resolved_version,
        }
    if not isinstance(metadata, dict):
        raise SchemaDriftError()
    expected_keys = {
        "component": {"kind", "wrapper_code", "wrapper_version"},
        "remote_plugin": {"kind", "wrapper_code", "wrapper_version", "remote_plugin_version"},
        "uniform_api": {
            "kind",
            "wrapper_code",
            "wrapper_version",
            "source_key",
            "plugin_id",
            "plugin_version",
            "url",
            "method",
            "credential_key",
        },
    }
    if (
        set(metadata) != expected_keys.get(reference.plugin_type, set())
        or metadata.get("kind") != reference.plugin_type
    ):
        raise SchemaDriftError()
    if reference.plugin_type == "component" and (
        metadata["wrapper_code"] != reference.code or metadata["wrapper_version"] != resolved_version
    ):
        raise SchemaDriftError()
    if reference.plugin_type == "remote_plugin" and (
        metadata["wrapper_code"] != "remote_plugin"
        or metadata["wrapper_version"] != "1.0.0"
        or metadata["remote_plugin_version"] != resolved_version
    ):
        raise SchemaDriftError()
    if reference.plugin_type == "uniform_api":
        if (
            metadata["wrapper_code"] != "uniform_api"
            or metadata["source_key"] != reference.source_key
            or metadata["plugin_id"] != reference.code
            or metadata["plugin_version"] != resolved_version
            or not isinstance(metadata["wrapper_version"], str)
            or not metadata["wrapper_version"]
            or not isinstance(metadata["url"], str)
            or not metadata["url"]
            or not isinstance(metadata["method"], str)
            or not metadata["method"]
            or (metadata["credential_key"] is not None and not isinstance(metadata["credential_key"], str))
        ):
            raise SchemaDriftError()
    return metadata


class CapabilityResolver:
    """Resolve opaque capability references against the currently authorized registry state."""

    def __init__(self, plugin_schema_service, manifest=None):
        self.plugin_schema_service = plugin_schema_service
        normalized_manifest = validate_manifest(manifest) if manifest is not None else load_manifest()
        self.defaults = normalized_manifest["defaults"]
        self.overrides = {
            (item["plugin_type"], item["source_key"], item["code"]): item
            for item in normalized_manifest["capabilities"]
        }
        reconcile_manifest_overrides(self.plugin_schema_service, self.overrides)

    def _metadata(self, plugin_type, source_key, code):
        """Read lifecycle/risk metadata only after exact identity matching."""
        override = self.overrides.get((plugin_type, source_key, code), {})
        return {
            "lifecycle": override.get("lifecycle", self.defaults["lifecycle"]),
            "risk_level": override.get("risk_level", self.defaults["risk_level"]),
        }

    def _authorized_plugin(self, reference):
        """Replay the registry's space/scope/source filtering before reading an exact schema."""
        plugins = list_authorized_plugins(self.plugin_schema_service, refresh=True, strict=True)
        for plugin in plugins:
            if (
                plugin.get("plugin_type") == reference.plugin_type
                and plugin.get("source_key") == reference.source_key
                and plugin.get("code") == reference.code
            ):
                return plugin
        raise CapabilityResolutionError("CAPABILITY_FORBIDDEN")

    def resolve(self, capability_ref, expected_schema_hash=None):
        """Resolve a pinned reference, enforcing current access, lifecycle, version, and schema hash."""
        try:
            reference = decode_capability_ref(capability_ref)
        except CapabilityReferenceError as error:
            raise CapabilityResolutionError("CAPABILITY_NOT_FOUND") from error
        try:
            reconcile_manifest_overrides(self.plugin_schema_service, self.overrides)
        except ValueError as error:
            raise CapabilityResolutionError("CAPABILITY_FORBIDDEN") from error
        try:
            self._authorized_plugin(reference)
        except PluginSchemaInfrastructureError as error:
            raise ProviderInfrastructureError() from error
        metadata = self._metadata(reference.plugin_type, reference.source_key, reference.code)
        if metadata["lifecycle"] not in ALLOWED_LIFECYCLES:
            raise CapabilityResolutionError("CAPABILITY_FORBIDDEN")
        requested_version = None if reference.version == UNVERSIONED else reference.version
        try:
            plugin_schema = self.plugin_schema_service.get_plugin_schema(
                code=reference.code,
                version=requested_version,
                plugin_type=reference.plugin_type,
                source_key=reference.source_key,
                refresh=True,
                exact_source=True,
                include_conversion_metadata=True,
            )
        except PluginSchemaVersionUnavailable as error:
            raise SchemaDriftError() from error
        except PluginSchemaInfrastructureError as error:
            raise ProviderInfrastructureError() from error
        except PluginSchemaAccessDenied as error:
            raise CapabilityResolutionError("CAPABILITY_FORBIDDEN") from error
        except PluginSchemaNotFound as error:
            raise CapabilityResolutionError("CAPABILITY_NOT_FOUND") from error
        except (KeyError, ValueError) as error:
            raise ProviderInfrastructureError() from error
        resolved_version = plugin_schema.get("resolved_version") or plugin_schema.get("version") or UNVERSIONED
        if resolved_version != reference.version:
            raise SchemaDriftError()
        resolved_schema = _schema_payload(plugin_schema, reference.plugin_type)
        resolved_schema_hash = schema_hash(resolved_schema)
        if expected_schema_hash is not None and expected_schema_hash != resolved_schema_hash:
            raise SchemaDriftError()
        conversion_metadata = _conversion_metadata(plugin_schema, reference, resolved_version)
        return ResolvedCapability(
            capability_ref=capability_ref,
            plugin_type=reference.plugin_type,
            code=reference.code,
            source_key=reference.source_key,
            resolved_version=resolved_version,
            schema_hash=resolved_schema_hash,
            schema=resolved_schema,
            risk_level=metadata["risk_level"],
            conversion_metadata=conversion_metadata,
            conversion_fingerprint=schema_hash(conversion_metadata),
        )


def resolve_capability(plugin_schema_service, capability_ref, expected_schema_hash=None, manifest=None):
    """Resolve one exact reference without exposing a raw-code lookup API."""
    return CapabilityResolver(plugin_schema_service, manifest=manifest).resolve(
        capability_ref, expected_schema_hash=expected_schema_hash
    )
